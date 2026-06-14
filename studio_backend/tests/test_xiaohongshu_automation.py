from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_backend import xiaohongshu_automation


class XiaohongshuAutomationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
