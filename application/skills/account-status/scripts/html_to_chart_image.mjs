#!/usr/bin/env node
/**
 * HTML `<script>`의 const 배열(월, chargeData, revenueData 등)을 읽어, **Chart.js를 Node에서
 * 직접** (skia-canvas + `chart.js/dist/chart.mjs`) 렌더 후, `sharp`로 **흰 배경 합성 → 가로 제한 리사이즈 → JPEG 또는 PNG** 저장.
 * 이메일·data URL은 **`.jpg` 권장**(PNG 대비 용량 대폭 감소). `CHART_IMAGE_MAX_WIDTH`(기본 820), `CHART_IMAGE_JPEG_QUALITY`(기본 72).
 * (의존: chart.js, skia-canvas, sharp — 저장소 루트 또는 `application/skills/account-status`에서 `npm install` 후 실행.)
 *
 * --- 에이전트/자동화용: npm 실패 시 임의 대체 금지 ---
 * `npm install`·레지스트리 차단·이 스크립트 실패 시 **연쇄로 시도하지 말 것:** Puppeteer/Playwright·`npx` 브라우저 캡처, Python(PIL·cairosvg·matplotlib), wkhtmltoimage/ImageMagick, Chrome/Chromium headless로 HTML 전체 스크린샷, 스킬 경로에만 `npm init` 등. 보장된 경로는 이 파일 + 루트 의존성뿐임(SKILL.md Step 6 동일). 실패 시 사용자에게 루트에서 재설치/정책 해제를 안내하거나 차트 이미지 생략. 사용자가 **명시**한 수단만 예외.
 *
 * 캡처: `new Chart(`가 있는 `<script>`, 월 라벨 `months12`(권장)·`months24`(레거시)·`labels`, `chargeData`+`revenueData` 등.
 * 제목: `#lg-account-monthly-trend-12m` 섹션의 `<h2>`(레거시 `#lg-account-monthly-trend-24m`도 제목 추출 시 시도).
 */
import fs from "fs";
import path from "path";
import sharp from "sharp";
import { Chart, registerables } from "chart.js/dist/chart.mjs";
import skia from "skia-canvas";

const { Canvas, Image: SkiaImage } = skia;
const _prevImage = globalThis.Image;
globalThis.Image = SkiaImage;

Chart.register(...registerables);

/** 차트 캔버스 가로(렌더). 이메일용으로 기본 1200. */
const DEFAULT_WIDTH = 1200;
const DEFAULT_SECTION_SELECTOR = "#account-monthly-trend-12m";
const LEGACY_SECTION_SELECTOR = "#account-monthly-trend-24m";
const DEFAULT_MAX_OUT_W = 820;
const DEFAULT_JPEG_Q = 72;

const input = process.argv[2];
const output = process.argv[3];

let width = DEFAULT_WIDTH;
let sectionSelector =
  process.env.CHART_IMAGE_SELECTOR ||
  process.env.LG_CHART_IMAGE_SELECTOR ||
  DEFAULT_SECTION_SELECTOR;
for (const arg of process.argv.slice(4)) {
  if (/^\d+$/.test(arg)) {
    width = parseInt(arg, 10);
  } else {
    sectionSelector = arg;
  }
}

if (!input || !output) {
  console.error(
    "Usage: node html_to_chart_image.mjs <input.html> <out.png|out.jpg> [widthPx] [cssSelector]\n" +
      "Default: " +
      DEFAULT_SECTION_SELECTOR +
      " (section id for <h2>; chart data from <script>; 12-month trend)\n" +
      "이메일용: out.jpg (작은 용량). 예: node .../html_to_chart_image.mjs report.html chart.jpg 1200"
  );
  process.exit(1);
}

const absInput = path.resolve(input);
if (!fs.existsSync(absInput)) {
  console.error("Input file not found:", absInput);
  process.exit(1);
}

