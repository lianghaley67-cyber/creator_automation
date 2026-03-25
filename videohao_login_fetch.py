from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from shared import BASE_DIR, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="网站登录采集：手动登录视频号后台导出CSV，脚本自动接收并触发日报+文案生成"
    )
    parser.add_argument("--config", type=str, default=None, help="配置文件路径，默认 config.json")
    parser.add_argument("--login-url", type=str, default="", help="登录页面 URL（不填用配置）")
    parser.add_argument("--watch-dir", type=str, default="", help="监听下载目录（不填用配置）")
    parser.add_argument("--timeout-sec", type=int, default=900, help="等待导出 CSV 的超时时间，默认 900 秒")
    parser.add_argument(
        "--output-csv",
        type=str,
        default=str(BASE_DIR / "data" / "videohao_posts.csv"),
        help="采集到的 CSV 输出路径",
    )
    parser.add_argument("--days", type=int, default=3, help="跑日报统计最近 N 天，默认 3")
    parser.add_argument("--library-output", type=str, default="", help="新奇特脚本库输出路径")
    parser.add_argument("--mock", action="store_true", help="生成文案时使用 mock")
    parser.add_argument("--mock-on-quota", action="store_true", help="配额不足自动 mock")
    parser.add_argument("--skip-open", action="store_true", help="不自动打开浏览器")
    parser.add_argument(
        "--source-csv",
        type=str,
        default="",
        help="测试用：直接指定一个 CSV 作为采集结果（跳过登录等待）",
    )
    parser.add_argument(
        "--python-exe",
        type=str,
        default=sys.executable,
        help="调用 daily_monitor 脚本的 Python 路径",
    )
    parser.add_argument("--allow-demo-data", action="store_true", help="允许模板演示数据")
    return parser.parse_args()


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def newest_csv_after(folder: Path, start_ts: float, baseline: set[Path]) -> Path | None:
    candidates: list[Path] = []
    for p in folder.glob("*.csv"):
        if p in baseline:
            continue
        try:
            if p.stat().st_mtime >= start_ts:
                candidates.append(p)
        except OSError:
            continue
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]


def run_daily_monitor(
    python_exe: str,
    config_path: str | None,
    input_csv: Path,
    days: int,
    library_output: str,
    mock: bool,
    mock_on_quota: bool,
    allow_demo_data: bool,
) -> tuple[int, str]:
    cmd = [
        python_exe,
        "-X",
        "utf8",
        str((BASE_DIR / "videohao_daily_monitor.py").resolve()),
        "--input",
        str(input_csv.resolve()),
        "--days",
        str(days),
    ]
    if config_path:
        cmd.extend(["--config", config_path])
    if library_output.strip():
        cmd.extend(["--library-output", library_output.strip()])
    if mock:
        cmd.append("--mock")
    elif mock_on_quota:
        cmd.append("--mock-on-quota")
    if allow_demo_data:
        cmd.append("--allow-demo-data")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, output.strip()


def main() -> None:
    configure_console()
    args = parse_args()
    config = load_config(args.config)
    login_cfg = config.get("videohao_login", {})

    login_url = args.login_url.strip() or str(
        login_cfg.get("login_url", "https://channels.weixin.qq.com/platform")
    )
    watch_dir = Path(args.watch_dir.strip() or str(login_cfg.get("watch_dir", Path.home() / "Downloads"))).resolve()
    timeout_sec = int(args.timeout_sec or login_cfg.get("timeout_sec", 900))
    output_csv = Path(args.output_csv).resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if args.source_csv.strip():
        source_csv = Path(args.source_csv).resolve()
        if not source_csv.exists():
            raise FileNotFoundError(f"--source-csv 文件不存在: {source_csv}")
        shutil.copy2(source_csv, output_csv)
        print(f"[TEST] 已复制 CSV: {source_csv} -> {output_csv}")
    else:
        if not watch_dir.exists():
            raise FileNotFoundError(f"监听目录不存在: {watch_dir}")

        baseline = set(watch_dir.glob("*.csv"))
        start_ts = time.time()
        deadline = start_ts + timeout_sec

        if not args.skip_open:
            webbrowser.open(login_url)

        print("请在浏览器里完成以下步骤：")
        print("1) 登录视频号后台")
        print("2) 导出作品数据为 CSV")
        print(f"3) 确保 CSV 下载到目录：{watch_dir}")
        print(f"脚本正在监听新 CSV，最长等待 {timeout_sec} 秒...")

        found: Path | None = None
        while time.time() < deadline:
            found = newest_csv_after(watch_dir, start_ts, baseline)
            if found:
                break
            time.sleep(2)

        if not found:
            raise TimeoutError(
                "在等待时间内未检测到新 CSV。\n"
                "请确认已导出并下载到监听目录，或使用 --source-csv 手动指定文件。"
            )

        shutil.copy2(found, output_csv)
        print(f"已捕获新 CSV: {found}")
        print(f"已写入标准路径: {output_csv}")

    code, monitor_output = run_daily_monitor(
        python_exe=args.python_exe,
        config_path=args.config,
        input_csv=output_csv,
        days=args.days,
        library_output=args.library_output,
        mock=args.mock,
        mock_on_quota=args.mock_on_quota,
        allow_demo_data=args.allow_demo_data,
    )

    print("\n===== daily monitor 输出 =====")
    print(monitor_output)
    if code != 0:
        raise RuntimeError("videohao_daily_monitor 执行失败，请检查上方日志。")

    print(f"\n完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
