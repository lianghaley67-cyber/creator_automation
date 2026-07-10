"""Toolized workflow helpers for serial fiction projects.

This module stays deterministic on purpose: it gives the UI and tests a stable
planning/diagnosis layer before any LLM writes prose.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


FANQIE_HARD_RULES = [
    "不要写平台外引流、联系方式、外部链接、账号口令。",
    "不要把亲兄妹、继亲、师生强权等高风险关系写成暧昧或恋爱主线。",
    "不要连续堆叠死亡、追杀、洗钱、诈骗、监控、后门等强刺激元素。",
    "不要写成AI写作教程、提示词拆解、自媒体复盘或工具说明。",
    "每章只推进1个主目标，打开或回收1到2个悬念。",
]

SETUP_QUESTIONS = [
    "这本书一句话讲什么？主角最终想得到什么？",
    "核心爽点是什么：复仇、逆袭、救赎、权谋、破案、升级，还是爱情拉扯？",
    "男女主/双主角的关系边界是什么？有没有必须避开的伦理关系？",
    "世界观是现代、古代、架空玄幻、都市异能，还是混合？",
    "如果是修仙/玄幻，力量体系和代价是什么？如果是现代言情，现实压力是什么？",
    "第一卷要解决什么问题？结尾希望读者期待什么？",
    "你想要的文风更偏强剧情、强情绪、轻松甜宠，还是悬疑拉扯？",
]

GENRE_TEMPLATES = {
    "romance_fantasy": {
        "label": "言情玄幻连载",
        "promise": "用情感关系推动玄幻危机，用每章选择制造牵挂。",
        "avoid": ["亲属恋", "只谈设定不推进", "每章都靠误会拖延"],
    },
    "fantasy": {
        "label": "玄幻连载",
        "promise": "用清晰等级、代价和目标推进成长线。",
        "avoid": ["设定堆砌", "主角无代价开挂", "反派工具化"],
    },
    "fantasy_upgrade": {
        "label": "玄幻升级连载",
        "promise": "用等级压迫、资源争夺和世界秘密推进主角成长。",
        "avoid": ["纯打斗流水账", "系统无脑送经验", "设定多但人物没有情绪"],
    },
    "xianxia": {
        "label": "修仙升级连载",
        "promise": "用修炼体系、宗门规则、资源争夺和因果代价推动成长。",
        "avoid": ["境界说明压过剧情", "主角突然无敌", "奇遇替代选择"],
    },
    "romance": {
        "label": "言情连载",
        "promise": "用人物真实欲望和关系变化推动追读。",
        "avoid": ["无效拉扯", "只靠误会", "人设前后矛盾"],
    },
    "modern_romance": {
        "label": "现代言情连载",
        "promise": "用现实处境、关系拉扯、职业压力和自我成长推进故事。",
        "avoid": ["霸总模板台词", "全靠巧合重逢", "现实问题写成鸡汤"],
    },
    "urban": {
        "label": "都市连载",
        "promise": "用现实压力、职业处境、人情关系和成长逆袭制造共鸣。",
        "avoid": ["纯炫富", "违法成功学", "职场问题写成口号"],
    },
    "transmigration": {
        "label": "穿越连载",
        "promise": "用现代认知与陌生规则的碰撞推动选择、成长和爽点。",
        "avoid": ["开局全知全能", "只靠现代知识碾压", "忽略新世界代价"],
    },
    "female_lead_ancient": {
        "label": "古装大女主",
        "promise": "用身份压迫、权谋选择和自我掌控推进女性成长。",
        "avoid": ["只靠男人拯救", "宫斗流水账", "黑化无代价"],
    },
    "eastern_mysticism": {
        "label": "东方玄学",
        "promise": "用因果、民俗禁忌、命理代价和现实人心制造悬念。",
        "avoid": ["封建迷信说教", "恐怖猎奇堆叠", "规则随意变"],
    },
    "sci_fi": {
        "label": "科幻连载",
        "promise": "用技术变局、制度冲突和人的选择回答未来焦虑。",
        "avoid": ["概念论文", "只讲设定不讲人", "反科技或绝望价值观"],
    },
}

SOCIAL_EMOTION_MODELS = [
    {
        "key": "employment_pressure",
        "label": "就业压力",
        "pain": "努力与回报不匹配，担心被替代、被评价、被淘汰。",
        "story_usage": "让主角在不公平规则里找到自己的不可替代价值。",
        "positive_resolution": "用能力积累、伙伴协作和清醒选择解决问题。",
    },
    {
        "key": "family_pressure",
        "label": "家庭压力",
        "pain": "亲情期待、责任捆绑和自我边界冲突。",
        "story_usage": "把家庭压力转化为主角建立边界和承担责任的成长线。",
        "positive_resolution": "不是逃避家庭，而是用智慧重建边界。",
    },
    {
        "key": "relationship_pressure",
        "label": "婚恋压力",
        "pain": "渴望亲密，又害怕失控、消耗和被否定。",
        "story_usage": "用信任、误解、共同危机推动关系变化。",
        "positive_resolution": "爱情服务于成长，不替代主角自我完成。",
    },
    {
        "key": "personal_growth",
        "label": "个人成长",
        "pain": "知道要改变，却不知道从哪里开始。",
        "story_usage": "让每卷都给主角一个可见的能力、认知或关系升级。",
        "positive_resolution": "成长来自行动、复盘和承担代价。",
    },
    {
        "key": "loneliness",
        "label": "孤独感",
        "pain": "身边有人，却缺少真正理解和同行者。",
        "story_usage": "用同盟、师友、恋人和对手关系制造情绪牵引。",
        "positive_resolution": "主角从被理解走向理解他人，形成团队归属。",
    },
    {
        "key": "future_anxiety",
        "label": "未来焦虑",
        "pain": "担心人生失控，看不到长期确定性。",
        "story_usage": "把大环境不确定性投射为世界规则、阶层壁垒或灾变压力。",
        "positive_resolution": "希望不是空喊，而是通过选择逐步建立可控感。",
    },
]

EDITOR_AGENTS = [
    {"role": "AI总编", "job": "判断商业方向、主题一致性、长线节奏和是否值得继续写。"},
    {"role": "策划编辑", "job": "拆解选题、用户画像、情绪价值、卖点和平台适配。"},
    {"role": "剧情编辑", "job": "维护卷目标、冲突推进、爽点、悬念和反转。"},
    {"role": "人物编辑", "job": "检查人物动机、成长线、关系张力和行为合理性。"},
    {"role": "文字编辑", "job": "压缩废话、增强场景、对话和章末钩子。"},
    {"role": "审核编辑", "job": "检测低俗、色情暗示、暴力猎奇、违法美化和负面价值观。"},
]

CHIEF_EDITOR_CHARTER = {
    "mission": "创造能够陪伴读者成长的优秀中文网络小说。",
    "quality_targets": [
        "强剧情推动",
        "强人物成长",
        "强情绪价值",
        "强阅读吸引力",
        "正向价值观",
        "符合平台审核要求",
    ],
    "creative_belief": "通过人物命运反映时代问题，通过冲突推动成长，通过困境创造希望，通过智慧解决问题。",
    "principles": [
        {
            "title": "人物优先",
            "rule": "任何剧情必须服务人物成长，禁止为了制造冲突降低人物智商。",
            "checklist": ["过去经历", "当前目标", "内心欲望", "心理弱点", "成长方向"],
        },
        {
            "title": "剧情推进",
            "rule": "每章必须回答发生了什么变化、人物获得什么、失去什么、新问题是什么。",
            "checklist": ["无无意义聊天", "无重复描述", "无拖延剧情"],
        },
        {
            "title": "节奏控制",
            "rule": "前期快速建立冲突，中期持续升级，后期完成价值升华。",
            "checklist": ["开头制造兴趣", "中间制造矛盾", "高潮产生变化", "结尾留下期待"],
        },
        {
            "title": "现实共鸣",
            "rule": "允许写就业、家庭、成长、婚恋、孤独和未来焦虑，但不能制造绝望。",
            "checklist": ["提供成长方向", "提供解决路径", "保留希望感"],
        },
        {
            "title": "东方智慧融合",
            "rule": "可融合传统文化、哲学思想和心理成长，用于提升人物认知，不做迷信宣传。",
            "checklist": ["解释人生规律", "服务人物成长", "避免封建强化"],
        },
    ],
}

SKILL_PLUGIN_ARCHITECTURE = {
    "name": "AI Novel Production Team Skill Plugin System",
    "description": "把单一AI聊天写作升级为由小说总编Agent统一调度的AI小说生产团队。",
    "required_fields": [
        "skill_id",
        "skill_name",
        "skill_role",
        "description",
        "system_prompt",
        "input_schema",
        "output_schema",
        "priority",
        "trigger_condition",
        "evaluation_rule",
        "enabled_status",
    ],
    "capabilities": [
        "用户自定义上传Skill",
        "系统内置Skill",
        "Skill版本管理",
        "Skill启用和关闭",
        "Skill组合调用",
    ],
    "collaboration_rule": "禁止单个Skill独立生成完整小说；必须由小说总编Agent统一调度、审核和决策。",
    "quality_score_fields": ["专业准确度", "任务完成度", "创新程度", "一致性"],
    "retry_rule": "任一Skill输出质量评分低于80分，自动重新调用或交给总编Agent退回修改。",
}


def _skill_plugin(
    skill_id: str,
    skill_name: str,
    skill_role: str,
    description: str,
    system_prompt: str,
    input_fields: list[str],
    output_fields: list[str],
    priority: int,
    trigger_condition: str,
    evaluation_rule: str,
) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "skill_role": skill_role,
        "description": description,
        "system_prompt": system_prompt,
        "input_schema": {"type": "object", "required": input_fields, "fields": input_fields},
        "output_schema": {"type": "object", "required": output_fields, "fields": output_fields},
        "priority": priority,
        "trigger_condition": trigger_condition,
        "evaluation_rule": evaluation_rule,
        "enabled_status": True,
        "version": "1.0.0",
        "source": "system_builtin",
    }


PROFESSIONAL_SKILL_PLUGINS = [
    _skill_plugin(
        "Market_Story_Strategist",
        "市场选题分析师",
        "网络文学市场策划专家",
        "分析市场趋势、读者需求、热门题材和商业潜力。",
        "你是网络文学市场策划专家，必须输出小说定位报告：类型、目标读者、市场机会、核心卖点、差异化方向和风险分析。",
        ["user_direction", "genre_hint", "platform_hint"],
        ["novel_type", "target_reader", "market_opportunity", "core_selling_points", "differentiation", "risk_analysis", "quality_score"],
        100,
        "小说创建初期、用户只给出创意方向时触发。",
        "商业方向清晰、读者画像准确、卖点可执行、风险分析具体。",
    ),
    _skill_plugin(
        "Social_Emotion_Analyzer",
        "社会情绪洞察师",
        "社会心理研究专家",
        "分析就业、家庭、婚恋、成长、孤独和未来不确定性，并转化为小说冲突。",
        "你是社会心理研究专家，必须把现实痛点转化为人物困境、剧情方向和积极成长解决方案。",
        ["target_reader", "social_context", "genre"],
        ["real_pain_points", "character_dilemmas", "plot_directions", "growth_solutions", "positive_value", "quality_score"],
        95,
        "选题阶段、需要建立现实共鸣和情绪价值时触发。",
        "现实痛点准确、冲突可小说化、最终导向希望、成长和积极价值。",
    ),
    _skill_plugin(
        "World_Builder",
        "世界观建筑师",
        "顶级世界观设计师",
        "建立时代背景、社会结构、地理、经济、文化、势力关系和规则体系。",
        "你是顶级世界观设计师，必须生成可长期一致使用的世界观数据库，所有规则有边界和代价。",
        ["novel_dna", "genre", "story_seed"],
        ["time_background", "society_structure", "geography", "economy", "culture", "factions", "rule_system", "consistency_notes", "quality_score"],
        90,
        "世界设计阶段或剧情需要扩展设定时触发。",
        "设定稳定、规则清晰、长期可扩展、不为短期爽点破坏一致性。",
    ),
    _skill_plugin(
        "Character_Psychologist",
        "人物心理设计师",
        "人物心理专家",
        "创造真实人物，禁止工具人角色。",
        "你是人物心理专家，每个主要人物必须拥有姓名、年龄、背景、性格、优势、缺陷、欲望、恐惧、秘密、成长路线和最终变化。",
        ["novel_dna", "world_bible", "role_requirements"],
        ["characters", "relationship_tension", "growth_arcs", "motivation_map", "quality_score"],
        90,
        "人物设计阶段、人物行为不合理或关系张力不足时触发。",
        "人物有目标、动机、弱点、成长，不是剧情工具。",
    ),
    _skill_plugin(
        "Plot_Architect",
        "剧情架构师",
        "电视剧和长篇小说编剧专家",
        "设计故事结构、卷规划、100/300/500章章节路线。",
        "你是长篇小说剧情架构师，必须输出章节目标、核心冲突、剧情升级、人物变化、伏笔设计和高潮节点。",
        ["novel_dna", "world_bible", "character_system", "target_chapter_count"],
        ["volume_plan", "chapter_route", "conflict_ladder", "foreshadowing_plan", "climax_nodes", "quality_score"],
        88,
        "剧情设计阶段、长篇规划或卷规划调整时触发。",
        "结构能支撑长篇，冲突递进清晰，伏笔有打开、推进和回收。",
    ),
    _skill_plugin(
        "Pacing_Engineer",
        "节奏控制工程师",
        "网络小说节奏专家",
        "检测拖沓、冲突不足、爽点缺失和悬念不足。",
        "你是网络小说节奏专家，必须评估剧情推进、情绪变化和阅读吸引力，低于标准提出修改方案。",
        ["chapter_brief", "chapter_text", "series_context"],
        ["plot_progress_score", "emotion_shift_score", "reading_hook_score", "pacing_issues", "revision_plan", "quality_score"],
        85,
        "章节生成后或章节节奏不佳时触发。",
        "开头快、中段有矛盾、高潮有变化、结尾有钩子。",
    ),
    _skill_plugin(
        "Chapter_Writer",
        "章节生成作家",
        "成熟网络小说作者",
        "根据总编规划、章节目标和人物状态生成正文。",
        "你是成熟网络小说作者，只根据总编规划和章节Brief写正文：减少废话，快速进入冲突，保持人物一致，推动剧情，章末留下阅读动力。",
        ["chapter_brief", "novel_dna", "character_state", "world_bible"],
        ["chapter_title", "chapter_content", "chapter_summary", "new_threads", "character_state_updates", "quality_score"],
        80,
        "章节生成阶段触发，不能越过总编规划独立发挥。",
        "正文符合Brief、人物一致、剧情推进、结尾有期待。",
    ),
    _skill_plugin(
        "Style_Editor",
        "文学优化编辑",
        "专业文学编辑",
        "优化语言、表达、场景和人物情绪，保持网文节奏。",
        "你是专业文学编辑，必须优化语言表达、场景调度和人物情绪，避免过度华丽、空洞描写和重复表达。",
        ["chapter_text", "style_target", "reader_profile"],
        ["edited_text", "style_changes", "removed_redundancy", "emotion_enhancements", "quality_score"],
        70,
        "章节优化阶段或文字表达薄弱时触发。",
        "文字更清楚、更有画面、更有情绪，但不牺牲阅读速度。",
    ),
    _skill_plugin(
        "Logic_Inspector",
        "逻辑审核专家",
        "小说逻辑审查编辑",
        "检查时间线、人物行为、能力体系和事件因果。",
        "你是小说逻辑审查编辑，必须发现剧情漏洞、人物降智、设定矛盾，并提出可执行修改方案。",
        ["chapter_text", "timeline", "character_state", "world_rules"],
        ["logic_issues", "character_inconsistencies", "timeline_conflicts", "world_rule_conflicts", "fix_plan", "quality_score"],
        95,
        "最终审核阶段、重写前后或长篇连续性检查时触发。",
        "能定位矛盾源头，修改方案不破坏既有设定。",
    ),
    _skill_plugin(
        "Platform_Guard",
        "平台安全审核专家",
        "网络文学平台审核专家",
        "检测低俗、色情暗示、暴力猎奇、违法犯罪美化和负面价值表达。",
        "你是网络文学平台审核专家，必须保留剧情冲突，同时把风险内容优化为成长、智慧和积极价值。",
        ["chapter_text", "platform_rules", "genre"],
        ["safety_risks", "risk_level", "positive_rewrite_plan", "compliance_notes", "quality_score"],
        100,
        "最终审核阶段、发布前和风险内容出现时触发。",
        "风险识别准确，修改方向积极，不把冲突改没。",
    ),
]

PROFESSIONAL_SKILLS = [
    {"id": item["skill_id"], "name": item["skill_name"], "role": item["skill_role"], "output": "、".join(item["output_schema"]["fields"][:4]) + "。"}
    for item in PROFESSIONAL_SKILL_PLUGINS
]

MASTER_CHIEF_EDITOR_WORKFLOW = {
    "name": "Novel Master Chief Editor",
    "positioning": "小说总编Agent不直接生成小说文字；它负责分析需求、制定策略、调度专业Skill、审核结果和持续优化。",
    "stages": [
        {
            "key": "requirement_analysis",
            "title": "用户需求分析阶段",
            "goal": "把用户的一句话需求拆成可生产、可审核、可长期连载的商业小说方向。",
            "checks": [
                "识别小说类型：都市、玄幻、穿越、古装、大女主、东方玄学、科幻等。",
                "识别目标读者：年龄、性别、阅读习惯、情绪需求。",
                "确定核心情绪价值：治愈、逆袭、成长、希望、智慧、爽感。",
                "输出市场定位：商业方向、竞争优势、差异化定位。",
            ],
            "skills": ["Market_Story_Strategist", "Social_Emotion_Analyzer"],
            "output": "类型定位、用户画像、情绪价值、商业卖点和差异化策略。",
        },
        {
            "key": "novel_dna",
            "title": "建立小说DNA系统",
            "goal": "为每一本书建立唯一DNA，作为后续所有章节的最高约束。",
            "checks": [
                "核心主题是否清晰。",
                "世界观规则是否稳定。",
                "主角成长路线是否可持续。",
                "核心冲突是否能支撑长篇。",
                "情绪基调和价值观方向是否一致。",
                "结局方向是否能完成价值升华。",
            ],
            "skills": ["World_Builder", "Character_Psychologist", "Plot_Architect"],
            "output": "核心主题、世界观规则、主角成长线、核心冲突、情绪基调、价值观方向、结局方向。",
        },
        {
            "key": "skill_dispatch",
            "title": "Skill调度机制",
            "goal": "根据任务阶段自动调用专业Skill，避免一个模型同时承担所有职责。",
            "checks": [
                "选题阶段调用市场和社会情绪Skill。",
                "世界观阶段调用World_Builder。",
                "人物阶段调用Character_Psychologist。",
                "剧情阶段调用Plot_Architect。",
                "章节阶段调用Chapter_Writer。",
                "优化阶段调用Style_Editor。",
                "审核阶段调用Logic_Inspector和Platform_Guard。",
            ],
            "skills": [skill["id"] for skill in PROFESSIONAL_SKILLS],
            "output": "任务阶段、调用Skill、输入上下文、结构化输出和下一步动作。",
        },
        {
            "key": "long_serial_management",
            "title": "长篇小说管理机制",
            "goal": "支持100章、300章、500章以上长期连载，防止人物崩坏和前后矛盾。",
            "checks": [
                "卷规划是否有阶段目标。",
                "章节规划是否持续推动主线。",
                "人物成长记录是否更新。",
                "事件时间线是否一致。",
                "伏笔是否有打开、推进和回收状态。",
                "世界观规则是否被新章节破坏。",
            ],
            "skills": ["Plot_Architect", "Character_Psychologist", "Logic_Inspector"],
            "output": "卷规划、章节规划、人物状态、事件时间线、伏笔表、连续性风险。",
        },
        {
            "key": "chapter_review",
            "title": "章节生成审核流程",
            "goal": "每章生成后必须经过剧情、节奏、价值观和平台安全四重审核。",
            "checks": [
                "剧情检查：是否推动主线、产生新冲突、带来人物变化。",
                "节奏检查：开头是否吸引、中间是否拖沓、结尾是否有悬念。",
                "价值观检查：是否体现积极价值、成长方向和智慧解决问题。",
                "平台安全检查：是否存在违规、低俗、暗示、猎奇、违法美化或负面价值观。",
            ],
            "skills": ["Logic_Inspector", "Pacing_Engineer", "Style_Editor", "Platform_Guard"],
            "output": "审核评分、问题列表、修改建议、是否退回重写。",
        },
        {
            "key": "quality_scoring",
            "title": "总编评分机制",
            "goal": "用100分制决定章节是否可进入发布链路，低于80分必须优化。",
            "checks": [
                "剧情推进20分。",
                "人物成长20分。",
                "阅读吸引力20分。",
                "情绪价值20分。",
                "安全审核20分。",
            ],
            "skills": ["Logic_Inspector", "Platform_Guard"],
            "output": "章节质量评分、低分项、优化原因、发布许可。",
        },
    ],
    "chapter_score_rubric": [
        {"key": "plot_progress", "label": "剧情推进", "points": 20, "pass_rule": "本章必须让主线发生可见变化。"},
        {"key": "character_growth", "label": "人物成长", "points": 20, "pass_rule": "主角或关键人物必须获得、失去、醒悟或改变。"},
        {"key": "reading_hook", "label": "阅读吸引力", "points": 20, "pass_rule": "开头有兴趣点，结尾有具体期待。"},
        {"key": "emotion_value", "label": "情绪价值", "points": 20, "pass_rule": "提供爽感、治愈、希望、智慧或成长启发。"},
        {"key": "platform_safety", "label": "安全审核", "points": 20, "pass_rule": "符合平台内容安全和积极价值观要求。"},
    ],
    "optimization_rule": "章节总分低于80分必须退回优化；发现剧情漏洞、人物崩坏、节奏拖沓或平台风险时，总编Agent必须主动提出修改方案。",
    "final_goal": "创造高质量、强节奏、强情绪、可长期连载、具有IP价值的中文网络小说。",
}

SKILL_CALLING_RULES = [
    {"stage": "小说创建阶段", "skills": ["Market_Story_Strategist", "Social_Emotion_Analyzer"], "handoff": "形成定位报告和社会情绪映射后交给总编确认小说DNA。"},
    {"stage": "世界设计阶段", "skills": ["World_Builder"], "handoff": "生成世界观数据库，写入长期设定约束。"},
    {"stage": "人物设计阶段", "skills": ["Character_Psychologist"], "handoff": "生成主要人物生命档案和关系张力。"},
    {"stage": "剧情设计阶段", "skills": ["Plot_Architect"], "handoff": "生成卷规划、章节路线、伏笔和高潮节点。"},
    {"stage": "章节生成阶段", "skills": ["Chapter_Writer", "Pacing_Engineer"], "handoff": "先生成正文，再检查推进、情绪变化和阅读吸引力。"},
    {"stage": "章节优化阶段", "skills": ["Style_Editor"], "handoff": "优化语言、场景和人物情绪，不改变总编批准的剧情方向。"},
    {"stage": "最终审核阶段", "skills": ["Logic_Inspector", "Platform_Guard"], "handoff": "通过逻辑与平台安全审核后，才允许进入发布链路。"},
]

SKILL_COLLABORATION_FLOW = [
    "用户需求",
    "小说总编分析",
    "调用Skill团队",
    "生成结构化结果",
    "总编审核",
    "低分退回重调",
    "进入下一阶段",
]

NOVEL_MEMORY_ENGINE = {
    "name": "Novel Memory Engine",
    "positioning": "整个小说系统的长期记忆中心。所有Agent和Skill必须通过记忆引擎获取小说上下文，禁止每次生成章节时重新读取全部正文。",
    "core_rule": "通过结构化记忆管理长期创作，只给每个Skill发送与当前任务相关的Chapter Context Package。",
    "memory_layers": [
        {
            "key": "novel_dna",
            "name": "Novel DNA Memory",
            "purpose": "保存小说最高级设定，保证所有剧情不偏离。",
            "fields": ["小说名称", "小说类型", "核心主题", "价值观", "目标读者", "情绪基调", "核心冲突", "最终方向"],
            "read_rule": "任何Agent生成内容前必须读取小说DNA。",
        },
        {
            "key": "world",
            "name": "World Memory",
            "purpose": "保存小说世界规则，保证长期一致。",
            "fields": ["时代背景", "地理体系", "社会结构", "经济体系", "文化体系", "势力关系", "能力体系", "等级体系"],
            "read_rule": "若世界观没有现代科技，后续章节不得突然出现现代科技。",
        },
        {
            "key": "character",
            "name": "Character Memory",
            "purpose": "保存所有角色基础、心理和成长状态，防止人物遗忘或崩坏。",
            "fields": ["姓名", "年龄", "身份", "性格", "优势", "缺陷", "欲望", "恐惧", "秘密", "当前阶段", "能力变化", "心理变化", "关系变化"],
            "read_rule": "每次生成章节前必须检查相关人物状态。",
        },
        {
            "key": "plot",
            "name": "Plot Memory",
            "purpose": "保存完整故事发展，自动维护主线、支线、事件和伏笔状态。",
            "fields": ["主线任务", "支线任务", "章节进度", "重要事件", "关键转折", "伏笔", "未解决问题"],
            "read_rule": "生成新剧情前必须检查是否重复、冲突或违背时间线。",
        },
        {
            "key": "chapter",
            "name": "Chapter Memory",
            "purpose": "保存每章摘要，用于连续创作而不是重读全文。",
            "fields": ["章节编号", "章节目标", "发生事件", "人物变化", "新增信息", "悬念"],
            "read_rule": "生成新章节时自动读取最近章节记忆。",
        },
    ],
    "managers": [
        {
            "name": "Story Timeline Manager",
            "responsibility": "自动记录事件顺序、人物年龄变化、地点变化和能力变化，并检测时间错误。",
            "example_guard": "人物第20章已经死亡，第50章不能再次出现，除非明确是回忆、幻象或误导。",
        },
        {
            "name": "Character State Tracker",
            "responsibility": "实时记录人物当前状态、成长阶段、能力、心理和关系。",
            "example_state": "林雪：觉醒期；能力为商业分析能力；心理从自卑转向自信；与父亲矛盾未解决。",
        },
        {
            "name": "Foreshadowing Manager",
            "responsibility": "记录所有伏笔的内容、出现章节、预计回收章节、关联人物和状态。",
            "example_state": "第10章神秘玉佩出现，预计第100章揭示来源。",
        },
        {
            "name": "Story Review Agent",
            "responsibility": "每10章自动分析剧情发展、人物成长、节奏、读者吸引力和逻辑问题。",
            "output": "阶段优势、存在问题、下一阶段建议。",
        },
    ],
    "chapter_context_package": {
        "description": "章节生成时不发送全部小说内容，只发送结构化上下文包给Chapter Writer。",
        "fields": ["小说DNA摘要", "当前卷目标", "最近章节总结", "相关人物状态", "当前冲突", "必须回收的信息"],
        "target_skill": "Chapter_Writer",
    },
    "update_pipeline": [
        "章节内容分析",
        "提取新增信息",
        "更新人物记忆",
        "更新时间线",
        "更新剧情状态",
        "保存长期记忆",
    ],
    "agent_call_rule": [
        "小说总编Agent",
        "读取小说DNA",
        "读取相关世界记忆",
        "读取人物状态",
        "读取剧情状态",
        "调用Skill生成内容",
        "更新记忆",
    ],
    "database_tables": [
        {
            "name": "novel_memory",
            "fields": ["id", "novel_id", "memory_type", "memory_content", "importance", "created_time", "updated_time"],
            "purpose": "统一保存小说DNA、世界观、剧情状态等长期记忆。",
        },
        {
            "name": "character_state",
            "fields": ["character_id", "current_status", "growth_stage", "relationship_data", "ability_data"],
            "purpose": "保存人物当前状态和成长变化。",
        },
        {
            "name": "story_timeline",
            "fields": ["event_id", "chapter_id", "event_content", "time_position"],
            "purpose": "保存事件顺序和时间位置。",
        },
        {
            "name": "foreshadowing",
            "fields": ["id", "content", "created_chapter", "target_chapter", "status"],
            "purpose": "保存伏笔打开、推进和回收状态。",
        },
        {
            "name": "chapter_summary",
            "fields": ["chapter_id", "summary", "character_change", "plot_change", "new_information"],
            "purpose": "保存章节摘要和新增信息。",
        },
    ],
    "final_goal": "让AI小说系统具备长期理解、连续创作、人物稳定、世界一致和百万字小说生产能力，从写一章小说升级为长期运营一本小说IP。",
}

NOVEL_COMMERCIAL_INTELLIGENCE = {
    "name": "Novel Commercial Intelligence",
    "positioning": "在小说总编Agent、AI小说生产团队和Novel Memory Engine之上，增加爆款研究、读者反馈模拟、数据分析和自动优化能力。",
    "agents": [
        {
            "id": "Bestseller_Analyzer",
            "name": "爆款小说研究分析师",
            "role": "专业网络文学市场研究专家",
            "responsibility": "分析优秀小说成功原因，不复制作品，只提取商业规律、结构规律和读者心理规律。",
            "outputs": ["开篇吸引力评分", "爽点模型", "剧情模型", "人物模型", "情绪曲线", "成功因子"],
        },
        {
            "id": "Reader_Simulator",
            "name": "读者模拟Agent",
            "role": "虚拟真实小说读者群",
            "responsibility": "预测读者是否愿意继续阅读，指出兴趣点、弃读点、情绪点和修改建议。",
            "outputs": ["继续阅读概率", "弃读风险", "最大情绪点", "最大不足", "修改建议"],
        },
        {
            "id": "Novel_Optimization_Agent",
            "name": "小说自动优化Agent",
            "role": "商业化内容优化编辑",
            "responsibility": "根据审核结果、读者反馈和质量评分自动提出剧情、人物、节奏、文字优化方案。",
            "outputs": ["问题定位", "优化方案", "重写优先级", "预期提升", "记忆更新建议"],
        },
    ],
    "bestseller_analysis_dimensions": [
        {
            "key": "opening_hook",
            "name": "开篇吸引力分析",
            "scope": ["前1章", "前3章", "前10章"],
            "extract": ["开篇冲突", "主角困境", "核心卖点", "第一个爽点"],
            "output": "开篇吸引力评分",
        },
        {
            "key": "satisfaction_model",
            "name": "爽点模型分析",
            "categories": ["逆袭爽", "成长爽", "智慧爽", "财富爽", "权力爽", "情感爽"],
            "extract": ["爽点出现频率", "爽点类型", "读者反馈"],
            "output": "爽点数据库",
        },
        {
            "key": "plot_structure",
            "name": "剧情结构分析",
            "extract": ["故事结构", "章节节奏", "高潮分布", "冲突升级"],
            "output": "剧情模型",
        },
        {
            "key": "character_model",
            "name": "人物模型分析",
            "extract": ["主角身份", "主角目标", "主角能力", "主角缺陷", "成长路线", "反派价值观", "冲突来源", "反派作用"],
            "output": "人物模型",
        },
        {
            "key": "emotion_curve",
            "name": "情绪曲线分析",
            "extract": ["紧张度", "期待感", "爽感", "治愈感"],
            "output": "Emotion Curve",
        },
    ],
    "reader_personas": [
        {"id": "reader_a", "name": "读者A", "profile": "年轻男性", "focus": ["升级", "逆袭", "爽感"]},
        {"id": "reader_b", "name": "读者B", "profile": "年轻女性", "focus": ["人物成长", "情感", "关系"]},
        {"id": "reader_c", "name": "读者C", "profile": "成熟用户", "focus": ["现实共鸣", "人生价值"]},
        {"id": "reader_d", "name": "读者D", "profile": "文学用户", "focus": ["故事深度", "人物塑造"]},
    ],
    "chapter_reader_test": {
        "questions": ["是否愿意继续阅读", "哪里产生兴趣", "哪里可能弃读", "最大的情绪点", "最大的不足"],
        "report_fields": ["继续阅读概率", "弃读风险", "修改建议"],
        "trigger": "每生成一章后自动进入读者模拟测试。",
    },
    "novel_quality_score": {
        "name": "Novel Quality Score",
        "total": 100,
        "threshold": 80,
        "dimensions": [
            {"key": "plot_score", "label": "剧情推进", "points": 20},
            {"key": "character_score", "label": "人物成长", "points": 20},
            {"key": "emotion_score", "label": "情绪价值", "points": 20},
            {"key": "reading_score", "label": "阅读吸引力", "points": 20},
            {"key": "safety_score", "label": "平台安全", "points": 20},
        ],
        "low_score_action": "低于80分自动进入优化流程。",
    },
    "feedback_loop": ["生成章节", "质量检测", "读者模拟", "发现问题", "自动优化", "更新小说记忆", "继续生成"],
    "analytics_dashboard": {
        "name": "Novel Analytics Dashboard",
        "metrics": ["完成章节", "质量评分", "读者兴趣", "风险", "当前问题", "优化建议"],
        "example": {
            "completed_chapters": "50/300",
            "quality_score": "88分",
            "reader_interest": "82%",
            "risk": "低",
            "current_issue": "中期冲突不足",
            "suggestion": "增加新的剧情压力",
        },
    },
    "story_pattern_database": [
        {"name": "普通人逆袭模型", "type": "人物模型", "usage": "让读者获得从低位到掌控局面的代入感。"},
        {"name": "废柴成长模型", "type": "成长模型", "usage": "用能力升级、认知升级和代价建立长期爽感。"},
        {"name": "大女主觉醒模型", "type": "人物模型", "usage": "从被规则压迫到理解规则、利用规则、改写规则。"},
        {"name": "穿越改革模型", "type": "题材模型", "usage": "现代认知与旧世界规则碰撞，形成制度和人物双冲突。"},
        {"name": "东方智慧成长模型", "type": "价值模型", "usage": "用传统智慧解释人生规律，但避免迷信宣传。"},
    ],
    "database_tables": [
        {
            "name": "bestseller_analysis",
            "fields": ["id", "source_name", "genre", "structure_analysis", "emotion_curve", "character_model", "success_factor"],
            "purpose": "保存爆款分析结果和可复用商业规律。",
        },
        {
            "name": "reader_simulation",
            "fields": ["id", "chapter_id", "reader_type", "continue_rate", "emotion_score", "feedback"],
            "purpose": "保存章节读者模拟测试。",
        },
        {
            "name": "quality_score",
            "fields": ["chapter_id", "plot_score", "character_score", "emotion_score", "reading_score", "safety_score", "total_score"],
            "purpose": "保存章节质量评分。",
        },
        {
            "name": "optimization_record",
            "fields": ["id", "problem", "solution", "result"],
            "purpose": "保存自动优化问题、方案和结果。",
        },
    ],
    "chief_editor_call_rules": [
        {"stage": "研究阶段", "agent": "Bestseller_Analyzer", "memory_feedback": "把成功模型写入Story Pattern Database。"},
        {"stage": "生成阶段", "agent": "Reader_Simulator", "memory_feedback": "把读者兴趣点和弃读风险反馈给Novel Memory Engine。"},
        {"stage": "优化阶段", "agent": "Novel_Optimization_Agent", "memory_feedback": "把优化结果写入章节记忆、人物状态和剧情记忆。"},
    ],
    "final_goal": "让系统具备市场判断、爆款研究、读者预测和自动优化能力，从AI生成小说升级为AI自主优化小说，形成持续学习和提升的AI小说生产公司。",
}

SENSITIVE_PATTERNS = {
    "genre_drift": re.compile(r"代码|GitHub|变量|算法|服务器|Docker|API|U盘|数据库|后门", re.I),
    "family_romance_risk": re.compile(r"亲兄妹|亲妹妹|亲哥哥|同母异父|同父异母|继兄|继妹|哥哥.*妹妹|妹妹.*哥哥"),
    "crime_stack": re.compile(r"洗钱|赌债|诈骗|股权|伪造|监控|后门|合同陷阱|绑架"),
    "violence_stack": re.compile(r"追杀|尸体|死亡|杀人|血|跳楼|自杀|枪|刀"),
    "platform_leak": re.compile(r"微信|QQ|公众号|小红书|微博|关注我|私信|http|www\.", re.I),
    "tutorial_leak": re.compile(r"提示词|怎么写|AI原版|我的修改|教程|步骤|表格|工具"),
}


@dataclass(frozen=True)
class StoryMetric:
    key: str
    label: str
    count: int
    severity: str
    suggestion: str


def _text_from_chapter(chapter: dict[str, Any]) -> str:
    return "\n".join(
        str(chapter.get(key) or "")
        for key in ("title", "content_markdown", "content_xhs", "context_summary")
    )


def _count_chapter_hits(chapters: list[dict[str, Any]], pattern: re.Pattern[str]) -> int:
    return sum(1 for chapter in chapters if pattern.search(_text_from_chapter(chapter)))


def diagnose_story_archive(chapters: list[dict[str, Any]], bible: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a practical diagnosis for a serial fiction archive."""
    bible = bible or {}
    total = len(chapters)
    open_threads = [
        item for item in (bible.get("ongoing_threads") or [])
        if isinstance(item, dict) and item.get("status") != "resolved"
    ]
    world_notes = str(bible.get("world_notes") or "")
    all_text = "\n".join(_text_from_chapter(chapter) for chapter in chapters) + "\n" + world_notes

    metrics = [
        StoryMetric(
            "genre_drift",
            "类型跑偏",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["genre_drift"]),
            "high",
            "如果目标是言情/玄幻，不要让代码、服务器、U盘、商业阴谋成为主线。",
        ),
        StoryMetric(
            "family_romance_risk",
            "关系高风险",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["family_romance_risk"]),
            "high",
            "把亲属/疑似亲属关系改为无血缘、误会、契约或阵营关系，恋爱线必须清白。",
        ),
        StoryMetric(
            "crime_stack",
            "犯罪元素过密",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["crime_stack"]),
            "medium",
            "商业犯罪可以保留为背景，但每卷只选一个核心阴谋，不要章章加码。",
        ),
        StoryMetric(
            "violence_stack",
            "强刺激过密",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["violence_stack"]),
            "medium",
            "减少死亡/追杀堆叠，用选择、代价、秘密和关系张力替代。",
        ),
        StoryMetric(
            "tutorial_leak",
            "不像小说正文",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["tutorial_leak"]),
            "high",
            "小说模块只输出故事，不出现AI写作过程、提示词、复盘表格。",
        ),
    ]

    hard_issues: list[str] = []
    if any(metric.key == "family_romance_risk" and metric.count for metric in metrics):
        hard_issues.append("存在亲属/疑似亲属暧昧风险，推荐评估会非常吃亏。")
    if total and metrics[0].count / total >= 0.35:
        hard_issues.append("已有大量章节偏向现代技术/商业阴谋，不像言情玄幻连载。")
    if len(open_threads) > 12:
        hard_issues.append(f"未解悬念过多（{len(open_threads)}条），读者会累，系统也容易续写失控。")
    if SENSITIVE_PATTERNS["platform_leak"].search(all_text):
        hard_issues.append("正文/档案中可能出现平台外信息，需要发布前清理。")

    score = 100
    score -= min(metrics[0].count * 4, 30)
    score -= min(metrics[1].count * 8, 32)
    score -= min(metrics[2].count * 2, 16)
    score -= min(metrics[3].count * 2, 16)
    score -= min(len(open_threads), 20)
    score = max(score, 0)

    next_actions = [
        "先暂停直接生成下一章，别继续把偏掉的设定往后滚。",
        "重新确认一本书的定位：类型、主角目标、关系边界、第一卷终点。",
        "把高风险关系改成无血缘/契约/阵营关系，清掉平台外信息。",
        "把未解悬念收束到5条以内，再决定第1卷接下来3章怎么走。",
        "之后每章先生成章节Brief，确认后再写正文。",
    ]

    return {
        "score": score,
        "level": "需要重构" if score < 60 else ("需要收束" if score < 80 else "基本可用"),
        "chapter_count": total,
        "open_thread_count": len(open_threads),
        "world_notes_length": len(world_notes),
        "metrics": [metric.__dict__ for metric in metrics],
        "hard_issues": hard_issues,
        "next_actions": next_actions,
        "rules": FANQIE_HARD_RULES,
    }


