import json
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from goofish_rent.auth import import_auth_state
from goofish_rent.cli import build_env_check, handle_init_config, handle_skill_check
from goofish_rent.config import ENV_FILE_PATH, PATHS, ROOT_DIR
from goofish_rent.models import Listing
from goofish_rent.scraper import diff_new_items, extract_item_id, normalize_url


class ScraperHelpersTest(unittest.TestCase):
    def test_normalize_url_rewrites_fleamarket_scheme(self) -> None:
        raw = "fleamarket://item?itemId=123"
        self.assertEqual(
            normalize_url(raw),
            "https://www.goofish.com/item?itemId=123",
        )

    def test_extract_item_id_prefers_query_param(self) -> None:
        url = "https://www.goofish.com/item?id=456&foo=bar"
        self.assertEqual(extract_item_id(url), "456")

    def test_diff_new_items_only_returns_missing_ids(self) -> None:
        seen_item_ids = {"1", "2"}
        current = [
            Listing("2", "B", "200", "杭州", "https://b"),
            Listing("3", "C", "300", "杭州", "https://c"),
        ]
        self.assertEqual(
            diff_new_items(current, seen_item_ids),
            [Listing("3", "C", "300", "杭州", "https://c")],
        )

    def test_import_auth_state_accepts_cookie_export(self) -> None:
        payload = {
            "cookies": [
                {
                    "domain": ".goofish.com",
                    "name": "sid",
                    "value": "abc",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "no_restriction",
                    "expirationDate": 1893456000,
                }
            ]
        }
        with TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "cookies.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            import_auth_state(str(source))
            state = json.loads(PATHS.storage_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["cookies"][0]["name"], "sid")
            self.assertEqual(state["cookies"][0]["sameSite"], "None")
            metadata = json.loads((PATHS.auth_dir / "auth_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["source_name"], "cookies.json")
            self.assertNotIn("source", metadata)


class SkillCheckCliTest(unittest.TestCase):
    @patch("goofish_rent.cli.run_check", return_value=("no_new_items", [], "暂无新的符合条件的租房信息"))
    def test_handle_skill_check_emits_stable_json(self, _: object) -> None:
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            exit_code = handle_skill_check(None)
        self.assertEqual(exit_code, 0)
        payload = json.loads(fake_stdout.getvalue())
        self.assertEqual(payload["status"], "no_new_items")
        self.assertFalse(payload["notify"])
        self.assertEqual(payload["items"], [])

    @patch(
        "goofish_rent.cli.run_check",
        side_effect=RuntimeError("当前 Chrome profile 登录态已失效，请重新执行 capture-state。"),
    )
    def test_handle_skill_check_maps_login_failure(self, _: object) -> None:
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            exit_code = handle_skill_check(None)
        self.assertEqual(exit_code, 0)
        payload = json.loads(fake_stdout.getvalue())
        self.assertEqual(payload["status"], "needs_login")
        self.assertFalse(payload["notify"])


class EnvCheckTest(unittest.TestCase):
    def test_build_env_check_returns_expected_shape(self) -> None:
        payload = build_env_check()
        self.assertIn("python_version", payload)
        self.assertIn("playwright_installed", payload)
        self.assertIn("config", payload)
        self.assertIn("nearby_location", payload["config"])

    def test_init_config_creates_env_from_template(self) -> None:
        template_path = ROOT_DIR / ".env.example"
        env_exists = ENV_FILE_PATH.exists()
        original_env = ENV_FILE_PATH.read_text(encoding="utf-8") if env_exists else None
        try:
            if env_exists:
                ENV_FILE_PATH.unlink()
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                exit_code = handle_init_config(None)
            self.assertEqual(exit_code, 0)
            self.assertTrue(ENV_FILE_PATH.exists())
            payload = json.loads(fake_stdout.getvalue())
            self.assertTrue(payload["created"])
            self.assertEqual(ENV_FILE_PATH.read_text(encoding="utf-8"), template_path.read_text(encoding="utf-8"))
        finally:
            if original_env is None:
                if ENV_FILE_PATH.exists():
                    ENV_FILE_PATH.unlink()
            else:
                ENV_FILE_PATH.write_text(original_env, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