const html = fs.readFileSync(absInput, "utf8");
const outPath = path.resolve(output);
const isJpeg = /\.jpe?g$/i.test(outPath);
const maxOutW = Math.max(
  200,
  parseInt(
    process.env.CHART_IMAGE_MAX_WIDTH ||
      process.env.LG_CHART_IMAGE_MAX_WIDTH ||
      String(DEFAULT_MAX_OUT_W),
    10
  ) || DEFAULT_MAX_OUT_W
);
const jpegQ = Math.min(
  100,
  Math.max(
    30,
    parseInt(
      process.env.CHART_IMAGE_JPEG_QUALITY ||
        process.env.LG_CHART_IMAGE_JPEG_QUALITY ||
        String(DEFAULT_JPEG_Q),
      10
    ) || DEFAULT_JPEG_Q
  )
);
const outDir = path.dirname(outPath);
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

function takeBracketRange(source, startIndex, openToken) {
  const close = openToken === "[" ? "]" : "}";
  let depth = 0;
  let i = startIndex;
  if (source[i] !== openToken) return null;
  for (; i < source.length; i++) {
    const c = source[i];
    if (c === openToken) depth++;
    else if (c === close) {
      depth--;
      if (depth === 0) return source.slice(startIndex, i + 1);
    }
  }
  return null;
}

function extractConstArrayExpr(script, varName) {
  const re = new RegExp("const\\s+" + varName + "\\s*=\\s*\\[", "m");
  const m = script.match(re);
  if (!m || m.index === undefined) return null;
  const openIdx = m.index + m[0].length - 1;
  return takeBracketRange(script, openIdx, "[");
}

function evalArrayExpr(expr) {
  const fn = new Function(`"use strict"; return ${expr};`);
  return fn();
}

