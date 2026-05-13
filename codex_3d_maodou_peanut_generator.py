from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 3-6 岁科普/益智早教 3D 动画短视频")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="后端 API 地址")
    parser.add_argument("--workspace", default=".", help="项目根目录，用于自动启动后端")
    parser.add_argument("--auto-start-backend", action="store_true", help="后端未启动时自动拉起")
    parser.add_argument("--python-exe", default="", help="指定启动后端的 Python")
    parser.add_argument("--topic", default="为什么小种子会发芽", help="视频主题")
    parser.add_argument(
        "--content-mode",
        choices=["science", "early_learning"],
        default="science",
        help="内容类型：science=科普动画，early_learning=益智早教",
    )
    parser.add_argument("--learning-goal", default="认识种子发芽需要水、阳光和耐心", help="3-6 岁学习目标")
    parser.add_argument("--seconds", type=int, default=45, help="目标时长，30-60 秒")
    parser.add_argument("--script-source", choices=["auto", "manual"], default="auto", help="文案来源")
    parser.add_argument("--manual-script-file", default="", help="手动文案 txt 文件")
    parser.add_argument("--prompt-hint", default="请你找一找小芽在哪里，再数一数叶子", help="互动提示")
    parser.add_argument("--edge-voice", default="zh-CN-XiaoyiNeural", help="Edge TTS 中文童声")
    parser.add_argument("--auto-approve", action="store_true", help="不进入确认，直接提交生成")
    parser.add_argument("--run-once", action="store_true", help="生成一次后退出")
    return parser.parse_args()


class StudioApiClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = request.Request(f"{self.api_base}{path}", data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"接口失败 HTTP {exc.code}: {path}\n{detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"无法连接后端：{self.api_base}{path} ({exc})") from exc
        return json.loads(raw)

    def health(self) -> bool:
        return self.request_json("GET", "/api/health", timeout=5).get("status") == "ok"

    def create_kids_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/api/kids/generate", payload=payload, timeout=60)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/api/jobs/{job_id}", timeout=20)


def clamp_seconds(seconds: int) -> int:
    return max(30, min(60, int(seconds or 45)))


def read_text_file(path_text: str) -> str:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"文案文件不存在：{path}")
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码文案文件：{path}")


def read_multiline_script() -> str:
    print("\n请输入文案，单独输入 END 结束：")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line.rstrip())
    return "\n".join(line for line in lines if line.strip()).strip()


def build_child_script(args: argparse.Namespace) -> str:
    if args.content_mode == "early_learning":
        return "\n".join(
            [
                f"毛豆和花生对你挥手：今天玩《{args.topic}》。",
                "花生问：你能找到画面里的小线索吗？",
                f"毛豆说：我们要练习{args.learning_goal}。",
                f"毛豆举起小牌子：{args.prompt_hint}。",
                "花生带你慢慢数：一个、两个、三个。",
                "他们一起比一比，找出一样和不一样。",
                "最后毛豆和花生说：你学会了，真棒！",
            ]
        )
    return "\n".join(
        [
            f"毛豆和花生跑到草地上：今天认识《{args.topic}》。",
            "花生眨眨眼问：你知道它为什么会这样吗？",
            f"毛豆拿出放大镜：我们只学一个小知识，{args.learning_goal}。",
            f"毛豆靠近镜头说：{args.prompt_hint}。",
            "他们一起看一看，发现颜色、形状和位置的变化。",
            "花生惊讶地说：原来仔细观察，答案就更清楚了！",
            "最后一起复习：先观察，再思考，你又学会一个小知识！",
        ]
    )


def ensure_backend_ready(
    client: StudioApiClient,
    *,
    workspace: Path,
    auto_start_backend: bool,
    python_exe: str,
) -> subprocess.Popen[str] | None:
    try:
        if client.health():
            return None
    except Exception:
        pass

    if not auto_start_backend:
        raise RuntimeError("后端未启动。请先运行 run_creator_studio_backend.ps1，或加 --auto-start-backend。")

    exe = python_exe.strip() or sys.executable
    env = dict(os.environ)
    env["CREATOR_STUDIO_DATA_DIR"] = str((workspace / "studio_runtime").resolve())
    print("后端未连接，正在自动启动...")
    proc = subprocess.Popen(
        [exe, "-m", "uvicorn", "studio_backend.app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(workspace),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    for _ in range(45):
        time.sleep(1)
        try:
            if client.health():
                print("后端已启动。")
                return proc
        except Exception:
            continue
    raise RuntimeError("自动启动后端失败，请手动启动后重试。")


def build_payload(args: argparse.Namespace, script_text: str) -> dict[str, Any]:
    return {
        "topic": args.topic,
        "content_mode": args.content_mode,
        "learning_goal": args.learning_goal,
        "seconds": clamp_seconds(args.seconds),
        "prompt_hint": args.prompt_hint,
        "custom_script": script_text,
        "uploaded_image_path": "",
        "auto_generate_image": False,
        "edge_voice": args.edge_voice,
        "animation_style": "cartoon_3d_duo_cinematic",
    }


def wait_for_job(client: StudioApiClient, job_id: str, max_wait_sec: int = 1800) -> dict[str, Any]:
    start = time.time()
    last_message = ""
    while True:
        job = client.get_job(job_id)
        status = str(job.get("status", "")).lower()
        message = f"{job.get('progress_percent', 0)}% {job.get('progress_stage', '')} {job.get('progress_message', '')}"
        if message != last_message:
            print(f"[进度] {message}")
            last_message = message
        if status in {"completed", "failed"}:
            return job
        if time.time() - start > max_wait_sec:
            raise TimeoutError(f"任务超时：{job_id}")
        time.sleep(4)


def print_result(job: dict[str, Any], api_base: str) -> None:
    artifacts = dict(job.get("artifacts") or {})
    output_dir = str(job.get("output_dir", "")).strip()
    video_url = str(artifacts.get("video_url", "")).strip()
    print("\n生成完成。")
    if output_dir:
        print(f"本地目录：{output_dir}")
        print(f"本地视频：{Path(output_dir) / 'final_video.mp4'}")
    if video_url:
        print(f"前端预览：{api_base.rstrip('/')}{video_url}")


def choose_script(args: argparse.Namespace) -> str:
    if args.script_source == "manual":
        if args.manual_script_file:
            return read_text_file(args.manual_script_file)
        return read_multiline_script()
    return build_child_script(args)


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    client = StudioApiClient(args.api_base)
    ensure_backend_ready(
        client,
        workspace=workspace,
        auto_start_backend=args.auto_start_backend,
        python_exe=args.python_exe,
    )

    while True:
        script_text = choose_script(args)
        if not script_text:
            raise ValueError("文案为空，无法生成。")
        print("\n--- 当前 3-6 岁文案 ---")
        print(script_text)
        print("-" * 72)
        if not args.auto_approve:
            answer = input("输入 Y 提交生成，输入 R 重新录入/生成，其他键退出：").strip().lower()
            if answer == "r":
                continue
            if answer != "y":
                return 0

        job = client.create_kids_job(build_payload(args, script_text))
        job_id = str(job.get("id", "")).strip()
        if not job_id:
            raise RuntimeError(f"任务创建失败：{job}")
        print(f"任务已提交：{job_id}")
        final_job = wait_for_job(client, job_id)
        if str(final_job.get("status", "")).lower() != "completed":
            raise RuntimeError(f"渲染失败：{final_job.get('error', 'unknown error')}")
        print_result(final_job, args.api_base)

        if args.run_once:
            return 0
        if input("\n继续生成下一条？输入 Y 继续：").strip().lower() != "y":
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已取消。")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n执行失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
