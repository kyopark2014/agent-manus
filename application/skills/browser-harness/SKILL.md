---
name: browser-harness
description: Site-specific browser playbooks (domain-skills, interaction-skills) for Naver, GitHub, etc. Automate the browser with the browser-use CLI (state/indexed elements, eval, screenshots)—same stack as skills/browser-use. Upstream browser-harness Python repo is optional for advanced CDP.
allowed-tools: Bash(browser-use:*)
---

# browser-harness (reference pack) + **browser-use CLI**

This folder bundles **`domain-skills/`** and **`interaction-skills/`** from [browser-use/browser-harness](https://github.com/browser-use/browser-harness) (site maps, UI mechanics). **Automation in this project uses the `browser-use` command**, documented in detail in **[`../browser-use/SKILL.md`](../browser-use/SKILL.md)**—same flow as that skill.

| Topic | Where |
|--------|--------|
| **Install, commands, `state` / `click` / `input` / `eval` / cloud / profiles** | [`../browser-use/SKILL.md`](../browser-use/SKILL.md) |
| **Naver, domains, gotchas, CAPTCHA, APIs** (this tree) | `domain-skills/<site>/` — e.g. [`domain-skills/naver/scraping.md`](domain-skills/naver/scraping.md) |
| **Dialogs, iframes, scroll, …** (bundled) | `interaction-skills/*.md` |

**Do not** use the separate `browser-harness` shell command as the default driver here unless the user explicitly asks for the upstream Python harness / `helpers.py` / `new_tab`+`js` workflow.

---

## Browser automation: **browser-use CLI** (default)

Prerequisites: `browser-use doctor` — see [browser-use skill README / upstream CLI docs](https://github.com/browser-use/browser-use/blob/main/browser_use/skill_cli/README.md).

### Core loop (match [`browser-use` skill](../browser-use/SKILL.md))

1. **Navigate:** `browser-use open <url>` (add `--headed` to see the window, `--connect` to attach to running Chrome, or `--profile "Default"` for saved logins)
2. **Inspect:** `browser-use state` — indices for click targets
3. **Interact:** `browser-use click <index>`, `browser-use input <index> "text"`, `browser-use keys "Enter"`
4. **Scripted DOM / one-off:** `browser-use eval "JavaScript returning a value"` (replaces a harness `js("...")` snippet)
5. **Screenshot:** `browser-use screenshot [path.png]` (or no path for base64)
6. **Session stays open** between commands — for “same tab, don’t open again”, **do not** run `open` for the same task; use `state` / `eval` / `click` on the current page
7. **Done:** `browser-use close`

### Maps from harness docs → CLI (when reading `domain-skills/`)

- **`js("...")` / in-page script** → `browser-use eval "..."` (escape quotes for shell; use `browser-use python` for multiline if needed)
- **`capture_screenshot(path)`** → `browser-use screenshot path.png`
- **`new_tab(url)` / first visit** → `browser-use open <url>`
- **“Which element?”** → `browser-use state` first, then `click` / `input` by **index**
- **Remote cloud browser** → `browser-use cloud connect` and related commands in [browser-use skill](../browser-use/SKILL.md) (not the harness `start_remote_daemon` + `BU_NAME` unless user insists on the harness)

### Chaining (same session)

```bash
browser-use open https://search.shopping.naver.com/search/all?query=demo
browser-use state
browser-use eval "document.body.innerText.slice(0,2000)"
```

Read [`../browser-use/SKILL.md`](../browser-use/SKILL.md) for the full command table, profiles, CDP, cloud, and troubleshooting.

---

## Search first (this directory)

```bash
rg --files domain-skills
rg -n "naver|shopping" domain-skills
```

Examples: `domain-skills/naver/scraping.md`, `domain-skills/github/scraping.md`, …

**Paths:** from repo root, under **`application/skills/browser-harness/`**.

---

## When to use this skill

- **Domain-specific** navigation (Naver security, site APIs, URL patterns) — read **`domain-skills/`** then drive the page with **`browser-use`**.
- **Reusable UI patterns** (iframes, scrolling) — **`interaction-skills/`**; implement with `browser-use` (`eval`, `wait`, `state`, `scroll`).

## Always contribute back

Non-obvious site learnings belong in **upstream** [`domain-skills/`](https://github.com/browser-use/browser-harness/tree/main/domain-skills) as PRs. This project’s `domain-skills/` is a **snapshot**; refresh from upstream when appropriate.

### What a domain skill should capture

Durable site shape: URL patterns, APIs, selectors, quirks, traps — not one-off run logs or secrets.

## Optional: upstream **browser-harness** command (not default here)

[browser-harness](https://github.com/browser-use/browser-harness) is a separate Python tool: `new_tab` / `click_at_xy` / `helpers.py` / CDP daemon. Use only if the user **explicitly** wants that flow; install and `SKILL.md` live **in the upstream repo**, not in this file.

- Docs: [upstream `SKILL.md`](https://github.com/browser-use/browser-harness/blob/main/SKILL.md), `install.md`, `helpers.py`
- This project’s **default** for agents is **`browser-use` CLI** as above

---

## References

- **CLI (canonical for this project):** [`../browser-use/SKILL.md`](../browser-use/SKILL.md) · [browser-use CLI README](https://github.com/browser-use/browser-use/blob/main/browser_use/skill_cli/README.md)
- **Upstream harness repo (optional):** [github.com/browser-use/browser-harness](https://github.com/browser-use/browser-harness)
- [docs.browser-use.com](https://docs.browser-use.com) · [llms.txt](https://docs.browser-use.com/llms.txt)

## Skill location in this project

| Path | Role |
|------|------|
| `SKILL.md` (this file) | **Use `browser-use` CLI** + where to read bundled skills |
| `domain-skills/` | Site-specific reference (bundled) |
| `interaction-skills/` | UI mechanics reference (bundled) |