function extractBorderColorsFromChartScript(script) {
  const out = [];
  const re = /borderColor:\s*['"](#[0-9a-fA-F]{6})['"]/g;
  let m;
  while ((m = re.exec(script)) !== null) {
    if (!out.includes(m[1])) out.push(m[1]);
  }
  return out;
}

function findChartScriptBlock(fullHtml) {
  const key = "new Chart(";
  const idx = fullHtml.lastIndexOf(key);
  if (idx === -1) {
    return null;
  }
  const scriptOpen = fullHtml.lastIndexOf("<script", idx);
  const scriptEnd = fullHtml.indexOf("</script>", idx);
  if (scriptOpen === -1 || scriptEnd === -1) {
    return null;
  }
  const contentStart = fullHtml.indexOf(">", scriptOpen) + 1;
  return fullHtml.slice(contentStart, scriptEnd);
}

function extractSectionTitle(fullHtml, selector) {
  const id = selector.replace(/^#/, "");
  const secRe = new RegExp(
    '<section\\s+[^>]*id=["\']' + id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '["\'][^>]*>([\\s\\S]*?)</section>',
    "i"
  );
  const sm = fullHtml.match(secRe);
  if (!sm) return null;
  const h2m = sm[1].match(/<h2[^>]*>([\s\S]*?)<\/h2>/i);
  if (!h2m) return null;
  return h2m[1]
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .trim();
}

const script = findChartScriptBlock(html);
if (!script) {
  console.error("new Chart(…)가 포함된 <script>를 찾을 수 없습니다. LG HTML 형식을 확인하세요.");
  process.exit(1);
}

const labels = (() => {
  for (const name of ["months12", "months24", "labels"]) {
    const ex = extractConstArrayExpr(script, name);
    if (ex) {
      try {
        return evalArrayExpr(ex);
      } catch {
        /* */
      }
    }
  }
  return null;
})();

let d1, d2;
for (const pair of [
  ["chargeData", "revenueData"],
  ["charges", "revenues"],
]) {
  const a = pair[0];
  const b = pair[1];
  const e1 = extractConstArrayExpr(script, a);
  const e2 = extractConstArrayExpr(script, b);
  if (e1 && e2) {
    try {
      d1 = evalArrayExpr(e1);
      d2 = evalArrayExpr(e2);
      break;
    } catch {
      /* */
    }
  }
}

if (!labels || !Array.isArray(labels) || !d1 || !d2) {
  console.error("const months12|months24|labels + chargeData/revenueData (또는 charges/revenues) 파싱 실패.");
  process.exit(1);
}
if (labels.length !== d1.length || labels.length !== d2.length) {
  console.error("labels·시계열 배열 길이 불일치", labels.length, d1.length, d2.length);
  process.exit(1);
}

const borderColors = extractBorderColorsFromChartScript(script);
const c0 = borderColors[0] || "#11998e";
const c1 = borderColors[1] || "#38ef7d";

let sectionTitle = extractSectionTitle(html, sectionSelector);
if (!sectionTitle && (sectionSelector === DEFAULT_SECTION_SELECTOR || sectionSelector.includes("12m"))) {
  sectionTitle =
    extractSectionTitle(html, LEGACY_SECTION_SELECTOR);
}
if (!sectionTitle) {
  sectionTitle = "월별 매출 추이 (12개월)";
}

const chartHeight = Math.round(Math.min(520, Math.max(360, width * 0.32)));
const titleOffset = 56;
const totalHeight = chartHeight + titleOffset;

const canvas = new Canvas(width, totalHeight);
const ctx = canvas.getContext("2d");

const configuration = {
  type: "line",
  data: {
    labels,
    datasets: [
      {
        label: "Charge",
        data: d1,
        borderColor: c0,
        backgroundColor: hexToRgba(c0, 0.1),
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.3,
        fill: true,
      },
      {
        label: "Revenue",
        data: d2,
        borderColor: c1,
        backgroundColor: hexToRgba(c1, 0.05),
        borderWidth: 2,
        pointRadius: 2,
        tension: 0.3,
        fill: false,
        borderDash: [5, 3],
      },
    ],
  },
  options: {
    responsive: false,
    maintainAspectRatio: false,
    animation: false,
    layout: { padding: 8 },
    interaction: { mode: "index", intersect: false },
    plugins: {
      title: {
        display: true,
        text: sectionTitle,
        font: { size: 16, weight: "600" },
        padding: { bottom: 12, top: 6 },
        color: "#333",
      },
      legend: {
        position: "top",
        labels: { usePointStyle: true, font: { size: 12 } },
      },
      tooltip: {
        callbacks: {
          label: (c) => {
            const y = c.parsed?.y;
            if (y == null) return c.dataset?.label || "";
            return `${c.dataset.label}: $${Number(y).toLocaleString()}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false, color: "#f0f0f0" },
        ticks: { maxRotation: 45, font: { size: 10 } },
      },
      y: {
        grid: { color: "#f0f0f0" },
        ticks: {
          font: { size: 10 },
          callback: (v) => "$" + (v / 1000).toFixed(0) + "K",
        },
      },
    },
  },
};

const chart = new Chart(ctx, configuration);
const rawPng = await canvas.toBuffer("png");
chart.destroy();
if (_prevImage !== undefined) {
  globalThis.Image = _prevImage;
} else {
  delete globalThis.Image;
}

const meta0 = await sharp(rawPng).metadata();
let pipe = sharp(rawPng).flatten({ background: { r: 255, g: 255, b: 255 } });
if (meta0.width && meta0.width > maxOutW) {
  pipe = pipe.resize(maxOutW, null, { withoutEnlargement: true, fit: "inside" });
}
const outBuf = isJpeg
  ? await pipe
      .jpeg({ quality: jpegQ, mozjpeg: true, chromaSubsampling: "4:2:0" })
      .toBuffer()
  : await pipe.png({ compressionLevel: 9, effort: 10 }).toBuffer();

fs.writeFileSync(outPath, outBuf);
console.log(
  "Wrote (Chart.js + skia, maxWidth=" +
    maxOutW +
    (isJpeg ? ", jpegQ=" + jpegQ : ", png") +
    "):",
  outPath,
  "→",
  Math.round(outBuf.length / 1024) +
    "KB"
);

function hexToRgba(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${a})`;
}
