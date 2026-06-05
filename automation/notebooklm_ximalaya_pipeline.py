from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STUDIO_URL = "http://43.156.8.162/"
DEFAULT_NOTEBOOKLM_URL = "https://notebooklm.google.com/notebook/8a28b3eb-d0f4-44a2-a57b-3d9b437a8f37"
DEFAULT_XIMALAYA_UPLOAD_URL = "https://www.ximalaya.com/anchor-center/upload"
DEFAULT_SKILL_PATH = Path("C:/Users/HP/AppData/Local/hermes/skills/domain/jianghushuo-perspective/SKILL.md")
RUN_DIR = ROOT_DIR / "studio_runtime" / "notebooklm_ximalaya"
PROFILE_DIR = ROOT_DIR / "studio_runtime" / "browser_profiles" / "notebooklm_ximalaya"


def _read_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _json_request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 90) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _text_request(url: str, *, timeout: int = 90) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _base_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _absolute_url(base: str, maybe_url: str) -> str:
    value = str(maybe_url or "").strip()
    if value.startswith(("http://", "https://")):
        return value
    return f"{_base_url(base)}/{value.lstrip('/')}"


def _set_clipboard(text: str) -> bool:
    system = platform.system().lower()
    try:
        if system == "windows":
            subprocess.run("clip", input=text, text=True, check=True, shell=True)
            return True
        if system == "darwin":
            subprocess.run(["pbcopy"], input=text, text=True, check=True)
            return True
        for command in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            try:
                subprocess.run(command, input=text, text=True, check=True)
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    except Exception:
        return False
    return False


def _clean_title(text: str, limit: int = 48) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"[\\/:*?\"<>|#\[\]]+", "-", value).strip("- ")
    return value[:limit] or "AI资讯播客"


def _extract_links(raw_text: str) -> list[str]:
    links: list[str] = []
    for line in raw_text.splitlines():
        value = line.strip()
        if value.startswith(("http://", "https://")) and value not in links:
            links.append(value)
    return links


def _load_skill(skill_path: Path) -> str:
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill 文件不存在：{skill_path}")
    return skill_path.read_text(encoding="utf-8", errors="replace").strip()


def _content_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", str(text or "")))


