from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RenderMode = Literal[
    "script_only",
    "subtitle_card",
    "avatar_command",
    "sadtalker",
    "cartoon_native_2d",
    "cartoon_native_3d",
]
ContentType = Literal["insight", "tutorial", "emotional", "qa"]
EmotionTone = Literal["steady", "warm", "intense"]
TtsProvider = Literal["edge", "pyttsx3", "openai", "elevenlabs", "local_clone"]
OutputResolution = Literal["source", "720p", "1080p", "1440p"]


class DistillRequest(BaseModel):
    name: str = "我的数字分身"


class PersonaUpdate(BaseModel):
    name: str | None = None
    hook_candidates: list[str] | None = None
    cta_candidates: list[str] | None = None
    signature_terms: list[str] | None = None
    prompt_block: str | None = None
    content_modes: list[dict[str, str]] | None = None


class GenerateRequest(BaseModel):
    topic: str = ""
    title: str = ""
    keywords: list[str] = Field(default_factory=list)
    story_memo: str = ""
    custom_script: str = ""
    content_type: ContentType = "insight"
    emotion_tone: EmotionTone = "steady"
    seconds: int = Field(default=60, ge=20, le=180)
    render_mode: RenderMode = "sadtalker"
    tts_provider: TtsProvider = "local_clone"
    voice_clone_reference_path: str = ""
    voice_clone_language: str = "zh-cn"
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_rate: str = ""
    edge_volume: str = ""
    background_image: str = ""
    background_color: str = "#10212c"
    subtitle_font: str = "Microsoft YaHei"
    subtitle_size: int = Field(default=18, ge=12, le=48)
    subtitle_margin_v: int = Field(default=120, ge=20, le=400)
    avatar_command_template: str = ""
    portrait_path: str = ""
    ref_eyeblink: str = ""
    ref_pose: str = ""
    avatar_preprocess: str = "full"
    avatar_enhancer: str = "gfpgan"
    avatar_background_enhancer: str = ""
    avatar_still_mode: bool = True
    avatar_pose_style: int = Field(default=0, ge=0, le=45)
    avatar_expression_scale: float = Field(default=1.0, ge=0.5, le=2.5)
    avatar_size: int = Field(default=512, ge=256, le=512)
    output_resolution: OutputResolution = "1080p"
    reference_style_tag: str = ""
    avatar_use_cpu: bool = False
    project_mode: str = ""
    dynamic_background: bool = False
    dynamic_style: str = ""
    animation_style: str = ""
    native_frame_animation: bool = False
    forbid_static_micro_motion: bool = False
    force_bgm: bool = False
    notes: str = ""


class SchedulePayload(BaseModel):
    id: str | None = None
    name: str
    time_of_day: str = "08:30"
    enabled: bool = True
    weekdays: list[str] = Field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )
    topic_pool: list[str] = Field(default_factory=list)
    request: GenerateRequest = Field(default_factory=GenerateRequest)


class SadTalkerConfigPayload(BaseModel):
    enabled: bool = False
    repo_dir: str = ""
    python_exe: str = ""
    checkpoint_dir: str = ""
    source_image: str = ""
    ref_eyeblink: str = ""
    ref_pose: str = ""
    preprocess: str = "full"
    enhancer: str = "gfpgan"
    background_enhancer: str = ""
    still_mode: bool = True
    pose_style: int = Field(default=0, ge=0, le=45)
    expression_scale: float = Field(default=1.0, ge=0.5, le=2.5)
    size: int = Field(default=512, ge=256, le=512)
    batch_size: int = Field(default=2, ge=1, le=8)
    use_cpu: bool = False
    notes: str = ""


class KidsScriptPreviewRequest(BaseModel):
    topic: str = "Daily routine"
    seconds: int = Field(default=45, ge=30, le=60)
    prompt_hint: str = ""
    content_mode: str = "science"
    learning_goal: str = ""
    script_provider: str = "zhipu"


class KidsGenerateRequest(BaseModel):
    topic: str = "Daily routine"
    seconds: int = Field(default=45, ge=30, le=60)
    prompt_hint: str = ""
    content_mode: str = "science"
    learning_goal: str = ""
    script_provider: str = "zhipu"
    custom_script: str = ""
    uploaded_image_path: str = ""
    reference_image_path: str = ""
    auto_generate_image: bool = False
    edge_voice: str = "zh-CN-XiaoyiNeural"
    maodou_voice_reference_path: str = ""
    peanut_voice_reference_path: str = ""
    dynamic_background: bool = False
    animation_style: str = "cartoon_3d_duo_cinematic"
    video_provider: str = "zhipu_qingying"


class DouyinPublishAssistantRequest(BaseModel):
    title: str = ""
    hashtags: list[str] = Field(default_factory=list)
