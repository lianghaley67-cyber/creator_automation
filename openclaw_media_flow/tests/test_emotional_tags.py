from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("media_flow_main", MODULE_PATH)
assert spec and spec.loader
media_flow_main = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media_flow_main
spec.loader.exec_module(media_flow_main)


class EmotionalTagsTest(unittest.TestCase):
    def test_parse_emotional_tags_preserves_anchors_and_structures_audio_params(self) -> None:
        text = "（噗，大笑）哈哈，这太离谱了吧！我当时直接愣住了。（叹气）不过说真的，职场妈妈太难了。"

        result = media_flow_main.parse_emotional_tags(text)

        self.assertEqual(result["raw_text"], text)
        self.assertIn("哈哈", result["text"])
        self.assertIn("离谱", result["text"])
        self.assertIn("职场妈妈太难了", result["text"])
        self.assertNotIn("（噗，大笑）", result["text"])
        self.assertNotIn("（叹气）", result["text"])
        self.assertIn(result["emotion"], {"laughter", "funny", "sigh"})
        self.assertIn("噗，大笑", result["emotion_tags"])
        self.assertIn("叹气", result["emotion_tags"])
        self.assertIn("laugh", result["audio_events"])
        self.assertIn("sigh", result["audio_events"])
        self.assertEqual(result["ssml_hints"]["emotion"], result["emotion"])
        self.assertIs(result["supports_plain_text_emotion"], True)

    def test_legacy_payload_includes_emotional_audio_directives(self) -> None:
        final_text = "\n".join(
            [
                "[画面]: 花生和毛豆坐在明亮的访谈桌前，镜头轻轻推进。",
                "[毛豆]:（噗，大笑）哈哈，这太离谱了吧！我当时直接愣住了。（叹气）不过说真的，职场妈妈太难了。",
            ]
        )
        config = media_flow_main.FlowConfig(
            mode="notebooklm",
            legacy_render_url="http://localhost:8000/api/render",
            voice_id_huasheng="Voice_ID_A",
            voice_id_maodou="Voice_ID_B",
            voice_id_human="MY_HUMAN_VOICE_MODEL_ID",
            minimax_api_key="test",
            minimax_group_id="test",
            minimax_model="test",
            deepseek_api_key="test",
            tavily_api_key="",
            wechat_webhook_url="",
            domestic_trend_urls=[],
            render_poll_url="",
            render_timeout_sec=10,
            use_my_real_voice=False,
            openclaw_message_cmd="",
        )

        parsed = media_flow_main.parse_final_script(final_text)
        payload = media_flow_main.build_legacy_render_payload(config, parsed, final_text)
        line = payload["dialogue"][0]

        self.assertEqual(line["role"], "毛豆")
        self.assertEqual(line["source_role"], "毛豆")
        self.assertEqual(line["voice_id"], "Voice_ID_B")
        self.assertTrue(line["raw_text"].startswith("（噗，大笑）"))
        self.assertIn("哈哈", line["text"])
        self.assertIn("emotion", line)
        self.assertEqual(line["emotion_tags"], ["噗，大笑", "叹气"])
        self.assertIn("laugh", line["audio_events"])
        self.assertIn("sigh", line["audio_events"])
        self.assertIs(payload["audio_pipeline"]["logic_a_structured_params"], True)
        self.assertIs(payload["audio_pipeline"]["logic_b_keep_plain_text_anchors"], True)

    def test_important_marker_boosts_volume_and_slows_rate(self) -> None:
        result = media_flow_main.parse_emotional_tags("[重要]这个 AI 工作流，能帮你早晨多出半小时。")

        self.assertIn("重要", result["emphasis_markers"])
        self.assertEqual(result["emotion"], "emphasis")
        self.assertEqual(result["prosody"]["volume"], "+10%")
        self.assertEqual(result["prosody"]["rate"], "slow")
        self.assertNotIn("[重要]", result["text"])

    def test_use_my_voice_routes_all_dialogue_to_human_voice(self) -> None:
        final_text = "\n".join(
            [
                "[花生]:[注意]AI 不能侵入打卡机，但能重构你的早晨工作流。",
                "[毛豆]:（噗，人间真实）哈哈，这不就是救命按钮吗？",
            ]
        )
        config = media_flow_main.FlowConfig(
            mode="notebooklm",
            legacy_render_url="http://localhost:8000/api/render",
            voice_id_huasheng="Voice_ID_A",
            voice_id_maodou="Voice_ID_B",
            voice_id_human="MY_HUMAN_VOICE_MODEL_ID",
            minimax_api_key="test",
            minimax_group_id="test",
            minimax_model="test",
            deepseek_api_key="test",
            tavily_api_key="",
            wechat_webhook_url="",
            domestic_trend_urls=[],
            render_poll_url="",
            render_timeout_sec=10,
            use_my_real_voice=True,
            openclaw_message_cmd="",
        )

        payload = media_flow_main.build_legacy_render_payload(config, media_flow_main.parse_final_script(final_text), final_text)

        self.assertTrue(payload["audio_pipeline"]["use_my_real_voice"])
        self.assertTrue(all(line["role"] == "真人" for line in payload["dialogue"]))
        self.assertTrue(all(line["voice_id"] == "MY_HUMAN_VOICE_MODEL_ID" for line in payload["dialogue"]))
        self.assertEqual(payload["dialogue"][0]["source_role"], "花生")
        self.assertEqual(payload["dialogue"][1]["source_role"], "毛豆")

    def test_videohao_markdown_parses_line_and_effects(self) -> None:
        final_text = "\n".join(
            [
                "[画面]: 真人坐在电脑前，手机上弹出老板消息。",
                "[特效花字]: 周一早晨，不是妈妈迟到，是系统过载",
                "[台词]:[重要]如果你正坐在公司厕所里崩溃，请听我说。",
            ]
        )
        config = media_flow_main.FlowConfig(
            mode="videohao",
            legacy_render_url="http://localhost:8000/api/render",
            voice_id_huasheng="Voice_ID_A",
            voice_id_maodou="Voice_ID_B",
            voice_id_human="My_Real_Voice_ID",
            minimax_api_key="test",
            minimax_group_id="test",
            minimax_model="test",
            deepseek_api_key="test",
            tavily_api_key="",
            wechat_webhook_url="",
            domestic_trend_urls=[],
            render_poll_url="",
            render_timeout_sec=10,
            use_my_real_voice=True,
            openclaw_message_cmd="",
        )

        parsed = media_flow_main.parse_final_script(final_text)
        payload = media_flow_main.build_legacy_render_payload(config, parsed, final_text)
        line = payload["dialogue"][0]

        self.assertEqual(line["source_role"], "真人")
        self.assertEqual(line["role"], "真人")
        self.assertEqual(line["voice_id"], "My_Real_Voice_ID")
        self.assertIn("重要", line["emphasis_markers"])
        self.assertEqual(line["prosody"]["volume"], "+10%")
        self.assertEqual(line["prosody"]["rate"], "slow")
        self.assertEqual(payload["visual_controls"]["effects"][0]["text"], "周一早晨，不是妈妈迟到，是系统过载")
        self.assertEqual(line["visual_effects"][0]["type"], "text_overlay")

    def test_monday_late_material_maps_to_working_mom_ai_topic(self) -> None:
        raw = "周一早晨送娃迟到被老板点名，心里很憋屈"
        topics = media_flow_main.match_topics(raw, [])

        self.assertEqual(topics[0]["topic"], "如何通过 AI 自动化解放妈妈的周一早晨？")
        self.assertEqual(topics[0]["content_pillar"]["key"], "working_mom_pain")


if __name__ == "__main__":
    unittest.main()
