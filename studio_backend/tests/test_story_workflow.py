from studio_backend.story_workflow import (
    build_chapter_brief,
    build_story_blueprint,
    diagnose_story_archive,
    validate_chapter_text,
)
from studio_backend.novel_engine import (
    build_chapter_brief_from_book,
    generate_chapter_from_plan,
)


def test_diagnose_story_archive_flags_genre_and_relationship_risk():
    chapters = [
        {
            "chapter_number": 1,
            "title": "第1章 变量醒来",
            "content_markdown": "她在服务器里看见GitHub日志，哥哥说他们是亲兄妹。",
            "context_summary": "代码和亲属关系风险。",
        },
        {
            "chapter_number": 2,
            "title": "第2章 U盘",
            "content_markdown": "U盘里有洗钱证据，追杀从雨夜开始。",
            "context_summary": "商业犯罪和追杀。",
        },
    ]
    bible = {
        "world_notes": "男主是同母异父哥哥。",
        "ongoing_threads": [{"thread": f"悬念{i}", "status": "open"} for i in range(15)],
    }

    result = diagnose_story_archive(chapters, bible)

    assert result["score"] < 80
    assert result["open_thread_count"] == 15
    assert any("亲属" in issue for issue in result["hard_issues"])
    metrics = {item["key"]: item for item in result["metrics"]}
    assert metrics["genre_drift"]["count"] == 2
    assert metrics["family_romance_risk"]["count"] == 1


def test_build_story_blueprint_creates_confirmable_outline():
    result = build_story_blueprint({
        "title": "烬月灯",
        "genre": "romance_fantasy",
        "idea": "被献祭的少女听见月神灯里的自己。",
        "first_volume_count": 8,
    })

    assert result["status"] == "needs_confirmation"
    assert result["book_profile"]["title"] == "烬月灯"
    assert result["book_profile"]["genre"] == "言情玄幻连载"
    assert len(result["questions"]) >= 5
    assert len(result["chapter_outline"]) == 8


def test_build_chapter_brief_uses_existing_context():
    story = {"id": "s1", "name": "烬月灯"}
    bible = {
        "ongoing_threads": [
            {"thread": "月神灯为什么只回应女主", "status": "open"},
            {"thread": "男主真实阵营", "status": "open"},
        ]
    }
    chapters = [
        {"chapter_number": 1, "title": "初见", "context_summary": "女主被献祭但逃出神殿。"}
    ]

    brief = build_chapter_brief(story, bible, chapters, user_note="男主别太快暴露身份")

    assert brief["chapter_number"] == 2
    assert brief["previous_summary"] == "女主被献祭但逃出神殿。"
    assert "男主真实阵营" in brief["open_threads_to_use"]
    assert brief["user_note"] == "男主别太快暴露身份"


def test_validate_chapter_text_rejects_tutorial_leak():
    text = "第1章\n这是一段小说片段。下面讲提示词怎么写，以及我的修改表格。"

    result = validate_chapter_text(text, {"story_name": "烬月灯"})

    assert not result["pass"]
    assert any("教程" in issue for issue in result["issues"])


def test_book_chapter_brief_contains_world_simulator_contract():
    book = {
        "id": "book-1",
        "title": "人间重启",
        "genre": "urban",
        "characters": [{"name": "林小满"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 1,
            "goal": "让主角帮助陌生人，获得一次新的机会。",
            "conflict": "房租压力和他人的紧急困境同时出现。",
            "suspense": "有人质疑这场善意是摆拍。",
        }],
    }

    brief = build_chapter_brief_from_book(book, {"chapters": []})

    assert brief["world_simulator_contract"]["identity"] == "小说世界模拟器"
    assert "只输出小说正文" in brief["must_do"][1]
    assert brief["chapter_mission"]["goal"] == "让主角帮助陌生人，获得一次新的机会。"


def test_book_chapter_title_uses_short_publishable_name():
    book = {
        "id": "book-title",
        "title": "香火簿",
        "genre": "eastern_mysticism",
        "characters": [{"name": "云栖"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 1,
            "goal": "开启【开局危机】：用一次具体事件把人物困境、世界规则和核心悬念同时压到眼前。",
            "conflict": "供桌残香忽然复燃，有人抱着孩子闯进破庙求救。",
            "suspense": "槐井里的东西已经追到庙门口。",
        }],
    }

    brief = build_chapter_brief_from_book(book, {"chapters": []})
    chapter = generate_chapter_from_plan(book, {"chapters": []}, brief)

    assert brief["title_hint"] == "第1章：开局危机"
    assert chapter["title"] == "第1章：开局危机"
    assert "用一次具体事件" not in chapter["title"]
    assert len(chapter["title"]) <= 30


def test_generate_modern_chapter_uses_grounded_scene_not_template_alarm():
    book = {
        "id": "book-1",
        "title": "人间重启",
        "genre": "urban",
        "hook": "普通人在平凡生活中努力拼搏，相互帮助。",
        "core_design": {"平台标签": "番茄,女频,职场,治愈,励志"},
        "world_setting": {"time_background": "现代城市社区", "social_system": "就业、房租和家庭压力构成现实困境。"},
        "characters": [{"name": "林小满"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 1,
            "goal": "让主角帮助陌生人，获得一次新的机会。",
            "conflict": "房租压力和他人的紧急困境同时出现。",
            "suspense": "有人质疑这场善意是摆拍。",
        }],
    }
    archive = {"chapters": []}
    brief = build_chapter_brief_from_book(book, archive)

    chapter = generate_chapter_from_plan(book, archive, brief)
    content = chapter["content"]

    assert chapter["title"] == "第1章：雨中援手"
    assert "林小满" in content
    assert "周望" in content
    assert "房东" in content or "房租" in content
    assert "警报" not in content
    assert "红字" not in content
    assert "章末留下" not in content
    assert "具体问题" not in content
    assert "更高层威胁" not in content
    assert "下期看点" in content
    assert "主角" not in content
    assert "本章" not in content
    assert "写作思路" not in content
    assert chapter["editorial_review"]["pass"]


def test_generic_protagonist_name_is_replaced_in_generated_chapter():
    book = {
        "id": "book-2",
        "title": "人间重启",
        "genre": "urban",
        "hook": "普通人在平凡生活中努力拼搏，相互帮助。",
        "core_design": {"平台标签": "番茄,女频,职场,治愈,励志"},
        "world_setting": {"time_background": "现代城市社区"},
        "characters": [{"name": "主角"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 1,
            "goal": "让主角帮助陌生人，获得一次新的机会。",
            "conflict": "房租压力和他人的紧急困境同时出现。",
            "suspense": "一段偷拍视频被发进群里，善意突然变成了质疑。",
        }],
    }
    brief = build_chapter_brief_from_book(book, {"chapters": []})
    chapter = generate_chapter_from_plan(book, {"chapters": []}, brief)

    assert "林小满" in chapter["content"]
    assert "主角" not in chapter["content"]


def test_validate_chapter_text_rejects_meta_narration():
    result = validate_chapter_text("本章的作用是增强冲突，章末留下一个具体问题。" * 80)

    assert not result["pass"]
    assert any("写作思路" in issue or "结构提示" in issue for issue in result["issues"])