def _local_expand_script(
    *,
    seed: str,
    query: str,
    platform_label: str,
    min_chars: int,
    target_chars: int,
    package: dict[str, Any],
    last_error: str = "",
) -> str:
    topic = query or str(package.get("title") or "AI 最新实时信息")
    source_count = len(package.get("source_urls") or [])
    seed_text = re.sub(r"\s+", " ", str(seed or "")).strip()
    noisy_markers = ("POST http", "HTTP 500", "扩写失败", "上一次扩写失败", "请重新生成完整")
    if any(marker in seed_text for marker in noisy_markers):
        seed_text = ""
    if not seed_text:
        seed_text = "我最近连续看了几份 AI 资讯，最明显的感觉是：普通人不能只看热闹，要开始建立自己的判断。"
    opening = (
        f"如果你最近也在刷到一堆 AI 新闻，然后心里有点慌，我想先说一句，真的不用急着把自己逼成专家。"
        f"我这次围绕“{topic}”整理了 {source_count or 1} 条资料，最强烈的感受不是某个工具又变厉害了，"
        "而是普通人终于到了一个必须重新整理工作方法的节点。"
    )
    story = (
        "我以前看 AI 资讯也很容易焦虑。今天这个模型升级，明天那个工具上新，后天又有人说某个岗位要被替代。"
        "看多了以后，人会有一种错觉：好像只要我没跟上，就会立刻掉队。可真正开始用起来以后，我发现不是这样。"
        "AI 不是让我们每天追热点追到崩溃，它真正有价值的地方，是把很多重复、低效、消耗人的事情先接过去。"
        "比如整理资料、提炼观点、搭一个初稿、做一个播客大纲、把一堆零散链接变成可理解的内容地图。"
    )
    point_one = (
        "第一层认知，其实不是先学工具，而是先改工作流。"
        "很多人一上来就问，哪个 AI 最强，哪个提示词最好用。可我的体感是，工具只是最后一步。"
        "你先要知道自己每天最卡的环节在哪里：是找资料慢，还是写开头慢，是剪辑慢，还是观点不成体系。"
        "先定位卡点，再让 AI 补位，而不是先收藏一百个工具，再让自己更混乱。"
    )
    point_two = (
        "第二层行动，你就记住一个动作：把输入、思考、输出分开。"
        "输入阶段，让 AI 帮你抓资料、列重点、做对比；思考阶段，你自己判断这件事和你的生活、工作、账号有什么关系；"
        "输出阶段，再让 AI 帮你把观点变成口播、图文、播客脚本。"
        "先有人味，再有工具味；先有判断，再有表达。这样生成出来的内容才不会像一段冷冰冰的说明书。"
    )
    point_three = (
        "第三层进阶，一定要把 AI 当成协作对象，而不是答案机器。"
        "它可以很快，但不代表它永远准确；它可以给你结构，但不能替你承担选择；它可以放大效率，也会放大你的盲区。"
        "所以我现在最常用的方法是，让 AI 给我三个版本：一个乐观版，一个风险版，一个普通人能听懂的版本。"
        "这一步特别适合职场妈妈和内容创作者，因为我们的时间太碎了，不能把晚上仅有的半小时浪费在反复开头、反复纠结上。"
    )
    golden = (
        "你就记住这句话：先上路再调整，先完成再完美。"
        "用做复盘的心态学 AI，而不是用考试的心态学 AI。"
        "一个会提问、会判断、会复用工具的人，不一定立刻领先所有人，但一定会比那个只收藏不行动的自己更稳。"
    )
    cta = (
        "所以这期我想留一个问题给你：如果 AI 今天只能帮你节省 30 分钟，你最想把这 30 分钟从哪件事里拿回来？"
        "是写文案、剪视频、整理资料，还是下班后终于能不带着脑子里的待办清单陪孩子十分钟？"
        "你可以在评论区留一句，我会继续把这个流程拆成普通人也能照着做的版本。"
    )
    draft = "\n\n".join([opening, seed_text, story, point_one, point_two, point_three, golden, cta]).strip()
    while _content_chars(draft) < min_chars:
        draft = f"{draft}\n\n{point_two}\n\n{golden}"
        if _content_chars(draft) >= target_chars:
            break
    return draft