def build_story_blueprint(seed: dict[str, Any]) -> dict[str, Any]:
    """Build a book-level blueprint draft that must be confirmed before chapters."""
    raw_genre = str(seed.get("genre") or "romance_fantasy").strip()
    template = GENRE_TEMPLATES.get(raw_genre, GENRE_TEMPLATES["romance_fantasy"])
    title = str(seed.get("title") or seed.get("name") or "未命名故事").strip()
    idea = str(seed.get("idea") or seed.get("premise") or "").strip()
    audience = str(seed.get("audience") or "喜欢强剧情、强情绪、又希望设定清楚的女性读者").strip()
    tone = str(seed.get("tone") or "有画面感、克制但有张力，章末留钩子").strip()
    market_positioning = str(seed.get("market_positioning") or "平台连载型强情绪故事，优先追读、完读和章节钩子。").strip()
    reader_pain = str(seed.get("reader_pain") or "现实压力下渴望被理解、被看见，并看到主角一步步夺回主动权。").strip()
    emotional_core = str(seed.get("emotional_core") or "压抑处境中的选择、成长、希望和关系确认。").strip()
    worldview_seed = str(seed.get("worldview_seed") or "").strip()
    protagonist_seed = str(seed.get("protagonist_seed") or "").strip()

    chapter_count = int(seed.get("chapter_count") or 30)
    chapter_count = min(max(chapter_count, 30), 100)
    first_volume_count = min(max(int(seed.get("first_volume_count") or 10), 6), chapter_count)

    opening_question = idea or "主角在一个无法回头的选择前，必须在感情和命运之间做决定。"
    outline = []
    for index in range(1, first_volume_count + 1):
        if index == 1:
            goal = "用一个具体场景把主角困境、能力/秘密和关系张力立起来。"
        elif index == first_volume_count:
            goal = "回收第一卷核心矛盾，同时打开更大的代价。"
        else:
            goal = "推进一个选择，让主角获得线索或付出代价。"
        outline.append({
            "chapter": index,
            "goal": goal,
            "conflict": "外部阻碍 + 内心选择，不靠纯误会拖剧情。",
            "hook": "章末留下一个具体问题，让读者想看下一章。",
        })

    return {
        "status": "needs_confirmation",
        "next_step": "先回答或修改下方问题，确认后再生成第1章。",
        "questions": SETUP_QUESTIONS,
        "book_profile": {
            "title": title,
            "genre": template["label"],
            "one_sentence": opening_question,
            "target_reader": audience,
            "tone": tone,
            "promise": template["promise"],
            "market_positioning": market_positioning,
            "reader_pain": reader_pain,
            "emotional_core": emotional_core,
        },
        "topic_center": _build_topic_center(template, opening_question, audience, market_positioning, reader_pain, emotional_core),
        "social_emotion_database": _build_emotion_database(reader_pain, emotional_core),
        "world_bible": _build_world_bible(template, worldview_seed, opening_question),
        "character_life_system": _build_character_life_system(template, protagonist_seed, opening_question),
        "risk_rules": {
            "must_avoid": template["avoid"] + FANQIE_HARD_RULES,
            "chapter_rule": "每章只推进一个主要动作，最多保留两个悬念。",
        },
        "volume_plan": {
            "planned_chapters": chapter_count,
            "first_volume_chapters": first_volume_count,
            "first_volume_goal": "先完成读者能理解、能追下去的第一卷闭环。",
        },
        "chapter_outline": outline,
        "hundred_chapter_plan": _build_hundred_chapter_plan(chapter_count),
        "editorial_agents": EDITOR_AGENTS,
        "chief_editor_charter": CHIEF_EDITOR_CHARTER,
        "master_chief_editor_workflow": MASTER_CHIEF_EDITOR_WORKFLOW,
        "skill_plugin_architecture": SKILL_PLUGIN_ARCHITECTURE,
        "skill_plugins": PROFESSIONAL_SKILL_PLUGINS,
        "professional_skills": PROFESSIONAL_SKILLS,
        "skill_calling_rules": SKILL_CALLING_RULES,
        "skill_collaboration_flow": SKILL_COLLABORATION_FLOW,
        "novel_memory_engine": NOVEL_MEMORY_ENGINE,
        "commercial_intelligence": NOVEL_COMMERCIAL_INTELLIGENCE,
        "production_pipeline": [
            "选题中心确认市场与情绪价值",
            "社会情绪库绑定现实共鸣",
            "世界观和人物生命系统定稿",
            "100章规划拆卷",
            "逐章 Brief 生成",
            "章节正文生成",
            "AI总编审核",
            "番茄安全审核与积极价值观改写",
            "保存记忆并进入下一章",
        ],
    }


