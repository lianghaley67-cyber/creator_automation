from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from studio_backend import publishing


class PublishingTests(unittest.TestCase):
    def test_prepare_trend_distribution_adds_xiaohongshu_recommendation(self):
        trend = {
            "id": "trend_1",
            "title": "AI 工具实时日报",
            "summary": "AI 正在降低普通人的内容制作门槛。",
            "items": [{"title": "新工具发布", "summary": "可以自动整理资料。"}],
            "angles": ["职场妈妈如何省时间"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def media_url(path):
                return f"/files/{Path(path).relative_to(output_dir).as_posix()}"

            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "to_media_url", side_effect=media_url),
            ):
                result = publishing.prepare_trend_distribution_package(
                    trend,
                    script="我用这个工具试了一次，确实能省下整理资料的时间。",
                    question="普通人应该怎么用 AI？",
                )
            package_path = (
                output_dir
                / "distribution"
                / result["id"]
                / "xiaohongshu_publish_package.zip"
            )
            self.assertTrue(package_path.exists())
            with zipfile.ZipFile(package_path) as bundle:
                self.assertIn("xiaohongshu_title.txt", bundle.namelist())
                self.assertIn("xiaohongshu_note.txt", bundle.namelist())
                self.assertIn("xiaohongshu_checklist.txt", bundle.namelist())
                self.assertIn("xiaohongshu_cover_text.txt", bundle.namelist())
                self.assertIn(
                    "xiaohongshu_fill_assistant.py",
                    bundle.namelist(),
                )
                assistant = bundle.read("xiaohongshu_fill_assistant.py").decode("utf-8")
                self.assertIn('action == "SAVE"', assistant)
                self.assertIn("保存草稿", assistant)
                compile(assistant, "xiaohongshu_fill_assistant.py", "exec")
                self.assertTrue(
                    any(
                        name.startswith("xiaohongshu_cards/")
                        and name.endswith(".png")
                        for name in bundle.namelist()
                    )
                )

        self.assertEqual(result["trend_id"], "trend_1")
        self.assertTrue(result["xiaohongshu"]["recommended"])
        self.assertTrue(result["xiaohongshu"]["cover_text"])
        self.assertTrue(result["xiaohongshu"]["card_urls"])
        self.assertEqual(
            result["xiaohongshu"]["skill_id"],
            "xiaohongshu_note_v1",
        )
        self.assertEqual(result["wechat"]["skill_id"], "wechat_article_v1")
        self.assertNotEqual(
            result["wechat"]["markdown"],
            result["xiaohongshu"]["body"],
        )
        self.assertEqual(len(result["xiaohongshu"]["publish_steps"]), 4)

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
        self.assertTrue(result["xiaohongshu"]["card_urls"])
        self.assertNotEqual(
            result["wechat"]["markdown"],
            result["xiaohongshu"]["body"],
        )

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
            self.assertTrue((package_dir / "xiaohongshu_cards" / "01.png").exists())
            self.assertIn("#职场妈妈", result["xiaohongshu"]["body"])
            self.assertEqual(result["wechat"]["status"], "ready")
            self.assertEqual(
                result["channel_skills"]["wechat"],
                "wechat_article_v1",
            )

    def test_submit_wechat_draft_uses_saved_cover(self):
        task = {
            "id": "distribution_1",
            "title": "测试标题",
            "summary": "测试摘要",
            "author": "作者",
        }
        responses = [
            {"media_id": "draft_123"},
            {"news_item": [{"title": "测试标题", "content": "<p>正文</p>"}]},
        ]

        def fake_post(path, token, payload):
            self.assertEqual(token, "token_1")
            if path == "draft/add":
                self.assertEqual(payload["articles"][0]["thumb_media_id"], "cover_1")
            else:
                self.assertEqual(path, "draft/get")
                self.assertEqual(payload["media_id"], "draft_123")
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
        self.assertTrue(result["verified"])
        self.assertEqual(result["verified_title"], "测试标题")

    def test_submit_wechat_draft_rejects_missing_media_id(self):
        task = {"id": "distribution_2", "title": "测试标题", "summary": ""}
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            article_dir = output_dir / "distribution" / task["id"]
            article_dir.mkdir(parents=True)
            (article_dir / "wechat_article.html").write_text(
                "<p>正文</p>", encoding="utf-8"
            )
            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "_post_wechat_json", return_value={}),
            ):
                with self.assertRaisesRegex(RuntimeError, "没有返回草稿 media_id"):
                    publishing.submit_wechat_draft(
                        task,
                        get_access_token=lambda: "token_1",
                        thumb_media_id="cover_1",
                    )


if __name__ == "__main__":
    unittest.main()
