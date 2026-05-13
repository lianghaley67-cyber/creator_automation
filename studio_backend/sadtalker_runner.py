from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex SadTalker runner")
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--driven_audio", required=True)
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--preprocess", default="full")
    parser.add_argument("--pose-style", type=int, default=0)
    parser.add_argument("--expression-scale", type=float, default=1.0)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--enhancer", default="")
    parser.add_argument("--background_enhancer", default="")
    parser.add_argument("--ref_eyeblink", default="")
    parser.add_argument("--ref_pose", default="")
    parser.add_argument("--still", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def _resolve_ref_video(args: argparse.Namespace, work_dir: Path) -> tuple[bool, str | None, str | None, str]:
    pose = str(args.ref_pose or "").strip()
    blink = str(args.ref_eyeblink or "").strip()
    if not pose and not blink:
        return False, None, None, ""

    warning = ""
    chosen = pose or blink
    ref_info = "pose" if pose else "blink"

    if pose and blink:
        pose_path = Path(pose).expanduser().resolve()
        blink_path = Path(blink).expanduser().resolve()
        if pose_path == blink_path:
            chosen = str(pose_path)
            ref_info = "pose+blink"
        else:
            chosen = str(pose_path)
            ref_info = "pose"
            warning = "SadTalker runner currently supports only one reference video; ref_pose was used."

    chosen_path = Path(chosen).expanduser().resolve()
    if not chosen_path.exists():
        raise FileNotFoundError(f"Reference video not found: {chosen_path}")

    ref_copy = work_dir / chosen_path.name
    shutil.copy2(chosen_path, ref_copy)
    return True, str(ref_copy), ref_info, warning


def main() -> int:
    args = _parse_args()
    repo_dir = Path(args.repo_dir).expanduser().resolve()
    checkpoint_dir = Path(args.checkpoint_dir).expanduser().resolve()
    source_image = Path(args.source_image).expanduser().resolve()
    driven_audio = Path(args.driven_audio).expanduser().resolve()
    result_dir = Path(args.result_dir).expanduser().resolve()
    config_dir = repo_dir / "src" / "config"

    if args.cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["PYTHONIOENCODING"] = "utf-8"

    if not repo_dir.exists():
        raise FileNotFoundError(f"SadTalker repo not found: {repo_dir}")
    if not checkpoint_dir.exists():
        raise FileNotFoundError(f"SadTalker checkpoints not found: {checkpoint_dir}")
    if not config_dir.exists():
        raise FileNotFoundError(f"SadTalker config dir not found: {config_dir}")
    if not source_image.exists():
        raise FileNotFoundError(f"Source image not found: {source_image}")
    if not driven_audio.exists():
        raise FileNotFoundError(f"Driven audio not found: {driven_audio}")

    sys.path.insert(0, str(repo_dir))
    from src.gradio_demo import SadTalker

    result_dir.mkdir(parents=True, exist_ok=True)

    warning_parts: list[str] = []
    if str(args.background_enhancer or "").strip():
        warning_parts.append("SadTalker runner does not support background_enhancer yet; the option was ignored.")

    with tempfile.TemporaryDirectory(prefix="codex-sadtalker-", dir=str(result_dir)) as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        source_copy = temp_dir / source_image.name
        audio_copy = temp_dir / driven_audio.name
        shutil.copy2(source_image, source_copy)
        shutil.copy2(driven_audio, audio_copy)

        use_ref_video, ref_video, ref_info, ref_warning = _resolve_ref_video(args, temp_dir)
        if ref_warning:
            warning_parts.append(ref_warning)

        model = SadTalker(
            checkpoint_path=str(checkpoint_dir),
            config_path=str(config_dir),
        )
        video_path = model.test(
            source_image=str(source_copy),
            driven_audio=str(audio_copy),
            preprocess=str(args.preprocess or "full"),
            still_mode=bool(args.still),
            use_enhancer=bool(str(args.enhancer or "").strip()),
            batch_size=max(int(args.batch_size or 1), 1),
            size=int(args.size or 512),
            pose_style=int(args.pose_style or 0),
            exp_scale=float(args.expression_scale or 1.0),
            use_ref_video=use_ref_video,
            ref_video=ref_video,
            ref_info=ref_info,
            result_dir=str(result_dir),
        )

    payload = {
        "video_path": str(Path(video_path).expanduser().resolve()),
        "warning": " ".join(item for item in warning_parts if item).strip(),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