def _expand_script_to_minimum(
    studio_url: str,
    *,
    script: str,
    skill_text: str,
    query: str,
    platform_label: str,
    min_chars: int,
    target_chars: int,
    package: dict[str, Any],
    max_retries: int = 2,
) -> str:
    current = str(script or "").strip()
    api_base = _base_url(studio_url)
    last_error = ""
    for attempt in range(1, max_retries + 1):
        current_chars = _content_chars(current)
        if current_chars >= min_chars:
            return current
        print(
            f"[长度校验] {platform_label}文案只有 {current_chars} 字，低于 {min_chars} 字，"
            f"第 {attempt} 次自动扩写到约 {target_chars} 字。"
        )
        payload = {
            "topic": query or str(package.get("title") or "AI 最新实时信息"),
            "seconds": 60,
            "prompt_hint": (
                f"必须严格应用这个 Skill，扩写为完整{platform_label}成稿。\n"
                f"硬性长度：正文至少 {min_chars} 个中文字符，目标约 {target_chars} 个中文字符。\n"
                "必须保留原始观点，但要加入真实经历感、具体数字、3段递进结构、金句和行动钩子。\n"
                "不要解释规则，不要输出标题说明，不要用项目符号，直接输出可口播正文。\n\n"
                f"【文案生成 Skill】\n{skill_text[:8000]}"
            ),
            "content_mode": "ai_growth",
            "learning_goal": f"把短稿扩写成可直接发布的{platform_label}完整口播稿。",
            "script_provider": os.getenv("SCRIPT_AI_PROVIDER", "gemini_minimax"),
            "draft_script": current,
            "review": {
                "length_check": "too_short",
                "current_chars": current_chars,
                "minimum_chars": min_chars,
                "target_chars": target_chars,
            },
            "human_feedback": (
                f"当前文案太短。请扩写到至少 {min_chars} 个中文字符，目标约 {target_chars} 个中文字符。"
                "要有故事、有观点、有方法、有金句、有互动钩子，严格遵守 Skill。"
            ),
        }
        try:
            result = _json_request(f"{api_base}/api/kids/revise-script", method="POST", payload=payload, timeout=180)
        except RuntimeError as exc:
            last_error = str(exc)
            fallback_payload = {
                "topic": (
                    f"{query or str(package.get('title') or 'AI 最新实时信息')}。"
                    f"请重新生成完整{platform_label}口播稿，不要沿用短稿。"
                ),
                "seconds": 60,
                "prompt_hint": (
                    f"上一次扩写失败：{last_error[:500]}\n"
                    f"请直接生成完整{platform_label}成稿。\n"
                    f"硬性长度：正文至少 {min_chars} 个中文字符，目标约 {target_chars} 个中文字符。\n"
                    "必须应用 Skill：标题公式、三段递进、真实故事、数字、金句、互动钩子。\n"
                    "不要解释规则，不要输出项目符号，只输出可口播正文。\n\n"
                    f"【文案生成 Skill】\n{skill_text[:8000]}"
                ),
                "content_mode": "ai_growth",
                "learning_goal": f"重新生成可直接发布的{platform_label}完整口播稿。",
                "script_provider": os.getenv("SCRIPT_AI_PROVIDER", "gemini_minimax"),
            }
            result = _json_request(f"{api_base}/api/kids/draft-review", method="POST", payload=fallback_payload, timeout=180)
        revised = str(result.get("script") or "").strip()
        if revised:
            current = revised
    if _content_chars(current) < min_chars:
        current = _local_expand_script(
            seed=current,
            query=query,
            platform_label=platform_label,
            min_chars=min_chars,
            target_chars=target_chars,
            package=package,
            last_error=last_error,
        )
    return current


def _review_pause(path: Path) -> str:
    print("\n========== 人工审核 ==========")
    print(f"已生成审核文件：{path}")
    print("你可以打开它检查标题、简介、标签和口播文案。")
    print("如果要补充修改意见，请直接在这里输入；不需要修改就直接回车。")
    try:
        return input("人工修改意见：").strip()
    except EOFError:
        print("当前没有可用的交互输入，自动按“无修改意见”继续。")
        return ""


def collect_notebooklm_links(studio_url: str, query: str) -> dict[str, Any]:
    api_base = _base_url(studio_url)
    if query:
        print(f"[1/6] 按要求抓取实时信息：{query}")
        _json_request(f"{api_base}/api/ai-trends/refresh", method="POST", payload={"query": query}, timeout=120)
    print("[2/6] 生成 NotebookLM 导入包和原始链接清单")
    package_response = _json_request(f"{api_base}/api/ai-trends/notebooklm-package", method="POST", payload={}, timeout=120)
    package = package_response.get("package") or {}
    markdown_url = _absolute_url(api_base, str(package.get("url") or ""))
    source_links_url = _absolute_url(api_base, str(package.get("source_links_url") or ""))
    source_urls = list(package.get("source_urls") or [])
    if not source_urls and source_links_url:
        source_urls = _extract_links(_text_request(source_links_url))
    if not source_urls:
        raise RuntimeError("NotebookLM 导入包里没有拿到原始链接，请先在 Studio 抓取 AI 实时信息。")
    return {
        "title": package.get("title") or package_response.get("title") or "AI 最新资讯",
        "markdown_url": markdown_url,
        "source_links_url": source_links_url,
        "source_urls": source_urls,
        "raw": package_response,
    }


