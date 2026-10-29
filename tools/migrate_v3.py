"""补丁 v3 · 增量迁移（幂等 / 可回滚 / 有守卫）。

只做三件事：
  1. 新增表 vision_asset、refusal_decision（CREATE TABLE IF NOT EXISTS）
  2. 给 memory_item 补一列 vision_tiles（PRAGMA 查过才 ALTER）
  3. 把 schema_version 推到 3

不改任何现有列、不删任何行、不重算历史记忆。
迁移前自动备份 db 文件与 state/*.json；迁移前后各数一次行数，**任何表变少就还原备份并退出 1**。

用法：
    python tools\\migrate_v3.py --dry-run     # 只看要做什么
    python tools\\migrate_v3.py               # 真跑
    python tools\\migrate_v3.py --force       # 已经有 v3 也再走一遍（验证幂等）
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import db, settings  # noqa: E402

TARGET_VERSION = 3
NEW_TABLES = ("vision_asset", "refusal_decision")
NEW_COLUMNS = (("memory_item", "vision_tiles"),)


def counts() -> dict:
    tables = [r["name"] for r in db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    out = {}
    for name in tables:
        try:
            out[name] = int(db.scalar(f"SELECT COUNT(*) FROM {name}", default=0) or 0)
        except Exception:
            out[name] = -1
    return out


def existing_tables() -> set[str]:
    return {r["name"] for r in db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def existing_columns(table: str) -> set[str]:
    try:
        return {r["name"] for r in db.q(f"PRAGMA table_info({table})")}
    except Exception:
        return set()


def plan() -> list[str]:
    todo = []
    tables = existing_tables()
    for name in NEW_TABLES:
        if name not in tables:
            todo.append(f"CREATE TABLE IF NOT EXISTS {name}")
    for table, column in NEW_COLUMNS:
        if column not in existing_columns(table):
            todo.append(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT NULL")
    if db.get_meta("schema_version") != str(TARGET_VERSION):
        todo.append(f"meta.schema_version: {db.get_meta('schema_version')} -> {TARGET_VERSION}")
    return todo


def backup_db() -> Path:
    db.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = db.BACKUP_DIR / f"dafeiyu-v3-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = db.connect()
    dst = sqlite3.connect(str(target))
    with dst:
        src.backup(dst)
    dst.close()
    return target


def backup_state() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = settings.STATE / "backup" / stamp
    target.mkdir(parents=True, exist_ok=True)
    for path in settings.STATE.glob("*.json"):
        try:
            shutil.copy2(path, target / path.name)
        except Exception:
            pass
    return target


def restore(db_backup: Path) -> None:
    db.close()
    try:
        shutil.copy2(db_backup, db.DB_PATH)
        for suffix in ("-wal", "-shm"):
            p = Path(str(db.DB_PATH) + suffix)
            if p.exists():
                p.unlink()
    finally:
        db.connect()


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    force = "--force" in argv
    settings.ensure_dirs()
    # 注意：这里**不能**调 db.init_db()，否则 dry-run 也会把表建出来。
    # 只有全新安装（库文件都不存在）才直接建 v3。
    if not db.DB_PATH.exists():
        print("库不存在：按全新安装直接建 v3")
        print(db.init_db())
        return 0

    todo = plan()
    before = counts()
    print(f"# 迁移 v{TARGET_VERSION} · {'DRY-RUN' if dry else 'EXECUTE'}")
    print(f"库：{db.DB_PATH}（{round(db.DB_PATH.stat().st_size / 1024 / 1024, 2)} MB）")
    print(f"schema_version：{db.get_meta('schema_version')}")
    print("\n## 计划")
    if not todo:
        print("- 已经是最新的 v3，无需改动（幂等）")
    for item in todo:
        print(f"- {item}")
    print("\n## 迁移前行数")
    for name, n in before.items():
        print(f"- {name}: {n}")

    if dry:
        print("\nDRY-RUN：没有写入任何东西。")
        return 0
    if not todo and not force:
        print("\n无需迁移。")
        return 0

    db_backup = backup_db()
    state_backup = backup_state()
    print(f"\n备份：{db_backup}\n      {state_backup}\\*.json")

    started = time.time()
    info = db.init_db()
    after = counts()

    lost = {name: (n, after.get(name, 0)) for name, n in before.items() if after.get(name, 0) < n}
    report_lines = [
        f"# 补丁 v3 迁移报告",
        f"时间：{datetime.now():%Y-%m-%d %H:%M:%S}｜耗时 {round(time.time() - started, 2)}s",
        f"库：{db.DB_PATH}",
        f"schema_version：{db.get_meta('schema_version')}",
        f"新增列：{info.get('added_columns') or '无（已存在）'}",
        "",
        "| 表 | 迁移前 | 迁移后 | 变化 |",
        "| --- | --- | --- | --- |",
    ]
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name, "-"), after.get(name, "-")
        delta = "-" if b == "-" or a == "-" else f"{a - b:+d}"
        report_lines.append(f"| {name} | {b} | {a} | {delta} |")
    report_lines += [
        "",
        f"新表：{', '.join(NEW_TABLES)}｜新列：memory_item.vision_tiles",
        f"回滚点：{db_backup}",
    ]
    if lost:
        report_lines.append(f"\n**行数减少：{lost} → 已还原备份并中止**")
    else:
        report_lines.append("\n结果：OK（没有任何表变少）")

    report_path = db.BACKUP_DIR / f"migrate-v3-{datetime.now():%Y%m%d-%H%M%S}.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(report_lines))
    print(f"\n报告：{report_path}")

    if lost:
        restore(db_backup)
        print("\n已还原。没丢东西，请把上面的报告发我。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
