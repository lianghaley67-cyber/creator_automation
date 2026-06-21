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
    topic: str = "今天送娃迟到被老板点名，心里很憋屈"
    seconds: int = Field(default=45, ge=30, le=60)
    prompt_hint: str = ""
    content_mode: str = "working_mom"
    learning_goal: str = ""
    script_provider: str = "gemini_minimax"


class KidsScriptReviseRequest(BaseModel):
    topic: str = "今天送娃迟到被老板点名，心里很憋屈"
    seconds: int = Field(default=45, ge=30, le=60)
    prompt_hint: str = ""
    content_mode: str = "working_mom"
    learning_goal: str = ""
    script_provider: str = "gemini_minimax"
    draft_script: str
    review: dict | str = Field(default_factory=dict)
    human_feedback: str = ""


class KidsGenerateRequest(BaseModel):
    topic: str = "今天送娃迟到被老板点名，心里很憋屈"
    seconds: int = Field(default=45, ge=30, le=60)
    prompt_hint: str = ""
    content_mode: str = "working_mom"
    learning_goal: str = ""
    script_provider: str = "gemini_minimax"
    custom_script: str = ""
    uploaded_image_path: str = ""
    reference_image_path: str = ""
    auto_generate_image: bool = False
    edge_voice: str = "zh-CN-XiaoyiNeural"
    maodou_voice_reference_path: str = ""
    peanut_voice_reference_path: str = ""
    dynamic_background: bool = False
    animation_style: str = "videohao_real_person"
    use_my_real_voice: bool = True
    video_provider: str = "zhipu_qingying"


class WeChatMaterialRequest(BaseModel):
    text: str
    source_user: str = ""
    source_message_id: str = ""
    source_type: str = "wechat_text"
    content_mode: str = "working_mom"
    script_provider: str = "gemini_minimax"
    learning_goal: str = "把微信发来的真实素材转成高共情、可落地的 AI 提效方案"
    prompt_hint: str = "保留素材里的真实情绪，生成适合视频号的痛点钩子、方法和互动结尾"
    seconds: int = Field(default=45, ge=30, le=60)
    auto_preview: bool = True


class MaterialTextRequest(BaseModel):
    text: str
    source_type: str = "web_text"
    content_mode: str = "working_mom"
    script_provider: str = "gemini_minimax"
    auto_preview: bool = True


class DouyinPublishAssistantRequest(BaseModel):
    title: str = ""
    hashtags: list[str] = Field(default_factory=list)


class AudioGenerateRequest(BaseModel):
    text: str
    provider: TtsProvider = "edge"
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = ""
    volume: str = ""


class DistributionPrepareRequest(BaseModel):
    title: str = ""
    summary: str = ""
    author: str = ""
    hashtags: list[str] = Field(default_factory=list)
    wechat_skill_id: str = ""
    xiaohongshu_skill_id: str = ""
    story_id: str = ""       # 连载故事 ID，为空则不关联故事档案


class WeChatDraftRequest(BaseModel):
    publish_now: bool = False


class TrendDistributionRequest(BaseModel):
    script: str = ""
    question: str = ""
    title: str = ""
    author: str = ""
    hashtags: list[str] = Field(default_factory=list)
    wechat_skill_id: str = ""
    xiaohongshu_skill_id: str = ""
    story_id: str = ""       # 连载故事 ID，为空则不关联故事档案


class TrendSummarizeRequest(BaseModel):
    trend_id: str = ""


class TrendChatRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    trend_context: str = ""
    query: str = ""


class XiaohongshuPublishStatusRequest(BaseModel):
    status: Literal[
        "ready_for_manual_confirm",
        "draft_saved",
        "platform_draft_saved",
        "publishing",
        "published",
        "failed",
    ]
    note_url: str = ""
    notes: str = ""


class XiaohongshuDirectPublishRequest(BaseModel):
    confirm_title: str = Field(min_length=1, max_length=100)
    confirm_publish: Literal[True]


class XiaohongshuSmsRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)


class XiaohongshuSmsVerifyRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=10)


class XiaohongshuDragRequest(BaseModel):
    start_x: float = Field(ge=0, le=1440)
    start_y: float = Field(ge=0, le=1000)
    end_x: float = Field(ge=0, le=1440)
    end_y: float = Field(ge=0, le=1000)
