"""在线更新：版本比较、安全解压、数据目录保护、下载校验、一键更新、回滚。

全程在临时目录里造更新包与程序目录，绝不碰真实安装，也不碰鱼的数据。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from .base import BaseCase

from core import updater


def make_zip(path: Path, *, version: str = "9.9.9", with_data: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("version.json", json.dumps({"version": version}))
        zf.writestr("core/new_feature.py", f"VERSION = '{version}'\n")
        zf.writestr("tools/new_tool.py", "# tool\n")
        zf.writestr("run.py", "# runner\n")
        if with_data:
            zf.writestr("config/app.json", '{"evil": true}')
            zf.writestr("db/dafeiyu.db", b"EXPLOIT")
            zf.writestr("state/emotion.json", '{"evil": true}')
            zf.writestr("记忆系统/2号长期记忆/开心.md", "被覆盖就完蛋")
            zf.writestr("logs/crash.log", "noise")
            zf.writestr("../evil.txt", "zip-slip")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class TestVersion(BaseCase):
    def test_parse_and_compare(self):
        self.assertEqual(updater.parse_version("0.9.2"), (0, 9, 2))
        self.assertEqual(updater.parse_version("v1.0"), (1, 0, 0))
        self.assertTrue(updater.is_newer("0.9.2", "0.9.1"))
        self.assertTrue(updater.is_newer("1.0.0", "0.9.9"))
        self.assertFalse(updater.is_newer("0.9.1", "0.9.1"))
        self.assertFalse(updater.is_newer("0.9.0", "0.9.1"))


class TestInstall(BaseCase):
    def test_installs_code_but_never_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "大肥鱼"
            (root / "core").mkdir(parents=True)
            (root / "config").mkdir()
            (root / "config" / "app.json").write_text('{"mine": true}', encoding="utf-8")
            (root / "db").mkdir()
            (root / "db" / "dafeiyu.db").write_bytes(b"REAL-DB")
            (root / "记忆系统" / "2号长期记忆").mkdir(parents=True)
            (root / "记忆系统" / "2号长期记忆" / "开心.md").write_text("真实记忆", encoding="utf-8")
            (root / "run.py").write_text("# old runner\n", encoding="utf-8")
            zip_path = make_zip(Path(tmp) / "pkg.zip")

            result = updater.install(zip_path, root=root)

            self.assertTrue(result["ok"])
            self.assertEqual((root / "run.py").read_text(encoding="utf-8"), "# runner\n")
            self.assertTrue((root / "core" / "new_feature.py").is_file())
            # 数据目录一个字节不动
            self.assertEqual((root / "config" / "app.json").read_text(encoding="utf-8"), '{"mine": true}')
            self.assertEqual((root / "db" / "dafeiyu.db").read_bytes(), b"REAL-DB")
            self.assertEqual((root / "记忆系统" / "2号长期记忆" / "开心.md").read_text(encoding="utf-8"), "真实记忆")
            # 危险条目被跳过并记录
            joined = " ".join(result["skipped"])
            for name in ("config/app.json", "db/dafeiyu.db", "state/emotion.json", "记忆系统/", "logs/crash.log", "../evil.txt"):
                self.assertIn(name, joined)
            # 旧文件被备份
            self.assertTrue(Path(result["backup"]).is_dir())
            self.assertEqual((Path(result["backup"]) / "run.py").read_text(encoding="utf-8"), "# old runner\n")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            root.mkdir()
            (root / "run.py").write_text("old", encoding="utf-8")
            zip_path = make_zip(Path(tmp) / "pkg.zip")
            result = updater.install(zip_path, root=root, dry_run=True)
            self.assertTrue(result["dry_run"])
            self.assertEqual((root / "run.py").read_text(encoding="utf-8"), "old")
            self.assertFalse((root / "core" / "new_feature.py").exists())


class TestDownload(BaseCase):
    def test_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = make_zip(Path(tmp) / "pkg.zip")
            dest = Path(tmp) / "download.zip"
            with self.assertRaises(RuntimeError):
                updater.download(str(zip_path), dest, sha256="0" * 64)
            self.assertFalse(dest.exists())

    def test_download_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = make_zip(Path(tmp) / "pkg.zip")
            dest = Path(tmp) / "download.zip"
            progress = []
            result = updater.download(str(zip_path), dest, sha256=sha256(zip_path),
                                      progress=lambda done, total: progress.append((done, total)))
            self.assertTrue(dest.is_file())
            self.assertEqual(result["sha256"], sha256(zip_path))
            self.assertTrue(progress)


class TestCheckAndUpdate(BaseCase):
    def _manifest(self, tmp: Path, version: str = "9.9.9") -> Path:
        zip_path = make_zip(tmp / "pkg.zip", version=version)
        manifest = {
            "version": version,
            "url": zip_path.resolve().as_uri(),
            "sha256": sha256(zip_path),
            "size": zip_path.stat().st_size,
            "notes": "测试更新",
        }
        path = tmp / "update.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_check_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(Path(tmp))
            info = updater.check(str(manifest))
            self.assertTrue(info["ok"])
            self.assertTrue(info["newer"])
            self.assertEqual(info["latest"], "9.9.9")

    def test_check_same_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(Path(tmp), version=updater.current_version())
            info = updater.check(str(manifest))
            self.assertFalse(info["newer"])

    def test_check_without_url(self):
        info = updater.check("")
        self.assertFalse(info["ok"])
        self.assertIn("更新地址", info["error"])

    def test_update_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(Path(tmp))
            root = Path(tmp) / "程序"
            (root / "core").mkdir(parents=True)
            (root / "config").mkdir()
            (root / "config" / "app.json").write_text('{"mine": true}', encoding="utf-8")
            result = updater.update(url=str(manifest), program_root=root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["installed"], 4)  # version.json / core / tools / run.py
            self.assertTrue((root / "core" / "new_feature.py").is_file())
            self.assertEqual((root / "config" / "app.json").read_text(encoding="utf-8"), '{"mine": true}')
            self.assertTrue((root / ".update" / "last.json").is_file())


if __name__ == "__main__":
    unittest.main()
