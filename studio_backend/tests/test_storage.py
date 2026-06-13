from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_storage(data_dir: Path):
    with patch.dict(os.environ, {"CREATOR_STUDIO_DATA_DIR": str(data_dir)}):
        import studio_backend.storage as storage

        return importlib.reload(storage)


class StudioStoreTests(unittest.TestCase):
    def test_creates_sqlite_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = load_storage(Path(temp_dir))

            store = storage.StudioStore()
            store.add_record(
                "stock_watchlist", {"id": "stock_1", "symbol": "AAPL"}
            )

            self.assertTrue(storage.DATABASE_FILE.exists())
            self.assertEqual(
                store.list_section("stock_watchlist"),
                [{"id": "stock_1", "symbol": "AAPL"}],
            )

    def test_migrates_existing_json_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            old_state = {
                "stock_watchlist": [{"id": "stock_1", "symbol": "000839.SZ"}],
                "persona": {"id": "persona_1", "name": "测试人设"},
            }
            (data_dir / "studio_state.json").write_text(
                json.dumps(old_state, ensure_ascii=False), encoding="utf-8"
            )
            storage = load_storage(data_dir)

            store = storage.StudioStore()

            self.assertEqual(
                store.list_section("stock_watchlist")[0]["symbol"], "000839.SZ"
            )
            self.assertEqual(store.get_persona()["name"], "测试人设")
            self.assertTrue((data_dir / "studio_state.json").exists())

    def test_failed_mutation_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = load_storage(Path(temp_dir))
            store = storage.StudioStore()

            def broken_update(state):
                state["stock_watchlist"].append({"id": "bad"})
                raise RuntimeError("stop")

            with self.assertRaises(RuntimeError):
                store.mutate(broken_update)

            self.assertEqual(store.list_section("stock_watchlist"), [])


if __name__ == "__main__":
    unittest.main()
