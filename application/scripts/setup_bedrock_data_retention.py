#!/usr/bin/env python3
"""Opt in to Bedrock provider data sharing for Claude Fable 5."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bedrock_data_retention


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Opt in to Bedrock Data Retention API (provider_data_share) for Claude Fable 5."
    )
    parser.add_argument(
        "--region",
        default=bedrock_data_retention.DEFAULT_REGION,
        help="Bedrock region for the account data retention API (default: us-east-1)",
    )
    parser.add_argument(
        "--all-fable-regions",
        action="store_true",
        help="Opt in for all Fable 5 bedrock-runtime regions (us-west-2, us-east-1, us-east-2)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="GET current data retention setting instead of opting in",
    )
    args = parser.parse_args()

    if args.check:
        success, message = bedrock_data_retention.get_data_retention_mode(region=args.region)
    elif args.all_fable_regions:
        success = bedrock_data_retention.ensure_fable_data_retention(
            "global.anthropic.claude-fable-5",
            bedrock_region=args.region,
        )
        message = "configured all Fable bedrock regions" if success else "one or more regions failed"
    else:
        success, message = bedrock_data_retention.opt_in_provider_data_share(region=args.region)

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
