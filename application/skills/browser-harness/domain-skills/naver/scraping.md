# Naver (네이버) — www.naver.com & 통합검색

[NAVER](https://www.naver.com/) is the default Korean web portal: unified search, 뉴스/쇼핑/증권/날씨 등 위젯, 로그인 시 MY/개인화 영역. **검색 결과·탭은 `search.naver.com`에 모이고**, 메인 `www.naver.com`은 콘텐츠/위젯 중심이다.

**브라우저 구동(이 프로젝트):** [`browser-use` CLI](https://github.com/browser-use/browser-use) — 상세는 **[`../../../browser-use/SKILL.md`](../../../browser-use/SKILL.md)**. 문서에 나오는 `js(...)` / `capture_screenshot` / `new_tab` 은 **`browser-use eval` / `browser-use screenshot` / `browser-use open`** 에 대응한다(아래 표 참고).

Field-tested map for **browser-use** (또는 동등한 자동화) + `http_get` (정적·직링크) 분리.

- **비밀번호·계정 자격 증명** — 스크린샷/페이지를 보고 **절대 입력하지 않는다** (상위 [SKILL.md](../../SKILL.md) “Auth wall”).
- **NAVER “보안 확인”** (가상 영수증·퀴즈형 질문, 예: “가게 전화번호의 **뒤에서 N번째** 숫자”) — **사람 풀이와 동일하게** 화면·스크린샷에서 정보를 읽고 **답을 입력·제출**한다. 이 단계를 **“다른 URL로 우회”** (같은 서비스를 우회 URL만 바꿔 재시도)로 **건너뛰지 말 것**; 우회는 재차 차단·빈 응답·잘못된 동작을 부르기 쉽다. 답이 불가능할 때만 사용자에게 **탭에서 수동 완료**를 요청한다.

---

## Do this first: task → 경로

| Goal | Best approach | Why |
|------|----------------|-----|
| 웹/뉴스/이미지 등 **통합검색** 결과 | **`https://search.naver.com/search.naver?query=…`** (+ 필요 시 `where=`) | 홈에서 입력 시뮬레이션보다 **직접 URL**이 안정적 |
| `www.naver.com` **홈 전용** (위젯, 레이아웃) | `browser-use open https://www.naver.com` → `browser-use screenshot` / `browser-use eval "..."` | 메인은 개인화·A/B·위젯으로 DOM이 자주 바뀐다 |
| **NAVER 보안 확인** (쇼핑 `search.shopping.naver.com` 등) | [아래 섹션](#naver-보안-확인-쇼핑·검색-등--질문에-답한다) — **답 제출** | **우회·대체 URL**이 아니라 **질문에 답** |
| 보안 화면에서 **영수증·전화번호가 이미지**라 `innerText`만으론 답이 안 잡힐 때 | `capture_screenshot` → [`text_extraction` MCP `extract_text_from_image`](#텍스트-추출-mcp--chatpy-이미지-분석-과-동일-계열) (또는 앱의 이미지 분석 + 커스텀 `prompt`) | LLM이 **질문+영수증**을 한 번에 보도록 [프롬프트에 질문을 명시](#권장-prompt-패턴) |
| **대량** 스태틱 HTML만 필요 | `http_get` + 파싱 시도(차단·HTML 변동 가능) | **항상** 실패/차단을 가정 |
| **공식 Open API** (검색·번역·지도 등) | [Naver Developers](https://developers.naver.com/) 앱·클라이언트 ID/시크릿(별도) | 하네스 `helpers.py`의 일반 `http_get`과는 **다른** 인증 모델 |

**선호:** 스크롤/클릭으로 “검색창에 타이핑”하기 전에, 아래 **검색 URL 패턴**으로 `query`만 넣을 수 있는지 먼저 본다.

### 같은 브라우저·같은 탭을 쓰기 (새 창/탭 꼬임 방지)

하네스는 **이미 떠 있는 Chrome**에 CDP로 붙는다. “작업하던 화면”을 이어 쓰려면:

| 상황 | 권장 | 피할 것 |
|------|------|--------|
| 쇼핑 검색/보안 확인 **이미 이 탭에 떠 있음** | **또** `browser-use open <같은 URL>` **하지 않기** — 새 탭/내비가 겹친다. 이어서는 **`browser-use state` / `eval` / `screenshot` / `input` / `click`** 만 사용. | `open`을 반복해 **세션이 둘**로 갈라짐 |
| 스크린샷을 **분석**만 하면 됨 | 파일 **경로**를 `text_extraction` / MCP에 넘기기(또는 `upload_file` 등). | OS **이미지 뷰어**로 PNG를 열어 Chrome과 **창이 둘**로 겹쳐 보이는 혼란 |
| 세션이 끊긴 느낌 | `browser-use state`로 현재 URL·요소 확인; 필요 시 `browser-use --connect open <url>`로 CDP 재부착( [browser-use skill](../../../browser-use/SKILL.md) ). | `open`·`cloud connect`를 **매 스텝** 중복 |
| **클라우드 브라우저** | `browser-use cloud connect` **한 번** + 같은 세션에서만 조작( [browser-use skill](../../../browser-use/SKILL.md) ). | 작업마다 새 `cloud connect` → 새 브라우저 |

**첫 방문 vs 이어 하기:** 첫 목적 URL은 `browser-use open …` 한 번. Capcha/보안이 **이미** 떠 있으면 **다시 `open`으로 같은 URL을 열지 말고**, `state` → `input` / `click` / `eval`로만 처리(불필요한 내비는 챌린지를 리셋할 수 있음).

---

## URL patterns (PC, `search.naver.com`)

호스트: **`https://search.naver.com/search.naver`**

- **`query`**: 검색어 — **UTF-8** — 반드시 URL 인코딩(`urllib.parse.quote`, 브라우저 주소창과 동일).
- **`ie`, `oe`**: 인코딩. 관습적으로 `ie=UTF-8`을 붙이는 경우가 많다.
- **`where`**: 탭/영역(제품마다 상세 값이 늘어난다 — 없으면 통합/웹에 가깝게 동작하는 경우가 많다).

| `where` (자주 쓰는 값) | 용도 |
|------------------------|------|
| `web` / 생략 (환경에 따라) | 일반 웹 문서 |
| `news` | 뉴스 |
| `image` | 이미지 |
| `video` | 동영상 |
| `view_blog` / `blog` 계열 (문서 뷰) | 블로그(제품에 따라 쿼리 키가 다를 수 있음) |
| `kin` | 지식iN |
| `encyc` | 백과 |

**직접 열기 예 (개념):**

```text
https://search.naver.com/search.naver?query={encoded}&ie=UTF-8
https://search.naver.com/search.naver?query={encoded}&where=news&ie=UTF-8
```

`{encoded}`는 `urllib.parse.quote("검색어", safe="")` 수준의 퍼센트 인코딩 문자열.

**모바일 뷰:** `m.naver.com` / `m.search.naver.com` — **PC DOM·쿼리와 다름**. `open` URL을 `www`와 `m`에 **혼용하지 말고** 한 쪽으로 통일.

---

## `www.naver.com` (메인) — browser-use CLI

- **Entry:** `browser-use open https://www.naver.com/` (필요 시 `browser-use --headed` 또는 `--connect` / `--profile` — [browser-use skill](../../../browser-use/SKILL.md))
- **로딩·DOM:** `browser-use wait` 또는 `eval "document.readyState"` (짧은 대기).
- **접근성용 스킵 링크:** “상단영역/서비스 메뉴/…” — 자동완성과 겹칠 수 있으니 검색은 **`search.naver.com` 직링크** + `open` 권장.
- **요소 지정:** `browser-use state`로 **index** 확보 → `click` / `input` (고정 `id`에 의존하지 않기). 픽셀은 `browser-use click <x> <y>`; 문서엔 *어떤 UI인지*만.
- **iframe / 광고:** [iframes](../../interaction-skills/iframes.md), [cross-origin](../../interaction-skills/cross-origin-iframes.md); 복잡하면 `eval`로 iframe 내부만 타겟.

---

## NAVER 보안 확인 (쇼핑·검색 등) — **질문에 답한다**

`search.shopping.naver.com`, `search.naver.com` 등에서 봇으로 의심되면 **“NAVER 보안 확인”** 전용 페이지·오버레이가 뜬다. 본문에 `document.body.innerText`로 다음 류가 보이면 **보안 확인 흐름**이다:

- `NAVER 보안 확인을 완료해 주세요` / `보안 확인`
- `해당 영수증은 가상으로 제작된` / `가게 전화번호` + **서수 질문** (예: `뒤에서 1번째 숫자`, `앞에서 …번째`)

### 절대 하지 말 것 (에이전트 동작)

- “CAPTCHA이니 **우회**해보자”며 **같은 목적**을 **다른 진입 URL**로만 갈아타기(예: “직접 쇼핑 검색으로 다시”)를 **1순위**로 하지 말 것 — 사용자가 기대하는 것은 **퀴즈를 풀고 통과**하는 것이다.
- “No text”만 보고 **질문을 읽지도 않고** 끝내기.
- (반복) **아이디·비밀번호** 입력 — 이 화면은 **영수증 기반 퀴즈**이지 로그인 폼이 아닐 수 있다. 요구되는 것은 **숫자/선택지 답**이다.

### 할 일 (권장 순서)

1. **질문 문장을 끝까지 읽는다** — `뒤에서` = **끝자리 쪽**부터 셀 때, `앞에서` = **앞자리**부터, “1번째”가 어느 쪽을 기준으로 하는지(문장 그대로) 확정.
2. **가상 영수증**에서 **가게 전화번호**(또는 질문이 가리키는 필드)를 찾는다. `010-1234-5678`처럼 **하이픈**이 있으면 **숫자만** 쓰고, 질문이 요구하는 **한 자리**를 계산한다.  
   - 예: “뒤에서 1번째” → 마지막 숫자; “뒤에서 2번째” → 끝에서 두 번째 숫자.
3. **시각·DOM**: 영수증이 **이미지**이면 `capture_screenshot`으로 **영수증+질문이 같이** 보이게 저장한다. `innerText`만으로는 **가게 전화번호**가 비어 있거나 `undefined`로 보일 수 있음 — **캡차/퀴즈를 “못 찾는” 주된 이유**는 여기. 이 경우 **아래 [텍스트 추출 MCP](#텍스트-추출-mcp--chatpy-이미지-분석-과-동일-계열)**로 스크린샷을 보내 **질문에 대한 답만** 돌려받는다.
4. **입력 + 확인(다음)까지** — 답을 **구하기만** 하고 끝내면 통과하지 못한다. `extract_text_from_image` / `execute_code`는 **브라우저 밖**이므로, **같은 세션**에서 [아래 “답 제출”](#naver-security-submit-form) 절에 따라 **`browser-use state` → `input` / `click` / `eval`**(또는 `keys "Enter"`)로 **값 주입 + 확인**을 **반드시** 이어서 수행한다.
5. `wait_for_load()` / 짧은 `time.sleep` 후 `document.body.innerText`에 **보안 문구가 사라졌는지**·원래 쇼핑/검색 UI가 복귀했는지 확인.
6. **새로고침** 링크가 있고 **영수증이 흐릿**할 때만 새로고침 후 2~5를 반복.

### 사용자에게 맡기는 경우

- `text_extraction`·이미지 분석까지 했는데도 **답이 불확실**하거나, **hCaptcha/클릭 그리드** 같이 “이 문서”가 아닌 **서드파티** 위젯이 요구될 때 — **이 탭에서 수동**으로 끝내 달라고 요청(우회 URL 제안이 아님).

### 텍스트 추출 MCP · `chat.py` 이미지 분석(과 동일 계열)

이 워크스페이스에서는 **`text_extraction`** MCP 서버([`application/mcp_server_text_extraction.py`](../../../../mcp_server_text_extraction.py))의 **`extract_text_from_image`**, [`application/chat.py`](../../../../chat.py)의 **`extract_text` / `summary_image` / `summarize_image`**와 **같은 식**으로 이미지+텍스트 프롬프트를 **Bedrock 멀티모달**에 넘긴다.

- **`extract_text_from_image(image_path=..., prompt=...)`**  
  - `prompt`를 생략하면 기본은 “텍스트 추출 + `<result>`”(**OCR**에 가깝다).  
  - NAVER **보안 확인(퀴즈)**에는 **반드시 `prompt`를 넘긴다** — [권장 패턴](#권장-prompt-패턴) 참고.

- **이미지 업로드 → `chat.summarize_image(image_content, prompt)`** ([`app.py`](../../../../app.py) 등)  
  - 내부에서 `text = extract_text(img_base64)` 후 **`image_summary = summary_image(img_base64, prompt)`** ([`chat.py` `summarize_image` / `summary_image`](../../../../chat.py)).  
  - `summary_image`는 `instruction`(= 사용자 `prompt`)이 있을 때  
    `f"{instruction}. <result> tag를 붙여주세요. 한국어로 답변하세요."`  
    를 질의로 쓴다 — 즉 **사용자 `prompt`에 “주어진 질문의 답을 찾아주세요” + 질문 본문**을 넣으면, **퀴즈 정답**이 잘 나오는 경로와 동일하다.

**브라우저 하네스와의 연결 (스크립트 흐름):**

1. `js`로 **질문 문장**만 먼저 수집 (예: `document.body.innerText`에서 `뒤에서`…`숫자`까지).
2. 영수증: `#rcpt_img`가 있으면 `browser-use eval "document.getElementById('rcpt_img')?.src || ''"` 로 **data URL / URL** 확인 → `base64`를 파일로 저장해 MCP에 넣거나, `browser-use screenshot path.png`로 보낸다.
3. MCP **`extract_text_from_image`**, `execute_code`, 또는 `summarize_image` — 아래 [권장 `prompt` 패턴](#권장-prompt-패턴) 사용; 반환에서 **한 자리**만 파싱.
4. **(필수)** [답 제출](#naver-security-submit-form): **다시 Bash로 `browser-use` 실행** — `input` / `click` / `eval`로 **입력란 + 확인** — `execute_code`에서 답만 `print`하고 끝내면 **페이지는 그대로**다.

### 권장 `prompt` 패턴

필드 테스트상 **이미지 분석 요청에 아래 문구를 같이 쓰면** 퀴즈 답(전화번호 한 자리 등)이 잘 나온다:

- **고정 머리말:** `주어진 질문의 답을 찾아주세요.`
- **이어서:** 가상 영수증에서 **읽을 필드**(가게 전화번호 등), **질문 전문**(`innerText`에서 복사), **답의 형식**(예: “한 자리 숫자만, 다른 설명 없이”).

**예 (`extract_text_from_image`용, 개념):**

```text
주어진 질문의 답을 찾아주세요. 가상 영수증 이미지에만 나온 가게 전화번호를 읽고, 질문이 요구하는 자리의 숫자 한 자리만 답하세요. 질문: {페이지 innerText에 나온 질문 전체}. 답은 숫자 한 자리만 출력하세요. <result> 태그로 감싸 주세요.
```

MCP 구현은 `<result>` 파싱을 `mcp_server_text_extraction.py`의 `_parse_result`에서 하므로, `chat.py`의 `summary_image`와 맞추려면 `prompt` 끝에 “`<result>`로 감싸 달라”는 식의 지시를 두면 된다.

**주의:** 경로는 실행 환경에서 읽을 수 있는 **`capture_screenshot`이 저장한 절대 경로**를 쓴다(아티팩트 디렉터리 등). 에이전트에 MCP가 없으면, 동일 `prompt`로 **UI 이미지 분석 모드**(`summarize_image`)를 호출하는 경로를 쓴다.

<a id="naver-security-submit-form"></a>

### 답을 얻은 뒤: **입력·이벤트·확인(다음) 버튼** (가장 흔한 실패 지점)

`extract_text_from_image` / `execute_code`로 **답 숫자만** 얻고 나면, **DOM에는 아직 아무것도 입력되지 않은 상태**다. “다음/확인”을 **누르지 못해** 막히는 경우는 대부분 아래 중 하나다.

1. **툴 체인이 끊김** — Python `execute_code`로 분석만 하고, **이어지는 `browser-use …` (Bash)** 없이 끝남. **반드시** 답을 얻은 뒤 **`browser-use state` → `input` / `keys` / `click`** 를 호출한다.
2. **값만 넣고 이벤트 없음** — `browser-use input` 이후에도 React가 무반응이면 `browser-use eval`로 `dispatchEvent` 또는 **`browser-use keys "Enter"`** / 확인 버튼 `click <index>`.
3. **잘못된 입력** — `querySelector("input")`이 **다른** 필드를 잡음. 영수증은 `#rcpt_img` — **같은 카드/폼** 안의 텍스트 필드를 찾는다.
4. **버튼** — `확인` / `다음` / `인증` / `제출` 문구, `button[type=submit]`, 비활성(`disabled`) 해제 **후** 클릭. 스크립트로 잡기 어려우면 [screenshots.md](../../interaction-skills/screenshots.md) 후 `click_at_xy`로 텍스트가 보이는 **확인** 영역.

**`js`로 한 번에 시도하는 패턴 (문자열 이스케이프에 주의, `digit`는 한 자리):**

- `#rcpt_img` **근방 폼**에서 `input`을 찾고, 값 설정 후 **이벤트** → **확인/다음** 후보를 찾아 `click()`.
- 아래는 **의사 코드**이며, 실제 DOM에 맞게 셀렉터·버튼 텍스트를 조정한다.

```javascript
(function() {
  var d = "REPLACE_ONE_DIGIT";  // 예: "7"
  var img = document.getElementById("rcpt_img");
  var root = (img && img.closest("form")) || (img && img.closest("section, article, .area, [class*='captcha' i]")) || document.body;
  var inputs = root.querySelectorAll("input");
  var inp = null;
  for (var i = 0; i < inputs.length; i++) {
    var t = (inputs[i].type || "").toLowerCase();
    if (t === "hidden" || t === "submit" || t === "button") continue;
    inp = inputs[i];
    break;
  }
  if (!inp) inp = document.querySelector('input[type="text"], input[type="tel"], input:not([type])');
  if (!inp) return "ERR_NO_INPUT";
  inp.focus();
  inp.value = d;
  inp.dispatchEvent(new Event("input", { bubbles: true }));
  if (window.InputEvent) inp.dispatchEvent(new InputEvent("input", { bubbles: true, data: d }));
  inp.dispatchEvent(new Event("change", { bubbles: true }));
  inp.dispatchEvent(new Event("blur", { bubbles: true }));
  var labels = [/^확인$/, /다음/, /인증/, /제출/];
  var buttons = Array.prototype.slice.call(document.querySelectorAll("button, [role=button], input[type=submit], a.btn, a"));
  for (var b = 0; b < buttons.length; b++) {
    var el = buttons[b], txt = (el.textContent || el.value || el.innerText || "").trim();
    if (el.disabled) continue;
    for (var k = 0; k < labels.length; k++) {
      if (labels[k].test(txt)) { el.click(); return "OK_CLICKED " + txt; }
    }
  }
  if (root.requestSubmit) { root.requestSubmit(); return "OK_FORM_REQUESTSUBMIT"; }
  return "ERR_NO_BUTTON";
})()
```

**`browser-use eval`:** `REPLACE_ONE_DIGIT`를 셸에서 이스케이프해 **한 줄**로 넘기거나, `browser-use python`으로 멀줄 스크립트에서 `document`를 조작( [browser-use skill](../../../browser-use/SKILL.md) ). **`state`로** 입력/확인 **index**를 잡는 편이 안정적이다.

- 여전히 버튼이 `disabled`이면, **한 글자씩** 타이핑(`input` + `type`) 또는 `eval`로 이벤트, 그다음 `state`로 다시 인덱스 확인.
- `Enter`로 제출: `browser-use keys "Enter"` ( [browser-use skill](../../../browser-use/SKILL.md) ).

---

## `http_get` (선택)

- **SERP HTML**을 `http_get`으로 가져와 파싱하는 건 **가능한 경우**와 **403/빈·다른 뷰**가 섞인다. User-Agent·차단·봇 정책에 따라 **브라우저가 더 안정적**인 경우가 많다.
- **RSS/뉴스 스탠다드**가 필요하면 네이버 **뉴스·스포츠** 등 **도메인별** 공개 피드가 있는지(제휴·뉴스 룸) **사이트 정책**을 먼저 확인한다(여기서 URL을 하드코딩한 공식 피드 목록을 유지하지 않는다 — 변동 큼).

---

## Waits & traps

- **자동완성/최근검색** 패널이 열리면 `Enter`·클릭이 **다른** SERP로 간다. 직링크 `search.naver.com`이면 이 클래스의 문제를 줄일 수 있다.
- **NAVER “보안 확인” (영수증·전화번호 퀴즈)** — [위 “질문에 답한다”](#naver-보안-확인-쇼핑·검색-등--질문에-답한다)를 따른다. **“우회”**가 기본이 아님.
- **아이디/비밀번호·결제 PIN** — 직접 **입력하지 않음**. 보안 확인의 **퀴즈 답**은 예외(위 섹션).
- **로그인 리다이렉트(계정 풀 사인인)** — 자격 증명 없이 **자동으로 넘지 않음**; 사용자에게.
- **세션/지역(해외 IP)**에 따라 콘텐츠·리디렉트가 달라질 수 있다.
- **이용약관·robots.txt** — 자동 수집이 금지된 영역은 `http_get`·스크래핑으로 시도하지 않는다.

---

## Minimal direct-search helper (PC)

`helpers`의 `http_get` + 브라우저로 SERP URL만 공유해도 되므로, **URL 생성**은 이렇게 맞추면 재현이 쉽다:

```python
import urllib.parse

def naver_search_url(query: str, where: str | None = None) -> str:
    q = urllib.parse.quote(query, safe="")
    base = f"https://search.naver.com/search.naver?query={q}&ie=UTF-8"
    if where:
        base += f"&where={urllib.parse.quote(where, safe='')}"
    return base
```

- 브라우저: `browser-use open <naver_search_url 결과>` → `browser-use get html` / `eval "document.body.innerText.slice(0,3000)"` 등(상한).

---

## Related

- [interaction-scrolling](../../interaction-skills/scrolling.md) — 홈/피드 무한 스크롤
- [screenshots](../../interaction-skills/screenshots.md) — 메인·SERP 시각 확인
- 코드: [`application/mcp_server_text_extraction.py`](../../../../mcp_server_text_extraction.py) (`extract_text_from_image`) · [`application/chat.py`](../../../../chat.py) (`summarize_image`, `summary_image`, `extract_text`)
- 상위: [Naver.com](https://www.naver.com/) · 통합검색 [search.naver.com](https://search.naver.com/) (PC 기준; 모바일은 `m` 호스트)
