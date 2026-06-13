from __future__ import annotations

import shutil
import subprocess
import threading
import re
import os
import hashlib
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .analysis import analyze_media_file, detect_media_kind, transcribe_audio
from .ai_trends import (
    archive_markdown_to_obsidian,
    build_notebooklm_import_package,
    build_trend_interview_followups,
    collect_ai_trends,
)
from .avatar import detect_sadtalker_status, normalize_sadtalker_config
from .generation import render_job, synthesize_audio_asset
from .kids_mode import (
    KIDS_ANIMATION_HARD_RULES,
    KIDS_CHARACTER_DESIGN,
    REFERENCE_STYLE_CONTRACT,
    build_kids_english_script,
    build_kids_generate_payload,
    build_kids_storyboard,
    clamp_kids_seconds,
    ensure_cartoon_dirs,
    make_uploaded_image_path,
    analyze_kids_script_quality,
    normalize_kids_script_text,
    normalize_content_mode,
    normalize_video_provider,
)
from .persona import default_persona, distill_persona
from .publishing import (
    prepare_material_distribution_package,
    prepare_trend_distribution_package,
    prepare_distribution_package,
    refresh_distribution_manifest,
    submit_wechat_draft,
    upload_wechat_cover,
)
from .scheduler import StudioScheduler
from .script_ai import generate_kids_script_with_ai, generate_reviewed_draft, revise_script_with_feedback
from .stock_skills import list_stock_skills, run_stock_skill
from .stocks import analyze_stock, normalize_stock_symbol, search_stocks, stock_quote
from .schemas import (
    AudioGenerateRequest,
    DistillRequest,
    DistributionPrepareRequest,
    DouyinPublishAssistantRequest,
    GenerateRequest,
    KidsGenerateRequest,
    KidsScriptPreviewRequest,
    KidsScriptReviseRequest,
    PersonaUpdate,
    SadTalkerConfigPayload,
    SchedulePayload,
    WeChatMaterialRequest,
    WeChatDraftRequest,
    TrendDistributionRequest,
    XiaohongshuPublishStatusRequest,
)
from .storage import (
    OUTPUTS_DIR,
    PORTRAITS_DIR,
    STUDIO_DIR,
    UPLOADS_DIR,
    VOICE_REFERENCES_DIR,
    StudioStore,
    make_id,
    now_iso,
    to_media_url,
)


def _resolve_script_revision_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized in {"gemini", "gemini_minimax", "gemini_deepseek_minimax"}:
        return "gemini"
    if normalized in {"minimax", "minimax_plan", "minimax_token_plan", "minimax_deepseek"}:
        return "minimax"
    return normalized or "unknown"


def _script_ai_error_detail(
    *,
    requested_provider: str,
    stage: str,
    message: str,
) -> dict[str, Any]:
    safe_message = re.sub(r"(sk-[A-Za-z0-9_-]{8,})", "***hidden***", str(message or ""))
    safe_message = re.sub(r"(key=)[^&\s]+", r"\1***hidden***", safe_message)
    lower_message = safe_message.lower()
    failed_provider = "unknown"
    if "gemini" in lower_message or "google" in lower_message:
        failed_provider = "gemini"
    elif "minimax" in lower_message:
        failed_provider = "minimax"
    elif "deepseek" in lower_message:
        failed_provider = "deepseek"
    return {
        "error": "script_ai_failed",
        "stage": stage,
        "failed_provider": failed_provider,
        "requested_provider": requested_provider,
        "resolved_revision_provider": _resolve_script_revision_provider(requested_provider),
        "review_provider": "deepseek",
        "message": safe_message[:1000],
    }


app = FastAPI(title="Creator Digital Studio", version="0.1.0")
store = StudioStore()
SADTALKER_RENDER_LOCK = threading.Lock()
ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR = ROOT_DIR / "studio_frontend" / "dist"


def _load_root_env() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and not os.getenv(name):
            os.environ[name] = value.strip().strip('"').strip("'")


_load_root_env()
DOUYIN_CREATOR_UPLOAD_URL = os.getenv(
    "DOUYIN_CREATOR_UPLOAD_URL",
    "https://creator.douyin.com/creator-micro/content/post/video",
).strip() or "https://creator.douyin.com/"
WECHAT_CALLBACK_TOKEN = os.getenv("WECHAT_CALLBACK_TOKEN", os.getenv("WECHAT_TOKEN", "")).strip()
WECHAT_SYNC_REPLY = os.getenv("WECHAT_SYNC_REPLY", "false").strip().lower() in {"1", "true", "yes", "on"}
WECHAT_QR_IMAGE_URL = os.getenv("WECHAT_QR_IMAGE_URL", "").strip()
WECHAT_ACCOUNT_NAME = os.getenv("WECHAT_ACCOUNT_NAME", "微信素材测试号").strip() or "微信素材测试号"
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "").strip()
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "").strip()
WECHAT_VOICE_FALLBACK_TRANSCRIBE = os.getenv("WECHAT_VOICE_FALLBACK_TRANSCRIBE", "true").strip().lower() in {"1", "true", "yes", "on"}
WECHAT_VOICE_WHISPER_MODEL = os.getenv("WECHAT_VOICE_WHISPER_MODEL", "small").strip() or "small"
WECHAT_NORMALIZE_SIMPLIFIED = os.getenv("WECHAT_NORMALIZE_SIMPLIFIED", "true").strip().lower() in {"1", "true", "yes", "on"}
AI_TRENDS_ENABLED = os.getenv("AI_TRENDS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
AI_TRENDS_TIME = os.getenv("AI_TRENDS_TIME", "07:30").strip() or "07:30"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/studio-files", StaticFiles(directory=str(STUDIO_DIR)), name="studio-files")
if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="frontend-assets")


@app.get("/")
def frontend_index() -> FileResponse:
    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build in studio_frontend.")
    return FileResponse(str(index_file))


def _sorted(records: list[dict[str, Any]], key: str = "created_at") -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: str(item.get(key, "")), reverse=True)


def _latest_reference_assets() -> dict[str, Any]:
    analyses_by_upload: dict[str, dict[str, Any]] = {}
    analyses_by_id: dict[str, dict[str, Any]] = {}
    for analysis in _sorted(store.list_section("analyses")):
        analysis_id = str(analysis.get("id", "")).strip()
        upload_id = str(analysis.get("upload_id", "")).strip()
        if analysis_id and analysis_id not in analyses_by_id:
            analyses_by_id[analysis_id] = analysis
        if upload_id and upload_id not in analyses_by_upload:
            analyses_by_upload[upload_id] = analysis

    assets = {
        "upload_id": "",
        "filename": "",
        "portrait_path": "",
        "portrait_url": "",
        "voice_reference_path": "",
        "voice_reference_url": "",
        "source_media_path": "",
        "source_media_url": "",
        "source_video_path": "",
        "source_video_url": "",
        "style_profiles": [],
    }
    style_profiles: dict[str, dict[str, Any]] = {}
    for upload in _sorted(store.list_section("uploads")):
        upload_id = str(upload.get("id", "")).strip()
        analysis_id = str(upload.get("analysis_id", "")).strip()
        analysis_record = analyses_by_id.get(analysis_id) or analyses_by_upload.get(upload_id) or {}
        analysis_assets = dict(analysis_record.get("reference_assets") or {})

        portrait_path = str(upload.get("portrait_path", "")).strip() or str(analysis_assets.get("portrait_path", "")).strip()
        portrait_url = str(upload.get("portrait_url", "")).strip() or str(analysis_assets.get("portrait_url", "")).strip()
        voice_reference_path = str(upload.get("voice_reference_path", "")).strip() or str(analysis_assets.get("voice_reference_path", "")).strip()
        voice_reference_url = str(upload.get("voice_reference_url", "")).strip() or str(analysis_assets.get("voice_reference_url", "")).strip()
        saved_path = str(upload.get("saved_path", "")).strip()
        media_url = str(upload.get("media_url", "")).strip()
        media_kind = str(upload.get("media_kind", "")).strip().lower() or detect_media_kind(Path(saved_path))
        style_tag = str(upload.get("style_tag", "")).strip()

        if saved_path and not assets["source_media_path"]:
            assets["upload_id"] = upload_id
            assets["filename"] = str(upload.get("filename", "")).strip()
            assets["source_media_path"] = saved_path
            assets["source_media_url"] = media_url
        if media_kind == "video" and saved_path and not assets["source_video_path"]:
            assets["source_video_path"] = saved_path
            assets["source_video_url"] = media_url
        if portrait_path and not assets["portrait_path"]:
            assets["portrait_path"] = portrait_path
            assets["portrait_url"] = portrait_url
        if voice_reference_path and not assets["voice_reference_path"]:
            assets["voice_reference_path"] = voice_reference_path
            assets["voice_reference_url"] = voice_reference_url

        if style_tag:
            profile = style_profiles.get(style_tag)
            if not profile:
                profile = {
                    "style_tag": style_tag,
                    "upload_id": upload_id,
                    "filename": str(upload.get("filename", "")).strip(),
                    "media_kind": media_kind,
                    "source_media_path": "",
                    "source_media_url": "",
                    "source_video_path": "",
                    "source_video_url": "",
                    "portrait_path": "",
                    "portrait_url": "",
                    "voice_reference_path": "",
                    "voice_reference_url": "",
                }
                style_profiles[style_tag] = profile
            if saved_path and not profile["source_media_path"]:
                profile["source_media_path"] = saved_path
                profile["source_media_url"] = media_url
            if media_kind == "video" and saved_path and not profile["source_video_path"]:
                profile["source_video_path"] = saved_path
                profile["source_video_url"] = media_url
            if portrait_path and not profile["portrait_path"]:
                profile["portrait_path"] = portrait_path
                profile["portrait_url"] = portrait_url
            if voice_reference_path and not profile["voice_reference_path"]:
                profile["voice_reference_path"] = voice_reference_path
                profile["voice_reference_url"] = voice_reference_url

    assets["style_profiles"] = list(style_profiles.values())
    return assets


def _attach_reference_assets(persona: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(persona)
    enriched["reference_assets"] = _latest_reference_assets()
    return enriched


def _ensure_persona() -> dict[str, Any]:
    persona = store.get_persona()
    if persona:
        return _attach_reference_assets(persona)
    persona = default_persona()
    store.set_persona(persona)
    return _attach_reference_assets(persona)


def _rebuild_persona(name: str | None = None) -> dict[str, Any]:
    analyses = store.list_section("analyses")
    existing = store.get_persona()
    persona = distill_persona(
        analyses,
        existing=existing,
        preferred_name=name or (existing or {}).get("name"),
    )
    store.set_persona(persona)
    return _attach_reference_assets(persona)


def _job_snapshot(job_id: str) -> dict[str, Any]:
    job = store.find_record("jobs", job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _compact_text(value: Any, *, limit: int = 80) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip()


def _normalize_hashtag(value: Any) -> str:
    text = re.sub(r"[#＃\s]+", "", str(value or "")).strip("，,。.!！?？、；;：:")
    return text[:24]


def _default_douyin_hashtags(job: dict[str, Any]) -> list[str]:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    topic = _compact_text(request_payload.get("topic"), limit=24)
    content_mode = str(request_payload.get("content_mode") or request_payload.get("kids_content_mode") or "").strip().lower()
    base = ["职场妈妈", "AI提效", "短视频创作"]
    if content_mode == "creator_tips":
        base += ["剪辑提效", "自媒体运营"]
    elif content_mode == "ai_growth":
        base += ["AI学习", "职业重塑"]
    else:
        base += ["时间管理", "情绪价值"]
    if topic:
        base.insert(0, topic)
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in base:
        clean = _normalize_hashtag(tag)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            normalized.append(clean)
    return normalized[:6]


def _build_douyin_caption(title: str, hashtags: list[str]) -> str:
    tag_text = " ".join(f"#{tag}" for tag in hashtags if tag)
    caption = f"{title.strip()} {tag_text}".strip()
    return caption[:1000]


def json_like_compact(value: Any) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value))[:900]


