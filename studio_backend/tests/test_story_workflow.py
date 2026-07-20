from studio_backend.story_workflow import (
    build_chapter_brief,
    build_story_blueprint,
    diagnose_story_archive,
    validate_chapter_text,
)
from studio_backend.novel_engine import (
    build_chapter_brief_from_book,
    build_chapter_plans,
    generate_chapter_from_plan,
    _editor_step,
    _enforce_paragraph_level_rules,
    _paragraph_similarity,
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

    assert brief["title_hint"] == "第1章：残香复燃，槐井索命"
    assert chapter["title"] == "第1章：残香复燃，槐井索命"
    assert "开局危机" not in chapter["title"]
    assert "用一次具体事件" not in chapter["title"]
    assert len(chapter["title"]) <= 30


def test_chapter_title_rewrites_stage_label_into_reader_hook():
    book = {
        "id": "book-title-2",
        "title": "香火簿",
        "genre": "eastern_mysticism",
        "characters": [{"name": "云栖"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 2,
            "goal": "推进【开局危机】：用一次具体事件把人物困境、世界规则和核心悬念同时压到眼前。",
            "conflict": "庙门外再次传来求救声，槐井里的东西已经追到门口。",
            "suspense": "供桌残香忽然复燃，木牌背面露出一个旧名字。",
        }],
    }

    archive = {"chapters": [{"chapter_number": 1, "title": "第1章：残香复燃，槐井索命"}]}
    brief = build_chapter_brief_from_book(book, archive)
    chapter = generate_chapter_from_plan(book, archive, brief)

    assert brief["title_hint"] == "第2章：求救声到了门口"
    assert chapter["title"] == "第2章：求救声到了门口"
    assert "推进" not in chapter["title"]
    assert "开局危机" not in chapter["title"]
    assert len(chapter["title"]) <= 30


def test_chapter_generation_avoids_duplicate_title_from_archive():
    book = {
        "id": "book-title-3",
        "title": "香火簿",
        "genre": "eastern_mysticism",
        "characters": [{"name": "云栖"}, {"name": "周望"}],
        "plot_outline": [{
            "chapter": 2,
            "goal": "推进【开局危机】：用一次具体事件把人物困境、世界规则和核心悬念同时压到眼前。",
            "conflict": "槐井里的东西追到庙门口。",
            "suspense": "供桌残香忽然复燃。",
        }],
    }
    archive = {"chapters": [{"chapter_number": 1, "title": "第1章：残香复燃，槐井索命"}]}
    brief = {
        "chapter_number": 2,
        "chapterPlan": book["plot_outline"][0],
    }

    chapter = generate_chapter_from_plan(book, archive, brief)

    assert chapter["title"] != "第2章：残香复燃，槐井索命"
    assert chapter["title"] == "第2章：槐井里的东西来了"


def test_generated_second_chapter_continues_without_repeating_first_chapter():
    plans = build_chapter_plans([
        {
            "chapter": 1,
            "title": "危机已经上门",
            "goal": "云栖救下供桌前的孩子，发现香灰断了三年。",
            "conflict": "庙外雨声急，村人把孩子的命推到他面前。",
            "suspense": "井口传来第二声哭喊。",
        },
        {
            "chapter": 2,
            "title": "新的麻烦来了",
            "goal": "云栖查清红纸上出现自己名字的原因。",
            "conflict": "救人后村人反而怀疑他惹来灾祸。",
            "suspense": "槐井边的功德簿翻到空白页，浮出云栖的名字。",
            "new_clues": ["红纸姓名", "槐井水痕", "供桌香灰"],
            "previous_consequence": "被救的孩子醒来后说井里还有名字。",
        },
    ], 2)
    book = {
        "id": "book-continuity",
        "title": "香火成仙：我替众生改命",
        "genre": "玄幻",
        "core_design": {"主角": "云栖", "重要配角": "香火明", "平台标签": "香火玄学"},
        "characters": [{"name": "云栖"}, {"name": "香火明"}],
        "plot_outline": plans,
    }
    archive = {"chapters": []}
    first_brief = build_chapter_brief_from_book(book, archive, chapter_number=1)
    first = generate_chapter_from_plan(book, archive, first_brief)
    archive["chapters"] = [first]

    second_brief = build_chapter_brief_from_book(book, archive, chapter_number=2)
    second = generate_chapter_from_plan(book, archive, second_brief)

    assert len(second["content"]) >= 2000
    assert second["continuity_review"]["pass"]
    assert second["chapter_self_check"]["pass"]
    assert second["chapter_self_check"]["similarity"] <= 0.1
    assert second["chapter_self_check"]["plot_paragraphs"] >= second["chapter_self_check"]["description_paragraphs"]
    assert second["chapter_self_check"]["dead_progress_windows"] == 0
    assert second["chapter_self_check"]["internal_repetition_count"] == 0
    assert second["chapter_self_check"]["adjacent_similarity_count"] == 0
    assert second["continuity_review"]["shared_sentences"] == []
    assert "第一声哭喊传进破庙时" not in second["content"]
    assert "供桌上的残香忽然自己亮了" not in second["content"]
    assert "女人膝盖一软，几乎是爬到供桌前的" not in second["content"]
    assert "推进主线" not in second["content"]
    assert "伏笔" not in second["content"]
    assert "上一章" not in second["content"]
    assert "想起" not in second["content"]


def test_chapter_brief_event_plan_labels_new_events_and_rewrites_repeats():
    book = {
        "id": "book-plan",
        "title": "香火簿",
        "genre": "eastern_mysticism",
        "characters": [{"name": "云栖"}, {"name": "香火明"}],
        "plot_outline": [{
            "chapter": 2,
            "goal": "云栖查清红纸上出现自己名字的原因。",
            "conflict": "救人后村人反而怀疑他惹来灾祸。",
            "suspense": "槐井边的功德簿翻到空白页，浮出云栖的名字。",
            "new_clues": ["红纸姓名", "槐井水痕", "供桌香灰"],
            "event_plan": [
                {"event": "女人抱着孩子闯进破庙求救，供桌上的残香忽然自己亮了。", "tags": ["推进主线"]},
                {"event": "村人把红纸堵到庙门口，逼云栖解释名字来源。", "tags": ["冲突"]},
                {"event": "供桌香灰里出现新的经手人指印。", "tags": ["推进主线", "伏笔"]},
            ],
        }],
    }
    archive = {
        "chapters": [{
            "chapter_number": 1,
            "title": "第1章：残香复燃，槐井索命",
            "content": "第一声哭喊传进破庙时，供桌上的残香忽然自己亮了。女人抱着孩子求救。",
        }]
    }

    brief = build_chapter_brief_from_book(book, archive, chapter_number=2)
    event_plan = brief["chapterPlan"]["event_plan"]

    assert 3 <= len(event_plan) <= 5
    assert all(item["event"] for item in event_plan)
    assert all(any(tag in ["冲突", "推进主线", "伏笔"] for tag in item["tags"]) for item in event_plan)
    assert all(item["advances_mainline"] in ["是", "否"] for item in event_plan)
    assert all(item["creates_conflict"] in ["是", "否"] for item in event_plan)
    assert all(item["new_information"] in ["是", "否"] for item in event_plan)
    assert "第一声哭喊传进破庙时" not in event_plan[0]["event"]
    assert "女人抱着孩子" not in event_plan[0]["event"]
    assert "破庙求救" not in event_plan[0]["event"]
    assert any("冲突" in item["tags"] for item in event_plan)
    assert any("推进主线" in item["tags"] for item in event_plan)
    assert any(item["new_information"] == "是" for item in event_plan)


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

    assert chapter["title"] == "第1章：她帮一单，命运改写"
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


def test_generated_chapter_does_not_leak_reader_meta_fallback():
    book = {
        "id": "book-no-reader-meta",
        "title": "香火簿",
        "genre": "eastern_mysticism",
        "characters": [{"name": "云栖"}, {"name": "香火明"}],
        "plot_outline": [{
            "chapter": 1,
            "goal": "云栖救下供桌前的孩子，发现香灰断了三年。",
            "conflict": "庙外雨声急，村人把孩子的命推到他面前。",
            "suspense": "井口传来第二声哭喊。",
        }],
    }
    brief = build_chapter_brief_from_book(book, {"chapters": []})
    chapter = generate_chapter_from_plan(book, {"chapters": []}, brief)

    assert "故事刚开始" not in chapter["content"]
    assert "读者" not in chapter["content"]
    assert "第一个选择" not in chapter["content"]
    assert "如何面对" not in chapter["content"]
    assert chapter["editorial_review"]["pass"]


def test_editor_rejects_template_phrase_and_overlong_memory():
    content = "\n\n".join([
        "第2章：槐井有名",
        "云栖推开庙门，水痕从门槛一路延到供桌下。",
        "他心中一震，暗暗发誓一定要查清真相。",
        "他想起上一章那些细节，想起雨声，想起女人磕头，想起孩子的手，想起供桌残香，想起井边黑水，想起每一句话。" * 16,
        "香火明压低声音问：“你看见什么了？”",
        "云栖把红纸按在香灰里，“名字不是浮出来的，是有人提前写上去的。”",
        "井口忽然响了一声，水面浮出第二张红纸。",
    ])

    result = _editor_step(content)

    assert not result["pass"]
    assert any("模板化" in issue for issue in result["issues"])
    assert any("回忆" in issue for issue in result["issues"])
    assert any("多处回忆" in issue or "不能多段展开" in issue for issue in result["issues"])


def test_paragraph_level_rules_remove_repeated_recap_and_extra_memory():
    archive = {
        "chapters": [{
            "chapter_number": 1,
            "content": "云栖推开庙门，供桌上的残香忽然亮了。\n\n女人抱着孩子求救。",
        }]
    }
    content = "\n\n".join([
        "第2章：井边红纸",
        "云栖推开庙门，供桌上的残香忽然亮了。",
        "他开始解释之前发生的事情经过。",
        "他想起那晚的铜铃。",
        "他又想起上一章的雨声和求救声。",
        "红纸从井沿翻起，露出一个新的名字。",
        "香火明拦住退走的人，“你把纸从哪拿来的？”",
    ])

    cleaned = _enforce_paragraph_level_rules(content, archive, 2)

    assert "供桌上的残香忽然亮了" not in cleaned
    assert "解释之前发生" not in cleaned
    assert "他又想起" not in cleaned
    assert "红纸从井沿翻起" in cleaned


def test_paragraph_level_rules_remove_internal_repeated_events_and_dialogue():
    archive = {
        "chapters": [{
            "chapter_number": 1,
            "content": "旧章只留下井边线索，没有发生新的搜查。",
        }]
    }
    content = "\n\n".join([
        "第2章：井边红纸",
        "云栖把红纸按在石面上，盯住纸边渗出的香灰。",
        "云栖又把红纸按在石面上，再次盯住纸边渗出的香灰。",
        "香火明拦住退走的人，“你把纸从哪拿来的？”",
        "香火明追上那人，“你把纸从哪拿来的？”",
        "铜铃忽然裂开，里面掉出一枚刻着生辰的木牌。",
        "槐井水面浮出新的名字，村长脸色当场变了。",
    ])

    cleaned = _enforce_paragraph_level_rules(content, archive, 2)

    assert cleaned.count("红纸按在石面上") == 1
    assert cleaned.count("你把纸从哪拿来的") == 1
    assert "铜铃忽然裂开" in cleaned
    assert "槐井水面浮出新的名字" in cleaned


def test_adjacent_similar_paragraphs_jump_to_new_event():
    archive = {"chapters": []}
    plan = {
        "chapter": 2,
        "conflict": "村长拒绝带路去旧渡口。",
        "suspense": "槐井边的功德簿翻到空白页。",
        "new_clues": ["红纸姓名", "槐井水痕"],
    }
    book = {
        "title": "香火成仙",
        "genre": "玄幻",
        "characters": [{"name": "云栖"}, {"name": "香火明"}],
        "core_design": {"平台标签": "香火玄学"},
    }
    content = "\n\n".join([
        "第2章：井边红纸",
        "云栖把红纸按在石面上，盯住纸边渗出的香灰。",
        "云栖又把红纸按到石面边缘，继续盯着纸边渗出的香灰。",
        "铜铃忽然裂开，里面掉出一枚刻着生辰的木牌。",
    ])

    cleaned = _enforce_paragraph_level_rules(content, archive, 2, plan, book)

    assert "继续盯着纸边渗出的香灰" not in cleaned
    assert "纸铺学徒" in cleaned or "井亭方向" in cleaned or "新红线" in cleaned or "湿脚印" in cleaned
    assert "铜铃忽然裂开" in cleaned


def test_generated_paragraph_pool_rewrites_similarity_over_point_eight():
    archive = {"chapters": []}
    first = "云栖把红纸按在石面上，盯住纸边渗出的香灰。"
    repeated = "云栖将红纸按在石面边缘，继续盯着纸边渗出的香灰。"
    new_event = "铜铃忽然裂开，里面掉出一枚刻着生辰的木牌。"
    content = "\n\n".join([
        "第2章：井边红纸",
        first,
        repeated,
        new_event,
    ])

    assert _paragraph_similarity(repeated, first) > 0.8

    cleaned = _enforce_paragraph_level_rules(
        content,
        archive,
        2,
        {"chapter": 2, "new_clues": ["红纸姓名"], "conflict": "村长拒绝交代。"},
        {"title": "香火成仙", "characters": [{"name": "云栖"}, {"name": "香火明"}]},
    )

    assert first in cleaned
    assert repeated not in cleaned
    assert "纸铺学徒" in cleaned or "井亭方向" in cleaned or "新红线" in cleaned or "湿脚印" in cleaned
    assert new_event in cleaned


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
