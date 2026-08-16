#!/usr/bin/env python3
"""
AWS Bedrock Anthropic 모델 지원 리전 확인 스크립트

사용법:
    python check_model.py "sonnet 4.7"
    python check_model.py "opus 4.7"
    python check_model.py "haiku 4.5"
"""

import subprocess
import json
import sys
import argparse

# AWS 주요 리전 목록
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-southeast-1",
    "ap-southeast-2",
]

REGION_LABELS = {
    "us-east-1":      "미국 동부 (버지니아)",
    "us-east-2":      "미국 동부 (오하이오)",
    "us-west-2":      "미국 서부 (오레곤)",
    "eu-west-1":      "유럽 (아일랜드)",
    "eu-west-2":      "유럽 (런던)",
    "eu-central-1":   "유럽 (프랑크푸르트)",
    "ap-northeast-1": "아시아 태평양 (도쿄)",
    "ap-northeast-2": "아시아 태평양 (서울)",
    "ap-southeast-1": "아시아 태평양 (싱가포르)",
    "ap-southeast-2": "아시아 태평양 (시드니)",
}


def normalize_keywords(user_input: str) -> list[str]:
    """
    사용자 입력을 키워드 리스트로 변환.
    예: "sonnet 4.7" -> ["sonnet", "4-7"]
         "opus 4.7"  -> ["opus", "4-7"]
    """
    normalized = user_input.lower().strip().replace(".", "-")
    return normalized.split()


def get_models_in_region(region: str) -> list[str] | None:
    """특정 리전의 Anthropic 모델 목록 조회. 실패 시 None 반환."""
    result = subprocess.run(
        [
            "aws", "bedrock", "list-foundation-models",
            f"--region={region}",
            "--by-provider", "anthropic",
            "--query", "modelSummaries[*].modelId",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def find_matching_models(model_ids: list[str], keywords: list[str]) -> list[str]:
    """모델 ID 목록에서 키워드를 모두 포함하는 모델만 필터링."""
    return [m for m in model_ids if all(kw in m.lower() for kw in keywords)]


def discover_model(user_input: str, regions: list[str] = None) -> dict:
    """
    모델 지원 리전 탐색 메인 함수.

    Returns:
        {
            "input": str,
            "keywords": list[str],
            "supported": {region: [model_id, ...]},
            "unsupported": [region, ...],
            "errors": [region, ...],
        }
    """
    if regions is None:
        regions = AWS_REGIONS

    keywords = normalize_keywords(user_input)
    result = {
        "input": user_input,
        "keywords": keywords,
        "supported": {},
        "unsupported": [],
        "errors": [],
    }

    for region in regions:
        model_ids = get_models_in_region(region)
        if model_ids is None:
            result["errors"].append(region)
            continue

        matched = find_matching_models(model_ids, keywords)
        if matched:
            result["supported"][region] = matched
        else:
            result["unsupported"].append(region)

    return result


def print_result(result: dict):
    """결과를 사람이 읽기 쉬운 형태로 출력."""
    print(f"\n🔍 모델 검색: '{result['input']}'")
    print(f"   검색 키워드: {result['keywords']}")
    print("=" * 65)

    if result["supported"]:
        print(f"\n✅ 지원 리전 ({len(result['supported'])}개):")
        for region, models in result["supported"].items():
            label = REGION_LABELS.get(region, region)
            print(f"  • {region:<20} ({label})")
            for model in models:
                print(f"      └─ {model}")
    else:
        print("\n❌ 지원하는 리전이 없습니다.")

    if result["unsupported"]:
        print(f"\n⛔ 미지원 리전 ({len(result['unsupported'])}개):")
        for region in result["unsupported"]:
            label = REGION_LABELS.get(region, region)
            print(f"  • {region:<20} ({label})")

    if result["errors"]:
        print(f"\n⚠️  조회 실패 리전 ({len(result['errors'])}개):")
        for region in result["errors"]:
            print(f"  • {region}")

    total = len(result["supported"]) + len(result["unsupported"]) + len(result["errors"])
    print(f"\n📊 요약: {total}개 리전 중 {len(result['supported'])}개 리전에서 지원")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="AWS Bedrock Anthropic 모델 지원 리전 확인"
    )
    parser.add_argument(
        "model",
        nargs="?",
        help="모델명 (예: 'sonnet 4.7', 'opus 4.7', 'haiku 4.5')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="결과를 JSON 형식으로 출력",
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        help="검색할 리전 목록 (기본값: 10개 주요 리전)",
    )
    args = parser.parse_args()

    if not args.model:
        parser.print_help()
        sys.exit(1)

    result = discover_model(args.model, regions=args.regions)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result)


if __name__ == "__main__":
    main()