def _format_wechat_copy_reply(preview: dict[str, Any] | None, *, material_text: str) -> dict[str, Any]:
    if not preview:
        return {
            "summary": f"已收到素材：{_compact_text(material_text, limit=80)}",
            "plain_text": "素材已进入队列，稍后生成文案。",
            "sections": [],
        }
    script = str(preview.get("script") or "").strip()
    script_ai = preview.get("script_ai") if isinstance(preview.get("script_ai"), dict) else {}
    review = script_ai.get("review") if isinstance(script_ai.get("review"), dict) else {}
    final_review = script_ai.get("final_review") if isinstance(script_ai.get("final_review"), dict) else {}
    issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    fixes = review.get("fix_instructions") if isinstance(review.get("fix_instructions"), list) else []
    lines = [
        "【素材已生成文案】",
        f"素材：{_compact_text(material_text, limit=80)}",
        f"来源：{preview.get('script_source', 'unknown')}",
    ]
    if review:
        lines.append(f"DeepSeek 初审：{review.get('score', '未评分')}/100")
    if final_review:
        lines.append(f"DeepSeek 复审：{final_review.get('score', '未评分')}/100")
    if issues or fixes:
        lines.append("审核摘要：")
        for item in [*issues, *fixes][:5]:
            lines.append(f"- {item}")
    lines.extend(["", "【终稿文案】", script])
    return {
        "summary": f"文案已生成：{_compact_text(script, limit=60)}",
        "plain_text": "\n".join(lines).strip(),
        "sections": [
            {"title": "素材", "content": material_text},
            {"title": "终稿文案", "content": script},
            {"title": "DeepSeek 审核", "content": json_like_compact(review)},
            {"title": "DeepSeek 复审", "content": json_like_compact(final_review)},
        ],
    }


def _wechat_signature_ok(signature: str, timestamp: str, nonce: str) -> bool:
    if not WECHAT_CALLBACK_TOKEN:
        return False
    values = sorted([WECHAT_CALLBACK_TOKEN, str(timestamp or ""), str(nonce or "")])
    digest = hashlib.sha1("".join(values).encode("utf-8")).hexdigest()
    return digest == str(signature or "").strip()


def _wechat_text_response(*, to_user: str, from_user: str, content: str) -> str:
    safe_content = str(content or "")[:1800]
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{safe_content}]]></Content>"
        "</xml>"
    )


def _record_wechat_callback_event(
    message: dict[str, str],
    *,
    action: str,
    reason: str,
    content_preview: str | None = None,
) -> dict[str, Any]:
    msg_type = str(message.get("MsgType") or "").strip() or "unknown"
    preview = (
        content_preview
        or message.get("Content")
        or message.get("Recognition")
        or message.get("Event")
        or message.get("PicUrl")
        or ""
    )
    record = {
        "id": make_id("wechat_callback"),
        "created_at": now_iso(),
        "msg_type": msg_type,
        "event": str(message.get("Event") or "").strip(),
        "source_user": str(message.get("FromUserName") or "").strip(),
        "source_message_id": str(message.get("MsgId") or "").strip(),
        "content_preview": _compact_text(preview, limit=160),
        "action": action,
        "reason": reason,
    }

    def updater(state: dict[str, Any]) -> dict[str, Any]:
        events = list(state.get("wechat_callback_events", []))
        events.append(record)
        state["wechat_callback_events"] = events[-80:]
        return record

    return store.mutate(updater)


def _parse_wechat_xml(raw_body: bytes) -> dict[str, str]:
    if not raw_body:
        return {}
    root = ET.fromstring(raw_body.decode("utf-8", errors="replace"))
    result: dict[str, str] = {}
    for child in root:
        result[child.tag] = str(child.text or "")
    return result


_OPENCC_CONVERTER: Any | None = None
_OPENCC_CHECKED = False
_TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "請": "请", "問": "问", "會": "会", "這": "这", "個": "个", "種": "种", "後": "后", "們": "们",
        "麼": "么", "嗎": "吗", "為": "为", "與": "与", "時": "时", "對": "对", "說": "说", "聽": "听",
        "讓": "让", "學": "学", "習": "习", "訊": "讯", "開": "开", "關": "关", "發": "发",
        "現": "现", "裡": "里", "裏": "里", "點": "点", "擊": "击", "頁": "页", "輸": "输", "錄": "录",
        "聲": "声", "識": "识", "別": "别", "產": "产", "業": "业", "職": "职", "場": "场", "媽": "妈",
        "寶": "宝", "貝": "贝", "幫": "帮", "檢": "检", "查": "查", "實": "实", "將": "将", "帶": "带",
        "過": "过", "還": "还", "並": "并", "從": "从", "變": "变", "應": "应", "該": "该", "滿": "满",
        "壓": "压", "線": "线", "網": "网", "圖": "图", "視": "视", "頻": "频", "號": "号", "質": "质",
        "選": "选", "題": "题", "審": "审", "核": "核", "補": "补", "充": "充", "語": "语", "氣": "气",
        "內": "内", "容": "容", "產": "产", "驗": "验", "證": "证", "權": "权", "限": "限", "雲": "云",
        "獲": "获", "取": "取", "資": "资", "料": "料", "庫": "库", "儲": "储", "存": "存", "檔": "档",
        "復": "复", "製": "制", "歸": "归", "導": "导", "覽": "览", "鏈": "链", "結": "结", "優": "优",
        "化": "化", "啟": "启", "動": "动", "項": "项", "目": "目", "嗎": "吗", "長": "长", "輕": "轻",
        "難": "难", "離": "离", "總": "总", "體": "体", "機": "机", "構": "构", "單": "单", "條": "条",
        "刪": "删", "除": "除", "統": "统", "緒": "绪", "調": "调", "節": "节", "處": "处", "備": "备",
        "無": "无", "國": "国", "際": "际", "標": "标", "籤": "签", "則": "则", "類": "类", "轉": "转",
        "寫": "写", "傳": "传", "測": "测", "試": "试", "顯": "显", "示": "示", "碼": "码", "從": "从",
    }
)


def _normalize_chinese_text(text: str) -> str:
    if not WECHAT_NORMALIZE_SIMPLIFIED:
        return str(text or "")
    raw = str(text or "")
    if not raw:
        return ""
    global _OPENCC_CONVERTER, _OPENCC_CHECKED
    if not _OPENCC_CHECKED:
        _OPENCC_CHECKED = True
        try:
            from opencc import OpenCC  # type: ignore

            _OPENCC_CONVERTER = OpenCC("t2s")
        except Exception:
            _OPENCC_CONVERTER = None
    if _OPENCC_CONVERTER is not None:
        try:
            return str(_OPENCC_CONVERTER.convert(raw))
        except Exception:
            pass
    return raw.translate(_TRADITIONAL_TO_SIMPLIFIED)


_WECHAT_ACCESS_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": 0.0}