def generate_ximalaya_copy(studio_url: str, skill_text: str, package: dict[str, Any], query: str) -> dict[str, str]:
    api_base = _base_url(studio_url)
    topic = (
        f"请基于 NotebookLM 最新 AI 资讯导入包，为喜马拉雅播客生成标题、简介和口播文案。"
        f"主题要求：{query or package.get('title') or 'AI 最新实时信息'}。"
        f"原始链接清单：{package.get('source_links_url')}"
    )
    prompt_hint = (
        "请严格应用下面 Skill 的风格规则，生成适合喜马拉雅发布的播客文案。"
        "输出要像真人口播，不要解释规则。"
        "硬性要求：播客口播正文至少 900 个中文字符，目标约 1200 个中文字符；"
        "要有开场钩子、3段递进观点、真实经历感、方法总结、结尾互动。"
        "\n\n【文案生成 Skill】\n"
        f"{skill_text[:8000]}"
    )
    payload = {
        "topic": topic,
        "seconds": 60,
        "prompt_hint": prompt_hint,
        "content_mode": "ai_growth",
        "learning_goal": "把 AI 最新资讯转成普通学习者能听懂、有观点、有温度的播客口播。",
        "script_provider": os.getenv("SCRIPT_AI_PROVIDER", "gemini_minimax"),
    }
    print("[3/6] 根据 Skill 生成喜马拉雅标题/简介/文案")
    result = _json_request(f"{api_base}/api/kids/draft-review", method="POST", payload=payload, timeout=180)
    script = str(result.get("script") or "").strip()
    script = _expand_script_to_minimum(
        studio_url,
        script=script,
        skill_text=skill_text,
        query=query,
        platform_label="喜马拉雅播客",
        min_chars=900,
        target_chars=1200,
        package=package,
    )
    title = _clean_title((package.get("title") or query or "AI最新资讯") + "：普通人该怎么看")
    description = (
        "本期基于最新 AI 资讯和 NotebookLM 分析整理，聊聊 AI 对普通学习者、职场妈妈、内容创作者的真实影响。\n\n"
        f"{script[:900]}"
    ).strip()
    tags = "AI,人工智能,NotebookLM,职场妈妈,学习方法,效率工具"
    return {"title": title, "description": description, "tags": tags, "script": script}


def generate_videohao_copy(studio_url: str, skill_text: str, package: dict[str, Any], query: str) -> dict[str, str]:
    api_base = _base_url(studio_url)
    topic = (
        "请基于 NotebookLM 最新 AI 资讯导入包，同时生成一条微信视频号真人出镜口播文案。"
        f"主题要求：{query or package.get('title') or 'AI 最新实时信息'}。"
        f"原始链接清单：{package.get('source_links_url')}"
    )
    prompt_hint = (
        "请严格应用下面 Skill 的风格规则，生成视频号 60-90 秒真人口播文案。"
        "必须符合：3秒黄金钩子、真实经历共情、3个可落地观点/方法、启发式金句结尾、评论区互动。"
        "硬性要求：正文至少 450 个中文字符，目标约 650 个中文字符。"
        "输出不要加角色标签，不要分镜说明，不要解释规则，只给可直接口播的正文。"
        "\n\n【文案生成 Skill】\n"
        f"{skill_text[:8000]}"
    )
    payload = {
        "topic": topic,
        "seconds": 60,
        "prompt_hint": prompt_hint,
        "content_mode": "ai_growth",
        "learning_goal": "把 AI 最新资讯转成视频号真人出镜口播，面向普通学习者和职场妈妈。",
        "script_provider": os.getenv("SCRIPT_AI_PROVIDER", "gemini_minimax"),
    }
    print("[3/6] 根据 Skill 同步生成视频号口播文案")
    result = _json_request(f"{api_base}/api/kids/draft-review", method="POST", payload=payload, timeout=180)
    script = str(result.get("script") or "").strip()
    script = _expand_script_to_minimum(
        studio_url,
        script=script,
        skill_text=skill_text,
        query=query,
        platform_label="视频号",
        min_chars=450,
        target_chars=650,
        package=package,
    )
    title = _clean_title((query or package.get("title") or "AI最新资讯") + "，普通人别只看热闹")
    hashtags = "#AI #人工智能 #普通人学AI #职场妈妈 #效率工具 #视频号"
    return {"title": title, "hashtags": hashtags, "script": script}


