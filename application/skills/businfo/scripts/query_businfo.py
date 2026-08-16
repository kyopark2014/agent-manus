#!/usr/bin/env python3
"""
Bus arrival / remaining-seat query CLI via Amazon Athena (AwsDataCatalog.businfo).

Examples:
  python query_businfo.py recent --hours 1
  python query_businfo.py plate 경기74아3798 --day today
  python query_businfo.py route 222000076 --day today
  python query_businfo.py summary --day today
  python query_businfo.py sql "SELECT COUNT(*) AS cnt FROM businfo LIMIT 1"
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python scripts/query_businfo.py` without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lib_athena as ath  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("businfo")


def _ensure_days(day_hours: dict) -> None:
    for day, hours in day_hours.items():
        # Prefer S3-present hours; fall back to requested set
        present = ath.list_hours_in_s3(day)
        target = sorted(set(hours) & set(present)) if present else hours
        if not target and present:
            target = present
        ath.ensure_partitions(day, target or hours)


def cmd_recent(args: argparse.Namespace) -> int:
    day_hours = ath.hours_for_last_n(args.hours)
    _ensure_days(day_hours)

    preds = []
    for day, hours in day_hours.items():
        if hours:
            preds.append(f"({ath.partition_predicate(day, hours)})")
    if not preds:
        print("ERROR: no partitions available for the requested window", file=sys.stderr)
        return 1

    cutoff = int(datetime.now(timezone.utc).timestamp()) - args.hours * 3600
    where = " OR ".join(preds)
    sql = f"""
SELECT
  timestamp,
  from_unixtime(CAST(timestamp AS bigint)) AS ts_utc,
  routeid,
  remainseatcnt,
  plateno,
  predicttime
FROM {ath.DEFAULT_TABLE}
WHERE ({where})
  AND CAST(timestamp AS bigint) >= {cutoff}
ORDER BY CAST(timestamp AS bigint) DESC
LIMIT {args.limit}
""".strip()

    rows = ath.run_sql(sql)
    for r in rows:
        r["ts_kst"] = ath.to_kst_str(r.get("ts_utc", ""))

    payload = {
        "query": "recent",
        "hours": args.hours,
        "cutoff_epoch": cutoff,
        "count": len(rows),
        "rows": [
            {
                "ts_kst": r["ts_kst"],
                "routeid": r.get("routeid", ""),
                "remainseatcnt": r.get("remainseatcnt", ""),
                "plateno": r.get("plateno", ""),
                "predicttime": r.get("predicttime", ""),
            }
            for r in rows
        ],
    }
    ath.emit(payload, args.json)
    return 0


def cmd_plate(args: argparse.Namespace) -> int:
    day = ath.resolve_day(args.day)
    hours = ath.list_hours_in_s3(day)
    if not hours:
        print(f"ERROR: no S3 data for {day.isoformat()}", file=sys.stderr)
        return 1
    ath.ensure_partitions(day, hours)

    plate = ath.sql_escape(args.plateno)
    pred = ath.partition_predicate(day, hours)
    sql = f"""
WITH base AS (
  SELECT
    CAST(timestamp AS bigint) AS ts,
    from_unixtime(CAST(timestamp AS bigint)) AS ts_utc,
    CAST(remainseatcnt AS integer) AS seats,
    routeid,
    predicttime
  FROM {ath.DEFAULT_TABLE}
  WHERE {pred}
    AND plateno = '{plate}'
)
SELECT
  CAST(ts_utc AS varchar) AS ts_utc,
  CAST(seats AS varchar) AS remainseatcnt,
  routeid,
  predicttime
FROM base
ORDER BY ts
LIMIT {args.limit}
""".strip()

    rows = ath.run_sql(sql)
    for r in rows:
        r["ts_kst"] = ath.to_kst_str(r.get("ts_utc", ""))

    seats = [int(r["remainseatcnt"]) for r in rows if r.get("remainseatcnt", "").isdigit()]
    summary = {
        "plateno": args.plateno,
        "day": day.isoformat(),
        "count": len(rows),
        "min_seats": min(seats) if seats else None,
        "max_seats": max(seats) if seats else None,
        "avg_seats": round(sum(seats) / len(seats), 1) if seats else None,
    }

    # hourly rollup
    hourly_sql = f"""
