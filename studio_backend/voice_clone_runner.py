from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local XTTS voice cloning.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--reference-audio", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--language", default="zh-cn")
    parser.add_argument("--model-name", default="tts_models/multilingual/multi-dataset/xtts_v2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reference_audio = Path(args.reference_audio).expanduser()
    output_file = Path(args.output_file).expanduser()
    if not reference_audio.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_audio}")

    try:
        import torch
        from TTS.api import TTS
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("Coqui TTS is not installed in the voice clone runtime.") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    tts = TTS(model_name=args.model_name)
    if hasattr(tts, "to"):
        tts = tts.to(device)
    tts.tts_to_file(
        text=args.text,
        speaker_wav=str(reference_audio),
        language=args.language,
        file_path=str(output_file),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "device": device,
                "model_name": args.model_name,
                "output_file": str(output_file),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
