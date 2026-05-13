from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO_DIR = BASE_DIR / "tools" / "digital_human" / "SadTalker"
DEFAULT_ENV_PYTHON = BASE_DIR / "tools" / "digital_human" / "envs" / "sadtalker" / "python.exe"
LEGACY_ENV_PYTHON = BASE_DIR / "tools" / "digital_human" / "envs" / "sadtalker" / "Scripts" / "python.exe"
RUNNER_SCRIPT = BASE_DIR / "studio_backend" / "sadtalker_runner.py"
STALL_TIMEOUT_ENV_KEY = "SADTALKER_STALL_TIMEOUT_SECONDS"
DEFAULT_STALL_TIMEOUT_SECONDS = 5 * 60


def _positive_int_from_env(name: str, default: int) -> int:
    raw_value = str(os.getenv(name, "")).strip()
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


STALL_TIMEOUT_SECONDS = _positive_int_from_env(STALL_TIMEOUT_ENV_KEY, DEFAULT_STALL_TIMEOUT_SECONDS)


def _resolve_media_binary(name: str) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct
    ffmpeg_root = BASE_DIR / "tools" / "ffmpeg"
    if not ffmpeg_root.exists():
        return None
    exe_name = f"{name}.exe" if os.name == "nt" else name
    for build_dir in sorted(ffmpeg_root.glob("*"), reverse=True):
        candidate = build_dir / "bin" / exe_name
        if candidate.exists():
            return str(candidate)
    return None


def _target_long_edge_from_resolution(value: str) -> int:
    token = str(value or "").strip().lower()
    mapping = {
        "source": 0,
        "native": 0,
        "720p": 1280,
        "1080p": 1920,
        "1440p": 2560,
        "2k": 2560,
    }
    return int(mapping.get(token, 1920))