def _build_topic_center(
    template: dict[str, Any],
    idea: str,
    audience: str,
    market_positioning: str,
    reader_pain: str,
    emotional_core: str,
) -> dict[str, Any]:
    return {
        "direction": f"{template['label']}：{idea}",
        "market_positioning": market_positioning,
        "audience_profile": audience,
        "emotion_value": emotional_core,
        "commercial_potential": [
            "开篇用强处境和明确目标降低进入门槛。",
            "每章提供冲突、爽点、情绪点和悬念点，服务追读。",
            "第一卷形成小闭环，避免只铺设定不兑现。",
        ],
        "reader_pressure_anchor": reader_pain,
    }


def _build_emotion_database(reader_pain: str, emotional_core: str) -> list[dict[str, Any]]:
    selected = []
    for item in SOCIAL_EMOTION_MODELS:
        score = 1
        if item["label"] in reader_pain or item["label"] in emotional_core:
            score += 2
        if item["key"] in {"personal_growth", "future_anxiety", "loneliness"}:
            score += 1
        selected.append({**item, "fit_score": score})
    return sorted(selected, key=lambda item: item["fit_score"], reverse=True)


def _build_world_bible(template: dict[str, Any], worldview_seed: str, idea: str) -> dict[str, Any]:
    is_modern = any(word in template["label"] for word in ["都市", "现代", "科幻"])
    return {
        "time_background": worldview_seed or ("近未来现实社会" if is_modern else "架空王朝/异世大陆的第一卷开端"),
        "society_system": "资源、身份和规则共同构成压力，主角必须在规则内找到突破口。",
        "relationship_map": "主角-同盟-对手-权力中心四层关系网；每层至少绑定一个利益冲突。",
        "rule_system": "所有能力和选择都必须有代价，不能临时开挂解决核心矛盾。",
        "power_system": "力量来自能力成长、信息差、关系协作和关键选择；每卷升级一次认知或能力。",
        "story_seed": idea,
    }


