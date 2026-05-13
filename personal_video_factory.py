from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = "data/style_profile.auto.json"
DEFAULT_SAMPLES_DIR = "data/style_samples"
DEFAULT_TOPICS_FILE = "data/daily_topics.txt"
DEFAULT_STATE_FILE = "data/daily_video_state.json"
DEFAULT_SCRIPT_CACHE_DIR = "data/generated_scripts"


@dataclass
class DistillStats:
    sample_count: int
    avg_chars: int
    avg_sentence_len: float
    hooks: list[str]
    ctas: list[str]
    signature_terms: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distill personal speaking style and generate one daily talking-head video."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    distill = subparsers.add_parser("distill", help="Build style profile from historical scripts.")
    distill.add_argument("--samples-dir", default=DEFAULT_SAMPLES_DIR, help="Folder with txt/md scripts.")
    distill.add_argument("--output-profile", default=DEFAULT_PROFILE_PATH, help="Output profile path.")
    distill.add_argument("--top-k", type=int, default=12, help="Top repeated elements to keep.")

    generate = subparsers.add_parser("generate", help="Generate one daily video from style profile.")
    generate.add_argument("--profile", default=DEFAULT_PROFILE_PATH, help="Style profile json path.")
    generate.add_argument("--topic", default="", help="Explicit topic for this run.")
    generate.add_argument("--topics-file", default=DEFAULT_TOPICS_FILE, help="Topic list file.")
    generate.add_argument("--state-file", default=DEFAULT_STATE_FILE, help="Topic rotation state file.")
    generate.add_argument("--seconds", type=int, default=60, help="Target script duration.")
    generate.add_argument("--provider", choices=["openai", "elevenlabs"], default="elevenlabs")
    generate.add_argument("--voice-authorized", action="store_true")
    generate.add_argument("--env-file", default=".env")
    generate.add_argument("--output-dir", default="outputs/ai_voice_video")
    generate.add_argument("--script-cache-dir", default=DEFAULT_SCRIPT_CACHE_DIR)
    generate.add_argument("--background-image", default="")
    generate.add_argument("--bg-color", default="#111827")
    generate.add_argument("--size", default="1080x1920")
    generate.add_argument("--fps", type=int, default=30)
    generate.add_argument("--line-chars", type=int, default=18)
    generate.add_argument("--force-next-topic", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode: {path}")


def clean_script(raw: str) -> str:
    text = raw.replace("\r", "")
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`{3}[\s\S]*?`{3}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?;\u3002\uff01\uff1f\uff1b])\s*", normalized)
    return [p.strip() for p in parts if p.strip()]


def collect_scripts(samples_dir: Path) -> list[tuple[Path, str]]:
    if not samples_dir.exists():
        raise FileNotFoundError(f"Samples folder not found: {samples_dir}")

    files: list[Path] = []
    for pattern in ("*.txt", "*.md"):
        files.extend(samples_dir.glob(pattern))
    files = sorted(files)

    data: list[tuple[Path, str]] = []
    for file_path in files:
        content = clean_script(read_text(file_path))
        if content:
            data.append((file_path, content))
    if not data:
        raise ValueError(f"No non-empty .txt/.md samples found in: {samples_dir}")
    return data


def extract_terms(text: str) -> list[str]:
    # Keeps both CJK and latin tokens.
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,10}", text)
    stop_tokens = {
        "this",
        "that",
        "with",
        "from",
        "you",
        "your",
        "and",
        "the",
        "for",
        "is",
        "are",
        "was",
        "were",
        "have",
        "has",
        "will",
        "just",
        "then",
    }
    result: list[str] = []
    for w in words:
        token = w.lower()
        if token in stop_tokens:
            continue
        result.append(w)
    return result


