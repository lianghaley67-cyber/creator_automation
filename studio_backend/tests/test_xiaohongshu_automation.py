from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from studio_backend import xiaohongshu_automation


class XiaohongshuAutomationTests(unittest.TestCase):
    def test_normalize_mainland_phone(self):
        self.assertEqual(
            xiaohongshu_automation._normalize_phone("+86 138-0013-8000"),
            "13800138000",
        )
        with self.assertRaisesRegex(ValueError, "11 位"):
            xiaohongshu_automation._normalize_phone("123")

    def test_resolve_media_paths_keeps_files_inside_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            studio_dir = Path(temp_dir)
            card = studio_dir / "outputs" / "distribution" / "task_1" / "cards" / "01.png"
            card.parent.mkdir(parents=True)
            card.write_bytes(b"png")
            task = {
                "xiaohongshu": {
                    "card_urls": [
                        "/studio-files/outputs/distribution/task_1/cards/01.png",
                        "/studio-files/../outside.png",
                    ]
                }
            }

            with patch.object(xiaohongshu_automation, "STUDIO_DIR", studio_dir):
                result = xiaohongshu_automation._resolve_media_paths(task)

        self.assertEqual(result, [card.resolve()])

    def test_drag_on_page_replays_pointer_gesture(self):
        page = MagicMock()
        page.viewport_size = {"width": 1440, "height": 1000}

        with (
            patch.object(xiaohongshu_automation, "_is_logged_in", return_value=False),
            patch.object(
                xiaohongshu_automation,
                "_login_page_screenshot",
                return_value="/studio-files/xiaohongshu_session/login.png?v=1",
            ),
        ):
            result = xiaohongshu_automation._drag_on_page(
                page,
                800,
                600,
                1050,
                600,
            )

        page.mouse.move.assert_any_call(800, 600)
        page.mouse.down.assert_called_once_with()
        page.mouse.move.assert_any_call(1050, 600, steps=35)
        page.mouse.up.assert_called_once_with()
        self.assertEqual(result["status"], "drag_completed")
        self.assertEqual(result["viewport_width"], 1440)

    def test_click_login_button_prefers_visible_submit_control(self):
        page = MagicMock()
        code_input = MagicMock()
        button = MagicMock()

        with patch.object(
            xiaohongshu_automation,
            "_first_visible",
            return_value=button,
        ):
            method = xiaohongshu_automation._click_login_button(page, code_input)

        self.assertEqual(method, "selector")
        button.scroll_into_view_if_needed.assert_called_once_with()
        button.click.assert_called_once_with(
            no_wait_after=True,
            timeout=10000,
            force=True,
        )

    def test_click_text_control_uses_dom_click_for_visible_tab(self):
        page = MagicMock()
        hidden = MagicMock()
        hidden.is_visible.return_value = False
        visible = MagicMock()
        visible.is_visible.return_value = True
        matches = MagicMock()
        matches.count.return_value = 2
        matches.nth.side_effect = [hidden, visible]
        page.get_by_text.return_value = matches

        clicked = xiaohongshu_automation._click_text_control(
            page,
            ["上传图文"],
        )

        self.assertEqual(clicked, "上传图文")
        visible.evaluate.assert_called_once_with("(element) => element.click()")

    def test_first_visible_action_matches_button_text_without_spaces(self):
        page = MagicMock()
        button = MagicMock()
        button.is_visible.return_value = True
        button.inner_text.return_value = "保存 并离开"
        candidates = MagicMock()
        candidates.count.return_value = 1
        candidates.nth.return_value = button
        page.locator.return_value = candidates

        result = xiaohongshu_automation._first_visible_action(
            page,
            ["保存并离开"],
        )

        self.assertIs(result, button)

    def test_wait_editor_idle_waits_for_loading_to_disappear(self):
        page = MagicMock()
        with patch.object(
            xiaohongshu_automation,
            "_first_visible_contains",
            side_effect=["加载中", ""],
        ):
            xiaohongshu_automation._wait_editor_idle(page, timeout_seconds=2)

        page.wait_for_timeout.assert_called_once_with(800)

    def test_dismiss_editor_suggestions_closes_popup_and_scrolls(self):
        page = MagicMock()
        body_input = MagicMock()
        page_body = MagicMock()
        page.locator.return_value = page_body

        xiaohongshu_automation._dismiss_editor_suggestions(page, body_input)

        body_input.press.assert_called_once_with("Escape")
        page_body.press.assert_called_once_with("Escape")
        page.evaluate.assert_called_once_with(
            "window.scrollTo(0, document.body.scrollHeight)"
        )


if __name__ == "__main__":
    unittest.main()
