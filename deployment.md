# Deployment

CDK / EC2 / lambda-rag 배포는 제거되었습니다.

- 인프라: `python installer.py` (공유 S3/CloudFront, 프로젝트 KB `mcp-manus`)
- 로컬 앱: `./run_local.sh` 또는 `uvicorn application.server:app --host 0.0.0.0 --port 8501`

자세한 내용은 [README.md](README.md)를 참고하세요.
