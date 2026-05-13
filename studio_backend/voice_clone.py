from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import ai_voice_video_generator as avvg  # noqa: E402


DEFAULT_TOOL_DIR = ROOT_DIR / "tools" / "voice_clone"
DEFAULT_EXECUTABLE = DEFAULT_TOOL_DIR / "voice_clone_simple-vad_cpu_windows_x86-64.exe"
DEFAULT_MODEL_DIR = DEFAULT_TOOL_DIR / "checkpoints_v2" / "converter"
DEFAULT_WORK_DIR = DEFAULT_TOOL_DIR / "work"


def _resolve_executable(value: str = "") -> Path:
    text = str(value or "").strip()
    if text:
        return Path(text).expanduser()
    return DEFAULT_EXECUTABLE


def _resolve_model_dir(value: str = "") -> Path:
    text = str(value or "").strip()
    if text:
        return Path(text).expanduser()
    return DEFAULT_MODEL_DIR


def _relative_to_tool_dir(path: Path) -> str:
    try:
        return path.resolve().relative_to(DEFAULT_TOOL_DIR.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def detect_local_voice_clone_status(
    *,
    executable: str = "",
    model_dir: str = "",
) -> dict[str, Any]:
    exe_path = _resolve_executable(executable)
    model_path = _resolve_model_dir(model_dir)
    config_file = model_path / "config.json"
    checkpoint_files = [item for item in model_path.glob("*.pth") if item.is_file()]
    return {
        "executable": str(exe_path),
        "model_dir": str(model_path),
        "executable_exists": exe_path.exists(),
        "model_exists": model_path.exists(),
        "config_exists": config_file.exists(),
        "checkpoint_count": len(checkpoint_files),
    }


def convert_with_local_voice_clone(
    *,
    source_audio: Path,
    reference_audio: Path,
    output_file: Path,
    executable: str = "",
    model_dir: str = "",
) -> dict[str, Any]:
    exe_path = _resolve_executable(executable)
    model_path = _resolve_model_dir(model_dir)
    source_audio = Path(source_audio).expanduser()
    reference_audio = Path(reference_audio).expanduser()
    output_file = Path(output_file).expanduser()

    if not exe_path.exists():
        raise RuntimeError(f"Local voice clone executable not found: {exe_path}")
    if not model_path.exists():
        raise RuntimeError(f"Local voice clone model directory not found: {model_path}")
    if not source_audio.exists():
        raise RuntimeError(f"Base speech audio not found: {source_audio}")
    if not reference_audio.exists():
        raise RuntimeError(f"Voice reference audio not found: {reference_audio}")

    DEFAULT_WORK_DIR.mkdir(parents=True, exist_ok=True)
    session_name = f"run_{uuid.uuid4().hex[:10]}"
    session_dir = DEFAULT_WORK_DIR / session_name
    session_dir.mkdir(parents=True, exist_ok=True)
    result_dir = session_dir / "result"
    result_dir.mkdir(parents=True, exist_ok=True)

    source_copy = session_dir / f"source{source_audio.suffix.lower() or '.mp3'}"
    reference_copy = session_dir / f"reference{reference_audio.suffix.lower() or '.wav'}"
    shutil.copyfile(source_audio, source_copy)
    shutil.copyfile(reference_audio, reference_copy)

    result_name = "cloned.wav"
    result_wav = result_dir / result_name
    source_arg = _relative_to_tool_dir(source_copy)
    target_arg = _relative_to_tool_dir(reference_copy)
    output_arg = _relative_to_tool_dir(result_dir)
    model_arg = _relative_to_tool_dir(model_path)

    command = [
        str(exe_path),
        "-s",
        source_arg,
        "-t",
        target_arg,
        "-o",
        output_arg,
        "-n",
        result_name,
        "-m",
        model_arg,
        "-T",
        "0",
    ]

    result = subprocess.run(
        command,
        cwd=str(DEFAULT_TOOL_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-30:])
        stdout_tail = "\n".join(result.stdout.splitlines()[-20:])
        details = stderr_tail or stdout_tail or "Local voice clone failed."
        raise RuntimeError(f"{details}\nWorkspace: {session_dir}")

    if not result_wav.exists():
        candidates = sorted(result_dir.glob("*.wav"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            raise RuntimeError(f"Local voice clone produced no wav output. Workspace: {session_dir}")
        result_wav = candidates[0]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)
    avvg.convert_audio_file(result_wav, output_file)
    shutil.rmtree(session_dir, ignore_errors=True)
    return {
        "provider": "local_clone",
        "output_file": str(output_file),
        "source_audio": str(source_audio),
        "reference_audio": str(reference_audio),
        "executable": str(exe_path),
        "model_dir": str(model_path),
    }
