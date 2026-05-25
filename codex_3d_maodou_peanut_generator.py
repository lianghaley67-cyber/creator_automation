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
    parser = argparse.ArgumentParser(description="生成职场妈妈/AI 提效 IP 动画或口播短视频")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="后端 API 地址")
    parser.add_argument("--workspace", default=".", help="项目根目录，用于自动启动后端")
    parser.add_argument("--auto-start-backend", action="store_true", help="后端未启动时自动拉起")
    parser.add_argument("--python-exe", default="", help="指定启动后端的 Python")
    parser.add_argument("--topic", default="今天送娃迟到被老板点名，心里很憋屈", help="视频主题")
    parser.add_argument(
        "--content-mode",
        choices=["working_mom", "creator_tips", "ai_growth"],
        default="working_mom",
        help="内容类型：working_mom=职场妈妈痛点，creator_tips=剪辑提效，ai_growth=AI职业重塑",
    )
    parser.add_argument("--learning-goal", default="把真实经历转成高共情、可落地的 AI 提效方案", help="内容目标")
    parser.add_argument("--seconds", type=int, default=45, help="目标时长，30-60 秒")
    parser.add_argument("--script-source", choices=["auto", "manual"], default="auto", help="文案来源")
    parser.add_argument("--manual-script-file", default="", help="手动文案 txt 文件")
    parser.add_argument("--prompt-hint", default="痛点钩子，结尾评论区互动", help="爆款角度/互动提示")
    parser.add_argument("--edge-voice", default="zh-CN-XiaoxiaoNeural", help="Edge TTS 中文声音")
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
    if args.content_mode == "creator_tips":
        return "\n".join(
            [
                f"如果你也卡在《{args.topic}》这种剪辑现场，先别急着熬夜硬扛。",
                "我以前也以为效率低是自己不够努力，后来发现是流程太散。",
                f"这条视频我只解决一件事：{args.learning_goal}。",
                f"我的切入角度是：{args.prompt_hint}。",
                "第一步，把素材按情绪、观点、动作三类丢给 AI 先分组。",
                "第二步，只保留最能推动完播的三个镜头，别让素材绑架你。",
                "第三步，标题和花字先用模板跑一版，再人工改出你的个人语气。",
                "你最耗时间的是剪辑哪一步？评论区丢给我，我帮你拆流程。",
            ]
        )
    return "\n".join(
        [
            f"如果你也经历过《{args.topic}》，先别急着怪自己。",
            "我当时也很憋屈，甚至觉得努力像被按了静音键。",
            f"但我后来发现，这件事真正要解决的是：{args.learning_goal}。",
            f"我的补充角度是：{args.prompt_hint}。",
            "第一步，我先把情绪写下来，不让它继续消耗我。",
            "第二步，我用 AI 把混乱的事拆成三个能执行的小动作。",
            "第三步，我只保留今天最重要的一件事，其他都交给流程。",
            "你有没有类似的瞬间？评论区留一句，我帮你拆一个工作流。",
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
        "animation_style": "videohao_real_person",
        "use_my_real_voice": True,
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
        print("\n--- 当前 IP 文案 ---")
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
