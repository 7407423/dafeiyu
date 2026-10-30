# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# ─────────────────────────────────────────────────────────────────────────────
"""打更新包 + 更新清单。

产物（默认在 dist/）：
    大肥鱼-v<版本>.zip       覆盖程序目录用的代码包（不含数据）
    update.json              更新清单（放任何能 HTTP 访问的地方）
    RELEASE_NOTES.md         本次更新说明

用法：
    python tools/release.py --version 0.9.2
    python tools/release.py --version 0.9.2 --base-url https://example.com/dafeiyu
    python tools/release.py --version 0.9.2 --notes-file NOTES.md

发布后把 dist/ 整个传上去，把 update_url 指向 update.json 的地址：
    config/app.json → "update_url": "https://example.com/dafeiyu/update.json"

更新包只含代码；`config/`、`db/`、`state/`、`记忆系统/`、`logs/`、`learning/`
等数据目录永远不进包 —— 客户端安装时也会再拦一次。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE_DIRS = ("core", "ui", "tools", "config.default", "docs")
INCLUDE_FILES = (
    "run.py",
    "start.bat",
    "requirements.txt",
    "README.md",
    "README_DEV.md",
    "LICENSE",
    "ADDITIONAL_TERMS.md",
    "NOTICE.md",
    "core_ethos.py",
    "config.example.json",
    "AI_INSTALL.md",
)
EXCLUDE_DIRS = {"__pycache__", ".venv", ".git", "dist", ".update", "config", "db", "state",
                "记忆系统", "logs", "learning", "demo", "tests", "build", "node_modules"}


def _iter_files():
    for name in INCLUDE_DIRS:
        folder = ROOT / name
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.suffix in (".pyc", ".pyo"):
                continue
            yield rel
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file():
            yield Path(name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(version: str, *, out_dir: Path, base_url: str = "", notes: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"大肥鱼-v{version}.zip"
    files = list(_iter_files())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("version.json", json.dumps({"version": version}, ensure_ascii=False))
        for rel in files:
            zf.write(ROOT / rel, rel.as_posix())
    size = zip_path.stat().st_size
    digest = _sha256(zip_path)
    manifest = {
        "version": version,
        "url": f"{base_url.rstrip('/')}/{zip_path.name}" if base_url else f"./{zip_path.name}",
        "sha256": digest,
        "size": size,
        "notes": notes,
        "released_at": datetime.now().isoformat(timespec="seconds"),
        "min_version": "0.9.0",
    }
    (out_dir / "update.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    (out_dir / "RELEASE_NOTES.md").write_text(
        f"# 大肥鱼 v{version}\n\n{notes or '（无说明）'}\n\n"
        f"- 包：`{zip_path.name}`（{size / 1024 / 1024:.2f} MB）\n"
        f"- sha256：`{digest}`\n"
        f"- 发布时间：{manifest['released_at']}\n",
        encoding="utf-8",
    )
    return {"zip": str(zip_path), "manifest": str(out_dir / "update.json"),
            "size": size, "sha256": digest, "files": len(files)}


def main() -> int:
    parser = argparse.ArgumentParser(description="大肥鱼 · 打更新包")
    parser.add_argument("--version", required=True, help="版本号，例如 0.9.2")
    parser.add_argument("--base-url", default="", help="更新包的公网目录（留空=相对同目录）")
    parser.add_argument("--notes", default="", help="更新说明")
    parser.add_argument("--notes-file", default="", help="从文件读更新说明")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="输出目录")
    args = parser.parse_args()

    notes = args.notes
    if args.notes_file:
        notes = Path(args.notes_file).read_text(encoding="utf-8").strip()
    result = build(args.version, out_dir=Path(args.out), base_url=args.base_url, notes=notes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
