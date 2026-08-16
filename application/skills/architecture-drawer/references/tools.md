# architecture-drawer CLI Ops Reference

로컬 CLI: `skills/architecture-drawer/scripts/drawio_cli.mjs`  
**MCP는 사용하지 않습니다.** ops JSON의 `op` 이름으로 동일 기능을 호출합니다.

```bash
node skills/architecture-drawer/scripts/drawio_cli.mjs apply --ops ops.json --out diagram.drawio
node skills/architecture-drawer/scripts/drawio_cli.mjs layout-guidance
node skills/architecture-drawer/scripts/drawio_cli.mjs list-groups
node skills/architecture-drawer/scripts/drawio_cli.mjs list-icons [--category compute]
node skills/architecture-drawer/scripts/drawio_cli.mjs search-icons <query>
node skills/architecture-drawer/scripts/drawio_cli.mjs info <file.drawio>
node skills/architecture-drawer/scripts/drawio_cli.mjs validate <file.drawio>
```

Ops 파일 형식: `{ "ops": [ { "op": "create_diagram", ... }, ... ] }` 또는 배열 `[...]`.

새 작업은 항상 `create_diagram` 또는 `load_diagram` / `--load`부터 시작하세요.

## Diagram management

| Op | Description | Key params |
|------|-------------|------------|
| `create_diagram` | 빈 다이어그램 생성 | `name` |
| `load_diagram` | `.drawio` 파일 로드 | `file_path` |
| `load_diagram_from_xml` | XML 문자열 로드 | `xml` |
| `save_diagram` | 파일 저장 (`--out`이 있으면 생략 가능) | `file_path` |
| `get_diagram_xml` | XML 반환 | — |
| `get_diagram_info` | 셀 통계 | — |
| `clear_diagram` | 모든 셀 삭제 | — |

## AWS-specific (prefer these for architecture)

| Op | Description | Key params |
|------|-------------|------------|
| `insert_aws_group` | AWS 그룹 컨테이너 | `group_type`, `geometry`, `label?`, `id?` |
| `insert_aws_icon` | AWS 서비스 아이콘 | `icon`, `geometry`, `category?`, `label?`, `id?` |
| `list_aws_group_types` | 그룹 타입 목록 (CLI: `list-groups`) | — |

### `group_type` values

`awsCloud`, `awsCloudAlt`, `region`, `availabilityZone`, `securityGroup`, `vpc`, `privateSubnet`, `publicSubnet`, `autoScalingGroup`, `ec2InstanceContents`, `elasticBeanstalkContainer`, `spotFleet`, `stepFunctionsWorkflow`, `awsAccount`, `corporateDataCenter`, `serverContents`, `iotGreengrassDeployment`, `iotGreengrass`, `generic`, `genericFilled`

### `insert_aws_icon` tips

- `icon`: `"lambda"`, `"s3"`, `"rds"`, `"api_gateway"` 등 (소문자, 언더스코어)
- `category` 힌트: `compute`, `storage`, `database`, `networking`, `security`, `integration`, `management`, `analytics`, `machine_learning`, `general`
- 실패 시 CLI `search-icons <query>`로 확인 후 다시 insert

## Cells

| Op | Description |
|------|-------------|
| `insert_vertex` | 일반 shape |
| `insert_edge` | 연결선 |
| `update_cell` | label/geometry/style 업데이트 |
| `remove_cell` | 삭제 |
| `get_cell` / `get_cells` | 조회 |
| `move_cell` / `resize_cell` | 위치·크기 |

### `insert_edge`

```json
{
  "op": "insert_edge",
  "source_id": "web-ec2",
  "target_id": "db-rds",
  "id": "edge-1",
  "label": "3306",
  "style": {
    "edgeStyle": "orthogonalEdgeStyle",
    "endArrow": "classic",
    "strokeWidth": 1
  }
}
```

## Grouping

| Op | Description |
|------|-------------|
| `create_group` | 셀들을 그룹 |
| `ungroup_cells` | 그룹 해제 |
| `get_parent` / `get_children` | 계층 조회 |
| `set_parent` | 시각적 의도만 기록 (모델 재부모화 없음 — 절대 geometry로 중첩) |

## Layout & validation

| Op / CLI | Description |
|------|-------------|
| `get_layout_guidance` / `layout-guidance` | 다이어그램 생성 전 레이아웃 가이드 |
| `plan_layout` | 그리드 좌표 계획 |
| `validate_diagram` / `validate` | orphan edge, overlap 등 |
| `find_overlapping_cells` | 겹치는 셀 쌍 |
| `search_icons` / `search-icons` | 아이콘 검색 |

## Geometry convention

```
geometry: { x: number, y: number, width?: number, height?: number }
```

- 아이콘 기본 크기: ~78×78
- 그룹(VPC 등): 자식이 들어갈 여유를 두고 크게 (`width` 400+, `height` 300+)
- spacing 100px 그리드를 기본으로 맞춤
- edge용 셀은 `id`를 명시해 `source_id`/`target_id`에 재사용
