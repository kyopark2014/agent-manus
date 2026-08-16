#!/usr/bin/env node
/**
 * Standalone draw.io CLI for architecture-drawer skill.
 * Powered by drawio-jsapi (vendored from aws-samples/sample-drawio-mcp).
 *
 * Usage:
 *   node drawio_cli.mjs apply --ops ops.json --out diagram.drawio
 *   node drawio_cli.mjs layout-guidance
 *   node drawio_cli.mjs list-groups
 *   node drawio_cli.mjs list-icons [--category compute]
 *   node drawio_cli.mjs search-icons <query>
 *   node drawio_cli.mjs info <file.drawio>
 *   node drawio_cli.mjs validate <file.drawio>
 *   node drawio_cli.mjs apply --help
 */

import { existsSync, mkdirSync, readFileSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

function ensureDeps() {
  try {
    require.resolve("drawio-jsapi");
    require.resolve("@xmldom/xmldom");
    require.resolve("pako");
  } catch {
    console.error(
      "Missing dependencies. Run once:\n  cd scripts && npm install",
    );
    process.exit(1);
  }
}

ensureDeps();

const {
  DiagramEngine,
  setupGlobalMocks,
  AWS4_ICONS,
} = await import("drawio-jsapi");
const { getLayoutGuidance, getLayoutGuidanceText } = await import(
  "./lib/layoutGuidance.js"
);

setupGlobalMocks();

const DEFAULT_EDGE_STYLE = {
  edgeStyle: "orthogonalEdgeStyle",
  endArrow: "classic",
  strokeWidth: 1,
  rounded: 0,
  html: 1,
};

function ok(data, message) {
  return { success: true, message, data };
}

function fail(error) {
  return { success: false, error: String(error) };
}

function requireLoaded(engine) {
  if (!engine.isLoaded) {
    throw new Error("No diagram loaded. Use create_diagram or load_diagram first.");
  }
}

/**
 * drawio-jsapi XmlParser expects mxGraphModel as root OR compressed text inside
 * <diagram>. Files saved by the same library nest <mxGraphModel> as an element,
 * which yields empty textContent. Extract the model XML before loading.
 * Also flatten nested parent attrs to parent="1" so reload works (jsapi serializer
 * only walks children of the default parent). Visual nesting uses geometry.
 */
function prepareXmlForLoad(xml) {
  const match = xml.match(/<mxGraphModel[\s\S]*?<\/mxGraphModel>/);
  let model = match ? match[0] : xml;
  model = model.replace(/\sparent="(?!0"|1")[^"]*"/g, ' parent="1"');
  return model;
}

function loadDiagramFile(engine, filePath) {
  const abs = resolve(filePath);
  if (!existsSync(abs)) {
    return fail(`File not found: ${abs}`);
  }
  const raw = readFileSync(abs, "utf8");
  const xml = prepareXmlForLoad(raw);
  const result = engine.loadFromXml(xml);
  if (!result.success) return fail(result.error);
  return ok(
    { ...(result.data || {}), file_path: abs },
    `Loaded ${abs}`,
  );
}

/**
 * Nesting is visual (geometry). Reparenting breaks save/load round-trip in
 * drawio-jsapi, so set_parent is a documented no-op that records intent only.
 */
function setParent(_engine, cellId, parentId) {
  return ok(
    { cell_id: cellId, parent_id: parentId, applied: false },
    `Noted nesting ${cellId} ⊂ ${parentId} (visual only; keep absolute geometry)`,
  );
}

function validateDiagram(engine, checks = ["all"]) {
  requireLoaded(engine);
  const runAll = checks.includes("all");
  const issues = [];

  const vertices = engine.api.cells.getVertices().data || [];
  const edges = engine.api.cells.getEdges().data || [];
  const vertexIds = new Set(vertices.map((v) => v.id));

  if (runAll || checks.includes("orphan_edges")) {
    for (const edge of edges) {
      const source = edge.sourceId || edge.source;
      const target = edge.targetId || edge.target;
      const hasSource = source && vertexIds.has(source);
      const hasTarget = target && vertexIds.has(target);
      if (!hasSource || !hasTarget) {
        issues.push({
          type: "orphan_edge",
          severity: "warning",
          cell_id: edge.id,
          message: `Edge "${edge.id}" missing ${[!hasSource && "source", !hasTarget && "target"].filter(Boolean).join(" and ")}`,
        });
      }
    }
  }

  if (runAll || checks.includes("overlapping_cells")) {
    for (let i = 0; i < vertices.length; i++) {
      for (let j = i + 1; j < vertices.length; j++) {
        const a = vertices[i];
        const b = vertices[j];
        const ag = a.geometry;
        const bg = b.geometry;
        if (!ag || !bg) continue;
        const aw = ag.width ?? 78;
        const ah = ag.height ?? 78;
        const bw = bg.width ?? 78;
        const bh = bg.height ?? 78;
        const overlap =
          ag.x < bg.x + bw &&
          ag.x + aw > bg.x &&
          ag.y < bg.y + bh &&
          ag.y + ah > bg.y;
        // Ignore large containers overlapping children (container typically much larger)
        const aIsContainer = aw > 200 || ah > 200;
        const bIsContainer = bw > 200 || bh > 200;
        if (overlap && !(aIsContainer || bIsContainer)) {
          issues.push({
            type: "overlapping_cells",
            severity: "warning",
            cell_ids: [a.id, b.id],
            message: `Cells "${a.id}" and "${b.id}" overlap`,
          });
        }
      }
    }
  }

  if (runAll || checks.includes("empty_labels")) {
    for (const v of vertices) {
      const label = v.label ?? v.value;
      if (!label || String(label).trim() === "") {
        issues.push({
          type: "empty_label",
          severity: "info",
          cell_id: v.id,
          message: `Vertex "${v.id}" has empty label`,
        });
      }
    }
  }

  return ok(
    { issue_count: issues.length, issues },
    issues.length === 0 ? "Validation passed" : `Found ${issues.length} issue(s)`,
  );
}

function findOverlapping(engine) {
  const result = validateDiagram(engine, ["overlapping_cells"]);
  return ok(
    { pairs: (result.data.issues || []).map((i) => i.cell_ids).filter(Boolean) },
    result.message,
  );
}

/**
 * Execute a single MCP-compatible operation against the engine.
 * @returns {{success:boolean, message?:string, data?:any, error?:string}}
 */
function runOp(engine, op) {
  const name = op.op || op.tool || op.action;
  if (!name) throw new Error("Operation missing 'op' field");

  switch (name) {
    case "create_diagram": {
      const result = engine.create({ name: op.name });
      if (!result.success) return fail(result.error);
      return ok(result.data, `Created diagram "${result.data?.name || op.name || "Page-1"}"`);
    }

    case "load_diagram": {
      return loadDiagramFile(engine, op.file_path);
    }

    case "load_diagram_from_xml": {
      const result = engine.loadFromXml(prepareXmlForLoad(op.xml));
      if (!result.success) return fail(result.error);
      return ok(result.data, "Loaded from XML");
    }

    case "save_diagram": {
      requireLoaded(engine);
      const path = resolve(op.file_path);
      mkdirSync(dirname(path), { recursive: true });
      const result = engine.saveToFile(path);
      if (!result.success) return fail(result.error);
      return ok({ file_path: path }, `Saved ${path}`);
    }

    case "get_diagram_info": {
      requireLoaded(engine);
      return ok(engine.getInfo().data, "Diagram info");
    }

    case "get_diagram_xml": {
      requireLoaded(engine);
      return ok({ xml: engine.toXml() }, "XML exported");
    }

    case "clear_diagram": {
      requireLoaded(engine);
      const result = engine.clear();
      if (!result.success) return fail(result.error);
      return ok(null, "Diagram cleared");
    }

    case "insert_aws_group": {
      requireLoaded(engine);
      const result = engine.api.cells.insertAwsGroup({
        id: op.id,
        groupType: op.group_type,
        label: op.label,
        geometry: op.geometry,
        styleOverrides: op.style_overrides,
      });
      if (!result.success) return fail(result.error);
      // parent_id is ignored for model reparenting (visual nesting via geometry)
      return ok(result.data, `Inserted AWS group ${op.group_type} (${result.data.id})`);
    }

    case "insert_aws_icon": {
      requireLoaded(engine);
      const geometry = {
        width: 78,
        height: 78,
        ...op.geometry,
      };
      const result = engine.api.cells.insertAwsIcon({
        id: op.id,
        icon: op.icon,
        category: op.category,
        label: op.label,
        geometry,
        styleOverrides: op.style_overrides,
      });
      if (!result.success) return fail(result.error);
      return ok(result.data, `Inserted AWS icon ${op.icon} (${result.data.id})`);
    }

    case "list_aws_group_types": {
      requireLoaded(engine);
      const result = engine.api.cells.getAwsGroupTypes();
      if (!result.success) return fail(result.error);
      return ok(result.data, "AWS group types");
    }

    case "insert_vertex": {
      requireLoaded(engine);
      const result = engine.api.cells.insertVertex({
        id: op.id,
        label: op.label,
        geometry: op.geometry,
        style: op.style,
      });
      if (!result.success) return fail(result.error);
      return ok(result.data, `Inserted vertex ${result.data.id}`);
    }

    case "insert_edge": {
      requireLoaded(engine);
      const result = engine.api.cells.insertEdge({
        id: op.id,
        sourceId: op.source_id,
        targetId: op.target_id,
        label: op.label,
        style: op.style || DEFAULT_EDGE_STYLE,
      });
      if (!result.success) return fail(result.error);
      return ok(result.data, `Inserted edge ${result.data.id}`);
    }

    case "update_cell": {
      requireLoaded(engine);
      const result = engine.api.cells.updateCell(op.cell_id || op.id, {
        label: op.label,
        geometry: op.geometry,
        style: op.style,
      });
      if (!result.success) return fail(result.error);
      return ok(null, `Updated ${op.cell_id || op.id}`);
    }

    case "move_cell": {
      requireLoaded(engine);
      const result = engine.api.cells.moveCell(op.cell_id, op.x, op.y);
      if (!result.success) return fail(result.error);
      return ok(null, `Moved ${op.cell_id}`);
    }

    case "resize_cell": {
      requireLoaded(engine);
      const result = engine.api.cells.resizeCell(op.cell_id, op.width, op.height);
      if (!result.success) return fail(result.error);
      return ok(null, `Resized ${op.cell_id}`);
    }

    case "remove_cell": {
      requireLoaded(engine);
      const result = engine.api.cells.removeCell(op.cell_id);
      if (!result.success) return fail(result.error);
      return ok(null, `Removed ${op.cell_id}`);
    }

    case "get_cell": {
      requireLoaded(engine);
      const result = engine.api.cells.getCell(op.cell_id);
      if (!result.success) return fail(result.error);
      return ok(result.data, `Cell ${op.cell_id}`);
    }

    case "get_cells": {
      requireLoaded(engine);
      if (op.type === "vertices") return ok(engine.api.cells.getVertices().data);
      if (op.type === "edges") return ok(engine.api.cells.getEdges().data);
      return ok(engine.api.cells.getCells().data);
    }

    case "set_parent": {
      requireLoaded(engine);
      return setParent(engine, op.cell_id, op.parent_id);
    }

    case "get_parent": {
      requireLoaded(engine);
      const result = engine.api.cells.getParent(op.cell_id);
      if (!result.success) return fail(result.error);
      return ok(result.data, result.data ? `Parent of ${op.cell_id}` : "No parent");
    }

    case "get_children": {
      requireLoaded(engine);
      const result = engine.api.cells.getChildren(op.cell_id);
      if (!result.success) return fail(result.error);
      return ok(result.data, `Children of ${op.cell_id}`);
    }

    case "create_group": {
      requireLoaded(engine);
      const result = engine.api.cells.groupCells(op.cell_ids);
      if (!result.success) return fail(result.error);
      return ok(result.data, `Created group ${result.data.id}`);
    }

    case "ungroup_cells": {
      requireLoaded(engine);
      const result = engine.api.cells.ungroupCells(op.group_id);
      if (!result.success) return fail(result.error);
      return ok(result.data, `Ungrouped ${op.group_id}`);
    }

    case "validate_diagram": {
      return validateDiagram(engine, op.checks || ["all"]);
    }

    case "find_overlapping_cells": {
      requireLoaded(engine);
      return findOverlapping(engine);
    }

    case "get_layout_guidance": {
      return ok(getLayoutGuidance(), "Layout guidance");
    }

    case "plan_layout": {
      // Simple grid planner (mirrors MCP plan_layout intent)
      const elements = op.elements || [];
      const cols = op.cols || Math.ceil(Math.sqrt(elements.length)) || 1;
      const spacing = op.spacing ?? 100;
      const margin = op.margin ?? 50;
      const startX = op.start_x ?? margin;
      const startY = op.start_y ?? margin;
      const positions = elements.map((el, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        return {
          id: typeof el === "string" ? el : el.id || el.name,
          x: startX + col * spacing,
          y: startY + row * spacing,
          col,
          row,
        };
      });
      return ok({ positions, spacing, cols }, "Layout planned");
    }

    case "search_shapes":
    case "search_icons": {
      const query = String(op.query || "").toLowerCase();
      const library = op.library || "aws4";
      if (library !== "aws4") {
        return fail(`Only aws4 library is supported in standalone mode (got: ${library})`);
      }
      const hits = [];
      for (const [category, icons] of Object.entries(AWS4_ICONS)) {
        for (const icon of Object.keys(icons)) {
          if (icon.toLowerCase().includes(query) || category.toLowerCase().includes(query)) {
            hits.push({ library: "aws4", category, icon, shape_id: icon });
          }
        }
      }
      return ok(hits, `Found ${hits.length} match(es) for "${query}"`);
    }

    default:
      return fail(`Unknown operation: ${name}`);
  }
}

function applyOps(ops, { out, load } = {}) {
  const engine = new DiagramEngine();
  const results = [];

  // Optional preload
  if (load) {
    const r = loadDiagramFile(engine, load);
    if (!r.success) {
      printJson(r);
      process.exit(1);
    }
    results.push(r);
  }

  for (let i = 0; i < ops.length; i++) {
    const op = ops[i];
    try {
      const result = runOp(engine, op);
      results.push({ index: i, op: op.op || op.tool || op.action, ...result });
      if (!result.success) {
        printJson({ success: false, failed_at: i, results });
        process.exit(1);
      }
    } catch (e) {
      results.push({ index: i, op: op.op || op.tool || op.action, ...fail(e.message) });
      printJson({ success: false, failed_at: i, results });
      process.exit(1);
    }
  }

  // Auto-save if --out given and last op wasn't save_diagram
  if (out) {
    const path = resolve(out);
    mkdirSync(dirname(path), { recursive: true });
    const save = engine.saveToFile(path);
    if (!save.success) {
      printJson(fail(save.error));
      process.exit(1);
    }
    results.push(ok({ file_path: path }, `Saved ${path}`));
  }

  const info = engine.isLoaded ? engine.getInfo().data : null;
  printJson({ success: true, output: out ? resolve(out) : null, info, results });
}

function printJson(obj) {
  console.log(JSON.stringify(obj, null, 2));
}

function listIcons(category) {
  if (category) {
    const icons = AWS4_ICONS[category];
    if (!icons) {
      printJson(fail(`Unknown category: ${category}. Available: ${Object.keys(AWS4_ICONS).join(", ")}`));
      process.exit(1);
    }
    printJson(ok({ category, icons: Object.keys(icons) }));
    return;
  }
  const all = {};
  for (const [cat, icons] of Object.entries(AWS4_ICONS)) {
    all[cat] = Object.keys(icons);
  }
  printJson(ok({ categories: Object.keys(AWS4_ICONS), icons: all }));
}

function usage() {
  console.log(`architecture-drawer drawio CLI (standalone, no MCP)

Commands:
  apply --ops <file.json> [--out <file.drawio>] [--load <file.drawio>]
  layout-guidance [--json]
  list-groups
  list-icons [--category <name>]
  search-icons <query>
  info <file.drawio>
  validate <file.drawio>

Ops JSON format:
  { "ops": [ { "op": "create_diagram", "name": "..." }, ... ] }
  or a bare array: [ { "op": "..." }, ... ]

Common ops: create_diagram, insert_aws_group, insert_aws_icon,
  set_parent, insert_edge, validate_diagram, save_diagram,
  load_diagram, move_cell, update_cell, remove_cell, get_cells,
  plan_layout, search_icons, get_layout_guidance

First-time setup:
  cd scripts && npm install
`);
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--ops" || a === "--out" || a === "--load" || a === "--category") {
      args[a.slice(2)] = argv[++i];
    } else if (a === "--json" || a === "--help" || a === "-h") {
      args[a.replace(/^--?/, "")] = true;
    } else {
      args._.push(a);
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0];

  if (!cmd || args.help || args.h) {
    usage();
    process.exit(cmd ? 0 : 1);
  }

  switch (cmd) {
    case "apply": {
      if (!args.ops) {
        console.error("--ops <file.json> required");
        process.exit(1);
      }
      const raw = JSON.parse(readFileSync(resolve(args.ops), "utf8"));
      const ops = Array.isArray(raw) ? raw : raw.ops;
      if (!Array.isArray(ops) || ops.length === 0) {
        console.error("Ops file must be an array or { ops: [...] }");
        process.exit(1);
      }
      // If first op isn't create/load and no --load, auto-create
      const first = ops[0]?.op || ops[0]?.tool || ops[0]?.action;
      if (!args.load && first !== "create_diagram" && first !== "load_diagram" && first !== "load_diagram_from_xml") {
        ops.unshift({ op: "create_diagram", name: raw.name || "Architecture" });
      }
      // If save_diagram present, use its path as default out
      const saveOp = [...ops].reverse().find((o) => (o.op || o.tool) === "save_diagram");
      const out = args.out || saveOp?.file_path;
      applyOps(ops, { out, load: args.load });
      break;
    }

    case "layout-guidance": {
      if (args.json) printJson(ok(getLayoutGuidance()));
      else console.log(getLayoutGuidanceText());
      break;
    }

    case "list-groups": {
      const engine = new DiagramEngine();
      engine.create({ name: "tmp" });
      printJson(ok(engine.api.cells.getAwsGroupTypes().data));
      break;
    }

    case "list-icons": {
      listIcons(args.category);
      break;
    }

    case "search-icons": {
      const query = args._[1];
      if (!query) {
        console.error("Usage: search-icons <query>");
        process.exit(1);
      }
      printJson(runOp(new DiagramEngine(), { op: "search_icons", query }));
      break;
    }

    case "info": {
      const file = args._[1];
      if (!file) {
        console.error("Usage: info <file.drawio>");
        process.exit(1);
      }
      const engine = new DiagramEngine();
      const r = loadDiagramFile(engine, file);
      if (!r.success) {
        printJson(r);
        process.exit(1);
      }
      printJson(ok(engine.getInfo().data));
      break;
    }

    case "validate": {
      const file = args._[1];
      if (!file) {
        console.error("Usage: validate <file.drawio>");
        process.exit(1);
      }
      const engine = new DiagramEngine();
      const r = loadDiagramFile(engine, file);
      if (!r.success) {
        printJson(r);
        process.exit(1);
      }
      printJson(validateDiagram(engine));
      break;
    }

    default:
      console.error(`Unknown command: ${cmd}`);
      usage();
      process.exit(1);
  }
}

main();