def _get_wechat_access_token() -> str:
    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        return ""
    now = time.time()
    cached_token = str(_WECHAT_ACCESS_TOKEN_CACHE.get("token") or "")
    expires_at = float(_WECHAT_ACCESS_TOKEN_CACHE.get("expires_at") or 0.0)
    if cached_token and now < expires_at - 120:
        return cached_token
    query = urllib.parse.urlencode(
        {
            "grant_type": "client_credential",
            "appid": WECHAT_APP_ID,
            "secret": WECHAT_APP_SECRET,
        }
    )
    url = f"https://api.weixin.qq.com/cgi-bin/token?{query}"
    with urllib.request.urlopen(url, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError(str(payload))
    _WECHAT_ACCESS_TOKEN_CACHE["token"] = token
    _WECHAT_ACCESS_TOKEN_CACHE["expires_at"] = now + float(payload.get("expires_in") or 7200)
    return token


def _download_wechat_voice_media(media_id: str, *, msg_id: str = "") -> Path:
    token = _get_wechat_access_token()
    if not token:
        raise RuntimeError("未配置 WECHAT_APP_ID / WECHAT_APP_SECRET，无法下载微信语音素材。")
    query = urllib.parse.urlencode({"access_token": token, "media_id": media_id})
    url = f"https://api.weixin.qq.com/cgi-bin/media/get?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "CreatorStudio/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = str(response.headers.get("Content-Type") or "").lower()
        body = response.read()
    if "json" in content_type or body[:1] == b"{":
        raise RuntimeError(body.decode("utf-8", errors="replace"))
    suffix = ".amr"
    if "speex" in content_type:
        suffix = ".speex"
    elif "audio/mpeg" in content_type:
        suffix = ".mp3"
    voice_dir = STUDIO_DIR / "wechat_voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "", msg_id or media_id)[:42] or make_id("wechat_voice")
    target = voice_dir / f"{safe_id}{suffix}"
    target.write_bytes(body)
    return target


def _transcribe_wechat_voice_media(message: dict[str, str]) -> tuple[str, str]:
    media_id = str(message.get("MediaId") or "").strip()
    if not media_id:
        return "", "微信语音回调没有 MediaId，无法下载语音。"
    if not WECHAT_VOICE_FALLBACK_TRANSCRIBE:
        return "", "已关闭 WECHAT_VOICE_FALLBACK_TRANSCRIBE，未尝试下载语音转写。"
    try:
        source_path = _download_wechat_voice_media(media_id, msg_id=str(message.get("MsgId") or ""))
        transcript, note = transcribe_audio(source_path, model_name=WECHAT_VOICE_WHISPER_MODEL)
        if transcript:
            return _normalize_chinese_text(re.sub(r"\s+", " ", transcript).strip()), f"微信未返回 Recognition，已下载语音并本地转写：{note}"
        return "", f"已下载语音但本地转写为空：{note}"
    except Exception as exc:  # noqa: BLE001
        return "", f"微信未返回 Recognition，下载/转写兜底失败：{exc}"


def _build_douyin_publish_draft(
    job: dict[str, Any],
    payload: DouyinPublishAssistantRequest | None = None,
) -> dict[str, Any]:
    if str(job.get("status", "")).strip().lower() != "completed":
        raise HTTPException(status_code=409, detail="视频生成完成后才能使用发布助手。")
    artifacts = job.get("artifacts") if isinstance(job.get("artifacts"), dict) else {}
    video_url = str(artifacts.get("video_url", "")).strip()
    if not video_url:
        raise HTTPException(status_code=400, detail="当前任务没有可发布的视频文件。")
    video_path = _resolve_download_target(video_url)
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    topic = _compact_text(request_payload.get("topic") or job.get("script_text"), limit=34)
    default_title = f"和毛豆花生一起认识：{topic}" if topic else "和毛豆花生一起学一个小知识"
    title = _compact_text((payload.title if payload else "") or default_title, limit=80)
    incoming_tags = payload.hashtags if payload else []
    hashtags = [_normalize_hashtag(tag) for tag in incoming_tags]
    hashtags = [tag for tag in hashtags if tag]
    if not hashtags:
        hashtags = _default_douyin_hashtags(job)
    caption = _build_douyin_caption(title, hashtags)
    return {
        "prepared_at": now_iso(),
        "platform": "douyin",
        "mode": "manual_confirm_assistant",
        "creator_url": DOUYIN_CREATOR_UPLOAD_URL,
        "video_url": video_url,
        "video_file_path": str(video_path),
        "title": title,
        "hashtags": hashtags,
        "caption": caption,
        "steps": [
            "点击打开抖音创作者服务平台并扫码登录。",
            "在投稿页面选择本地视频文件。",
            "复制标题和话题到发布标题输入框。",
            "检查封面、可见范围和内容合规性。",
            "确认无误后，由你手动点击发布。",
        ],
        "manual_confirm_required": True,
    }


def _sync_scheduler() -> None:
    scheduler.sync(store.list_section("schedules"))


def _recover_interrupted_jobs() -> int:
    def updater(state: dict[str, Any]) -> int:
        recovered = 0
        for job in state.get("jobs", []):
            status = str(job.get("status", "")).strip().lower()
            if status not in {"running", "queued"}:
                continue
            recovered += 1
            job["status"] = "failed"
            job["progress_stage"] = "interrupted"
            job["progress_message"] = "Task interrupted by backend restart. Please run generation again."
            if not str(job.get("error", "")).strip():
                job["error"] = "Task interrupted by backend restart."
            job["updated_at"] = now_iso()
            job["completed_at"] = now_iso()
        return recovered

    return int(store.mutate(updater))


def _build_job(request_payload: dict[str, Any], *, trigger: str, schedule_id: str = "") -> dict[str, Any]:
    avatar_settings = normalize_sadtalker_config(store.get_state().get("avatar_settings"))
    job = {
        "id": make_id("job"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "queued",
        "progress_percent": 0,
        "progress_stage": "queued",
        "progress_message": "Waiting to start",
        "trigger": trigger,
        "schedule_id": schedule_id,
        "request": request_payload,
        "avatar_settings": avatar_settings,
        "artifacts": {},
        "summary": {},
        "script_text": "",
        "error": "",
    }
    store.add_record("jobs", job)
    return job


def _normalize_primary_portrait_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(request_payload)
    project_mode = str(normalized.get("project_mode", "")).strip().lower()
    if project_mode == "kids_cartoon":
        requested_render_mode = str(normalized.get("render_mode", "")).strip().lower()
        requested_animation_style = str(normalized.get("animation_style", "")).strip().lower()
        use_2d = requested_render_mode == "cartoon_native_2d" or requested_animation_style in {"2d", "cartoon_2d"}
        requested_single_mode = "single" in requested_animation_style and "duo" not in requested_animation_style
        normalized["render_mode"] = "cartoon_native_2d" if use_2d else "cartoon_native_3d"
        normalized["tts_provider"] = "edge"
        if not str(normalized.get("edge_voice", "")).strip():
            normalized["edge_voice"] = "zh-CN-XiaoyiNeural"
        if not str(normalized.get("edge_rate", "")).strip():
            normalized["edge_rate"] = "+3%"
        if not str(normalized.get("edge_volume", "")).strip():
            normalized["edge_volume"] = "+2%"
        try:
            subtitle_margin = int(normalized.get("subtitle_margin_v", 0) or 0)
        except (TypeError, ValueError):
            subtitle_margin = 0
        if subtitle_margin <= 0 or subtitle_margin == 96:
            normalized["subtitle_margin_v"] = 360
        seconds = normalized.get("seconds", 45)
        try:
            normalized["seconds"] = clamp_kids_seconds(int(seconds))
        except (TypeError, ValueError):
            normalized["seconds"] = 45
        normalized["dynamic_background"] = False
        if use_2d:
            normalized["dynamic_style"] = "native_frame_2d"
            normalized["animation_style"] = "cartoon_2d"
        else:
            normalized_style = requested_animation_style or "cartoon_3d_duo_cinematic"
            if normalized_style in {"cartoon_3d", "3d"}:
                normalized_style = "cartoon_3d_duo_cinematic"
            single_mode = requested_single_mode or normalized_style == "cartoon_3d_toddler_single"
            normalized["dynamic_style"] = "native_single_toddler_3d" if single_mode else "native_duo_cinematic_3d"
            normalized["animation_style"] = normalized_style
            normalized["single_protagonist"] = bool(single_mode)
            normalized["single_scene_locked"] = bool(single_mode)
            normalized["forbid_extra_characters"] = True
            normalized["forbid_clutter_props"] = True
            normalized["target_fps"] = 24 if single_mode else 30
            normalized["optical_flow_temporal_align"] = True
            normalized["layered_clean_rendering"] = True
            if not str(normalized.get("output_resolution", "")).strip():
                normalized["output_resolution"] = "1080p"
        normalized["native_frame_animation"] = True
        normalized["forbid_static_micro_motion"] = True
        normalized["force_bgm"] = True
        normalized["voice_character"] = "cute_child_cn"
        normalized["animation_hard_rules"] = list(KIDS_ANIMATION_HARD_RULES)
        return normalized

    render_mode = str(normalized.get("render_mode", "")).strip() or "subtitle_card"
    normalized["render_mode"] = render_mode
    if not str(normalized.get("tts_provider", "")).strip():
        normalized["tts_provider"] = "local_clone" if render_mode == "sadtalker" else "edge"
    if not str(normalized.get("output_resolution", "")).strip():
        normalized["output_resolution"] = "1080p"
    if render_mode == "sadtalker":
        use_cpu = str(normalized.get("avatar_use_cpu", "")).strip().lower() in {"1", "true", "yes", "on"}
        try:
            current_size = int(normalized.get("avatar_size") or 0)
        except (TypeError, ValueError):
            current_size = 0
        if use_cpu:
            if current_size <= 0 or current_size > 256:
                normalized["avatar_size"] = 256
        else:
            if current_size < 384:
                normalized["avatar_size"] = 512
            if not str(normalized.get("avatar_enhancer", "")).strip():
                normalized["avatar_enhancer"] = "gfpgan"
    else:
        if not str(normalized.get("edge_voice", "")).strip():
            normalized["edge_voice"] = "en-US-AriaNeural"
        seconds = normalized.get("seconds", 45)
        try:
            normalized["seconds"] = max(30, min(60, int(seconds)))
        except (TypeError, ValueError):
            normalized["seconds"] = 45
    return normalized


def _parse_style_tags(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[,\n;/|，、]+", raw) if item.strip()]


def _update_job_progress(job_id: str, *, percent: int, stage: str, message: str, status: str = "running") -> None:
    bounded = max(0, min(100, int(percent)))
    store.update_record(
        "jobs",
        job_id,
        {
            "status": status,
            "progress_percent": bounded,
            "progress_stage": stage,
            "progress_message": message,
            "updated_at": now_iso(),
        },
    )


def _run_job(job_id: str) -> None:
    job = _job_snapshot(job_id)
    render_mode = str((job.get("request") or {}).get("render_mode", ""))
    _update_job_progress(
        job_id,
        percent=6,
        stage="starting",
        message="Task started, preparing resources",
        status="running",
    )
    store.update_record("jobs", job_id, {"started_at": now_iso(), "error": ""})
    try:
        persona = _ensure_persona()
        progress_callback = lambda percent, stage, message: _update_job_progress(
            job_id,
            percent=percent,
            stage=stage,
            message=message,
            status="running",
        )
        if render_mode == "sadtalker":
            if SADTALKER_RENDER_LOCK.locked():
                _update_job_progress(
                    job_id,
                    percent=12,
                    stage="waiting_renderer",
                    message="Another portrait render is using the GPU. Waiting for renderer slot.",
                    status="running",
                )
            with SADTALKER_RENDER_LOCK:
                result = render_job(
                    job,
                    persona,
                    progress_callback=progress_callback,
                )
        else:
            result = render_job(
                job,
                persona,
                progress_callback=progress_callback,
            )
        result["updated_at"] = now_iso()
        store.update_record("jobs", job_id, result)
    except Exception as exc:  # noqa: BLE001
        store.update_record(
            "jobs",
            job_id,
            {
                "status": "failed",
                "completed_at": now_iso(),
                "updated_at": now_iso(),
                "progress_stage": "failed",
                "progress_message": "Task failed",
                "error": str(exc),
            },
        )


def _materialize_schedule_request(schedule_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    def updater(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        for schedule in state.get("schedules", []):
            if str(schedule.get("id")) != schedule_id:
                continue
            request_payload = _normalize_primary_portrait_request(dict(schedule.get("request") or {}))
            topic_pool = [item.strip() for item in schedule.get("topic_pool", []) if str(item).strip()]
            if topic_pool:
                next_index = int(schedule.get("next_topic_index", 0))
                request_payload["topic"] = topic_pool[next_index % len(topic_pool)]
                schedule["next_topic_index"] = (next_index + 1) % len(topic_pool)
            schedule["last_requested_at"] = now_iso()
            return dict(schedule), request_payload
        raise KeyError(f"Schedule not found: {schedule_id}")

    return store.mutate(updater)


def _run_schedule(schedule_id: str) -> None:
    try:
        schedule_record, request_payload = _materialize_schedule_request(schedule_id)
    except KeyError:
        return
    if not schedule_record.get("enabled"):
        return
    job = _build_job(request_payload, trigger="schedule", schedule_id=schedule_id)
    _run_job(job["id"])


def _safe_remove_children(directory: Path) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for item in directory.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            removed += 1
        except OSError:
            continue
    return removed


def _clear_human_distill_data() -> dict[str, Any]:
    output_ids_to_remove: list[str] = []

    def updater(state: dict[str, Any]) -> dict[str, Any]:
        previous_uploads = len(state.get("uploads", []))
        previous_analyses = len(state.get("analyses", []))
        removed_jobs = 0
        kept_jobs: list[dict[str, Any]] = []
        for job in state.get("jobs", []):
            request_payload = dict(job.get("request") or {})
            project_mode = str(request_payload.get("project_mode", "")).strip().lower()
            render_mode = str(request_payload.get("render_mode", "")).strip().lower()
            tts_provider = str(request_payload.get("tts_provider", "")).strip().lower()
            is_human = project_mode != "kids_cartoon" and (render_mode == "sadtalker" or tts_provider == "local_clone")
            if is_human:
                removed_jobs += 1
                job_id = str(job.get("id", "")).strip()
                if job_id:
                    output_ids_to_remove.append(job_id)
                continue
            kept_jobs.append(job)

        state["jobs"] = kept_jobs
        state["uploads"] = []
        state["analyses"] = []
        state["persona"] = default_persona()

        for schedule in state.get("schedules", []):
            request_payload = dict(schedule.get("request") or {})
            render_mode = str(request_payload.get("render_mode", "")).strip().lower()
            tts_provider = str(request_payload.get("tts_provider", "")).strip().lower()
            if render_mode == "sadtalker" or tts_provider == "local_clone":
                schedule["enabled"] = False
                schedule["updated_at"] = now_iso()

        avatar_settings = normalize_sadtalker_config(state.get("avatar_settings"))
        avatar_settings["enabled"] = False
        state["avatar_settings"] = avatar_settings

        return {
            "removed_jobs": removed_jobs,
            "removed_uploads": previous_uploads,
            "removed_analyses": previous_analyses,
        }

    result = store.mutate(updater)
    removed_outputs = 0
    for job_id in output_ids_to_remove:
        target = OUTPUTS_DIR / job_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed_outputs += 1

    removed_upload_files = _safe_remove_children(UPLOADS_DIR)
    removed_portraits = _safe_remove_children(PORTRAITS_DIR)
    removed_voice_refs = _safe_remove_children(VOICE_REFERENCES_DIR)

    return {
        **result,
        "removed_output_dirs": removed_outputs,
        "removed_upload_files": removed_upload_files,
        "removed_portraits": removed_portraits,
        "removed_voice_references": removed_voice_refs,
    }


scheduler = StudioScheduler(_run_schedule)
ai_trends_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _sync_ai_trends_scheduler() -> None:
    if not AI_TRENDS_ENABLED:
        return
    if not ai_trends_scheduler.running:
        ai_trends_scheduler.start()
    hour_text, minute_text = (AI_TRENDS_TIME.split(":", 1) + ["30"])[:2]
    ai_trends_scheduler.add_job(
        _run_ai_trends_collection,
        trigger=CronTrigger(hour=int(hour_text), minute=int(minute_text), timezone="Asia/Shanghai"),
        id="daily_ai_trends",
        replace_existing=True,
        misfire_grace_time=1800,
    )


def _run_ai_trends_collection(query: str | None = None) -> dict[str, Any]:
    report = collect_ai_trends(query=query)
    record = {
        "id": make_id("ai_trends"),
        **report,
    }
    store.add_record("ai_trends", record)
    return record


@app.on_event("startup")
def on_startup() -> None:
    ensure_cartoon_dirs()
    _ensure_persona()
    _recover_interrupted_jobs()
    _sync_scheduler()
    _sync_ai_trends_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler.shutdown()
    if ai_trends_scheduler.running:
        ai_trends_scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stocks/search")
def api_stock_search(q: str = Query("")) -> dict[str, Any]:
    try:
        return {"items": search_stocks(q)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"股票搜索暂时不可用：{str(exc)[:180]}") from exc


@app.get("/api/stocks/skills")
def api_stock_skills() -> dict[str, Any]:
    return {"items": list_stock_skills()}


@app.get("/api/stocks/watchlist")
def api_stock_watchlist() -> dict[str, Any]:
    return {"items": _stock_watchlist_with_quotes()}


def _stock_watchlist_with_quotes() -> list[dict[str, Any]]:
    items = _sorted(store.list_section("stock_watchlist"), key="updated_at")
    quotes: list[dict[str, Any]] = []
    for item in items:
        symbol = str(item.get("symbol") or "")
        try:
            quote = stock_quote(symbol)
            quotes.append({**item, "quote": quote, "position": _stock_position_snapshot(item, quote), "error": ""})
        except Exception as exc:
            quotes.append({**item, "quote": None, "position": {}, "error": str(exc)[:240]})
    return quotes


@app.post("/api/stocks/watchlist")
def api_upsert_stock_watchlist(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = normalize_stock_symbol(str(payload.get("symbol") or ""), str(payload.get("market") or ""))
    if not symbol:
        raise HTTPException(status_code=400, detail="股票代码不能为空。")
    now = now_iso()
    record = {
        "id": symbol,
        "symbol": symbol,
        "name": str(payload.get("name") or symbol).strip(),
        "market": str(payload.get("market") or "").strip() or "",
        "cost": payload.get("cost") or "",
        "shares": payload.get("shares") or "",
        "alert_high": payload.get("alert_high") or "",
        "alert_low": payload.get("alert_low") or "",
        "risk_level": str(payload.get("risk_level") or "balanced").strip() or "balanced",
        "holding_period": str(payload.get("holding_period") or "swing").strip() or "swing",
        "max_position_percent": payload.get("max_position_percent") or "20",
        "notes": str(payload.get("notes") or "").strip(),
        "created_at": now,
        "updated_at": now,
    }

    def updater(state: dict[str, Any]) -> dict[str, Any]:
        items = list(state.get("stock_watchlist", []))
        for index, item in enumerate(items):
            if str(item.get("symbol")) == symbol:
                record["created_at"] = item.get("created_at") or now
                items[index] = {**item, **record}
                state["stock_watchlist"] = items
                return items[index]
        items.append(record)
        state["stock_watchlist"] = items
        return record

    return store.mutate(updater)


@app.delete("/api/stocks/watchlist/{symbol}")
def api_delete_stock_watchlist(symbol: str) -> dict[str, Any]:
    normalized = normalize_stock_symbol(symbol)

    def updater(state: dict[str, Any]) -> int:
        items = list(state.get("stock_watchlist", []))
        before = len(items)
        state["stock_watchlist"] = [item for item in items if str(item.get("symbol")) != normalized]
        return before - len(state["stock_watchlist"])

    return {"deleted": normalized, "removed": store.mutate(updater)}


def _stock_position_snapshot(item: dict[str, Any], quote: dict[str, Any]) -> dict[str, Any]:
    price = _float_or_none(quote.get("price"))
    cost = _float_or_none(item.get("cost"))
    shares = _float_or_none(item.get("shares"))
    alert_high = _float_or_none(item.get("alert_high"))
    alert_low = _float_or_none(item.get("alert_low"))
    market_value = price * shares if price is not None and shares is not None else None
    cost_value = cost * shares if cost is not None and shares is not None else None
    profit = market_value - cost_value if market_value is not None and cost_value is not None else None
    profit_percent = (profit / cost_value * 100) if profit is not None and cost_value else None
    alerts: list[str] = []
    if price is not None and alert_high is not None and price >= alert_high:
        alerts.append(f"已触及上方预警 {alert_high}")
    if price is not None and alert_low is not None and price <= alert_low:
        alerts.append(f"已触及下方预警 {alert_low}")
    if profit_percent is not None and profit_percent <= -8:
        alerts.append("持仓浮亏超过 8%，建议复核止损纪律")
    return {
        "market_value": round(market_value, 2) if market_value is not None else None,
        "profit": round(profit, 2) if profit is not None else None,
        "profit_percent": round(profit_percent, 2) if profit_percent is not None else None,
        "risk_level": str(item.get("risk_level") or "balanced"),
        "holding_period": str(item.get("holding_period") or "swing"),
        "max_position_percent": _float_or_none(item.get("max_position_percent")),
        "alerts": alerts,
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@app.get("/api/stocks/quote")
def api_stock_quote(symbol: str = Query("")) -> dict[str, Any]:
    if not symbol:
        raise HTTPException(status_code=400, detail="股票代码不能为空。")
    try:
        return stock_quote(symbol)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"行情源暂时不可用：{str(exc)[:220]}") from exc


@app.get("/api/stocks/market")
def api_stock_market_overview() -> dict[str, Any]:
    indexes = [
        {"symbol": "^GSPC", "name": "标普500"},
        {"symbol": "^IXIC", "name": "纳斯达克"},
        {"symbol": "^DJI", "name": "道琼斯"},
        {"symbol": "000001.SS", "name": "上证指数"},
        {"symbol": "399001.SZ", "name": "深证成指"},
        {"symbol": "^HSI", "name": "恒生指数"},
    ]
    items: list[dict[str, Any]] = []
    for item in indexes:
        try:
            quote = stock_quote(item["symbol"])
            items.append({**item, **quote, "error": ""})
        except Exception as exc:
            items.append({**item, "error": str(exc)[:180]})
    valid_changes = [float(item.get("change_percent") or 0) for item in items if not item.get("error")]
    average_change = sum(valid_changes) / len(valid_changes) if valid_changes else 0
    if average_change >= 0.6:
        mood = "偏积极"
    elif average_change <= -0.6:
        mood = "偏谨慎"
    else:
        mood = "中性分化"
    return {"items": items, "mood": mood, "average_change": round(average_change, 2), "fetched_at": now_iso()}


@app.post("/api/stocks/analyze")
def api_stock_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="股票代码不能为空。")
    try:
        result = analyze_stock(symbol, question=str(payload.get("question") or "").strip(), position=payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"暂时无法取得足够行情数据：{str(exc)[:220]}") from exc
    record = {
        "id": make_id("stock_analysis"),
        "created_at": now_iso(),
        "symbol": result["quote"]["symbol"],
        "name": result["quote"]["name"],
        "score": result["score"],
        "stance": result["stance"],
        "report": result["report"],
    }
    store.add_record("stock_analysis_history", record)
    return result


@app.post("/api/stocks/skills/run")
def api_run_stock_skill(payload: dict[str, Any]) -> dict[str, Any]:
    skill_id = str(payload.get("skill_id") or "").strip()
    if not skill_id:
        raise HTTPException(status_code=400, detail="Stock Skill 不能为空。")
    symbol = str(payload.get("symbol") or "").strip()
    question = str(payload.get("question") or "").strip()
    latest_analysis = payload.get("latest_analysis") if isinstance(payload.get("latest_analysis"), dict) else None
    watchlist = _stock_watchlist_with_quotes()
    try:
        result = run_stock_skill(
            skill_id,
            symbol=symbol,
            question=question,
            watchlist=watchlist,
            latest_analysis=latest_analysis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record = {
        "id": make_id("stock_skill"),
        "created_at": now_iso(),
        "skill_id": result.get("skill_id"),
        "symbol": result.get("symbol") or symbol,
        "title": result.get("title"),
        "report": result.get("report"),
        "cards": result.get("cards") or [],
        "items": result.get("items") or [],
    }
    store.add_record("stock_skill_runs", record)
    return {**result, "run_id": record["id"], "created_at": record["created_at"]}


@app.get("/api/stocks/analysis-history")
def api_stock_analysis_history(symbol: str = Query("")) -> dict[str, Any]:
    normalized = normalize_stock_symbol(symbol) if symbol else ""
    items = _sorted(store.list_section("stock_analysis_history"))
    if normalized:
        items = [item for item in items if str(item.get("symbol")) == normalized]
    return {"items": items[:50]}


@app.get("/api/stocks/skill-runs")
def api_stock_skill_runs() -> dict[str, Any]:
    return {"items": _sorted(store.list_section("stock_skill_runs"))[:50]}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    uploads = _sorted(store.list_section("uploads"))
    jobs = _sorted(store.list_section("jobs"))
    analyses = _sorted(store.list_section("analyses"))
    schedules = [_decorate_schedule(item) for item in _sorted(store.list_section("schedules"))]
    return {
        "stats": {
            "upload_count": len(uploads),
            "analysis_count": len(analyses),
            "job_count": len(jobs),
            "completed_jobs": sum(1 for item in jobs if item.get("status") == "completed"),
            "scheduled_jobs": sum(1 for item in schedules if item.get("enabled")),
        },
        "persona": _ensure_persona(),
        "avatar_settings": _get_avatar_settings(),
        "recent_uploads": uploads[:5],
        "recent_jobs": jobs[:6],
        "recent_analyses": analyses[:5],
        "schedules": schedules,
    }


def _get_avatar_settings() -> dict[str, Any]:
    config = normalize_sadtalker_config(store.get_state().get("avatar_settings"))
    config["status"] = detect_sadtalker_status(config)
    return config


def _resolve_download_target(media_path: str) -> Path:
    prefix = "/studio-files/"
    if not media_path.startswith(prefix):
        raise HTTPException(status_code=400, detail="Only studio files can be downloaded.")
    relative = media_path[len(prefix) :].lstrip("/\\")
    target = (STUDIO_DIR / Path(relative)).resolve()
    studio_root = STUDIO_DIR.resolve()
    if studio_root != target and studio_root not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid download path.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return target


@app.get("/api/uploads")
def list_uploads() -> list[dict[str, Any]]:
    return _sorted(store.list_section("uploads"))


@app.get("/api/analyses")
def list_analyses() -> list[dict[str, Any]]:
    return _sorted(store.list_section("analyses"))


@app.get("/api/download")
def download_file(path: str = Query(...)) -> FileResponse:
    target = _resolve_download_target(path)
    return FileResponse(path=str(target), filename=target.name)


@app.post("/api/uploads/videos")
@app.post("/api/uploads/media")
async def upload_media(
    files: list[UploadFile] = File(...),
    transcript_text: str = Form(""),
    notes: str = Form(""),
    style_tag: str = Form(""),
    style_tags: str = Form(""),
    persona_name: str = Form("My Digital Twin"),
    whisper_model: str = Form("small"),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one media file is required.")

    created_uploads: list[dict[str, Any]] = []
    created_analyses: list[dict[str, Any]] = []
    normalized_style_tag = str(style_tag or "").strip()
    parsed_style_tags = _parse_style_tags(style_tags)

    for index, file in enumerate(files):
        upload_id = make_id("upload")
        filename = file.filename or f"{upload_id}.bin"
        suffix = Path(filename).suffix
        content_type = str(file.content_type or "").lower()
        if not suffix:
            if content_type.startswith("video/"):
                suffix = ".mp4"
            elif content_type.startswith("image/"):
                suffix = ".jpg"
            else:
                suffix = ".bin"
        saved_path = UPLOADS_DIR / f"{upload_id}{suffix.lower()}"

        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        await file.close()
        media_kind = "image" if content_type.startswith("image/") else "video" if content_type.startswith("video/") else detect_media_kind(saved_path)
        per_file_style_tag = parsed_style_tags[index] if index < len(parsed_style_tags) else normalized_style_tag

        analysis_payload = analyze_media_file(
            saved_path,
            transcript_text=transcript_text if len(files) == 1 else "",
            notes=notes,
            whisper_model=whisper_model,
            media_kind_hint=media_kind,
        )
        analysis_record = {
            "id": make_id("analysis"),
            "upload_id": upload_id,
            "created_at": now_iso(),
            "media_kind": media_kind,
            "style_tag": per_file_style_tag,
            **analysis_payload,
        }
        upload_record = {
            "id": upload_id,
            "filename": filename,
            "created_at": now_iso(),
            "saved_path": str(saved_path),
            "media_url": to_media_url(saved_path),
            "analysis_id": analysis_record["id"],
            "notes": notes,
            "media_kind": media_kind,
            "style_tag": per_file_style_tag,
            "transcript_text": analysis_payload["transcript_text"],
            "portrait_path": ((analysis_payload.get("reference_assets") or {}).get("portrait_path", "")),
            "portrait_url": ((analysis_payload.get("reference_assets") or {}).get("portrait_url", "")),
            "voice_reference_path": ((analysis_payload.get("reference_assets") or {}).get("voice_reference_path", "")),
            "voice_reference_url": ((analysis_payload.get("reference_assets") or {}).get("voice_reference_url", "")),
        }
        store.add_record("uploads", upload_record)
        store.add_record("analyses", analysis_record)
        created_uploads.append(upload_record)
        created_analyses.append(analysis_record)

    persona = _rebuild_persona(persona_name)
    return {"uploads": created_uploads, "analyses": created_analyses, "persona": persona}


@app.get("/api/persona")
def get_persona() -> dict[str, Any]:
    return _ensure_persona()


@app.post("/api/persona/distill")
def distill_persona_endpoint(payload: DistillRequest) -> dict[str, Any]:
    return _rebuild_persona(payload.name)


@app.put("/api/persona")
def update_persona(payload: PersonaUpdate) -> dict[str, Any]:
    persona = _ensure_persona()
    if payload.name is not None:
        persona["name"] = payload.name
    if payload.hook_candidates is not None:
        persona["hook_candidates"] = payload.hook_candidates
        persona["speech_profile"]["hook_candidates"] = payload.hook_candidates
    if payload.cta_candidates is not None:
        persona["cta_candidates"] = payload.cta_candidates
        persona["speech_profile"]["cta_candidates"] = payload.cta_candidates
    if payload.signature_terms is not None:
        persona["signature_terms"] = payload.signature_terms
        persona["speech_profile"]["signature_terms"] = payload.signature_terms
    if payload.prompt_block is not None:
        persona["prompt_block"] = payload.prompt_block
    if payload.content_modes is not None:
        persona["content_modes"] = payload.content_modes
    persona["updated_at"] = now_iso()
    store.set_persona(persona)
    return _attach_reference_assets(persona)


@app.get("/api/avatar/sadtalker")
def get_sadtalker_settings() -> dict[str, Any]:
    return _get_avatar_settings()


@app.put("/api/avatar/sadtalker")
def update_sadtalker_settings(payload: SadTalkerConfigPayload) -> dict[str, Any]:
    config = normalize_sadtalker_config(payload.model_dump())
    store.mutate(lambda state: state.__setitem__("avatar_settings", config))
    return _get_avatar_settings()


@app.post("/api/generate")
def create_generation(payload: GenerateRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    job = _build_job(_normalize_primary_portrait_request(payload.model_dump()), trigger="manual")
    background_tasks.add_task(_run_job, job["id"])
    return job


@app.post("/api/kids/preview-script")
def preview_kids_script(payload: KidsScriptPreviewRequest) -> dict[str, Any]:
    seconds = clamp_kids_seconds(payload.seconds)
    script_source = "local_rules"
    script_ai: dict[str, Any] = {}
    try:
        if str(payload.script_provider or "").strip().lower() not in {"local", "local_rules", "rules"}:
            script_ai = generate_kids_script_with_ai(
                provider=payload.script_provider,
                topic=payload.topic,
                seconds=seconds,
                prompt_hint=payload.prompt_hint,
                content_mode=normalize_content_mode(payload.content_mode),
                learning_goal=payload.learning_goal,
            )
            script = script_ai["script"]
            script_source = f"third_party_ai:{script_ai.get('provider', '')}"
        else:
            raise RuntimeError("Local rules selected.")
    except Exception as exc:
        script = build_kids_english_script(
            topic=payload.topic,
            seconds=seconds,
            prompt_hint=payload.prompt_hint,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        )
        script_ai = {"fallback_reason": str(exc)[:500]}
    return {
        "topic": payload.topic,
        "seconds": seconds,
        "script": script,
        "script_source": script_source,
        "script_ai": script_ai,
        "word_count": len([token for token in re.split(r"\s+", script) if token]),
        "content_mode": normalize_content_mode(payload.content_mode),
        "learning_goal": payload.learning_goal,
        "quality": analyze_kids_script_quality(
            script,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
        "storyboard": build_kids_storyboard(
            script,
            seconds,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
        "hard_rules": list(KIDS_ANIMATION_HARD_RULES),
        "character_design": dict(KIDS_CHARACTER_DESIGN),
        "reference_style_contract": dict(REFERENCE_STYLE_CONTRACT),
        "visual_pipeline": {
            "recommended": "upload_reference_image_then_generate_keyframes_then_video",
            "current_local_renderer": "preview_fallback_only",
            "reference_image_required_for_template_fidelity": True,
        },
    }


@app.post("/api/kids/upload-image")
async def upload_kids_image(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = str(file.filename or "").strip() or "cartoon.png"
    suffix = Path(filename).suffix.lower()
    target = make_uploaded_image_path(suffix)
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    await file.close()
    return {
        "path": str(target),
        "url": to_media_url(target),
        "filename": filename,
    }


def _resolve_kids_background(uploaded_image_path: str, auto_generate_image: bool) -> str:
    # Kids reference images are character identity inputs, not background plates.
    # Keep this as an empty background so the renderer/model uses generated scenes.
    return ""


def _resolve_kids_reference_image(reference_image_path: str, uploaded_image_path: str = "") -> str:
    raw_path = str(reference_image_path or "").strip() or str(uploaded_image_path or "").strip()
    image_path = Path(raw_path).expanduser()
    if image_path and image_path.exists() and image_path.is_file():
        return str(image_path.resolve())
    return ""


def _resolve_kids_reference_image_url(reference_image_path: str) -> str:
    raw = str(reference_image_path or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw
    public_base = os.getenv("CREATOR_STUDIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base:
        return ""
    image_path = Path(raw).expanduser()
    if image_path and image_path.exists() and image_path.is_file():
        try:
            return f"{public_base}{to_media_url(image_path)}"
        except ValueError:
            return ""
    return ""


def _extract_kids_voice_sample(source_path: Path, role: str) -> dict[str, Any]:
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        try:
            import ai_voice_video_generator as avvg

            ffmpeg_exe = avvg.resolve_binary("ffmpeg")
        except Exception:
            ffmpeg_exe = ""
    if not ffmpeg_exe:
        raise HTTPException(status_code=500, detail="ffmpeg is required to extract character voice audio.")
    safe_role = "maodou" if role == "maodou" else "peanut"
    target = VOICE_REFERENCES_DIR / f"kids_{safe_role}_{make_id('voice')}.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-t",
            "30",
            str(target),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 or not target.exists() or target.stat().st_size < 1024:
        stderr = "\n".join(result.stderr.splitlines()[-12:])
        raise HTTPException(status_code=400, detail=stderr or "Failed to extract character voice audio.")
    return {
        "role": safe_role,
        "path": str(target),
        "url": to_media_url(target),
        "source_path": str(source_path),
    }


@app.get("/api/ai-trends")
def list_ai_trends() -> list[dict[str, Any]]:
    return _sorted(store.list_section("ai_trends"))[:14]


@app.post("/api/ai-trends/refresh")
async def refresh_ai_trends(request: Request) -> dict[str, Any]:
    query = ""
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            query = str(payload.get("query") or "").strip()
    except Exception:  # noqa: BLE001
        query = ""
    return _run_ai_trends_collection(query=query or None)


@app.post("/api/ai-trends/notebooklm-package")
def create_notebooklm_package() -> dict[str, Any]:
    latest = _sorted(store.list_section("ai_trends"))[:1]
    package = build_notebooklm_import_package(latest[0] if latest else None)
    archive = archive_markdown_to_obsidian(
        title=f"NotebookLM AI 资讯导入包 {str(package.get('title') or '')[:28]}",
        body=str(package.get("body") or ""),
        source="creator_studio_notebooklm_package",
    )
    record = {
        "id": make_id("notebooklm_package"),
        "created_at": now_iso(),
        "source_type": "ai_trends_notebooklm",
        "package": {key: value for key, value in package.items() if key != "body"},
        "archive": archive,
    }
    store.add_record("obsidian_archives", record)
    return {"status": "ok", **record}


@app.post("/api/ai-trends/{trend_id}/distribution")
def prepare_ai_trend_distribution(
    trend_id: str,
    payload: TrendDistributionRequest = TrendDistributionRequest(),
) -> dict[str, Any]:
    trend = store.find_record("ai_trends", trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="实时资讯记录不存在。")
    try:
        record = prepare_trend_distribution_package(
            trend,
            script=payload.script,
            question=payload.question,
            title=payload.title,
            author=payload.author,
            hashtags=payload.hashtags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.add_record("distribution_tasks", record)
    return record


@app.post("/api/ai-trends/interview/followups")
async def create_ai_trend_interview_followups(request: Request) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    try:
        raw_payload = await request.json()
        if isinstance(raw_payload, dict):
            payload = raw_payload
    except Exception:  # noqa: BLE001
        payload = {}
    latest = _sorted(store.list_section("ai_trends"))[:1]
    report = latest[0] if latest else collect_ai_trends()
    question = str(payload.get("question") or "").strip()
    answer = str(payload.get("answer") or "").strip()
    depth = int(payload.get("depth") or 1)
    if not question:
        raise HTTPException(status_code=400, detail="请先选择一个想继续探讨的问题。")
    followups = build_trend_interview_followups(report, question=question, answer=answer, depth=depth)
    return {
        "status": "ok",
        "base_question": question,
        "answer": answer,
        "depth": depth,
        "followups": followups,
    }


@app.post("/api/ai-trends/interview/transcribe")
async def transcribe_ai_trend_interview_voice(file: UploadFile = File(...)) -> dict[str, Any]:
    content_type = str(file.content_type or "").lower()
    filename = str(file.filename or "").strip() or "interview_voice.webm"
    suffix = Path(filename).suffix.lower() or ".webm"
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".oga", ".aac", ".mp4"}:
        raise HTTPException(status_code=400, detail="请上传常见音频格式：webm、wav、mp3、m4a、ogg。")
    if content_type and not (content_type.startswith("audio/") or content_type.startswith("video/") or content_type == "application/octet-stream"):
        raise HTTPException(status_code=400, detail="上传文件不是音频。")

    voice_dir = STUDIO_DIR / "interview_voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    target = voice_dir / f"{make_id('interview_voice')}{suffix}"
    try:
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    transcript, note = transcribe_audio(target, model_name=os.getenv("INTERVIEW_VOICE_WHISPER_MODEL", WECHAT_VOICE_WHISPER_MODEL))
    transcript = _normalize_chinese_text(re.sub(r"\s+", " ", transcript).strip())
    status = "ok" if transcript else "transcribe_failed"
    return {
        "status": status,
        "transcript": transcript,
        "note": note,
        "path": str(target),
        "url": to_media_url(target),
    }


@app.post("/api/archive/obsidian")
def archive_copy_to_obsidian(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "Creator Studio 文案").strip()
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="归档内容不能为空。")
    result = archive_markdown_to_obsidian(title=title, body=body, source="creator_studio_manual")
    record = {"id": make_id("obsidian_archive"), "created_at": now_iso(), "source_type": "manual", **result}
    store.add_record("obsidian_archives", record)
    return {"status": "ok", "archive": record}


@app.post("/api/kids/draft-review")
def draft_review_kids_script(payload: KidsScriptPreviewRequest) -> dict[str, Any]:
    seconds = clamp_kids_seconds(payload.seconds)
    try:
        if str(payload.script_provider or "").strip().lower() in {"local", "local_rules", "rules", "zhipu"}:
            raise RuntimeError("Reviewed draft requires Gemini or MiniMax.")
        script_ai = generate_reviewed_draft(
            draft_provider=payload.script_provider,
            topic=payload.topic,
            seconds=seconds,
            prompt_hint=payload.prompt_hint,
            content_mode=normalize_content_mode(payload.content_mode),
            learning_goal=payload.learning_goal,
        )
        script = script_ai["script"]
        script_source = f"third_party_ai:{script_ai.get('provider', '')}"
    except Exception as exc:
        script = build_kids_english_script(
            topic=payload.topic,
            seconds=seconds,
            prompt_hint=payload.prompt_hint,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        )
        script_ai = {"fallback_reason": str(exc)[:500]}
        script_source = "local_rules"
    return {
        "topic": payload.topic,
        "seconds": seconds,
        "script": script,
        "script_source": script_source,
        "script_ai": script_ai,
        "content_mode": normalize_content_mode(payload.content_mode),
        "learning_goal": payload.learning_goal,
        "quality": analyze_kids_script_quality(
            script,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
        "storyboard": build_kids_storyboard(
            script,
            seconds,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
    }


@app.post("/api/kids/revise-script")
def revise_kids_script(payload: KidsScriptReviseRequest) -> dict[str, Any]:
    draft_script = normalize_kids_script_text(payload.draft_script)
    if not draft_script:
        raise HTTPException(status_code=400, detail="初稿为空，无法二次修改。")
    seconds = clamp_kids_seconds(payload.seconds)
    try:
        script_ai = revise_script_with_feedback(
            revision_provider=payload.script_provider,
            draft_script=draft_script,
            review=payload.review,
            human_feedback=payload.human_feedback,
            topic=payload.topic,
            seconds=seconds,
            prompt_hint=payload.prompt_hint,
            content_mode=normalize_content_mode(payload.content_mode),
            learning_goal=payload.learning_goal,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_script_ai_error_detail(
                requested_provider=payload.script_provider,
                stage="revision_or_final_review",
                message=str(exc),
            ),
        ) from exc
    script = script_ai["script"]
    return {
        "topic": payload.topic,
        "seconds": seconds,
        "script": script,
        "script_source": f"third_party_ai:{script_ai.get('provider', '')}",
        "script_ai": script_ai,
        "content_mode": normalize_content_mode(payload.content_mode),
        "learning_goal": payload.learning_goal,
        "quality": analyze_kids_script_quality(
            script,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
        "storyboard": build_kids_storyboard(
            script,
            seconds,
            content_mode=payload.content_mode,
            learning_goal=payload.learning_goal,
        ),
    }


@app.post("/api/integrations/wechat/material")
def receive_wechat_material(payload: WeChatMaterialRequest) -> dict[str, Any]:
    material_text = _normalize_chinese_text(re.sub(r"\s+", " ", str(payload.text or "")).strip())
    if not material_text:
        raise HTTPException(status_code=400, detail="微信素材不能为空。")
    record = {
        "id": make_id("wechat_material"),
        "created_at": now_iso(),
        "source_user": payload.source_user,
        "source_message_id": payload.source_message_id,
        "source_type": payload.source_type,
        "text": material_text,
        "content_mode": normalize_content_mode(payload.content_mode),
        "script_provider": payload.script_provider,
        "status": "received",
    }
    store.add_record("wechat_materials", record)
    preview: dict[str, Any] | None = None
    if payload.auto_preview:
        try:
            preview = preview_kids_script(
                KidsScriptPreviewRequest(
                    topic=material_text,
                    seconds=payload.seconds,
                    prompt_hint=payload.prompt_hint,
                    content_mode=payload.content_mode,
                    learning_goal=payload.learning_goal,
                    script_provider=payload.script_provider,
                )
            )
            reply = _format_wechat_copy_reply(preview, material_text=material_text)
            store.update_record(
                "wechat_materials",
                record["id"],
                {
                    "status": "preview_generated",
                    "script_source": preview.get("script_source"),
                    "script": preview.get("script"),
                    "storyboard": preview.get("storyboard"),
                    "quality": preview.get("quality"),
                    "script_ai": preview.get("script_ai"),
                    "reply": reply,
                    "updated_at": now_iso(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            reply = _format_wechat_copy_reply(preview, material_text=material_text)
            store.update_record(
                "wechat_materials",
                record["id"],
                {
                    "status": "preview_failed",
                    "error": str(exc),
                    "reply": reply,
                    "updated_at": now_iso(),
                },
            )
    else:
        reply = _format_wechat_copy_reply(preview, material_text=material_text)
    return {
        "status": "ok",
        "material_id": record["id"],
        "material": record,
        "preview": preview,
        "wechat_reply": reply,
        "next_step": "后续微信机器人只需要把消息文本 POST 到本接口，即可进入现有文案生成流水线。",
    }


@app.get("/api/integrations/wechat/entry")
def get_wechat_entry() -> dict[str, Any]:
    public_base = os.getenv("CREATOR_STUDIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    callback_path = "/api/integrations/wechat/callback"
    qr_path = "/api/integrations/wechat/qr"
    integration_settings = store.get_state().get("integration_settings") or {}
    saved_thumb = str(integration_settings.get("wechat_thumb_media_id") or "").strip()
    return {
        "status": "ok",
        "account_name": WECHAT_ACCOUNT_NAME,
        "qr_image_url": WECHAT_QR_IMAGE_URL,
        "qr_proxy_url": f"{public_base}{qr_path}" if public_base else qr_path,
        "callback_url": f"{public_base}{callback_path}" if public_base else callback_path,
        "voice_supported": True,
        "voice_requirement": "微信后台需要开启语音识别，语音消息回调里才会带 Recognition 文本。",
        "voice_fallback_enabled": WECHAT_VOICE_FALLBACK_TRANSCRIBE,
        "voice_fallback_configured": bool(WECHAT_APP_ID and WECHAT_APP_SECRET),
        "draft_api_configured": bool(WECHAT_APP_ID and WECHAT_APP_SECRET),
        "cover_configured": bool(saved_thumb or os.getenv("WECHAT_THUMB_MEDIA_ID", "").strip()),
    }


@app.post("/api/integrations/wechat/cover")
async def upload_official_account_cover(file: UploadFile = File(...)) -> dict[str, Any]:
    content_type = str(file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传 JPG、PNG 等图片文件。")
    body = await file.read()
    if len(body) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="封面图片不能超过 10MB。")
    try:
        result = upload_wechat_cover(
            filename=str(file.filename or "cover.jpg"),
            content_type=content_type,
            body=body,
            get_access_token=_get_wechat_access_token,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:500]) from exc

    def updater(state: dict[str, Any]) -> dict[str, Any]:
        settings = dict(state.get("integration_settings") or {})
        settings["wechat_thumb_media_id"] = result["media_id"]
        settings["wechat_cover_url"] = result.get("url", "")
        settings["updated_at"] = now_iso()
        state["integration_settings"] = settings
        return settings

    settings = store.mutate(updater)
    return {"status": "ok", **result, "settings": settings}


@app.get("/api/integrations/wechat/qr")
def get_wechat_qr() -> Response:
    if not WECHAT_QR_IMAGE_URL:
        raise HTTPException(status_code=404, detail="WECHAT_QR_IMAGE_URL is not configured.")
    try:
        request = urllib.request.Request(
            WECHAT_QR_IMAGE_URL,
            headers={
                "User-Agent": "Mozilla/5.0 CreatorStudio/1.0",
                "Referer": "https://mp.weixin.qq.com/",
            },
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type") or "image/jpeg"
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch WeChat QR image: {exc}") from exc
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/api/integrations/wechat/materials")
def list_wechat_materials() -> list[dict[str, Any]]:
    return _sorted(store.list_section("wechat_materials"))[:30]


@app.delete("/api/integrations/wechat/materials")
def clear_wechat_materials(status: str = Query("all")) -> dict[str, Any]:
    status_filter = str(status or "all").strip()

    def updater(state: dict[str, Any]) -> dict[str, Any]:
        existing = list(state.get("wechat_materials", []))
        if status_filter == "all":
            state["wechat_materials"] = []
            removed = len(existing)
        else:
            kept = [item for item in existing if str(item.get("status")) != status_filter]
            removed = len(existing) - len(kept)
            state["wechat_materials"] = kept
        return {"removed": removed, "remaining": len(state.get("wechat_materials", []))}

    return {"status": "ok", **store.mutate(updater)}


@app.delete("/api/integrations/wechat/materials/{material_id}")
def delete_wechat_material(material_id: str) -> dict[str, Any]:
    def updater(state: dict[str, Any]) -> dict[str, Any]:
        existing = list(state.get("wechat_materials", []))
        kept = [item for item in existing if str(item.get("id")) != material_id]
        state["wechat_materials"] = kept
        return {"removed": len(existing) - len(kept), "remaining": len(kept)}

    result = store.mutate(updater)
    if not result.get("removed"):
        raise HTTPException(status_code=404, detail="微信素材不存在。")
    return {"status": "ok", **result}


@app.get("/api/integrations/wechat/callback-events")
def list_wechat_callback_events() -> list[dict[str, Any]]:
    return _sorted(store.list_section("wechat_callback_events"))[:50]


@app.delete("/api/integrations/wechat/callback-events")
def clear_wechat_callback_events() -> dict[str, Any]:
    def updater(state: dict[str, Any]) -> dict[str, Any]:
        existing = list(state.get("wechat_callback_events", []))
        state["wechat_callback_events"] = []
        return {"removed": len(existing), "remaining": 0}

    return {"status": "ok", **store.mutate(updater)}


@app.post("/api/integrations/wechat/materials/{material_id}/generate")
def generate_wechat_material_script(material_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    material = store.find_record("wechat_materials", material_id)
    if not material:
        raise HTTPException(status_code=404, detail="微信素材不存在。")
    material_text = str(material.get("text", "")).strip()
    if not material_text:
        raise HTTPException(status_code=400, detail="微信素材文本为空。")
    content_mode = normalize_content_mode(str(payload.get("content_mode") or material.get("content_mode") or "working_mom"))
    script_provider = str(payload.get("script_provider") or material.get("script_provider") or "gemini_minimax")
    prompt_hint = str(payload.get("prompt_hint") or "根据选择的模式重写成适合视频号发布的文案。")
    learning_goal = str(payload.get("learning_goal") or "把微信发来的真实素材转成高共情、可落地的 AI 提效方案")
    seconds = int(payload.get("seconds") or 45)
    preview = preview_kids_script(
        KidsScriptPreviewRequest(
            topic=material_text,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
            script_provider=script_provider,
        )
    )
    patch = {
        "status": "preview_generated",
        "content_mode": content_mode,
        "script_provider": script_provider,
        "animation_style": str(payload.get("animation_style") or material.get("animation_style") or ""),
        "use_my_real_voice": bool(payload.get("use_my_real_voice", material.get("use_my_real_voice", True))),
        "script_source": preview.get("script_source"),
        "script": preview.get("script"),
        "storyboard": preview.get("storyboard"),
        "quality": preview.get("quality"),
        "script_ai": preview.get("script_ai"),
        "reply": _format_wechat_copy_reply(preview, material_text=material_text),
        "updated_at": now_iso(),
    }
    return store.update_record("wechat_materials", material_id, patch)


@app.post("/api/integrations/wechat/materials/{material_id}/distribution")
def prepare_wechat_material_distribution(
    material_id: str,
    payload: DistributionPrepareRequest = DistributionPrepareRequest(),
) -> dict[str, Any]:
    material = store.find_record("wechat_materials", material_id)
    if not material:
        raise HTTPException(status_code=404, detail="微信素材不存在。")
    try:
        record = prepare_material_distribution_package(
            material,
            title=payload.title,
            summary=payload.summary,
            author=payload.author,
            hashtags=payload.hashtags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.add_record("distribution_tasks", record)
    store.update_record(
        "wechat_materials",
        material_id,
        {"distribution_task_id": record["id"], "updated_at": now_iso()},
    )
    return record


@app.post("/api/integrations/wechat/materials/{material_id}/archive")
def archive_wechat_material(material_id: str) -> dict[str, Any]:
    material = store.find_record("wechat_materials", material_id)
    if not material:
        raise HTTPException(status_code=404, detail="微信素材不存在。")
    script = str(material.get("script") or "").strip()
    if not script:
        raise HTTPException(status_code=400, detail="这条微信素材还没有生成文案，不能归档。")
    title = str(material.get("text") or "微信素材文案")[:50]
    result = archive_markdown_to_obsidian(
        title=title,
        body=f"## 原始素材\n\n{material.get('text', '')}\n\n## 生成文案\n\n{script}\n",
        source="creator_studio_wechat",
    )
    archive_record = {
        "id": make_id("obsidian_archive"),
        "created_at": now_iso(),
        "source_type": "wechat_material",
        "source_id": material_id,
        **result,
    }
    store.add_record("obsidian_archives", archive_record)
    store.update_record("wechat_materials", material_id, {"archived_at": now_iso(), "archive": archive_record})
    return {"status": "ok", "archive": archive_record}


@app.get("/api/integrations/wechat/callback")
def verify_wechat_callback(
    signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
) -> Response:
    if not _wechat_signature_ok(signature, timestamp, nonce):
        raise HTTPException(status_code=403, detail="Invalid WeChat signature.")
    return Response(content=echostr, media_type="text/plain")


@app.post("/api/integrations/wechat/callback")
async def receive_wechat_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
) -> Response:
    if WECHAT_CALLBACK_TOKEN and not _wechat_signature_ok(signature, timestamp, nonce):
        _record_wechat_callback_event(
            {"MsgType": "signature_check"},
            action="rejected",
            reason="签名校验失败，请检查微信测试号 Token 是否和 .env 的 WECHAT_CALLBACK_TOKEN 一致。",
        )
        raise HTTPException(status_code=403, detail="Invalid WeChat signature.")
    raw_body = await request.body()
    try:
        message = _parse_wechat_xml(raw_body)
    except Exception:
        _record_wechat_callback_event(
            {"MsgType": "invalid_xml"},
            action="rejected",
            reason=f"微信 XML 解析失败，body_length={len(raw_body)}。",
        )
        raise HTTPException(status_code=400, detail="Invalid WeChat XML.")
    msg_type = message.get("MsgType", "")
    to_user = message.get("FromUserName", "")
    from_user = message.get("ToUserName", "")
    content = _normalize_chinese_text(re.sub(r"\s+", " ", message.get("Content", "")).strip())
    recognition = _normalize_chinese_text(re.sub(r"\s+", " ", message.get("Recognition", "")).strip())
    msg_id = message.get("MsgId", "")
    material_text = content if msg_type == "text" else recognition if msg_type == "voice" else ""
    voice_fallback_note = ""
    if msg_type == "voice" and not material_text:
        material_text, voice_fallback_note = _transcribe_wechat_voice_media(message)
    if msg_type == "voice" and not material_text:
        _record_wechat_callback_event(
            message,
            action="ignored",
            reason=voice_fallback_note or "已收到语音，但微信回调没有 Recognition 识别文本；请在微信后台开启语音识别。",
        )
        reply = (
            "语音已收到，但微信没有返回识别文字，本地兜底转写也没有成功。\n"
            "请确认：1）语音识别已开启；2）重新关注测试号后再发；3）如需兜底下载转写，请配置 WECHAT_APP_ID 和 WECHAT_APP_SECRET。"
        )
        return Response(
            content=_wechat_text_response(to_user=to_user, from_user=from_user, content=reply),
            media_type="application/xml",
        )
    if msg_type not in {"text", "voice"} or not material_text:
        _record_wechat_callback_event(
            message,
            action="ignored",
            reason="已收到微信回调，但当前只把文字或带识别文本的语音写入素材箱。",
        )
        reply = "我现在支持文字素材，也支持开启语音识别后的语音素材。你可以直接说：今天发生了什么、你的感想、剪辑心得。"
        return Response(
            content=_wechat_text_response(to_user=to_user, from_user=from_user, content=reply),
            media_type="application/xml",
        )

    payload = WeChatMaterialRequest(
        text=material_text,
        source_user=to_user,
        source_message_id=msg_id,
        source_type="wechat_voice" if msg_type == "voice" else "wechat_text",
        auto_preview=True,
    )
    _record_wechat_callback_event(
        message,
        action="queued_material",
        reason=(voice_fallback_note or "语音素材已识别并进入生成队列。") if msg_type == "voice" else "文字素材已进入生成队列。",
        content_preview=material_text,
    )
    if WECHAT_SYNC_REPLY:
        result = receive_wechat_material(payload)
        reply_text = (result.get("wechat_reply") or {}).get("plain_text") or "素材已收到，文案已生成。"
    else:
        background_tasks.add_task(receive_wechat_material, payload)
        reply_text = (
            "素材已收到，我会按职场妈妈/AI 提效 IP 流水线生成文案。\n"
            "为了避免微信回调超时，生成结果会先保存在系统里；后续接入客服消息/企业微信机器人后可自动推回聊天框。"
        )
    return Response(
        content=_wechat_text_response(to_user=to_user, from_user=from_user, content=reply_text),
        media_type="application/xml",
    )


@app.post("/api/kids/upload-voice")
async def upload_kids_voice(role: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    safe_role = str(role or "").strip().lower()
    if safe_role not in {"maodou", "peanut"}:
        raise HTTPException(status_code=400, detail="role must be maodou or peanut.")
    filename = str(file.filename or "").strip() or f"{safe_role}_voice.wav"
    suffix = Path(filename).suffix.lower() or ".wav"
    if suffix not in {".wav", ".mp3", ".m4a", ".aac", ".mp4", ".mov", ".webm", ".ogg"}:
        suffix = ".wav"
    source_path = VOICE_REFERENCES_DIR / f"kids_{safe_role}_source_{make_id('voice')}{suffix}"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    with source_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    await file.close()
    extracted = _extract_kids_voice_sample(source_path, safe_role)
    return {
        "status": "ok",
        "filename": filename,
        **extracted,
    }


@app.post("/api/kids/generate")
def create_kids_generation(payload: KidsGenerateRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    seconds = clamp_kids_seconds(payload.seconds)
    script_text = str(payload.custom_script or "").strip()
    if not script_text:
        try:
            if str(payload.script_provider or "").strip().lower() not in {"local", "local_rules", "rules"}:
                script_ai = generate_kids_script_with_ai(
                    provider=payload.script_provider,
                    topic=payload.topic,
                    seconds=seconds,
                    prompt_hint=payload.prompt_hint,
                    content_mode=normalize_content_mode(payload.content_mode),
                    learning_goal=payload.learning_goal,
                )
                script_text = script_ai["script"]
            else:
                raise RuntimeError("Local rules selected.")
        except Exception:
            script_text = build_kids_english_script(
                topic=payload.topic,
                seconds=seconds,
                prompt_hint=payload.prompt_hint,
                content_mode=payload.content_mode,
                learning_goal=payload.learning_goal,
            )
    script_text = normalize_kids_script_text(script_text)

    request_payload = build_kids_generate_payload(
        topic=payload.topic,
        seconds=seconds,
        script_text=script_text,
        background_image_path=_resolve_kids_background(
            uploaded_image_path=payload.uploaded_image_path,
            auto_generate_image=bool(payload.auto_generate_image),
        ),
        reference_image_path=_resolve_kids_reference_image(
            reference_image_path=payload.reference_image_path,
            uploaded_image_path=payload.uploaded_image_path,
        ),
        reference_image_url=_resolve_kids_reference_image_url(payload.reference_image_path or payload.uploaded_image_path),
        video_provider=payload.video_provider,
        edge_voice=payload.edge_voice,
        dynamic_background=False,
        content_mode=payload.content_mode,
        learning_goal=payload.learning_goal,
    )
    request_payload["maodou_voice_reference_path"] = str(payload.maodou_voice_reference_path or "").strip()
    request_payload["peanut_voice_reference_path"] = str(payload.peanut_voice_reference_path or "").strip()
    request_payload["use_my_real_voice"] = bool(payload.use_my_real_voice)
    if payload.use_my_real_voice:
        request_payload["voice_role_mode"] = "my_real_voice"
        request_payload["single_protagonist"] = True
        request_payload["voice_clone_reference_path"] = str(
            payload.maodou_voice_reference_path
            or payload.peanut_voice_reference_path
            or request_payload.get("voice_clone_reference_path", "")
            or ""
        ).strip()
    else:
        request_payload["voice_role_mode"] = "duo_interview"
    selected_provider = normalize_video_provider(payload.video_provider)
    if not str(request_payload.get("reference_image", "")).strip():
        if selected_provider == "zhipu_qingying":
            request_payload["visual_fidelity_mode"] = "zhipu_text_to_video_original_characters"
            request_payload["reference_image_required"] = False
            request_payload["quality_warning"] = (
                "No template image is attached. Zhipu Qingying will create original cute anthropomorphic "
                "edamame and peanut characters directly from the script and character prompt."
            )
        else:
            request_payload["visual_fidelity_mode"] = "local_preview_only"
            request_payload["reference_image_required"] = True
            request_payload["quality_warning"] = (
                "No character reference image was provided. Local OpenCV rendering is preview-only "
                "and cannot reproduce the uploaded template character one-to-one."
            )
    if (
        selected_provider == "kling"
        and not str(request_payload.get("reference_image_url", "")).strip()
        and not str(request_payload.get("reference_image", "")).strip()
    ):
        request_payload["quality_warning"] = (
            "Kling API needs a character reference image. Upload a template image, "
            "or provide an HTTP/HTTPS reference image URL."
        )
    if (
        selected_provider == "zhipu_qingying"
        and not str(request_payload.get("reference_image_url", "")).strip()
        and not str(request_payload.get("reference_image", "")).strip()
    ):
        request_payload["quality_warning"] = (
            "Zhipu Qingying text-to-video mode is active: no default image, no base video, "
            "original edamame and peanut characters will be generated from the script prompt."
        )
    request_payload["animation_style"] = (
        str(payload.animation_style or request_payload.get("animation_style") or "").strip()
        or "cartoon_3d_duo_cinematic"
    )
    request_payload = _normalize_primary_portrait_request(request_payload)
    job = _build_job(request_payload, trigger="kids_manual")
    background_tasks.add_task(_run_job, job["id"])
    return job


@app.post("/api/maintenance/clear-human-data")
def clear_human_data() -> dict[str, Any]:
    result = _clear_human_distill_data()
    _sync_scheduler()
    return {"status": "ok", **result}


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return _sorted(store.list_section("jobs"))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return _job_snapshot(job_id)


@app.post("/api/audio/generate")
def generate_audio(payload: AudioGenerateRequest) -> dict[str, Any]:
    audio_id = make_id("audio")
    output_file = OUTPUTS_DIR / "audio" / f"{audio_id}.mp3"
    try:
        result = synthesize_audio_asset(
            text=payload.text,
            output_file=output_file,
            provider=payload.provider,
            voice=payload.voice,
            rate=payload.rate,
            volume=payload.volume,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"音频生成失败：{str(exc)[:500]}。请检查服务器网络，或配置 OPENAI_API_KEY 作为备用语音。",
        ) from exc
    return {
        "id": audio_id,
        "created_at": now_iso(),
        "audio_url": to_media_url(output_file),
        **result,
    }


@app.get("/api/distribution/tasks")
def list_distribution_tasks() -> dict[str, Any]:
    return {"items": _sorted(store.list_section("distribution_tasks"), key="updated_at")[:50]}


@app.post("/api/jobs/{job_id}/distribution")
def prepare_job_distribution(
    job_id: str,
    payload: DistributionPrepareRequest = DistributionPrepareRequest(),
) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    try:
        record = prepare_distribution_package(
            job,
            title=payload.title,
            summary=payload.summary,
            author=payload.author,
            hashtags=payload.hashtags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.add_record("distribution_tasks", record)
    return record


@app.post("/api/distribution/tasks/{task_id}/wechat-draft")
def create_distribution_wechat_draft(
    task_id: str,
    payload: WeChatDraftRequest = WeChatDraftRequest(),
) -> dict[str, Any]:
    task = store.find_record("distribution_tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="分发任务不存在。")
    try:
        integration_settings = store.get_state().get("integration_settings") or {}
        wechat_result = submit_wechat_draft(
            task,
            get_access_token=_get_wechat_access_token,
            publish_now=payload.publish_now,
            thumb_media_id=str(integration_settings.get("wechat_thumb_media_id") or ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:500]) from exc
    updated_wechat = {
        **(task.get("wechat") if isinstance(task.get("wechat"), dict) else {}),
        **wechat_result,
    }
    return store.update_record(
        "distribution_tasks",
        task_id,
        {"wechat": updated_wechat, "updated_at": now_iso()},
    )


@app.post("/api/distribution/tasks/{task_id}/xiaohongshu/status")
def update_distribution_xiaohongshu_status(
    task_id: str,
    payload: XiaohongshuPublishStatusRequest,
) -> dict[str, Any]:
    task = store.find_record("distribution_tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="分发任务不存在。")
    xiaohongshu = {
        **(task.get("xiaohongshu") if isinstance(task.get("xiaohongshu"), dict) else {}),
        "status": payload.status,
        "notes": payload.notes.strip(),
    }
    if payload.status == "publishing":
        xiaohongshu["started_at"] = now_iso()
    if payload.status == "published":
        note_url = payload.note_url.strip()
        if not note_url:
            raise HTTPException(status_code=422, detail="请填写发布后的小红书笔记链接。")
        xiaohongshu["published_note_url"] = note_url
        xiaohongshu["published_at"] = now_iso()
    updated = store.update_record(
        "distribution_tasks",
        task_id,
        {"xiaohongshu": xiaohongshu, "updated_at": now_iso()},
    )
    return refresh_distribution_manifest(updated)


@app.get("/api/jobs/{job_id}/publish/douyin-assistant")
def get_douyin_publish_assistant(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    draft = job.get("douyin_publish_assistant")
    if isinstance(draft, dict) and draft.get("video_url"):
        return draft
    return _build_douyin_publish_draft(job)


@app.post("/api/jobs/{job_id}/publish/douyin-assistant")
def prepare_douyin_publish_assistant(
    job_id: str,
    payload: DouyinPublishAssistantRequest = DouyinPublishAssistantRequest(),
) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    draft = _build_douyin_publish_draft(job, payload)
    store.update_record("jobs", job_id, {"douyin_publish_assistant": draft, "updated_at": now_iso()})
    return draft


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, Any]:
    snapshot = store.find_record("jobs", job_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Job not found.")

    status = str(snapshot.get("status", "")).strip().lower()
    if status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Task is still running and cannot be deleted.")

    def updater(state: dict[str, Any]) -> int:
        jobs = state.get("jobs", [])
        before = len(jobs)
        state["jobs"] = [item for item in jobs if str(item.get("id")) != job_id]
        return before - len(state["jobs"])

    removed_records = int(store.mutate(updater))

    output_candidates: list[Path] = []
    output_dir_text = str(snapshot.get("output_dir", "")).strip()
    if output_dir_text:
        output_candidates.append(Path(output_dir_text).expanduser())
    output_candidates.append(OUTPUTS_DIR / job_id)

    removed_output_dirs = 0
    output_root = OUTPUTS_DIR.resolve()
    seen: set[str] = set()
    for candidate in output_candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if not resolved.exists() or not resolved.is_dir():
            continue
        if output_root != resolved and output_root not in resolved.parents:
            continue
        shutil.rmtree(resolved, ignore_errors=True)
        removed_output_dirs += 1

    return {
        "deleted": job_id,
        "removed_records": removed_records,
        "removed_output_dirs": removed_output_dirs,
    }


def _decorate_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(schedule)
    enriched["next_run_at"] = scheduler.next_run_for(str(schedule["id"]))
    return enriched


@app.get("/api/schedules")
def list_schedules() -> list[dict[str, Any]]:
    return [_decorate_schedule(item) for item in _sorted(store.list_section("schedules"))]


@app.post("/api/schedules")
def upsert_schedule(payload: SchedulePayload) -> dict[str, Any]:
    existing = store.find_record("schedules", payload.id) if payload.id else None
    schedule_record = {
        "id": payload.id or make_id("schedule"),
        "name": payload.name,
        "time_of_day": payload.time_of_day,
        "enabled": payload.enabled,
        "weekdays": payload.weekdays,
        "topic_pool": [item.strip() for item in payload.topic_pool if item.strip()],
        "request": _normalize_primary_portrait_request(payload.request.model_dump()),
        "next_topic_index": (existing or {}).get("next_topic_index", 0),
        "created_at": (existing or {}).get("created_at", now_iso()),
        "updated_at": now_iso(),
    }
    if existing:
        store.update_record("schedules", schedule_record["id"], schedule_record)
    else:
        store.add_record("schedules", schedule_record)
    _sync_scheduler()
    return _decorate_schedule(store.find_record("schedules", schedule_record["id"]) or schedule_record)


@app.post("/api/schedules/{schedule_id}/run")
def run_schedule_now(schedule_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        schedule_record, request_payload = _materialize_schedule_request(schedule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = _build_job(request_payload, trigger="schedule_manual", schedule_id=schedule_id)
    background_tasks.add_task(_run_job, job["id"])
    return {"schedule": schedule_record, "job": job}


@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: str) -> dict[str, str]:
    def updater(state: dict[str, Any]) -> None:
        schedules = state.get("schedules", [])
        state["schedules"] = [item for item in schedules if str(item.get("id")) != schedule_id]

    store.mutate(updater)
    _sync_scheduler()
    return {"deleted": schedule_id}


@app.get("/api/files/outputs")
def outputs_summary() -> dict[str, Any]:
    jobs = [job for job in _sorted(store.list_section("jobs")) if job.get("status") == "completed"]
    return {
        "count": len(jobs),
        "items": jobs[:20],
        "output_root": str(OUTPUTS_DIR),
    }