def revise_copy_if_needed(
    studio_url: str,
    copy: dict[str, str],
    feedback: str,
    skill_text: str,
    query: str,
    *,
    platform_label: str,
    learning_goal: str,
    package: dict[str, Any],
    min_chars: int,
    target_chars: int,
) -> dict[str, str]:
    if not feedback:
        return copy
    api_base = _base_url(studio_url)
    payload = {
        "topic": query or copy["title"],
        "seconds": 60,
        "prompt_hint": f"继续遵守这个 Skill：\n{skill_text[:8000]}",
        "content_mode": "ai_growth",
        "learning_goal": learning_goal,
        "script_provider": os.getenv("SCRIPT_AI_PROVIDER", "gemini_minimax"),
        "draft_script": copy["script"],
        "review": {"manual_stage": f"{platform_label}_publish_review"},
        "human_feedback": feedback,
    }
    print(f"[3.5/6] 根据人工意见二次修改{platform_label}文案")
    result = _json_request(f"{api_base}/api/kids/revise-script", method="POST", payload=payload, timeout=180)
    script = str(result.get("script") or copy["script"]).strip()
    script = _expand_script_to_minimum(
        studio_url,
        script=script,
        skill_text=skill_text,
        query=query,
        platform_label=platform_label,
        min_chars=min_chars,
        target_chars=target_chars,
        package=package,
    )
    copy["script"] = script
    if "description" in copy:
        copy["description"] = (
            "本期基于最新 AI 资讯和 NotebookLM 分析整理，聊聊 AI 对普通学习者、职场妈妈、内容创作者的真实影响。\n\n"
            f"{script[:900]}"
        ).strip()
    return copy


def save_review_files(package: dict[str, Any], ximalaya_copy: dict[str, str], videohao_copy: dict[str, str]) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RUN_DIR / f"{run_id}_notebooklm_publish_review.md"
    links = "\n".join(f"- {item}" for item in package["source_urls"])
    body = f"""# NotebookLM 多平台发布审核单 {run_id}

## NotebookLM 导入信息

- Markdown 导入包：{package.get("markdown_url")}
- 原始链接清单：{package.get("source_links_url")}

## 原始网页链接

{links}

## 喜马拉雅发布内容

### 标题

{ximalaya_copy["title"]}

### 标签

{ximalaya_copy["tags"]}

### 简介

{ximalaya_copy["description"]}

### 播客口播文案

{ximalaya_copy["script"]}

## 视频号口播内容

### 标题

{videohao_copy["title"]}

### 话题

{videohao_copy["hashtags"]}

### 真人出镜口播文案

{videohao_copy["script"]}
"""
    path.write_text(body, encoding="utf-8")
    return path