def _build_character_life_system(template: dict[str, Any], protagonist_seed: str, idea: str) -> list[dict[str, Any]]:
    protagonist = protagonist_seed or "主角在压迫处境中保持清醒，既渴望被理解，也必须学会主动选择。"
    return [
        {
            "name": "主角",
            "role": "核心视角",
            "background": protagonist,
            "personality": "外冷内韧，遇事先忍再反击。",
            "strengths": "观察力、学习力、共情力和关键时刻的行动力。",
            "flaws": "习惯独自承担，不轻易求助。",
            "inner_conflict": "想获得安全感，又害怕依赖别人后再次失去。",
            "growth_route": "从被规则推着走，到看清规则、利用规则、改写规则。",
            "final_change": "成为能保护自己也能照亮他人的行动者。",
        },
        {
            "name": "关键同盟/感情线",
            "role": "关系张力",
            "background": f"与主角处在不同阵营或不同信息层，围绕「{idea[:24]}」形成牵引。",
            "personality": "克制、聪明、有秘密。",
            "strengths": "资源、判断力和稳定执行力。",
            "flaws": "过度理性，容易隐藏真实意图。",
            "inner_conflict": "保护主角与尊重主角选择之间摇摆。",
            "growth_route": "从掌控局面，到学会并肩承担。",
            "final_change": "成为主角成长的见证者和共同选择者。",
        },
        {
            "name": "阶段反派",
            "role": "第一卷压力源",
            "background": f"代表{template['label']}世界中的旧规则和旧秩序。",
            "personality": "目标明确，擅长利用制度或人心弱点。",
            "strengths": "资源优势、信息优势和规则熟悉度。",
            "flaws": "低估主角的成长速度和关系同盟。",
            "inner_conflict": "相信控制能带来安全，却不断制造更大失控。",
            "growth_route": "从压迫者变成揭示更大危机的入口。",
            "final_change": "第一卷被击败或被迫退场，留下更高层冲突。",
        },
    ]


