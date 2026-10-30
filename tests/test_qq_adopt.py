"""QQ 接入接管：发现、预检、接管、回滚。

全程在临时 DAFEIYU_HOME 里跑（`tests.base` 已经切好），用一个临时 `qq-bridge` 目录
模拟「用户已经接好的 QQ」；绝不碰真实桥接，也绝不碰鱼的数据。
"""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from .base import BaseCase

from core import qq_adopt, settings


def make_bridge(root: Path, *, owner: int = 123456, port: int = 3100,
                console_token: str = "console-fixture", agent_token: str = "agent-fixture",
                emotion_mode: str = "local") -> Path:
    """搭一个最小 qq-bridge 目录（只放本模块会读的文件）。"""
    root.mkdir(parents=True, exist_ok=True)
    cfg = {
        "consolePort": port,
        "ownerQQ": owner,
        "allow": {"private": [owner], "groups": [654321]},
        "dafeiyu": {"emotionMode": emotion_mode, "corePort": 18766},
        "socialV2": {"tools": {"diary": True}},
        "onebot": {"kind": "napcat", "homeDir": "D:/NapCat"},
        "token-usage": "keep-me",
    }
    (root / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "state").mkdir(exist_ok=True)
    (root / "state" / "console-token").write_text(console_token, encoding="utf-8")
    social = {
        "conversations": {
            f"private:{owner}": {"agentToken": agent_token, "recentMessages": []},
        }
    }
    (root / "state" / "social-v2.json").write_text(json.dumps(social, ensure_ascii=False), encoding="utf-8")
    return root


class FakeStatusServer:
    """在回环端口上假装 qq-bridge 控制台。"""

    def __init__(self, payload: dict):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path != "/api/status":
                    self.send_response(404)
                    self.end_headers()
                    return
                token = self.headers.get("x-console-token", "")
                body = dict(payload)
                body["tokenSeen"] = token
                raw = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        outer.payload = payload

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestDiscover(BaseCase):
    def test_looks_like_bridge(self):
        with self.subTest("合法目录"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                root = make_bridge(Path(tmp) / "qq-bridge")
                self.assertTrue(qq_adopt.looks_like_bridge(root))
        with self.subTest("不像的目录"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                self.assertFalse(qq_adopt.looks_like_bridge(Path(tmp)))

    def test_inspect_reads_owner_allow_token(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge", owner=123456)
            info = qq_adopt.inspect(root)
        self.assertEqual(info["ownerQQ"], "123456")
        self.assertEqual(info["allow"]["groups"], [654321])
        self.assertTrue(info["hasConsoleToken"])
        self.assertTrue(info["hasAgentToken"])
        self.assertEqual(info["onebotKind"], "napcat")
        self.assertEqual(info["emotionMode"], "local")
        self.assertFalse(info["online"])  # 没有真服务

    def test_discover_finds_extra_dir(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            # 只扫这个临时目录：不让测试去碰本机真实桥接（沙盒边界）
            with mock.patch.object(qq_adopt, "candidates", return_value=[Path(root)]):
                rows = qq_adopt.discover()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["dir"], str(root))

    def test_probe_online(self):
        import tempfile

        with FakeStatusServer({"ownerQQ": "999", "mode": "reserved2", "allowPrivate": [123456], "allowGroups": [654321]}) as srv:
            with tempfile.TemporaryDirectory() as tmp:
                root = make_bridge(Path(tmp) / "qq-bridge", port=srv.port)
                info = qq_adopt.inspect(root)
        self.assertTrue(info["online"])
        self.assertEqual(info["ownerQQ"], "999")
        self.assertEqual(info["mode"], "reserved2")


class TestAdopt(BaseCase):
    def test_plan_does_not_write(self):
        import tempfile

        before = (settings.CONFIG / "app.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            planned = qq_adopt.plan(root)
        after = (settings.CONFIG / "app.json").read_text(encoding="utf-8")
        self.assertEqual(planned["after"]["dir"], str(root))
        self.assertEqual(before, after, "plan 不能写配置")

    def test_adopt_writes_bridge_and_local_copy(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge", owner=123456)
            result = qq_adopt.adopt(root, sync_bridge=True)
            # 临时目录还在时把要断言的文件读出来
            local = json.loads((settings.CONFIG / "qq_config.json").read_text(encoding="utf-8"))
            synced = json.loads((root / "config.json").read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        app = json.loads((settings.CONFIG / "app.json").read_text(encoding="utf-8"))
        bridge = app["bridge"]
        self.assertTrue(bridge["enabled"])
        self.assertEqual(bridge["dir"], str(root))
        self.assertEqual(bridge["owner_qq"], "123456")
        self.assertTrue(bridge["send_api"].endswith("/api/send/private"))
        self.assertIn("3100", bridge["send_api"])
        # 本地副本（面板读的）
        self.assertEqual(local["owner_qq"], "123456")
        self.assertEqual(local["allow"]["groups"], [654321])
        # 桥接 config 被 merge：owner/allow 改了，别的字段还在
        self.assertEqual(synced["ownerQQ"], 123456)
        self.assertEqual(synced["allow"]["groups"], [654321])
        self.assertEqual(synced["socialV2"]["tools"]["diary"], True)
        self.assertEqual(synced["token-usage"], "keep-me")
        # 备份存在
        self.assertTrue(Path(result["backup"]).is_file())

    def test_adopt_does_not_touch_fish_data(self):
        import tempfile

        from core import db

        before_rows = db.scalar("SELECT COUNT(*) FROM memory_item", default=0)
        db_mtime = db.DB_PATH.stat().st_mtime_ns if db.DB_PATH.exists() else 0
        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            qq_adopt.adopt(root)
        after_rows = db.scalar("SELECT COUNT(*) FROM memory_item", default=0)
        self.assertEqual(before_rows, after_rows)
        if db.DB_PATH.exists():
            self.assertEqual(db_mtime, db.DB_PATH.stat().st_mtime_ns, "接管不得写数据库")

    def test_adopt_rejects_non_bridge(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                qq_adopt.adopt(Path(tmp))

    def test_adopt_dry_run_writes_nothing(self):
        import tempfile

        before = (settings.CONFIG / "app.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            result = qq_adopt.adopt(root, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(before, (settings.CONFIG / "app.json").read_text(encoding="utf-8"))

    def test_rollback_restores_previous_bridge(self):
        import tempfile

        original = json.loads((settings.CONFIG / "app.json").read_text(encoding="utf-8")).get("bridge") or {}
        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            qq_adopt.adopt(root)
            rolled = qq_adopt.rollback()
        self.assertTrue(rolled["ok"])
        app = json.loads((settings.CONFIG / "app.json").read_text(encoding="utf-8"))
        self.assertEqual(app.get("bridge") or {}, original)

    def test_emotion_mode_core_aligns_core_port(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge", emotion_mode="core")
            result = qq_adopt.adopt(root)
        self.assertEqual(result["after"]["emotion_mode"], "core")
        self.assertEqual(result["after"]["core_emotion_api_port"], 18766)
        self.assertTrue(any("核心" in w for w in result["warnings"]))

    def test_status_reports_adopted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_bridge(Path(tmp) / "qq-bridge")
            qq_adopt.adopt(root)
        state = qq_adopt.status()
        self.assertTrue(state["adopted"])
        self.assertEqual(state["dir"], str(root))
        self.assertFalse(state["online"])


if __name__ == "__main__":
    unittest.main()
