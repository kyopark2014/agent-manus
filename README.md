# MCP Manus (agent-skills style)

Manus multi-agent(Coordinator → Planner ↔ Operator → Reporter)를 **agent-skills**와 같은 FastAPI + React / Skills + MCP 구조로 실행합니다.

## 개요

| 구분 | 경로 | 역할 |
|------|------|------|
| Web UI | `application/server.py`, `application/web/` | Task·Chat·Skill/MCP 설정, SSE 스트리밍 |
| Agent | `application/runtime_mode.py` → `manus.run_manus` | 입력 시 Manus 파이프라인 실행 |
| Skills / MCP | `skills/`, `mcp.list`, `mcp_config.py` | UI에서 선택, Manus tools에 주입 |
| 인프라 | `installer.py` | 공유 S3/CloudFront + 프로젝트 KB (`docs/mcp-manus/`) |

```text
Browser (React :8501)
    │  REST + SSE (/api/tasks/{id}/chat)
    ▼
FastAPI (application/server.py)
    │  runtime_mode.run_agent → chat.run_manus_agent
    ▼
Manus (Coordinator / Planner / Operator / Reporter)
    + MCP (kb-retriever, tavily, …) + Skills
    + S3 artifacts via CloudFront sharing_url
```

Streamlit / CDK / lambda-rag는 사용하지 않습니다. Knowledge Base 조회는 **kb-retriever MCP**(Bedrock Retrieve)입니다.

## 로컬 실행

```bash
# 인프라·config.json (공유 버킷/CF 재사용, docs/mcp-manus/ 생성)
python installer.py

# 프론트 빌드 후 FastAPI (포트 8501)
./run_local.sh

# 또는
cd application/web && npm install && npm run build && cd ../..
pip install -r requirements.txt
uvicorn application.server:app --host 0.0.0.0 --port 8501
```

브라우저: [http://localhost:8501](http://localhost:8501)

- 채팅 입력 시 Manus agent가 동작합니다.
- Skill / MCP는 UI Config에서 선택합니다 (기본: `favorite_tools.json`).
- `application/config.json`의 `s3_bucket` / `sharing_url`은 다른 레포와 공유하는 RAG 스토리지를 가리킵니다.

프론트만 수정할 때:

```bash
cd application/web && npm run dev   # Vite :5173, /api → :8501 프록시
# 다른 터미널
uvicorn application.server:app --host 0.0.0.0 --port 8501
```

## 인프라 공유 규칙

- **공유**: S3 `storage-for-rag-project-{account}-{region}`, CloudFront comment `CloudFront-for-rag-project`
- **프로젝트 전용**: Knowledge Base / OpenSearch 이름 `mcp-manus`, 문서 prefix `docs/mcp-manus/`

## Manus 결과

- 본문 markdown + Operator에서 수집한 이미지 URL
- HTML/PDF artifact 링크는 응답의 **최종 결과** 섹션과 CloudFront URL로 제공