def distill_stats(scripts: list[str], top_k: int) -> DistillStats:
    hook_counter: Counter[str] = Counter()
    cta_counter: Counter[str] = Counter()
    term_counter: Counter[str] = Counter()
    char_counts: list[int] = []
    sentence_lengths: list[int] = []

    for script in scripts:
        compact = re.sub(r"\s+", "", script)
        if compact:
            char_counts.append(len(compact))

        sentences = split_sentences(script)
        if not sentences:
            continue
        hook_counter[sentences[0]] += 1
        cta_counter[sentences[-1]] += 1
        sentence_lengths.extend(len(re.sub(r"\s+", "", s)) for s in sentences)
        term_counter.update(extract_terms(script))

    avg_chars = int(sum(char_counts) / len(char_counts)) if char_counts else 0
    avg_sentence_len = (sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0
    hooks = [h for h, _ in hook_counter.most_common(top_k)]
    ctas = [c for c, _ in cta_counter.most_common(top_k)]
    terms = [t for t, _ in term_counter.most_common(top_k * 2)]
    return DistillStats(
        sample_count=len(scripts),
        avg_chars=avg_chars,
        avg_sentence_len=round(avg_sentence_len, 2),
        hooks=hooks,
        ctas=ctas,
        signature_terms=terms,
    )


def build_prompt_block(profile: dict[str, Any]) -> str:
    hooks = profile.get("hook_candidates", [])[:4]
    ctas = profile.get("cta_candidates", [])[:4]
    terms = profile.get("signature_terms", [])[:10]
    lines = [
        "Use spoken Chinese with short punchy sentences.",
        f"Keep total length around {profile.get('recommended_chars_60s', 240)} chars for 60s.",
        "Structure: hook -> insight -> action -> CTA.",
    ]
    if hooks:
        lines.append("Hook examples: " + " | ".join(hooks))
    if ctas:
        lines.append("CTA examples: " + " | ".join(ctas))
    if terms:
        lines.append("Frequent terms: " + ", ".join(terms))
    return "\n".join(lines)


def distill_command(args: argparse.Namespace) -> int:
    samples_dir = Path(args.samples_dir).expanduser().resolve()
    output_path = Path(args.output_profile).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pairs = collect_scripts(samples_dir)
    scripts = [content for _, content in pairs]
    stats = distill_stats(scripts, top_k=args.top_k)

    profile: dict[str, Any] = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(samples_dir),
        "sample_count": stats.sample_count,
        "recommended_chars_60s": max(stats.avg_chars, 180),
        "avg_sentence_len": stats.avg_sentence_len,
        "hook_candidates": stats.hooks
        or [
            "\u4f60\u662f\u4e0d\u662f\u4e5f\u9047\u5230\u8fd9\u4e2a\u95ee\u9898\uff1f",
            "\u5f88\u591a\u4eba\u4ee5\u4e3a\u8fd9\u662f\u80fd\u529b\u95ee\u9898\uff0c\u5176\u5b9e\u662f\u7ed3\u6784\u95ee\u9898\u3002",
        ],
        "cta_candidates": stats.ctas
        or [
            "\u5982\u679c\u4f60\u8981\u6a21\u677f\uff0c\u8bc4\u8bba\u533a\u6253\u6a21\u677f\u3002",
            "\u5173\u6ce8\u6211\uff0c\u4e0b\u4e00\u6761\u6211\u7ed9\u4f60\u62c6\u5b9e\u64cd\u3002",
        ],
        "signature_terms": stats.signature_terms,
        "style_rules": [
            "Use direct and practical language.",
            "Start with a sharp hook in the first sentence.",
            "Keep each sentence short for easy one-take recording.",
            "End with a clear CTA.",
        ],
        "script_blueprint": ["hook", "pain", "insight", "action", "cta"],
        "prompt_block": "",
    }
    profile["prompt_block"] = build_prompt_block(profile)
    output_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Distilled profile saved: {output_path}")
    print(f"Samples used: {stats.sample_count}")
    print(f"Recommended chars for 60s: {profile['recommended_chars_60s']}")
    return 0


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Style profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_topics(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Topics file not found: {path}")
    topics: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        topics.append(t)
    if not topics:
        raise ValueError(f"No topics found in: {path}")
    return topics


def choose_topic(topic: str, topics_file: Path, state_file: Path, force_next: bool) -> tuple[str, int]:
    if topic.strip():
        return topic.strip(), -1

    topics = read_topics(topics_file)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    state: dict[str, Any] = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}

    last_date = str(state.get("last_date", ""))
    last_index = int(state.get("last_index", -1))
    last_topic = str(state.get("last_topic", ""))
    if not force_next and last_date == today and last_topic:
        return last_topic, last_index

    next_index = (last_index + 1) % len(topics)
    chosen = topics[next_index]
    state = {
        "last_date": today,
        "last_index": next_index,
        "last_topic": chosen,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return chosen, next_index


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def render_template_line(template: str, topic: str) -> str:
    if "{topic}" in template:
        return template.format(topic=topic)
    if topic not in template:
        return f"{template} {topic}"
    return template


def build_script(topic: str, profile: dict[str, Any], seconds: int) -> str:
    random.seed(int(datetime.now().strftime("%Y%m%d")))

    hooks = profile.get("hook_candidates") or [
        "\u4f60\u662f\u4e0d\u662f\u4e5f\u5728\u8fd9\u4ef6\u4e8b\u4e0a\u53cd\u590d\u5361\u4f4f\uff1f",
        "\u5f88\u591a\u4eba\u4ee5\u4e3a\u8fd9\u662f\u5929\u8d4b\u95ee\u9898\uff0c\u5176\u5b9e\u662f\u65b9\u6cd5\u95ee\u9898\u3002",
    ]
    ctas = profile.get("cta_candidates") or [
        "\u5982\u679c\u4f60\u8981\u6211\u7684\u6a21\u677f\uff0c\u8bc4\u8bba\u533a\u6253\u6a21\u677f\u3002",
        "\u5173\u6ce8\u6211\uff0c\u4e0b\u4e00\u6761\u6211\u628a\u6b65\u9aa4\u62c6\u7ed9\u4f60\u3002",
    ]
    terms = profile.get("signature_terms") or ["\u7ed3\u6784", "\u590d\u76d8", "\u7a33\u5b9a\u8f93\u51fa", "\u6267\u884c"]

    hook = render_template_line(random.choice(hooks), topic)
    cta = random.choice(ctas)
    insight_terms = "\u3001".join(terms[:4]) if terms else "\u7ed3\u6784\u3001\u8282\u594f\u3001\u6267\u884c"

    if contains_cjk(topic):
        structure = (
            "\u5f00\u573a\u94a9\u5b50 -> \u6838\u5fc3\u89c2\u70b9 -> "
            "\u4e00\u4e2a\u52a8\u4f5c -> \u7ed3\u5c3e\u5f15\u5bfc"
        )
        action = (
            f"\u4eca\u5929\u4f60\u53ea\u505a\u4e00\u6b65\uff1a\u56f4\u7ed5\u201c{topic}\u201d"
            "\u5199\u4e09\u53e5\uff0c\u5206\u522b\u662f\u89c2\u70b9\u3001\u6848\u4f8b\u3001\u884c\u52a8\uff0c\u7136\u540e\u76f4\u63a5\u5f00\u5f55\u3002"
        )
        body = [
            f"\u5f88\u591a\u4eba\u5728\u505a{topic}\u65f6\uff0c\u95ee\u9898\u4e0d\u662f\u4e0d\u52aa\u529b\uff0c"
            "\u800c\u662f\u8868\u8fbe\u6ca1\u6709\u56fa\u5b9a\u7ed3\u6784\u3002",
            f"\u4f60\u5148\u8bb0\u4f4f\u8fd9\u6761\u9aa8\u67b6\uff1a{structure}\u3002"
            "\u6bcf\u6b21\u90fd\u6309\u8fd9\u4e2a\u987a\u5e8f\u8bf4\uff0c\u7a33\u5b9a\u6027\u4f1a\u660e\u663e\u63d0\u5347\u3002",
            f"\u6211\u81ea\u5df1\u7684\u7ecf\u9a8c\u662f\uff0c\u53ea\u8981\u628a{insight_terms}"
            "\u8fd9\u51e0\u4e2a\u70b9\u56fa\u5b9a\u4f4f\uff0c\u5185\u5bb9\u5c31\u66f4\u5bb9\u6613\u6301\u7eed\u4ea7\u51fa\u3002",
            action,
            cta,
        ]
    else:
        structure = "hook -> core point -> one action -> CTA"
        action = (
            f"Today do one thing only: for '{topic}', write three lines: point, example, and action, then record now."
        )
        body = [
            f"Most people fail at {topic} not because of effort, but because the expression has no repeatable structure.",
            f"Use this structure every time: {structure}. Consistency improves immediately.",
            f"My own lesson: when {insight_terms} stay fixed, output becomes stable.",
            action,
            cta,
        ]

    lines = [hook] + body
    script = "\n".join(lines)
    target_chars = max(int(seconds * 3.8), 160)
    compact_len = len(re.sub(r"\s+", "", script))

    if compact_len < int(target_chars * 0.85):
        if contains_cjk(topic):
            addon = (
                "\u5f55\u5b8c\u4e4b\u540e\u4e0d\u8981\u7ea0\u7ed3\uff0c\u5148\u53d1\u4e00\u6761\uff0c"
                "\u518d\u6839\u636e\u5b8c\u64ad\u548c\u8bc4\u8bba\u53bb\u590d\u76d8\u3002"
            )
        else:
            addon = "Do not overthink after recording. Publish first, then improve with retention and comments."
        script = script + "\n" + addon
    elif compact_len > int(target_chars * 1.25):
        script = "\n".join(lines[:5])
    return script


def write_script_cache(script: str, topic: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    token = re.sub(r"[^a-zA-Z0-9]+", "-", topic).strip("-").lower() or "topic"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = cache_dir / f"{stamp}_{token[:40]}.txt"
    path.write_text(script, encoding="utf-8")
    return path


def run_video_generator(args: argparse.Namespace, script_file: Path) -> int:
    tool_path = Path(__file__).resolve().parent / "ai_voice_video_generator.py"
    if not tool_path.exists():
        raise FileNotFoundError(f"Missing dependency: {tool_path}")

    cmd = [
        sys.executable,
        str(tool_path),
        "--env-file",
        args.env_file,
        "--script-file",
        str(script_file),
        "--provider",
        args.provider,
        "--output-dir",
        args.output_dir,
        "--bg-color",
        args.bg_color,
        "--size",
        args.size,
        "--fps",
        str(args.fps),
        "--line-chars",
        str(args.line_chars),
    ]
    if args.background_image:
        cmd.extend(["--background-image", args.background_image])
    if args.provider == "elevenlabs":
        if not args.voice_authorized:
            raise ValueError("For cloned voice, pass --voice-authorized.")
        cmd.append("--voice-authorized")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def generate_command(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile).expanduser().resolve()
    topics_path = Path(args.topics_file).expanduser().resolve()
    state_path = Path(args.state_file).expanduser().resolve()
    cache_dir = Path(args.script_cache_dir).expanduser().resolve()

    profile = load_profile(profile_path)
    topic, topic_index = choose_topic(
        topic=args.topic,
        topics_file=topics_path,
        state_file=state_path,
        force_next=args.force_next_topic,
    )
    script = build_script(topic=topic, profile=profile, seconds=args.seconds)
    script_path = write_script_cache(script=script, topic=topic, cache_dir=cache_dir)

    print(f"Topic: {topic}")
    if topic_index >= 0:
        print(f"Topic index: {topic_index}")
    print(f"Script file: {script_path}")

    rc = run_video_generator(args, script_file=script_path)
    if rc != 0:
        return rc
    print("Daily video generated successfully.")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "distill":
        return distill_command(args)
    if args.command == "generate":
        return generate_command(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
