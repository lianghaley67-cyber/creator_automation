from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from studio_backend import publishing


class PublishingTests(unittest.TestCase):
    def test_wechat_channel_html_renders_markdown_table(self):
        html_output = publishing._wechat_channel_html(
            "\n".join(
                [
                    "## 同类工具怎么比",
                    "| 维度 | Trae | 同类工具 |",
                    "| --- | --- | --- |",
                    "| 适合人群 | 新手先测小任务 | 看是否更适合专业用户 |",
                    "| 数据风险 | 先看权限提示 | 敏感资料谨慎上传 |",
                ]
            )
        )

        self.assertIn("<table", html_output)
        self.assertIn("<th", html_output)
        self.assertIn("维度", html_output)
        self.assertIn("新手先测小任务", html_output)
        self.assertNotIn("| 维度 | Trae | 同类工具 |", html_output)

    def test_wechat_channel_html_renders_table_with_blank_lines(self):
        html_output = publishing._wechat_channel_html(
            "\n".join(
                [
                    "## 同类工具怎么比",
                    "| 维度 | Claude Code | 同类工具 |",
                    "| --- | --- | --- |",
                    "",
                    "| 适合人群 | 适合命令行用户 | 看是否更适合图形界面新手 |",
                    "",
                    "| 数据风险 | 先看项目权限 | 敏感资料谨慎上传 |",
                ]
            )
        )

        self.assertIn("<table", html_output)
        self.assertIn("Claude Code", html_output)
        self.assertIn("敏感资料谨慎上传", html_output)
        self.assertNotIn("| 数据风险 |", html_output)

    def test_tool_tutorial_images_are_labeled_as_illustrations(self):
        article_html = "<!doctype html><html><body><p>正文</p></body></html>"
        injected = publishing._inject_tool_tutorial_screenshots(
            article_html,
            [
                {
                    "src": "tutorial_screenshots/01.png",
                    "alt": "示意图 1：确认官方入口",
                    "caption": "小白看这张图，要能确认下一步点哪里。",
                }
            ],
        )

        self.assertIn("配图实操版：操作示意图", injected)
        self.assertIn("不是真实网页截图", injected)
        self.assertNotIn("下面这 4 张图不是装饰图", injected)

    def test_tool_tutorial_images_injected_after_existing_heading(self):
        article_html = (
            '<!doctype html><html><body><section>'
            '<h2 style="color:#0b6670;">配图实操版：照着这几张图做</h2>'
            "<p>下面补图。</p></section></body></html>"
        )
        injected = publishing._inject_tool_tutorial_screenshots(
            article_html,
            [
                {
                    "src": "tutorial_screenshots/01.png",
                    "alt": "Claude Code 官方入口真实截图",
                    "caption": "真实截图：确认官方入口。",
                    "kind": "real",
                }
            ],
        )

        self.assertIn('src="tutorial_screenshots/01.png"', injected)
        self.assertIn("真实截图：确认官方入口", injected)
        self.assertEqual(injected.count("配图实操版"), 1)

    def test_public_screenshot_url_safety(self):
        self.assertTrue(publishing._is_public_https_url("https://www.trae.ai/"))
        self.assertFalse(publishing._is_public_https_url("http://www.trae.ai/"))
        self.assertFalse(publishing._is_public_https_url("https://localhost/admin"))
        self.assertFalse(publishing._is_public_https_url("https://127.0.0.1/admin"))
        self.assertFalse(publishing._is_public_https_url("https://192.168.1.2/admin"))

    def test_generate_tool_tutorial_images_prefers_real_official_screenshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir)

            def fake_capture(url, output_path):
                output_path.write_bytes(b"png")
                return True

            with patch.object(publishing, "_capture_public_webpage_screenshot", side_effect=fake_capture):
                images = publishing._generate_tool_tutorial_screenshots(
                    package_dir,
                    tool_name="Trae",
                    official_url="https://www.trae.ai/",
                )

        self.assertEqual(images[0]["kind"], "real")
        self.assertIn("真实截图", images[0]["caption"])
        self.assertEqual(images[0]["src"], "tutorial_screenshots/01.png")
        self.assertTrue(any(item["kind"] == "illustration" for item in images[1:]))

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
                patch.dict("os.environ", {"CREATOR_STUDIO_REAL_SCREENSHOTS": "0"}),
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
                self.assertIn(
                    "一键保存到小红书草稿箱.bat",
                    bundle.namelist(),
                )
                assistant = bundle.read("xiaohongshu_fill_assistant.py").decode("utf-8")
                self.assertIn('action == "SAVE"', assistant)
                self.assertIn("保存草稿", assistant)
                self.assertIn('["上传图文"]', assistant)
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
            "xiaohongshu_operator_flywheel_v1",
        )
        self.assertEqual(result["wechat"]["skill_id"], "wechat_operator_flywheel_v1")
        self.assertNotEqual(
            result["wechat"]["markdown"],
            result["xiaohongshu"]["body"],
        )
        self.assertEqual(len(result["xiaohongshu"]["publish_steps"]), 4)

    def test_prepare_tool_trend_distribution_uses_deep_review_skill(self):
        trend = {
            "id": "trend_tool_1",
            "title": "Trae 安装说明",
            "summary": "Trae 安装和上手资料。",
            "items": [
                {
                    "title": "Trae 安装教程",
                    "summary": "包含下载、登录和模型配置。",
                    "url": "https://example.com/trae",
                }
            ],
            "angles": ["Trae 是什么", "Trae 怎么安装"],
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
                    script="帮我说明 Trae 是什么，以及新手怎么安装。",
                    question="Trae 安装说明",
                )

        self.assertEqual(
            result["channel_skills"]["wechat"],
            "wechat_tool_deep_review_v1",
        )
        self.assertEqual(
            result["channel_skills"]["xiaohongshu"],
            "xiaohongshu_tool_deep_review_v1",
        )
        self.assertIn("安装前先检查", result["wechat"]["markdown"])
        self.assertNotIn("核心信息卡", result["wechat"]["markdown"])
        self.assertIn("同类工具怎么比", result["wechat"]["markdown"])

    def test_tool_deep_review_bypasses_ai_when_api_key_exists(self):
        trend = {
            "id": "trend_tool_2",
            "title": "Claude Code 零基础上手",
            "summary": "Claude Code 安装、配置和第一个任务。",
            "items": [
                {
                    "title": "Claude Code 官方文档",
                    "summary": "包含安装、登录、权限和命令行使用说明。",
                    "url": "https://docs.anthropic.com/en/docs/claude-code/overview",
                },
                {
                    "title": "Top 5 AI Tools For Content Creators",
                    "summary": "这条是无关的 AI 资讯，不应该混进 Claude Code 教程。",
                    "url": "https://example.com/unrelated-ai-tools",
                },
            ],
            "angles": ["Claude Code 怎么安装", "Claude Code 第一次怎么用"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def media_url(path):
                return f"/files/{Path(path).relative_to(output_dir).as_posix()}"

            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "to_media_url", side_effect=media_url),
                patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "CREATOR_STUDIO_REAL_SCREENSHOTS": "0"}),
                patch(
                    "studio_backend.channel_skills._ai_generate_channel_drafts",
                    side_effect=AssertionError("tool deep review should not call AI"),
                ) as ai_generate,
            ):
                result = publishing.prepare_trend_distribution_package(
                    trend,
                    script="帮我把 Claude Code 讲成小白也能照着做的安装教程。",
                    question="Claude Code 零基础上手",
                    wechat_skill_id="wechat_tool_deep_review_v1",
                    xiaohongshu_skill_id="xiaohongshu_tool_deep_review_v1",
                )

        ai_generate.assert_not_called()
        markdown = result["wechat"]["markdown"]
        self.assertEqual(result["wechat"]["skill_id"], "wechat_tool_deep_review_v1")
        self.assertEqual(
            result["xiaohongshu"]["skill_id"],
            "xiaohongshu_tool_deep_review_v1",
        )
        self.assertIn("Claude Code 零基础上手", result["title"])
        self.assertNotIn("## 先给结论", markdown)
        self.assertNotIn("## 先说结论", markdown)
        self.assertIn("我会先测 Claude Code，是因为我在做", markdown)
        self.assertIn("## 它的功能，对普通人意味着什么", markdown)
        self.assertIn("省哪一步", result["xiaohongshu"]["body"])
        self.assertIn("## 10 分钟实操：照着跑一遍", markdown)
        self.assertIn("第一次测试这类工具", markdown)
        self.assertIn("## 发布前再核验：这 5 件事别省", markdown)
        self.assertIn("## 截图清单", markdown)
        self.assertIn("## 同类工具怎么比", markdown)
        self.assertIn("A 看懂项目", markdown)
        self.assertNotIn("你怎么看", markdown)
        self.assertNotIn("## 我为什么测它", markdown)
        self.assertNotIn("当前抓到的资料", markdown)
        self.assertNotIn("Top 5 AI Tools For Content Creators", markdown)

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

    def test_submit_wechat_draft_uploads_local_article_images(self):
        task = {
            "id": "distribution_img",
            "title": "测试标题",
            "summary": "测试摘要",
            "author": "作者",
        }
        captured_content = ""

        def fake_post(path, token, payload):
            nonlocal captured_content
            self.assertEqual(token, "token_1")
            if path == "draft/add":
                captured_content = payload["articles"][0]["content"]
                self.assertIn("https://mmbiz.qpic.cn/article-image.png", captured_content)
                self.assertNotIn("tutorial_screenshots/01.png", captured_content)
                return {"media_id": "draft_123"}
            self.assertEqual(path, "draft/get")
            return {"news_item": [{"title": "测试标题", "content": captured_content}]}

        def fake_upload(*, token, image_path):
            self.assertEqual(token, "token_1")
            self.assertEqual(image_path.name, "01.png")
            return "https://mmbiz.qpic.cn/article-image.png"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            article_dir = output_dir / "distribution" / task["id"]
            image_dir = article_dir / "tutorial_screenshots"
            image_dir.mkdir(parents=True)
            (image_dir / "01.png").write_bytes(b"png")
            (article_dir / "wechat_article.html").write_text(
                '<p>正文</p><img src="tutorial_screenshots/01.png" alt="图">',
                encoding="utf-8",
            )
            with (
                patch.object(publishing, "OUTPUTS_DIR", output_dir),
                patch.object(publishing, "_post_wechat_json", side_effect=fake_post),
                patch.object(
                    publishing,
                    "_upload_wechat_article_image",
                    side_effect=fake_upload,
                ),
            ):
                result = publishing.submit_wechat_draft(
                    task,
                    get_access_token=lambda: "token_1",
                    thumb_media_id="cover_1",
                )

        self.assertEqual(result["status"], "draft_created")
        self.assertIn("mmbiz.qpic.cn", captured_content)

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
