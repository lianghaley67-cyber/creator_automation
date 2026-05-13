from __future__ import annotations

import shutil
import subprocess
import threading
import re
import os
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import analyze_media_file, detect_media_kind
from .avatar import detect_sadtalker_status, normalize_sadtalker_config
from .generation import render_job
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
from .scheduler import StudioScheduler
from .script_ai import generate_kids_script_with_ai
from .schemas import (
    DistillRequest,
    GenerateRequest,
    KidsGenerateRequest,
    KidsScriptPreviewRequest,
    PersonaUpdate,
    SadTalkerConfigPayload,
    SchedulePayload,
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


@app.on_event("startup")
def on_startup() -> None:
    ensure_cartoon_dirs()
    _ensure_persona()
    _recover_interrupted_jobs()
    _sync_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler.shutdown()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
