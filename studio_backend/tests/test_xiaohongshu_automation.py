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


if __name__ == "__main__":
    unittest.main()
