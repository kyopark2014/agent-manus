#!/usr/bin/env python3
"""
시스템 모니터링 스크립트
CPU / 메모리 / 디스크 / 네트워크 / 상위 프로세스 정보를 수집하고,
임계치를 초과하는 항목에 대해 경고를 표시합니다.

system-moni UX(진행 바·업타임·CPU 주파수·인터페이스별 네트워크)와
고급 CLI(임계치·JSON·리포트/그래프)를 융합한 버전입니다.

사용법:
    python3 monitor.py
    python3 monitor.py --json
    python3 monitor.py --top 10
    python3 monitor.py --cpu-threshold 80 --mem-threshold 80 --disk-threshold 85
    python3 monitor.py --report /path/to/out_dir
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime

try:
    import psutil
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
        import psutil
    except Exception:
        print("psutil 라이브러리가 필요합니다. 'pip install psutil' 로 설치해주세요.", file=sys.stderr)
        sys.exit(1)


def bytes_to_human(n: float) -> str:
    """바이트를 사람이 읽기 쉬운 단위(KB/MB/GB/TB)로 변환"""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} EB"


def usage_bar(percent: float, width: int = 20) -> str:
    """텍스트 진행 바. 예: [████████░░░░░░░░░░░░]"""
    filled = max(0, min(width, int(percent // (100 / width))))
    return "█" * filled + "░" * (width - filled)


def format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}일 {hours}시간 {minutes}분"
    return f"{hours}시간 {minutes}분"


def collect_system_info() -> dict:
    uname = platform.uname()
    boot_ts = psutil.boot_time()
    boot_time = datetime.fromtimestamp(boot_ts)
    uptime_sec = time.time() - boot_ts
    return {
        "hostname": socket.gethostname(),
        "os": f"{uname.system} {uname.release}",
        "kernel": uname.release,
        "architecture": uname.machine,
        "platform": platform.platform(),
        "boot_time": boot_time.isoformat(timespec="seconds"),
        "uptime_seconds": int(uptime_sec),
        "uptime": format_uptime(uptime_sec),
    }


def collect_cpu(interval: float = 1.0) -> dict:
    """CPU 사용률 수집. interval초 동안 측정해 순간 스파이크 왜곡을 줄인다."""
    per_cpu = psutil.cpu_percent(interval=interval, percpu=True)
    overall = sum(per_cpu) / len(per_cpu) if per_cpu else 0.0
    load_avg = None
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        pass

    freq_current = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            freq_current = round(freq.current, 1)
    except Exception:
        pass

    return {
        "overall_percent": round(overall, 1),
        "per_cpu_percent": [round(x, 1) for x in per_cpu],
        "core_count_logical": psutil.cpu_count(logical=True),
        "core_count_physical": psutil.cpu_count(logical=False),
        "frequency_mhz": freq_current,
        "load_avg_1_5_15": load_avg,
    }


def collect_memory() -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": vm.total,
        "available": vm.available,
        "used": vm.used,
        "percent": vm.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
    }


def collect_disk() -> list:
    """마운트된 파티션 사용량. 접근 불가능한 파티션은 건너뜀."""
    result = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        result.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })
    return result


def collect_network(interval: float = 1.0) -> dict:
    """전송률(초당) + 인터페이스별 누적 송수신량."""
    before = psutil.net_io_counters()
    pernic_before = psutil.net_io_counters(pernic=True)
    time.sleep(interval)
    after = psutil.net_io_counters()
    pernic_after = psutil.net_io_counters(pernic=True)

    interfaces = []
    for iface, stats in pernic_after.items():
        if stats.bytes_sent == 0 and stats.bytes_recv == 0:
            continue
        prev = pernic_before.get(iface)
        sent_rate = ((stats.bytes_sent - prev.bytes_sent) / interval) if prev else 0.0
        recv_rate = ((stats.bytes_recv - prev.bytes_recv) / interval) if prev else 0.0
        interfaces.append({
            "name": iface,
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "sent_rate_bytes_per_sec": round(sent_rate, 1),
            "recv_rate_bytes_per_sec": round(recv_rate, 1),
        })

    return {
        "bytes_sent_total": after.bytes_sent,
        "bytes_recv_total": after.bytes_recv,
        "sent_rate_bytes_per_sec": round((after.bytes_sent - before.bytes_sent) / interval, 1),
        "recv_rate_bytes_per_sec": round((after.bytes_recv - before.bytes_recv) / interval, 1),
        "interfaces": interfaces,
    }


def collect_top_processes(n: int = 10, by: str = "cpu") -> list:
    """CPU 또는 메모리 사용량 기준 상위 프로세스 n개.
    psutil cpu_percent는 첫 호출이 0이므로 초기화 후 재측정한다."""
    for p in psutil.process_iter(attrs=["pid", "name", "username"]):
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.3)

    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "username"]):
        try:
            info = p.info
            info["cpu_percent"] = round(p.cpu_percent(None), 1)
            info["memory_percent"] = round(p.memory_percent(), 2)
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    key = "cpu_percent" if by == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)
    return procs[:n]


def build_snapshot(top_n: int = 10, cpu_interval: float = 1.0, net_interval: float = 1.0) -> dict:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system": collect_system_info(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu": collect_cpu(interval=cpu_interval),
        "memory": collect_memory(),
        "disk": collect_disk(),
        "network": collect_network(interval=net_interval),
        "top_processes_cpu": collect_top_processes(n=top_n, by="cpu"),
        "top_processes_memory": collect_top_processes(n=top_n, by="memory"),
    }


def check_thresholds(snapshot: dict, cpu_th: float = 90.0, mem_th: float = 90.0, disk_th: float = 90.0) -> list:
    warnings = []
    cpu_pct = snapshot["cpu"]["overall_percent"]
    if cpu_pct >= cpu_th:
        warnings.append(f"⚠️ CPU 사용률이 {cpu_pct}% 로 임계치({cpu_th}%)를 초과했습니다.")

    mem_pct = snapshot["memory"]["percent"]
    if mem_pct >= mem_th:
        warnings.append(f"⚠️ 메모리 사용률이 {mem_pct}% 로 임계치({mem_th}%)를 초과했습니다.")

    for d in snapshot["disk"]:
        if d["percent"] >= disk_th:
            warnings.append(
                f"⚠️ 디스크({d['mountpoint']}) 사용률이 {d['percent']}% 로 임계치({disk_th}%)를 초과했습니다."
            )
    return warnings


def format_text_summary(snapshot: dict, warnings: list, top_n: int = 5) -> str:
    sysinfo = snapshot["system"]
    cpu = snapshot["cpu"]
    mem = snapshot["memory"]
    net = snapshot["network"]
    sep = "─" * 55

    lines = [
        "=" * 55,
        "  🖥️  시스템 현황 리포트",
        "=" * 55,
        f"  호스트명   : {sysinfo['hostname']}",
        f"  OS         : {sysinfo['os']}",
        f"  아키텍처   : {sysinfo['architecture']}",
        f"  부팅 시각  : {sysinfo['boot_time'].replace('T', ' ')}",
        f"  업타임     : {sysinfo['uptime']}",
        f"  조회 시각  : {snapshot['timestamp'].replace('T', ' ')}",
        "",
        sep,
        "  🔲  CPU",
        sep,
        f"  물리 코어  : {cpu['core_count_physical']}개  /  논리 코어: {cpu['core_count_logical']}개",
    ]

    if cpu.get("frequency_mhz"):
        lines.append(f"  현재 주파수: {cpu['frequency_mhz']:.0f} MHz")
    lines.append(f"  사용률     : [{usage_bar(cpu['overall_percent'])}] {cpu['overall_percent']:.1f}%")
    if cpu.get("load_avg_1_5_15"):
        la = cpu["load_avg_1_5_15"]
        lines.append(f"  Load Avg   : {la[0]:.2f} / {la[1]:.2f} / {la[2]:.2f}  (1/5/15분)")

    lines.extend([
        "",
        sep,
        "  💾  메모리 (RAM)",
        sep,
        f"  전체       : {bytes_to_human(mem['total'])}",
        f"  사용 중    : {bytes_to_human(mem['used'])}",
        f"  여유       : {bytes_to_human(mem['available'])}",
        f"  사용률     : [{usage_bar(mem['percent'])}] {mem['percent']:.1f}%",
    ])
    if mem["swap_total"] > 0:
        lines.append(
            f"  SWAP 사용  : {bytes_to_human(mem['swap_used'])} / {bytes_to_human(mem['swap_total'])} "
            f"({mem['swap_percent']:.1f}%)"
        )

    lines.extend(["", sep, "  💿  디스크", sep])
    for d in snapshot["disk"]:
        lines.append(
            f"  {d['mountpoint']:<12}: [{usage_bar(d['percent'])}] {d['percent']:.1f}%"
        )
        lines.append(
            f"    전체 {bytes_to_human(d['total'])}  사용 {bytes_to_human(d['used'])}  "
            f"여유 {bytes_to_human(d['free'])}"
        )

    lines.extend([
        "",
        sep,
        "  🌐  네트워크",
        sep,
        f"  전체 전송률: ↑ {bytes_to_human(net['sent_rate_bytes_per_sec'])}/s  "
        f"↓ {bytes_to_human(net['recv_rate_bytes_per_sec'])}/s",
        f"  누적       : ↑ {bytes_to_human(net['bytes_sent_total'])}  "
        f"↓ {bytes_to_human(net['bytes_recv_total'])}",
    ])
    for iface in net.get("interfaces", []):
        lines.append(
            f"  {iface['name']:<12}: ↑ {bytes_to_human(iface['bytes_sent'])}  "
            f"↓ {bytes_to_human(iface['bytes_recv'])}  "
            f"(↑{bytes_to_human(iface['sent_rate_bytes_per_sec'])}/s "
            f"↓{bytes_to_human(iface['recv_rate_bytes_per_sec'])}/s)"
        )

    lines.extend([
        "",
        sep,
        f"  📋  상위 프로세스 (CPU 기준 Top {top_n})",
        sep,
        f"  {'PID':<8} {'이름':<25} {'CPU%':>6} {'MEM%':>6}",
        f"  {'─'*8} {'─'*25} {'─'*6} {'─'*6}",
    ])
    for p in snapshot["top_processes_cpu"][:top_n]:
        lines.append(
            f"  {p['pid']:<8} {str(p.get('name') or 'N/A')[:25]:<25} "
            f"{p.get('cpu_percent', 0):>5.1f}% {p.get('memory_percent', 0):>5.1f}%"
        )

    lines.extend([
        "",
        sep,
        f"  📋  상위 프로세스 (메모리 기준 Top {top_n})",
        sep,
        f"  {'PID':<8} {'이름':<25} {'CPU%':>6} {'MEM%':>6}",
        f"  {'─'*8} {'─'*25} {'─'*6} {'─'*6}",
    ])
    for p in snapshot["top_processes_memory"][:top_n]:
        lines.append(
            f"  {p['pid']:<8} {str(p.get('name') or 'N/A')[:25]:<25} "
            f"{p.get('cpu_percent', 0):>5.1f}% {p.get('memory_percent', 0):>5.1f}%"
        )

    lines.extend(["", "=" * 55])
    if warnings:
        for w in warnings:
            lines.append(f"  {w}")
    else:
        lines.append("  ✅  모든 지표가 정상 범위입니다.")
    lines.append("=" * 55)
    return "\n".join(lines)


def write_markdown_report(snapshot: dict, warnings: list, out_path: str, top_n: int = 10, chart_path: str | None = None):
    sysinfo = snapshot["system"]
    cpu = snapshot["cpu"]
    mem = snapshot["memory"]
    net = snapshot["network"]

    md = [
        "# 시스템 모니터링 리포트",
        f"- 생성 시각: {snapshot['timestamp']}",
        f"- 호스트: {sysinfo['hostname']}",
        f"- OS: {sysinfo['os']} ({sysinfo['architecture']})",
        f"- 부팅 시각: {sysinfo['boot_time']}",
        f"- 업타임: {sysinfo['uptime']}",
        "",
        "## 요약",
    ]
    if warnings:
        md.extend(f"- {w}" for w in warnings)
    else:
        md.append("- ✅ 모든 지표가 정상 범위입니다.")
    md.append("")

    md.extend([
        "## CPU",
        f"- 전체 사용률: **{cpu['overall_percent']}%**",
        f"- 논리 코어: {cpu['core_count_logical']}개 / 물리 코어: {cpu['core_count_physical']}개",
    ])
    if cpu.get("frequency_mhz"):
        md.append(f"- 현재 주파수: {cpu['frequency_mhz']:.0f} MHz")
    if cpu.get("load_avg_1_5_15"):
        la = cpu["load_avg_1_5_15"]
        md.append(f"- Load Average (1/5/15분): {la[0]:.2f} / {la[1]:.2f} / {la[2]:.2f}")
    md.append("")

    md.extend([
        "## 메모리",
        f"- 사용률: **{mem['percent']}%** ({bytes_to_human(mem['used'])} / {bytes_to_human(mem['total'])})",
        f"- 여유: {bytes_to_human(mem['available'])}",
    ])
    if mem["swap_total"] > 0:
        md.append(
            f"- 스왑: {mem['swap_percent']}% ({bytes_to_human(mem['swap_used'])} / {bytes_to_human(mem['swap_total'])})"
        )
    md.append("")

    md.extend(["## 디스크", "| 마운트 | 사용률 | 사용 | 전체 | 여유 |", "|---|---|---|---|---|"])
    for d in snapshot["disk"]:
        md.append(
            f"| {d['mountpoint']} | {d['percent']}% | {bytes_to_human(d['used'])} | "
            f"{bytes_to_human(d['total'])} | {bytes_to_human(d['free'])} |"
        )
    md.append("")

    md.extend([
        "## 네트워크",
        f"- 송신 속도: {bytes_to_human(net['sent_rate_bytes_per_sec'])}/s",
        f"- 수신 속도: {bytes_to_human(net['recv_rate_bytes_per_sec'])}/s",
        f"- 누적 송신: {bytes_to_human(net['bytes_sent_total'])}",
        f"- 누적 수신: {bytes_to_human(net['bytes_recv_total'])}",
    ])
    if net.get("interfaces"):
        md.extend(["", "| 인터페이스 | 송신 | 수신 | 송신률 | 수신률 |", "|---|---|---|---|---|"])
        for iface in net["interfaces"]:
            md.append(
                f"| {iface['name']} | {bytes_to_human(iface['bytes_sent'])} | "
                f"{bytes_to_human(iface['bytes_recv'])} | "
                f"{bytes_to_human(iface['sent_rate_bytes_per_sec'])}/s | "
                f"{bytes_to_human(iface['recv_rate_bytes_per_sec'])}/s |"
            )
    md.append("")

    md.extend([
        f"## CPU 상위 프로세스 Top {top_n}",
        "| PID | 이름 | CPU% | MEM% |",
        "|---|---|---|---|",
    ])
    for p in snapshot["top_processes_cpu"][:top_n]:
        md.append(f"| {p['pid']} | {p.get('name')} | {p.get('cpu_percent', 0)} | {p.get('memory_percent', 0)} |")
    md.append("")

    md.extend([
        f"## 메모리 상위 프로세스 Top {top_n}",
        "| PID | 이름 | MEM% | CPU% |",
        "|---|---|---|---|",
    ])
    for p in snapshot["top_processes_memory"][:top_n]:
        md.append(f"| {p['pid']} | {p.get('name')} | {p.get('memory_percent', 0)} | {p.get('cpu_percent', 0)} |")

    if chart_path:
        md.extend(["", "## 그래프", f"![system chart]({chart_path})"])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def write_chart(snapshot: dict, out_path: str):
    """CPU/메모리/디스크 사용률을 간단한 막대그래프로 시각화"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    for font_name in ["AppleGothic", "Apple SD Gothic Neo", "Nanum Gothic", "Malgun Gothic", "NanumGothic"]:
        if any(f.name == font_name for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False

    # 그래프가 너무 길어지지 않도록 주요 마운트만 표시
    disks = snapshot["disk"][:6]
    labels = ["CPU", "메모리"] + [d["mountpoint"] for d in disks]
    values = [snapshot["cpu"]["overall_percent"], snapshot["memory"]["percent"]] + [d["percent"] for d in disks]
    colors = []
    for v in values:
        if v >= 90:
            colors.append("#e74c3c")
        elif v >= 70:
            colors.append("#f39c12")
        else:
            colors.append("#2ecc71")

    plt.figure(figsize=(max(6, len(labels) * 1.2), 4))
    bars = plt.bar(labels, values, color=colors)
    plt.ylim(0, 100)
    plt.ylabel("사용률 (%)")
    plt.title(f"시스템 리소스 사용률 - {snapshot['timestamp']}")
    for bar, v in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
    plt.axhline(90, color="red", linestyle="--", linewidth=0.8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="시스템 리소스 모니터링")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    parser.add_argument("--top", type=int, default=5, help="상위 프로세스 개수 (기본 5)")
    parser.add_argument("--cpu-threshold", type=float, default=90.0)
    parser.add_argument("--mem-threshold", type=float, default=90.0)
    parser.add_argument("--disk-threshold", type=float, default=90.0)
    parser.add_argument("--cpu-interval", type=float, default=1.0, help="CPU 측정 샘플링 시간(초)")
    parser.add_argument("--net-interval", type=float, default=1.0, help="네트워크 측정 샘플링 시간(초)")
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="지정한 디렉터리에 Markdown 리포트(.md)와 그래프(.png)를 생성",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(
        top_n=max(args.top, 10),
        cpu_interval=args.cpu_interval,
        net_interval=args.net_interval,
    )
    warnings = check_thresholds(
        snapshot,
        cpu_th=args.cpu_threshold,
        mem_th=args.mem_threshold,
        disk_th=args.disk_threshold,
    )

    if args.json:
        print(json.dumps({"snapshot": snapshot, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        print(format_text_summary(snapshot, warnings, top_n=args.top))

    if args.report:
        import os

        os.makedirs(args.report, exist_ok=True)
        ts = snapshot["timestamp"].replace(":", "-")
        chart_file = f"system_chart_{ts}.png"
        md_file = os.path.join(args.report, f"system_report_{ts}.md")
        chart_full_path = os.path.join(args.report, chart_file)
        try:
            write_chart(snapshot, chart_full_path)
            write_markdown_report(snapshot, warnings, md_file, top_n=max(args.top, 10), chart_path=chart_file)
        except ImportError:
            write_markdown_report(snapshot, warnings, md_file, top_n=max(args.top, 10), chart_path=None)
            print("\n⚠️ matplotlib이 없어 그래프는 생략하고 Markdown만 생성했습니다.", file=sys.stderr)
        print(f"\n📄 리포트 생성됨: {md_file}")


if __name__ == "__main__":
    main()