SELECT
  date_format(from_unixtime(CAST(timestamp AS bigint)), '%Y-%m-%d %H:00') AS hour_utc,
  CAST(COUNT(*) AS varchar) AS cnt,
  CAST(MIN(CAST(remainseatcnt AS integer)) AS varchar) AS min_seats,
  CAST(MAX(CAST(remainseatcnt AS integer)) AS varchar) AS max_seats,
  CAST(AVG(CAST(remainseatcnt AS integer)) AS varchar) AS avg_seats
FROM {ath.DEFAULT_TABLE}
WHERE {pred}
  AND plateno = '{plate}'
GROUP BY 1
ORDER BY 1
""".strip()
    hourly = ath.run_sql(hourly_sql)
    for h in hourly:
        h["hour_kst"] = ath.to_kst_str(h.get("hour_utc", "") + ":00")[:16] + ":00"

    payload = {
        "query": "plate",
        **summary,
        "hourly": [
            {
                "hour_kst": h["hour_kst"],
                "cnt": h.get("cnt", ""),
                "min_seats": h.get("min_seats", ""),
                "max_seats": h.get("max_seats", ""),
                "avg_seats": h.get("avg_seats", ""),
            }
            for h in hourly
        ],
        "rows": [
            {
                "ts_kst": r["ts_kst"],
                "remainseatcnt": r.get("remainseatcnt", ""),
                "routeid": r.get("routeid", ""),
                "predicttime": r.get("predicttime", ""),
            }
            for r in rows
        ],
    }

    if args.json:
        ath.emit(payload, True)
    else:
        print(f"차량번호: {summary['plateno']}")
        print(f"날짜: {summary['day']} (KST 기준 일자)")
        print(
            f"관측: {summary['count']}건 | "
            f"잔여좌석 min={summary['min_seats']} max={summary['max_seats']} "
            f"avg={summary['avg_seats']}"
        )
        print("\n=== 시간대별 ===")
        ath.print_table(
            payload["hourly"],
            ["hour_kst", "cnt", "min_seats", "max_seats", "avg_seats"],
        )
        print("\n=== 상세 ===")
        ath.print_table(
            payload["rows"],
            ["ts_kst", "remainseatcnt", "routeid", "predicttime"],
        )
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    day = ath.resolve_day(args.day)
    hours = ath.list_hours_in_s3(day)
    if not hours:
        print(f"ERROR: no S3 data for {day.isoformat()}", file=sys.stderr)
        return 1
    ath.ensure_partitions(day, hours)

    route = ath.sql_escape(args.routeid)
    pred = ath.partition_predicate(day, hours)
    sql = f"""
SELECT
  from_unixtime(CAST(timestamp AS bigint)) AS ts_utc,
  plateno,
  remainseatcnt,
  predicttime
FROM {ath.DEFAULT_TABLE}
WHERE {pred}
  AND routeid = '{route}'
ORDER BY CAST(timestamp AS bigint) DESC
LIMIT {args.limit}
""".strip()
    rows = ath.run_sql(sql)
    for r in rows:
        r["ts_kst"] = ath.to_kst_str(r.get("ts_utc", ""))

    payload = {
        "query": "route",
        "routeid": args.routeid,
        "day": day.isoformat(),
        "count": len(rows),
        "rows": [
            {
                "ts_kst": r["ts_kst"],
                "plateno": r.get("plateno", ""),
                "remainseatcnt": r.get("remainseatcnt", ""),
                "predicttime": r.get("predicttime", ""),
            }
            for r in rows
        ],
    }
    ath.emit(payload, args.json)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    day = ath.resolve_day(args.day)
    hours = ath.list_hours_in_s3(day)
    if not hours:
        print(f"ERROR: no S3 data for {day.isoformat()}", file=sys.stderr)
        return 1
    ath.ensure_partitions(day, hours)
    pred = ath.partition_predicate(day, hours)

    sql = f"""
