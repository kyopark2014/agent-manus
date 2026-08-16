# PPT Translator

이 디렉터리는 PPT를 번역하는 에이전트 스킬을 Amazon Bedrock으로 구현합니다. 슬라이드·도형·노트·차트 메타(제목·축 등)를 가능한 한 유지한 채 텍스트를 번역할 수 있습니다.

## 기반 코드(출처)

**이 폴더의 Python 패키지(`ppt_translator/`)와 동작은 아래 upstream 저장소를 기준으로 가져온 것입니다.**

- **Base / upstream:** [https://github.com/daekeun-ml/ppt-translator](https://github.com/daekeun-ml/ppt-translator)

이 `agent-skills` 저장소에 포함된 구성은 에이전트 스킬(`SKILL.md`의 `{WORKING_DIR}` 등)에 맞춘 **다운스트림 번들**입니다. Upstream과 디렉터리·실행 방식이 다를 수 있으니, 전체 기능·문서·릴리스는 위 GitHub을 참고해 주십시오.

## 문서

| 파일 | 용도 |
|------|------|
| [SKILL.md](SKILL.md) | 에이전트용 지침(워크스페이스 경로, CLI, 흐름) |
| [requirements.txt](requirements.txt) | Python 의존성 |
| [glossary.yaml](glossary.yaml) | 용어집 예시 (`./glossary.yaml` 자동 탐색과 함께 참고) |

## 빠른 실행 (스킬 루트에서)

아래와 같이 필요한 패키지를 설치합니다. SKILL뿐 아니라 CLI로 실행할 수 있습니다.

```bash
cd application/skills/ppt-translator"
pip install -r requirements.txt
python -m ppt_translator.cli translate /path/to/file.pptx --target-language ko
```

- AWS 자격 증명과 Bedrock 모델 액세스가 필요합니다. 환경 변수·설정은 `ppt_translator/config.py`를 참고해 주십시오.
- 기본 대상 언어는 `ko`(한국어)입니다.