def run_browser_flow(args: argparse.Namespace, package: dict[str, Any], copy: dict[str, str]) -> Path | None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("缺少 Playwright。请先运行：python -m pip install playwright && python -m playwright install chromium") from exc

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    audio_path: Path | None = None
    links_text = "\n".join(package["source_urls"])
    review_text = f"标题：{copy['title']}\n\n标签：{copy['tags']}\n\n简介：\n{copy['description']}\n"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 960},
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("[4/6] 打开 Creator Digital Studio，确认最新导入包")
        page.goto(args.studio_url, wait_until="domcontentloaded")
        input("请确认 Studio 页面可用；需要的话点击“生成 NotebookLM 导入包”。确认后回车继续：")

        print("[5/6] 打开 NotebookLM")
        page.goto(args.notebooklm_url, wait_until="domcontentloaded")
        print("已复制最新原始链接到剪贴板。" if _set_clipboard(links_text) else "剪贴板写入失败，请从审核单复制链接。")
        print("请在 NotebookLM 里：1）删除上一次网页来源；2）添加来源 -> 网站；3）粘贴刚复制的链接；4）等待资料加载完成。")
        input("NotebookLM 资料源清空并重新导入完成后，按回车继续生成音频：")

        print("请在 NotebookLM 里点击生成 Audio Overview/音频概览，生成完成后点击下载。脚本会捕获下载文件。")
        try:
            with page.expect_download(timeout=args.download_timeout * 1000) as download_info:
                input("准备好后，请点击 NotebookLM 的音频下载按钮，然后回到终端按回车：")
            download = download_info.value
            suggested = _clean_title(download.suggested_filename or "notebooklm_audio.mp3", limit=80)
            suffix = Path(suggested).suffix or ".mp3"
            audio_path = RUN_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_notebooklm_audio{suffix}"
            download.save_as(str(audio_path))
            print(f"音频已下载：{audio_path}")
        except PlaywrightTimeoutError:
            print("没有捕获到下载。你可以先手动下载音频，稍后在喜马拉雅页面手动上传。")

        print("[6/6] 打开喜马拉雅投稿页，辅助填写发布信息")
        page.goto(args.ximalaya_upload_url, wait_until="domcontentloaded")
        print("已复制标题/标签/简介到剪贴板。" if _set_clipboard(review_text) else "剪贴板写入失败，请从审核单复制标题和简介。")
        print("请在喜马拉雅页面登录后手动上传音频，并粘贴标题、简介、标签。最终“发布”按钮请你人工确认后再点。")
        if audio_path:
            print(f"音频文件位置：{audio_path}")
        input("喜马拉雅信息填写和人工审核完成后，按回车结束脚本：")
        context.close()

    return audio_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Creator Studio -> NotebookLM -> 喜马拉雅半自动流水线")
    parser.add_argument("--studio-url", default=os.getenv("CREATOR_STUDIO_URL", DEFAULT_STUDIO_URL))
    parser.add_argument("--notebooklm-url", default=os.getenv("NOTEBOOKLM_URL", DEFAULT_NOTEBOOKLM_URL))
    parser.add_argument("--ximalaya-upload-url", default=os.getenv("XIMALAYA_UPLOAD_URL", DEFAULT_XIMALAYA_UPLOAD_URL))
    parser.add_argument("--skill-path", default=os.getenv("XIMALAYA_COPY_SKILL_PATH", str(DEFAULT_SKILL_PATH)))
    parser.add_argument("--query", default=os.getenv("AI_TRENDS_QUERY", ""))
    parser.add_argument("--download-timeout", type=int, default=int(os.getenv("NOTEBOOKLM_AUDIO_DOWNLOAD_TIMEOUT", "1800")))
    parser.add_argument("--no-browser", action="store_true", help="只生成 NotebookLM 链接和喜马拉雅审核单，不打开浏览器。")
    return parser.parse_args()


def main() -> int:
    _read_env_file(ROOT_DIR / ".env")
    args = parse_args()
    skill_text = _load_skill(Path(args.skill_path))
    package = collect_notebooklm_links(args.studio_url, args.query)
    copy = generate_ximalaya_copy(args.studio_url, skill_text, package, args.query)
    videohao_copy = generate_videohao_copy(args.studio_url, skill_text, package, args.query)
    review_path = save_review_files(package, copy, videohao_copy)
    feedback = _review_pause(review_path)
    copy = revise_copy_if_needed(
        args.studio_url,
        copy,
        feedback,
        skill_text,
        args.query,
        platform_label="喜马拉雅",
        learning_goal="按人工意见修成可直接发布的喜马拉雅播客文案。",
        package=package,
        min_chars=900,
        target_chars=1200,
    )
    videohao_copy = revise_copy_if_needed(
        args.studio_url,
        videohao_copy,
        feedback,
        skill_text,
        args.query,
        platform_label="视频号",
        learning_goal="按人工意见修成可直接发布的视频号真人出镜口播文案。",
        package=package,
        min_chars=450,
        target_chars=650,
    )
    review_path = save_review_files(package, copy, videohao_copy)
    print(f"最终审核单：{review_path}")
    if not args.no_browser:
        run_browser_flow(args, package, copy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
