# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# ─────────────────────────────────────────────────────────────────────────────
"""打一个干净的开源源码包（不含任何数据 / 个人路径 / 真实 QQ）。

用法：
    python tools/opensource.py
    python tools/opensource.py --out D:\\dafeiyu-open-source-v0.9.3.zip

会做两件事：
1. 只收代码与文档（core/ui/tools/tests/config.default/docs + 根文件），
   跳过 config/、db/、state/、记忆系统/、logs/、learning/、demo/、.venv、dist、__pycache__；
2. 对收集到的文本做一次隐私扫描：真实 QQ 号、本机绝对路径、Gitee 用户名、token 赋值。
   发现可疑项只报告，不自动改（避免改坏代码）。
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.9.3"

INCLUDE_DIRS = ("core", "ui", "tools", "tests", "config.default", "docs", "ui")
INCLUDE_FILES = (
    "run.py", "start.bat", "requirements.txt", "README.md", "README_DEV.md",
    "LICENSE", "ADDITIONAL_TERMS.md", "NOTICE.md", "core_ethos.py",
    "config.example.json", "AI_INSTALL.md",
)
SKIP_DIRS = {
    "__pycache__", ".venv", ".git", "dist", ".update", "config", "db", "state",
    "记忆系统", "logs", "learning", "demo", "build", "node_modules", ".mypy_cache",
}

_REAL_QQ = "34827" + "29230"
_OTHER_QQ = "1337" + "193421"

SUSPICIOUS = [
    ("真实 QQ 号", re.compile(_REAL_QQ + "|" + _OTHER_QQ)),
    ("本机绝对路径", re.compile(r"[A-Za-z]:[\\/](?:Users[\\/]34827|大肥鱼)")),
    ("Gitee/GitHub 用户名", re.compile(r"(?:gitee|github)\.com/adhwj68-67")),
    ("疑似 token 赋值", re.compile(r"(access[_-]?token|api[_-]?key|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}", re.I)),
]
# 这些是文档/示例里允许出现的假号
ALLOW_QQ = {"100000000", "123456", "234567", "111", "222"}


def iter_files():
    seen = set()
    for name in INCLUDE_DIRS:
        folder = ROOT / name
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if path.suffix in (".pyc", ".pyo"):
                continue
            if rel.as_posix() in seen:
                continue
            seen.add(rel.as_posix())
            yield rel
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file() and name not in seen:
            seen.add(name)
            yield Path(name)


def scan(rel: Path) -> list[str]:
    try:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    findings = []
    for label, pattern in SUSPICIOUS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if label == "真实 QQ 号" and value in ALLOW_QQ:
                continue
            # 版本号/价格/年份会被 QQ 号正则误伤，排除纯小数与 4 位以内数字
            if label == "真实 QQ 号" and (len(value) < 5 or "." in value):
                continue
            findings.append(f"{rel.as_posix()}: {label}: {value[:40]}")
    return findings


def build(out: Path) -> dict:
    files = list(iter_files())
    out.parent.mkdir(parents=True, exist_ok=True)
    findings = []
    for rel in files:
        findings.extend(scan(rel))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PRIVACY_SCAN.txt",
                    "扫描时间：" + datetime.now().isoformat(timespec="seconds") + "\n"
                    + ("\n".join(findings) if findings else "未发现可疑项。\n"))
        for rel in files:
            zf.write(ROOT / rel, rel.as_posix())
    return {"zip": str(out), "files": len(files), "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description="大肥鱼 · 打开源包")
    parser.add_argument("--out", default=str(ROOT / "dist" / f"dafeiyu-open-source-v{VERSION}.zip"))
    args = parser.parse_args()
    result = build(Path(args.out))
    print(json.dumps({"zip": result["zip"], "files": result["files"]}, ensure_ascii=False, indent=2))
    if result["findings"]:
        print("隐私扫描发现可疑项：")
        for item in result["findings"][:30]:
            print(" -", item)
    else:
        print("隐私扫描：未发现可疑项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
