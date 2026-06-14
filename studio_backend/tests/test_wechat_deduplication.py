from __future__ import annotations

import unittest
from unittest.mock import patch

from studio_backend import app
from studio_backend.schemas import WeChatMaterialRequest


class MemoryStore:
    def __init__(self) -> None:
        self.state: dict = {}

    def mutate(self, fn):
        return fn(self.state)

    def update_record(self, section, record_id, patch_data):
        for record in self.state.get(section, []):
            if record.get("id") == record_id:
                record.update(patch_data)
                return dict(record)
        raise KeyError(record_id)


class WeChatDeduplicationTests(unittest.TestCase):
    def test_claim_wechat_message_only_once(self):
        memory_store = MemoryStore()
        message = {
            "MsgId": "wechat-message-1",
            "MsgType": "voice",
            "FromUserName": "user-1",
        }

        with patch.object(app, "store", memory_store):
            self.assertTrue(app._claim_wechat_message(message))
            self.assertFalse(app._claim_wechat_message(message))

    def test_receive_wechat_material_deduplicates_message_id(self):
        memory_store = MemoryStore()
        payload = WeChatMaterialRequest(
            text="这是一条微信语音转写",
            source_message_id="wechat-message-2",
            source_type="wechat_voice",
            auto_preview=False,
        )

        with patch.object(app, "store", memory_store):
            first = app.receive_wechat_material(payload)
            second = app.receive_wechat_material(payload)

        self.assertFalse(first.get("deduplicated", False))
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["material_id"], second["material_id"])
        self.assertEqual(len(memory_store.state["wechat_materials"]), 1)


if __name__ == "__main__":
    unittest.main()