def _probe_video_dimensions(video_file: Path, ffprobe_exe: str | None) -> tuple[int, int]:
    if not ffprobe_exe:
        return 0, 0
    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        str(video_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return 0, 0
    payload = result.stdout.strip()
    if "x" not in payload:
        return 0, 0
    width_text, height_text = payload.split("x", 1)
    try:
        return int(width_text), int(height_text)
    except ValueError:
        return 0, 0


def _scaled_size(width: int, height: int, target_long_edge: int) -> tuple[int, int]:
    if width <= 0 or height <= 0 or target_long_edge <= 0:
        return 0, 0
    current_long = max(width, height)
    if current_long >= target_long_edge:
        return width, height
    scale = target_long_edge / float(current_long)
    scaled_width = max(int(round(width * scale)), 2)
    scaled_height = max(int(round(height * scale)), 2)
    if scaled_width % 2:
        scaled_width += 1
    if scaled_height % 2:
        scaled_height += 1
    return scaled_width, scaled_height


def _reencode_for_browser_preview(
    source_file: Path,
    output_file: Path,
    *,
    ffmpeg_exe: str | None,
    ffprobe_exe: str | None,
    output_resolution: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> tuple[bool, str]:
    if not ffmpeg_exe:
        shutil.copyfile(source_file, output_file)
        return False, "ffmpeg unavailable, used raw SadTalker mp4 (preview compatibility may vary by browser)."

    if progress_callback:
        progress_callback(96, "Optimizing output codec for browser preview")

    target_long_edge = _target_long_edge_from_resolution(output_resolution)
    source_width, source_height = _probe_video_dimensions(source_file, ffprobe_exe)
    scale_width, scale_height = _scaled_size(source_width, source_height, target_long_edge)
    if scale_width and scale_height and (scale_width != source_width or scale_height != source_height):
        video_filter = f"scale={scale_width}:{scale_height}:flags=lanczos"
        upscale_note = f"Upscaled to {scale_width}x{scale_height}."
    else:
        video_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        upscale_note = ""

    temp_output = output_file.with_name(f"{output_file.stem}.h264.mp4")
    if temp_output.exists():
        temp_output.unlink()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source_file),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(temp_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not temp_output.exists():
        temp_output.unlink(missing_ok=True)
        shutil.copyfile(source_file, output_file)
        stderr_tail = "\n".join(result.stderr.splitlines()[-10:])
        fallback_reason = stderr_tail or "ffmpeg re-encode failed"
        return False, f"Used raw SadTalker mp4 because browser re-encode failed: {fallback_reason}"

    shutil.move(str(temp_output), str(output_file))
    return True, upscale_note


def _preferred_python_path(value: Any) -> Path:
    text = str(value or "").strip()
    if text:
        candidate = Path(text).expanduser()
        if candidate.exists():
            return candidate
        if candidate.name.lower() == "python.exe" and candidate.parent.name.lower() == "scripts":
            root_candidate = candidate.parent.parent / "python.exe"
            if root_candidate.exists():
                return root_candidate
        return candidate
    if DEFAULT_ENV_PYTHON.exists():
        return DEFAULT_ENV_PYTHON
    if LEGACY_ENV_PYTHON.exists():
        return LEGACY_ENV_PYTHON
    return DEFAULT_ENV_PYTHON


def default_sadtalker_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "repo_dir": str(DEFAULT_REPO_DIR),
        "python_exe": str(DEFAULT_ENV_PYTHON),
        "checkpoint_dir": str(DEFAULT_REPO_DIR / "checkpoints"),
        "source_image": "",
        "ref_eyeblink": "",
        "ref_pose": "",
        "preprocess": "full",
        "enhancer": "gfpgan",
        "background_enhancer": "",
        "still_mode": True,
        "pose_style": 0,
        "expression_scale": 1.0,
        "size": 512,
        "batch_size": 2,
        "use_cpu": False,
        "notes": "",
    }


def normalize_sadtalker_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = default_sadtalker_config()
    if config:
        merged.update(config)
    merged["python_exe"] = str(_preferred_python_path(merged.get("python_exe")))
    return merged


def detect_sadtalker_status(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = normalize_sadtalker_config(config)
    repo_dir = Path(cfg["repo_dir"]).expanduser()
    python_exe = _preferred_python_path(cfg.get("python_exe"))
    checkpoint_dir = Path(cfg["checkpoint_dir"]).expanduser() if cfg.get("checkpoint_dir") else repo_dir / "checkpoints"
    source_image_text = _string(cfg.get("source_image"))
    source_image = Path(source_image_text).expanduser() if source_image_text else None
    inference_file = repo_dir / "src" / "gradio_demo.py"
    config_dir = repo_dir / "src" / "config"
    checkpoints_found = []
    if checkpoint_dir.exists():
        checkpoints_found = [str(item.relative_to(checkpoint_dir)) for item in checkpoint_dir.rglob("*") if item.is_file()]

    return {
        "enabled": bool(cfg.get("enabled")),
        "repo_exists": repo_dir.exists(),
        "inference_exists": inference_file.exists(),
        "runner_exists": RUNNER_SCRIPT.exists(),
        "config_exists": config_dir.exists(),
        "python_exists": python_exe.exists() if python_exe else False,
        "checkpoints_exist": checkpoint_dir.exists(),
        "checkpoint_file_count": len(checkpoints_found),
        "default_source_exists": source_image.exists() if source_image is not None else False,
        "repo_dir": str(repo_dir),
        "python_exe": str(python_exe) if python_exe else "",
        "checkpoint_dir": str(checkpoint_dir),
    }


def _string(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def build_sadtalker_command(
    config: dict[str, Any] | None,
    *,
    audio_file: Path,
    result_dir: Path,
    request_payload: dict[str, Any],
) -> tuple[list[str], Path]:
    cfg = normalize_sadtalker_config(config)
    repo_dir = Path(_string(cfg["repo_dir"])).expanduser().resolve()
    python_text = _string(cfg.get("python_exe"))
    python_exe = _preferred_python_path(python_text)
    checkpoint_text = _string(cfg.get("checkpoint_dir"))
    checkpoint_dir = Path(checkpoint_text).expanduser() if checkpoint_text else repo_dir / "checkpoints"
    source_image = _string(request_payload.get("portrait_path")) or _string(cfg.get("source_image"))
    ref_eyeblink = _string(request_payload.get("ref_eyeblink")) or _string(cfg.get("ref_eyeblink"))
    ref_pose = _string(request_payload.get("ref_pose")) or _string(cfg.get("ref_pose"))
    preprocess = _string(request_payload.get("avatar_preprocess")) or _string(cfg.get("preprocess")) or "full"
    request_enhancer = _string(request_payload.get("avatar_enhancer"))
    enhancer = request_enhancer or _string(cfg.get("enhancer"))
    background_enhancer = _string(request_payload.get("avatar_background_enhancer")) or _string(cfg.get("background_enhancer"))
    still_mode = bool(request_payload.get("avatar_still_mode", cfg.get("still_mode", True)))
    pose_style = int(request_payload.get("avatar_pose_style", cfg.get("pose_style", 0)) or 0)
    expression_scale = float(request_payload.get("avatar_expression_scale", cfg.get("expression_scale", 1.0)) or 1.0)
    request_size = request_payload.get("avatar_size")
    size = int(request_size or cfg.get("size", 512) or 512)
    batch_size = int(cfg.get("batch_size", 2) or 2)
    use_cpu = bool(request_payload.get("avatar_use_cpu", cfg.get("use_cpu", False)))

    # CPU rendering can easily stall a consumer laptop. When the user has not
    # explicitly overridden these knobs, use a lighter configuration.
    if use_cpu:
        batch_size = 1
        if not request_size:
            size = min(size, 256)
        if not request_enhancer:
            enhancer = ""

    if not repo_dir.exists():
        raise RuntimeError(f"SadTalker repo not found: {repo_dir}")
    if not (repo_dir / "src" / "gradio_demo.py").exists():
        raise RuntimeError(f"SadTalker runtime entry not found: {repo_dir / 'src' / 'gradio_demo.py'}")
    if not RUNNER_SCRIPT.exists():
        raise RuntimeError(f"SadTalker runner not found: {RUNNER_SCRIPT}")
    if not python_exe.exists():
        raise RuntimeError(
            "SadTalker Python runtime not found. Configure python_exe in the SadTalker settings first."
        )
    if not source_image:
        raise RuntimeError("SadTalker needs a portrait_path or a configured default source_image.")
    source_image_path = Path(source_image).expanduser()
    if not source_image_path.exists():
        raise RuntimeError(f"SadTalker source image not found: {source_image_path}")

    result_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(python_exe),
        str(RUNNER_SCRIPT),
        "--repo-dir",
        str(repo_dir),
        "--checkpoint-dir",
        str(checkpoint_dir),
        "--source-image",
        str(source_image_path),
        "--driven_audio",
        str(audio_file),
        "--result-dir",
        str(result_dir),
        "--preprocess",
        preprocess,
        "--pose-style",
        str(pose_style),
        "--expression-scale",
        f"{expression_scale:.2f}",
        "--size",
        str(size),
        "--batch-size",
        str(batch_size),
    ]
    if still_mode:
        cmd.append("--still")
    if enhancer:
        cmd.extend(["--enhancer", enhancer])
    if background_enhancer:
        cmd.extend(["--background_enhancer", background_enhancer])
    if ref_eyeblink:
        cmd.extend(["--ref_eyeblink", ref_eyeblink])
    if ref_pose:
        cmd.extend(["--ref_pose", ref_pose])
    if use_cpu:
        cmd.append("--cpu")
    return cmd, repo_dir


def run_sadtalker(
    config: dict[str, Any] | None,
    *,
    audio_file: Path,
    output_file: Path,
    request_payload: dict[str, Any],
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    result_dir = output_file.parent / "sadtalker_outputs"
    cmd, repo_dir = build_sadtalker_command(
        config,
        audio_file=audio_file,
        result_dir=result_dir,
        request_payload=request_payload,
    )
    env = os.environ.copy()
    ffmpeg_exe = _resolve_media_binary("ffmpeg")
    ffprobe_exe = _resolve_media_binary("ffprobe")
    if ffmpeg_exe:
        ffmpeg_dir = Path(ffmpeg_exe).parent
        env["PATH"] = str(ffmpeg_dir) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    stdout_log = result_dir / "_runner_stdout.log"
    stderr_log = result_dir / "_runner_stderr.log"
    result_dir.mkdir(parents=True, exist_ok=True)

    def is_temp_work_path(candidate: Path) -> bool:
        try:
            relative_parts = candidate.resolve().relative_to(result_dir.resolve()).parts
        except ValueError:
            return False
        return any(part.startswith("codex-sadtalker-") for part in relative_parts[:-1])

    def pick_best_video() -> Path | None:
        candidates = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
        for candidate in candidates:
            name = candidate.name.lower()
            if name.startswith("temp_"):
                continue
            if is_temp_work_path(candidate):
                continue
            if candidate.resolve() == output_file.resolve():
                continue
            return candidate
        return None

    def latest_activity_timestamp() -> float:
        latest = 0.0
        for candidate in result_dir.rglob("*"):
            try:
                latest = max(latest, candidate.stat().st_mtime)
            except (FileNotFoundError, PermissionError, OSError):
                continue
        return latest

    with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            cmd,
            cwd=str(repo_dir),
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        rescued = False
        stable_video: Path | None = None
        stable_size = -1
        stable_count = 0
        render_started_at = time.time()
        last_heartbeat = 0.0
        last_activity = time.time()

        while True:
            return_code = process.poll()
            loop_now = time.time()
            newest_activity = latest_activity_timestamp()
            if newest_activity:
                last_activity = max(last_activity, newest_activity)
            candidate = pick_best_video()
            if candidate and candidate.exists():
                current_size = int(candidate.stat().st_size)
                if stable_video and candidate.resolve() == stable_video.resolve() and current_size == stable_size:
                    stable_count += 1
                else:
                    stable_video = candidate
                    stable_size = current_size
                    stable_count = 0

                if return_code is None and stable_count >= 2:
                    rescued = True
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                    break

            if return_code is not None:
                break
            if progress_callback and (loop_now - last_heartbeat) >= 12:
                elapsed = int(loop_now - render_started_at)
                progress = min(95, 78 + max(1, elapsed // 25))
                progress_callback(progress, f"SadTalker rendering... {elapsed}s elapsed")
                last_heartbeat = loop_now
            stalled_for = loop_now - last_activity
            if stalled_for > STALL_TIMEOUT_SECONDS:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                timeout_minutes = max(1, STALL_TIMEOUT_SECONDS // 60)
                stalled_seconds = int(stalled_for)
                raise RuntimeError(
                    f"SadTalker render stalled for about {stalled_seconds}s without new output "
                    f"(timeout {timeout_minutes} min). "
                    f"If your device is slower, increase {STALL_TIMEOUT_ENV_KEY} and restart backend."
                )
            time.sleep(4)

    stdout_text = stdout_log.read_text(encoding="utf-8", errors="replace")
    stderr_text = stderr_log.read_text(encoding="utf-8", errors="replace")
    if process.returncode != 0 and not rescued:
        stderr_tail = "\n".join(stderr_text.splitlines()[-40:])
        stdout_tail = "\n".join(stdout_text.splitlines()[-20:])
        details = stderr_tail or stdout_tail or "SadTalker inference failed."
        raise RuntimeError(details)

    payload: dict[str, Any] = {}
    for line in reversed(stdout_text.splitlines()):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
            break
        except json.JSONDecodeError:
            continue

    produced: Path | None = None
    produced_text = str(payload.get("video_path", "")).strip()
    if produced_text:
        candidate = Path(produced_text).expanduser()
        if candidate.exists() and candidate.is_file():
            produced = candidate

    if produced is None:
        for line in reversed(stdout_text.splitlines()):
            text = line.strip()
            if "The generated video is named " in text:
                raw_path = text.split("The generated video is named ", 1)[1].strip()
                candidate = Path(raw_path).expanduser()
                if candidate.exists() and candidate.is_file():
                    produced = candidate
                    break

    if produced is None:
        rescued_candidate = pick_best_video()
        if not rescued_candidate:
            raise RuntimeError("SadTalker did not produce an mp4 output.")
        produced = rescued_candidate

    reencoded, reencode_warning = _reencode_for_browser_preview(
        produced,
        output_file,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
        output_resolution=_string(request_payload.get("output_resolution")),
        progress_callback=progress_callback,
    )
    return {
        "provider": "sadtalker",
        "raw_video_path": str(produced),
        "video_preview_codec": "h264" if reencoded else "raw",
        "command": cmd,
        "warning": " ".join(
            item
            for item in [
                str(payload.get("warning", "")).strip(),
                "SadTalker output was recovered before the runner fully exited." if rescued else "",
                reencode_warning,
            ]
            if item
        ).strip(),
    }