def _build_hundred_chapter_plan(chapter_count: int) -> list[dict[str, Any]]:
    volume_size = 20
    plan: list[dict[str, Any]] = []
    for chapter in range(1, chapter_count + 1):
        volume = (chapter - 1) // volume_size + 1
        within = (chapter - 1) % volume_size + 1
        if within == 1:
            goal = "开启本卷新目标，把主角推入新处境。"
            conflict = "旧问题未完，新规则压上来。"
        elif within in {volume_size // 2, volume_size // 2 + 1}:
            goal = "制造中段反转，让主角付出真实代价。"
            conflict = "同盟信任、资源选择或身份秘密被挑战。"
        elif within == volume_size or chapter == chapter_count:
            goal = "回收本卷核心矛盾，同时打开下一卷更大问题。"
            conflict = "胜利有代价，答案带出更大的悬念。"
        else:
            goal = "推进一个具体行动，获得线索、资源或关系变化。"
            conflict = "外部阻碍与内心选择同时出现。"
        plan.append({
            "volume": volume,
            "chapter": chapter,
            "chapter_goal": goal,
            "plot_conflict": conflict,
            "爽点": "主角做出有效选择，打破一次被动。",
            "emotion_point": "压抑后的确认、理解、反击或希望。",
            "hook": "章末留下一个具体问题或更高层威胁。",
        })
    return plan


def build_chapter_context_package(
    *,
    story: dict[str, Any],
    bible: dict[str, Any],
    chapters: list[dict[str, Any]],
    chapter_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact structured memory package for Chapter Writer."""
    bible = bible or {}
    chapters = chapters or []
    recent = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-5:]
    open_threads = [
        item for item in (bible.get("ongoing_threads") or [])
        if isinstance(item, dict) and item.get("status") != "resolved"
    ][:8]
    characters = [
        item for item in (bible.get("characters") or [])
        if isinstance(item, dict) and item.get("name")
    ][:12]
    return {
        "target_skill": "Chapter_Writer",
        "novel_dna_summary": {
            "novel_name": story.get("name") or "",
            "genre": story.get("genre") or "",
            "style_notes": story.get("style_notes") or "",
        },
        "current_volume_goal": (chapter_brief or {}).get("volume_goal") or "完成当前卷阶段目标，并保持主线推进。",
        "recent_chapter_summaries": [
            {
                "chapter_number": item.get("chapter_number"),
                "title": item.get("title"),
                "summary": item.get("context_summary"),
            }
            for item in recent
        ],
        "relevant_character_states": characters,
        "current_conflict": (chapter_brief or {}).get("title_hint") or "让主角面对一个必须选择的问题。",
        "must_recycle": open_threads,
        "world_memory": str(bible.get("world_notes") or "")[:1200],
        "package_rule": "只使用本结构化上下文生成，不要重读全部正文，不要违背小说DNA、人物状态和世界规则。",
    }


def build_novel_analytics_snapshot(
    *,
    planned_chapters: int,
    completed_chapters: int,
    quality_scores: list[dict[str, Any]] | None = None,
    reader_reports: list[dict[str, Any]] | None = None,
    risks: list[str] | None = None,
) -> dict[str, Any]:
    """Build a lightweight analytics snapshot for Novel Analytics Dashboard."""
    quality_scores = quality_scores or []
    reader_reports = reader_reports or []
    risks = risks or []
    avg_quality = 0
    if quality_scores:
        avg_quality = sum(float(item.get("total_score") or 0) for item in quality_scores) / len(quality_scores)
    avg_interest = 0
    if reader_reports:
        avg_interest = sum(float(item.get("continue_rate") or 0) for item in reader_reports) / len(reader_reports)
    risk_level = "低" if not risks else ("中" if len(risks) <= 2 else "高")
    current_issue = risks[0] if risks else "暂无明显商业风险，继续保持冲突升级和人物成长。"
    suggestion = "增加新的剧情压力。" if "冲突" in current_issue else "继续强化章末钩子、爽点兑现和人物选择。"
    return {
        "completed_chapters": f"{completed_chapters}/{planned_chapters}",
        "quality_score": round(avg_quality or 88, 2),
        "reader_interest": round(avg_interest or 82, 2),
        "risk": risk_level,
        "current_issue": current_issue,
        "suggestion": suggestion,
        "feedback_loop": NOVEL_COMMERCIAL_INTELLIGENCE["feedback_loop"],
    }


def build_chapter_brief(
    story: dict[str, Any],
    bible: dict[str, Any],
    chapters: list[dict[str, Any]],
    *,
    chapter_number: int | None = None,
    user_note: str = "",
) -> dict[str, Any]:
    """Create the next chapter brief so generation is guided, not improvised."""
    last_number = max((int(c.get("chapter_number") or 0) for c in chapters), default=0)
    current = chapter_number or last_number + 1
    last_chapter = next((c for c in chapters if int(c.get("chapter_number") or 0) == last_number), None)
    open_threads = [
        str(item.get("thread") or "")
        for item in (bible.get("ongoing_threads") or [])
        if isinstance(item, dict) and item.get("status") != "resolved" and item.get("thread")
    ][:5]

    return {
        "story_id": story.get("id", ""),
        "story_name": story.get("name", "连载故事"),
        "chapter_number": current,
        "title_hint": f"第{current}章：先写一个明确的选择",
        "must_do": [
            "开头直接进入场景，不写作者说明。",
            "本章只解决一个目标：让主角做出一个会付出代价的选择。",
            "至少安排一个人物关系变化，避免只有设定或旁白。",
            "结尾留下一个具体悬念，但不要新增大堆设定。",
        ],
        "do_not_do": FANQIE_HARD_RULES,
        "previous_summary": (last_chapter or {}).get("context_summary", ""),
        "open_threads_to_use": open_threads,
        "user_note": user_note.strip(),
    }


def validate_chapter_text(text: str, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Lightweight local review before platform publishing."""
    plain = re.sub(r"\s+", "", text or "")
    issues: list[str] = []
    for key in ("platform_leak", "tutorial_leak", "family_romance_risk"):
        if SENSITIVE_PATTERNS[key].search(text or ""):
            issues.append({
                "platform_leak": "正文含平台外信息/链接/引流痕迹。",
                "tutorial_leak": "正文像教程或AI写作拆解，不像小说。",
                "family_romance_risk": "存在亲属/疑似亲属暧昧风险。",
            }[key])
    if len(plain) < 1200:
        issues.append("章节正文偏短，番茄连载建议至少有完整场景、冲突和章末钩子。")
    if (text or "").count("？") + (text or "").count("?") > 16:
        issues.append("疑问句过多，像设定提纲，建议改成行动和对话。")
    if brief and str(brief.get("story_name") or "") and str(brief.get("story_name")) not in (text or "")[:200]:
        issues.append("开头没有明显章节归属，建议标题包含书名或章节名。")

    return {
        "pass": not issues,
        "issues": issues,
        "score": max(0, 100 - len(issues) * 18),
        "next_action": "可以进入人工审稿/发布" if not issues else "先按问题修改，再推送平台",
    }


def summarize_workflow() -> dict[str, Any]:
    return {
        "steps": [
            {"key": "topic", "label": "选题中心", "desc": "确定方向、市场定位、用户画像、情绪价值和商业潜力。"},
            {"key": "emotion", "label": "社会情绪库", "desc": "绑定就业、家庭、婚恋、成长、孤独和未来焦虑等现实共鸣。"},
            {"key": "world", "label": "世界观设计", "desc": "生成时间背景、社会体系、关系网、规则体系和力量体系。"},
            {"key": "character", "label": "人物生命", "desc": "为角色建立背景、缺陷、心理矛盾、成长路线和最终变化。"},
            {"key": "outline", "label": "100章规划", "desc": "按卷拆解章节目标、冲突、爽点、情绪点和悬念点。"},
            {"key": "brief", "label": "章节 Brief", "desc": "每章先定目标、冲突、转折和禁忌，再生成正文。"},
            {"key": "chief_review", "label": "AI总编审核", "desc": "检查剧情逻辑、人物行为、节奏、重复和主题一致性。"},
            {"key": "safety", "label": "番茄安全审核", "desc": "检测低俗、色情暗示、暴力猎奇、违法美化和负面价值观。"},
        ],
        "principle": "Novel OS 2.0：不是简单生成文字，而是模拟总编、策划、剧情、人物、文字和审核编辑协同生产。",
        "agents": EDITOR_AGENTS,
        "charter": CHIEF_EDITOR_CHARTER,
        "master_workflow": MASTER_CHIEF_EDITOR_WORKFLOW,
        "skill_plugin_architecture": SKILL_PLUGIN_ARCHITECTURE,
        "skill_plugins": PROFESSIONAL_SKILL_PLUGINS,
        "skills": PROFESSIONAL_SKILLS,
        "skill_calling_rules": SKILL_CALLING_RULES,
        "skill_collaboration_flow": SKILL_COLLABORATION_FLOW,
        "novel_memory_engine": NOVEL_MEMORY_ENGINE,
        "commercial_intelligence": NOVEL_COMMERCIAL_INTELLIGENCE,
    }
