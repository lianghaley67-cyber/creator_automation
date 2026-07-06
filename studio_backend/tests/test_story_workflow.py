from studio_backend.story_workflow import (
    build_chapter_brief,
    build_story_blueprint,
    diagnose_story_archive,
    validate_chapter_text,
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