SELECT
  CAST(COUNT(*) AS varchar) AS cnt,
  CAST(COUNT(DISTINCT routeid) AS varchar) AS routes,
  CAST(COUNT(DISTINCT plateno) AS varchar) AS plates,
  CAST(MIN(from_unixtime(CAST(timestamp AS bigint))) AS varchar) AS min_ts_utc,
  CAST(MAX(from_unixtime(CAST(timestamp AS bigint))) AS varchar) AS max_ts_utc,
  CAST(AVG(CAST(remainseatcnt AS integer)) AS varchar) AS avg_seats
FROM {ath.DEFAULT_TABLE}
WHERE {pred}
""".strip()
    rows = ath.run_sql(sql)
    row = rows[0] if rows else {}
    avg_raw = row.get("avg_seats", "")
    try:
        avg_disp = f"{float(avg_raw):.1f}" if avg_raw else ""
    except ValueError:
        avg_disp = avg_raw
    payload = {
        "query": "summary",
        "day": day.isoformat(),
        "hours_covered": hours,
        "count": row.get("cnt", "0"),
        "routes": row.get("routes", "0"),
        "plates": row.get("plates", "0"),
        "avg_seats": avg_disp,
        "min_ts_kst": ath.to_kst_str(row.get("min_ts_utc", "")),
        "max_ts_kst": ath.to_kst_str(row.get("max_ts_utc", "")),
    }
    if args.json:
        ath.emit(payload, True)
    else:
        print(f"날짜: {payload['day']}")
        print(f"파티션 시간(UTC): {', '.join(hours)}")
        print(f"건수: {payload['count']} | 노선: {payload['routes']} | 차량: {payload['plates']}")
        print(f"평균 잔여좌석: {payload['avg_seats']}")
        print(f"기간(KST): {payload['min_ts_kst']} ~ {payload['max_ts_kst']}")
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    sql = args.sql.strip().rstrip(";")
    upper = sql.lstrip().upper()
    if not upper.startswith(("SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN")):
        print("ERROR: only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN are allowed", file=sys.stderr)
        return 1
    rows = ath.run_sql(sql)
    ath.emit({"query": "sql", "count": len(rows), "rows": rows}, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Query businfo via Amazon Athena (AwsDataCatalog)"
    )
    p.add_argument("--json", action="store_true", help="Emit JSON")
    sub = p.add_subparsers(dest="command", required=True)

    recent = sub.add_parser("recent", help="Last N hours of bus arrivals")
    recent.add_argument("--hours", type=int, default=1)
    recent.add_argument("--limit", type=int, default=100)
    recent.set_defaults(func=cmd_recent)

    plate = sub.add_parser("plate", help="Remaining seats for a plate number")
    plate.add_argument("plateno", help="Vehicle plate, e.g. 경기74아3798")
    plate.add_argument("--day", default="today", help="YYYY-MM-DD | today | yesterday")
    plate.add_argument("--limit", type=int, default=500)
    plate.set_defaults(func=cmd_plate)

    route = sub.add_parser("route", help="Arrivals for a route id")
    route.add_argument("routeid", help="Route id, e.g. 222000076")
    route.add_argument("--day", default="today")
    route.add_argument("--limit", type=int, default=200)
    route.set_defaults(func=cmd_route)

    summary = sub.add_parser("summary", help="Daily aggregate summary")
    summary.add_argument("--day", default="today")
    summary.set_defaults(func=cmd_summary)

    raw = sub.add_parser("sql", help="Run a read-only SQL against businfo DB")
    raw.add_argument("sql", help="SELECT/WITH SQL string")
    raw.set_defaults(func=cmd_sql)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI surface
        logger.exception("query failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
