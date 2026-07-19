from studio_backend.novel_platforms.fanqie import _fanqie_editor_title


def test_fanqie_editor_title_strips_chapter_prefix():
    assert _fanqie_editor_title("第2章：求救声到了门口", 2) == "求救声到了门口"
    assert _fanqie_editor_title("第12章 槐井里的东西来了", 12) == "槐井里的东西来了"


def test_fanqie_editor_title_handles_book_prefix():
    assert _fanqie_editor_title("香火簿 · 第3章：槐井索命", 3) == "槐井索命"


def test_fanqie_editor_title_keeps_plain_subtitle():
    assert _fanqie_editor_title("她帮一单，命运改写", 1) == "她帮一单，命运改写"
