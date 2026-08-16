#!/usr/bin/env python3
"""Shared Athena / Glue helpers for businfo skill."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("businfo")

KST = timezone(timedelta(hours=9))

DEFAULT_REGION = os.environ.get("BUSINFO_REGION", "us-west-2")
DEFAULT_CATALOG = os.environ.get("BUSINFO_CATALOG", "AwsDataCatalog")
DEFAULT_DATABASE = os.environ.get("BUSINFO_DATABASE", "businfo")
DEFAULT_TABLE = os.environ.get("BUSINFO_TABLE", "businfo")
DEFAULT_WORKGROUP = os.environ.get("BUSINFO_WORKGROUP", "primary")

QUERY_POLL_INTERVAL_SEC = 0.5
QUERY_TIMEOUT_SEC = int(os.environ.get("BUSINFO_QUERY_TIMEOUT_SEC", "120"))

_athena = None
_glue = None
_s3 = None
_sts = None


def get_region() -> str:
    return DEFAULT_REGION


def get_account_id() -> str:
    global _sts
    if _sts is None:
        _sts = boto3.client("sts", region_name=get_region())
    return _sts.get_caller_identity()["Account"]


def default_output_location() -> str:
    env = os.environ.get("BUSINFO_OUTPUT_LOCATION")
    if env:
        return env.rstrip("/") + "/"
    account = get_account_id()
    region = get_region()
    return f"s3://aws-athena-query-results-{account}-{region}/"


def default_data_prefix() -> str:
    env = os.environ.get("BUSINFO_DATA_PREFIX")
    if env:
        return env.rstrip("/") + "/"
    account = get_account_id()
    region = get_region()
    return f"s3://businfo-{account}-{region}/businfo/"


def athena():
    global _athena
    if _athena is None:
        _athena = boto3.client("athena", region_name=get_region())
    return _athena


def glue():
    global _glue
    if _glue is None:
        _glue = boto3.client("glue", region_name=get_region())
    return _glue


def s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=get_region())
    return _s3


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    path = uri[5:]
    bucket, _, key = path.partition("/")
    return bucket, key


def wait_for_query(query_execution_id: str) -> dict:
    client = athena()
    deadline = time.time() + QUERY_TIMEOUT_SEC
    while time.time() < deadline:
        execution = client.get_query_execution(QueryExecutionId=query_execution_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state == "SUCCEEDED":
            return execution
        if state in ("FAILED", "CANCELLED"):
            reason = execution["Status"].get("StateChangeReason", state)
            raise RuntimeError(reason)
        time.sleep(QUERY_POLL_INTERVAL_SEC)
    raise TimeoutError(
        f"Athena query timed out after {QUERY_TIMEOUT_SEC}s "
        f"(QueryExecutionId={query_execution_id})"
    )


def fetch_query_results(query_execution_id: str) -> list[dict[str, str]]:
    client = athena()
    paginator = client.get_paginator("get_query_results")
    headers: Optional[list[str]] = None
    rows: list[dict[str, str]] = []
    for page in paginator.paginate(QueryExecutionId=query_execution_id):
        page_rows = page["ResultSet"]["Rows"]
        if not page_rows:
            continue
        if headers is None:
            headers = [c.get("VarCharValue", "") for c in page_rows[0]["Data"]]
            page_rows = page_rows[1:]
        for row in page_rows:
            values = [c.get("VarCharValue", "") for c in row["Data"]]
            rows.append(dict(zip(headers, values)))
    return rows


def run_sql(sql: str, database: str = DEFAULT_DATABASE) -> list[dict[str, str]]:
    response = athena().start_query_execution(
        QueryString=sql,
        QueryExecutionContext={
            "Database": database,
            "Catalog": DEFAULT_CATALOG,
        },
        ResultConfiguration={"OutputLocation": default_output_location()},
        WorkGroup=DEFAULT_WORKGROUP,
    )
    qid = response["QueryExecutionId"]
    logger.info("started Athena query %s", qid)
    wait_for_query(qid)
    return fetch_query_results(qid)


def list_hours_in_s3(day: date) -> list[str]:
    """Return hour folder names (00-23) present under businfo/YYYY/MM/DD/."""
    prefix_uri = default_data_prefix()
    bucket, base = parse_s3_uri(prefix_uri)
    day_prefix = f"{base}{day.year:04d}/{day.month:02d}/{day.day:02d}/"
    hours: list[str] = []
    token = None
    while True:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": day_prefix,
            "Delimiter": "/",
        }
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3().list_objects_v2(**kwargs)
        for cp in resp.get("CommonPrefixes", []):
            # e.g. businfo/2026/08/05/14/
            part = cp["Prefix"][len(day_prefix) :].strip("/")
            if part.isdigit() and len(part) == 2:
                hours.append(part)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return sorted(hours)


def ensure_partitions(day: date, hours: Optional[Iterable[str]] = None) -> list[str]:
    """Create missing Glue partitions for the given day/hours. Returns ensured hours."""
    if hours is None:
        hours = list_hours_in_s3(day)
    hours = list(hours)
    if not hours:
        logger.warning("no S3 hour prefixes for %s", day.isoformat())
        return []

    data_prefix = default_data_prefix()
    created: list[str] = []
    for hour in hours:
        values = [
            f"{day.year:04d}",
            f"{day.month:02d}",
            f"{day.day:02d}",
            hour,
        ]
        location = (
            f"{data_prefix}{values[0]}/{values[1]}/{values[2]}/{values[3]}/"
        )
        try:
            glue().create_partition(
                DatabaseName=DEFAULT_DATABASE,
                TableName=DEFAULT_TABLE,
                PartitionInput={
                    "Values": values,
                    "StorageDescriptor": {
                        "Location": location,
                        "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                        "OutputFormat": (
                            "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
                        ),
                        "SerdeInfo": {
                            "SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe"
                        },
                    },
                },
            )
            created.append(hour)
            logger.info("created partition %s", "/".join(values))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("AlreadyExistsException", "EntityAlreadyExistsException"):
                continue
            raise
    return hours


def partition_predicate(day: date, hours: Iterable[str]) -> str:
    hours = list(hours)
    hour_list = ", ".join(f"'{h}'" for h in hours)
    return (
        f"partition_0 = '{day.year:04d}' "
        f"AND partition_1 = '{day.month:02d}' "
        f"AND partition_2 = '{day.day:02d}' "
        f"AND partition_3 IN ({hour_list})"
    )


def resolve_day(day_str: Optional[str], tz: timezone = KST) -> date:
    if not day_str or day_str in ("today", "금일", "오늘"):
        return datetime.now(tz).date()
    if day_str in ("yesterday", "어제"):
        return datetime.now(tz).date() - timedelta(days=1)
    return date.fromisoformat(day_str)


def hours_for_last_n(n_hours: int, now: Optional[datetime] = None) -> dict[date, list[str]]:
    """Map UTC dates -> hour labels covering the last n hours."""
    now = now or datetime.now(timezone.utc)
    needed: dict[date, set[str]] = {}
    # include current hour and previous n hours
    for i in range(n_hours + 1):
        t = now - timedelta(hours=i)
        needed.setdefault(t.date(), set()).add(f"{t.hour:02d}")
    return {d: sorted(hs) for d, hs in sorted(needed.items())}


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def to_kst_str(utc_ts: str) -> str:
    """Convert Athena from_unixtime string to KST display."""
    if not utc_ts:
        return ""
    raw = utc_ts[:19]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return utc_ts


def print_table(rows: list[dict[str, str]], columns: Optional[list[str]] = None) -> None:
    if not rows:
        print("(no rows)")
        return
    cols = columns or list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, dict) and "rows" in data:
            meta = {k: v for k, v in data.items() if k != "rows"}
            if meta:
                for k, v in meta.items():
                    print(f"{k}: {v}")
                print()
            print_table(data["rows"])
        elif isinstance(data, list):
            print_table(data)
        else:
            print(data)
