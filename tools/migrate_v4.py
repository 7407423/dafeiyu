"""补丁 v4 · 增量迁移（跨会话思维链残留通道）。

只做三件事：
  1. thought_node 补三列：last_active_at / in_residual / session_tag
  2. 建 residual_index 表（只存索引，不复制正文）
  3. schema_version → 4

不动任何现有列、不删任何行、不重算历史节点的 strength/salience/level/concepts。
迁移前自动备份 db 与 state/*.json；迁移前后各数一次行数，任何表变少就还原并退出 1。

用法：
    python tools\\migrate_v4.py --dry-run
    python tools\\migrate_v4.py
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import db, settings  # noqa: E402

TARGET_VERSION = 4
NEW_TABLES = ("residual_index",)
NEW_COLUMNS = (
    ("thought_node", "last_active_at", "TEXT"),
    ("thought_node", "in_residual", "INTEGER DEFAULT 0"),
    ("thought_node", "session_tag", "TEXT"),
)


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


def tables_now() -> set[str]:
    return {r["name"] for r in db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def columns_now(table: str) -> set[str]:
    try:
        return {r["name"] for r in db.q(f"PRAGMA table_info({table})")}
    except Exception:
        return set()


def plan() -> list[str]:
    todo = []
    existing = tables_now()
    for name in NEW_TABLES:
        if name not in existing:
            todo.append(f"CREATE TABLE IF NOT EXISTS {name}")
    for table, column, ddl in NEW_COLUMNS:
        if column not in columns_now(table):
            todo.append(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    # 单向：已经升到更高版本就不动它（v12 之后跑 v4 脚本绝不能把版本改回去）
    try:
        if int(db.get_meta("schema_version") or 0) < TARGET_VERSION:
            todo.append(f"meta.schema_version: {db.get_meta('schema_version')} -> {TARGET_VERSION}")
    except (TypeError, ValueError):
        todo.append(f"meta.schema_version: {db.get_meta('schema_version')} -> {TARGET_VERSION}")
    return todo


def backup_db() -> Path:
    db.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = db.BACKUP_DIR / f"dafeiyu-v4-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = db.connect()
    dst = sqlite3.connect(str(target))
    with dst:
        src.backup(dst)
    dst.close()
    return target


def backup_state() -> Path:
    target = settings.STATE / "backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    for path in settings.STATE.glob("*.json"):
        try:
            shutil.copy2(path, target / path.name)
        except Exception:
            pass
    return target


def restore(backup: Path) -> None:
    db.close()
    try:
        shutil.copy2(backup, db.DB_PATH)
        for suffix in ("-wal", "-shm"):
            p = Path(str(db.DB_PATH) + suffix)
            if p.exists():
                p.unlink()
    finally:
        db.connect()


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    settings.ensure_dirs()
    if not db.DB_PATH.exists():
        print("库不存在：按全新安装直接建 v4")
        print(db.init_db())
        return 0

    todo = plan()
    before = counts()
    print(f"# 迁移 v{TARGET_VERSION} · {'DRY-RUN' if dry else 'EXECUTE'}")
    print(f"库：{db.DB_PATH}（{round(db.DB_PATH.stat().st_size / 1024 / 1024, 2)} MB）"
          f"｜schema_version={db.get_meta('schema_version')}")
    print("\n## 计划")
    if not todo:
        print("- 已经是最新的 v4，无需改动（幂等）")
    for item in todo:
        print(f"- {item}")
    print("\n## 迁移前行数")
    for name, n in before.items():
        print(f"- {name}: {n}")
    if dry:
        print("\nDRY-RUN：没有写入任何东西。")
        return 0
    if not todo:
        print("\n无需迁移。")
        return 0

    db_backup = backup_db()
    state_backup = backup_state()
    print(f"\n备份：{db_backup}\n      {state_backup}\\*.json")

    started = time.time()
    info = db.init_db()
    after = counts()
    lost = {name: (n, after.get(name, 0)) for name, n in before.items() if after.get(name, 0) < n}

    lines = [
        "# 补丁 v4 迁移报告",
        f"时间：{datetime.now():%Y-%m-%d %H:%M:%S}｜耗时 {round(time.time() - started, 2)}s",
        f"库：{db.DB_PATH}｜schema_version：{db.get_meta('schema_version')}",
        f"新增列：{info.get('added_columns') or '无（已存在）'}",
        "",
        "| 表 | 迁移前 | 迁移后 | 变化 |",
        "| --- | --- | --- | --- |",
    ]
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name, "-"), after.get(name, "-")
        delta = "-" if b == "-" or a == "-" else f"{a - b:+d}"
        lines.append(f"| {name} | {b} | {a} | {delta} |")
    lines += ["", f"新表：{', '.join(NEW_TABLES)}｜新列：thought_node.last_active_at / in_residual / session_tag",
              f"回滚点：{db_backup}",
              ("\n**行数减少：%s → 已还原备份并中止**" % lost) if lost else "\n结果：OK（没有任何表变少）"]
    report = db.BACKUP_DIR / f"migrate-v4-{datetime.now():%Y%m%d-%H%M%S}.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\n报告：{report}")
    if lost:
        restore(db_backup)
        print("\n已还原。没丢东西，请把上面的报告发我。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
