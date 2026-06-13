from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_backend import publishing


class PublishingTests(unittest.TestCase):
    def test_prepare_material_distribution_without_video_job(self):
        material = {
            "id": "wechat_1",
            "text": "今天我用 AI 整理了重复工作",
            "script": "真正有用的自动化，是把省下来的时间还给自己。",
            "content_mode": "working_mom",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def media_url(path):
                return f"/files/{Path(path).relative_to(output_dir).as_posix()}"

            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "to_media_url", side_effect=media_url),
            ):
                result = publishing.prepare_material_distribution_package(material)

        self.assertEqual(result["material_id"], "wechat_1")
        self.assertEqual(result["source_type"], "wechat_material")
        self.assertEqual(result["wechat"]["status"], "ready")

    def test_prepare_distribution_package_writes_channel_files(self):
        job = {
            "id": "job_1",
            "status": "completed",
            "script_text": "这是第一段。\n这是第二段，也是一条可执行建议。",
            "request": {
                "topic": "职场妈妈如何用 AI 提效",
                "content_mode": "working_mom",
            },
            "artifacts": {"audio_url": "/studio-files/audio.mp3"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def media_url(path):
                return f"/files/{Path(path).relative_to(output_dir).as_posix()}"

            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "to_media_url", side_effect=media_url),
            ):
                result = publishing.prepare_distribution_package(job)

            package_dir = output_dir / "distribution" / result["id"]
            self.assertTrue((package_dir / "wechat_article.html").exists())
            self.assertTrue((package_dir / "xiaohongshu_note.txt").exists())
            self.assertTrue((package_dir / "manifest.json").exists())
            self.assertIn("#职场妈妈", result["xiaohongshu"]["body"])
            self.assertEqual(result["wechat"]["status"], "ready")

    def test_submit_wechat_draft_uses_saved_cover(self):
        task = {
            "id": "distribution_1",
            "title": "测试标题",
            "summary": "测试摘要",
            "author": "作者",
        }
        responses = [{"media_id": "draft_123"}]

        def fake_post(path, token, payload):
            self.assertEqual(path, "draft/add")
            self.assertEqual(token, "token_1")
            self.assertEqual(payload["articles"][0]["thumb_media_id"], "cover_1")
            return responses.pop(0)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            article_dir = output_dir / "distribution" / task["id"]
            article_dir.mkdir(parents=True)
            (article_dir / "wechat_article.html").write_text(
                "<p>正文</p>", encoding="utf-8"
            )
            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "_post_wechat_json", side_effect=fake_post),
            ):
                result = publishing.submit_wechat_draft(
                    task,
                    get_access_token=lambda: "token_1",
                    thumb_media_id="cover_1",
                )

        self.assertEqual(result["status"], "draft_created")
        self.assertEqual(result["draft_media_id"], "draft_123")


if __name__ == "__main__":
    unittest.main()
