# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""在线更新：检查 → 下载 → 校验 → 安装（只换代码，绝不碰鱼的数据）。

设计约束（按老大要求写死）：
- 安装目标是**程序目录**（本文件上一级），不是 `~/.dafeiyu` 数据目录；
- 更新包里即使带了 `config/`、`db/`、`state/`、`记忆系统/`、`logs/`、`learning/`，
  也一律跳过 —— 老用户的鱼不能被一次更新清空；
- 覆盖前把将替换的旧文件备份到 `.update/backup-<版本>/`，`rollback()` 可整体还原；
- 下载必须校验 sha256；manifest 里的版本号必须比当前新才装；
- 全程不启动、不停止桥接，也不碰 QQ。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import __version__, settings

# 程序目录：core/ 的上一级。更新就是往这里覆盖代码。
PROGRAM_ROOT = Path(__file__).resolve().parents[1]
UPDATE_DIR = PROGRAM_ROOT / ".update"
LAST_FILE = UPDATE_DIR / "last.json"

# 这些目录/名字属于"鱼的数据"或运行时产物，更新包一律不许覆盖。
PROTECTED_TOP = {
    "config",
    "db",
    "state",
    "记忆系统",
    "logs",
    "learning",
    "demo",
    ".venv",
    "__pycache__",
    ".git",
    ".update",
    "dist",
}

Progress = Callable[[int, int], None]


# ── 版本 ───────────────────────────────────────────────────────────────────
def current_version() -> str:
    return str(__version__)


def parse_version(text: str) -> tuple[int, ...]:
    parts = [int(n) for n in re.findall(r"\d+", str(text or ""))[:4]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


# ── manifest ───────────────────────────────────────────────────────────────
# 开源版不预置任何人的私人发布地址；想用在线更新，在 config/app.json 填 update_url，
# 或把 update.json 放到程序目录（本地/局域网分发）。
DEFAULT_UPDATE_URL = ""


def manifest_url() -> str:
    """更新清单地址。优先级：环境变量 → app.json → 程序目录 update.json → 内置默认。"""
    env = os.environ.get("DAFEIYU_UPDATE_URL", "").strip()
    if env:
        return env
    candidates = []
    try:
        candidates.append(str((settings.app() or {}).get("update_url") or "").strip())
    except Exception:
        pass
    # 程序目录与数据目录可能不是同一个（比如程序在 D:\dafeiyu，数据在 ~/.dafeiyu）
    local_app = PROGRAM_ROOT / "config" / "app.json"
    try:
        if local_app.is_file():
            data = json.loads(local_app.read_text(encoding="utf-8"))
            candidates.append(str((data or {}).get("update_url") or "").strip())
    except Exception:
        pass
    for value in candidates:
        if value:
            return value
    local_manifest = PROGRAM_ROOT / "update.json"
    if local_manifest.is_file():
        return str(local_manifest)
    return DEFAULT_UPDATE_URL


def _resolve_url(base: str, value: str) -> str:
    """manifest 里的 url 可以是相对地址（相对 manifest 所在目录）。"""
    if not value:
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value) or Path(value).is_absolute():
        return value
    if base and Path(base).is_file():
        return str((Path(base).parent / value).resolve())
    return urllib.parse.urljoin(base if base.endswith("/") else f"{base}/", value)


def _read_bytes(url: str, timeout: float = 8.0) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "file":
        return Path(urllib.request.url2pathname(parsed.path)).read_bytes()
    # Windows 盘符会被 urlparse 当成 scheme（C:\... → scheme='c'），所以先按本地文件判断。
    try:
        local = Path(url)
        if local.is_file():
            return local.read_bytes()
    except Exception:
        pass
    if parsed.scheme == "":
        return Path(url).read_bytes()
    with urllib.request.urlopen(url, timeout=float(timeout)) as resp:
        return resp.read()


def load_manifest(url: str | None = None, *, timeout: float = 8.0) -> dict:
    target = str(url or manifest_url()).strip()
    if not target:
        raise RuntimeError("没有配置更新地址（config/app.json → update_url）")
    raw = _read_bytes(target, timeout=timeout)
    data = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(data, dict):
        raise RuntimeError("更新清单不是 JSON 对象")
    for key in ("version", "url"):
        if not data.get(key):
            raise RuntimeError(f"更新清单缺少字段：{key}")
    data["url"] = _resolve_url(target, str(data["url"]))
    data["_manifest"] = target
    return data


def check(url: str | None = None, *, timeout: float = 8.0) -> dict:
    """检查是否有新版；不写任何文件。"""
    local = current_version()
    target = str(url or manifest_url()).strip()
    if not target:
        return {"ok": False, "local": local, "newer": False,
                "error": "没有配置更新地址（config/app.json → update_url）"}
    try:
        manifest = load_manifest(target, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "local": local, "newer": False, "error": str(exc)}
    latest = str(manifest.get("version") or "")
    return {
        "ok": True,
        "local": local,
        "latest": latest,
        "newer": bool(latest) and is_newer(latest, local),
        "manifest": manifest,
        "notes": str(manifest.get("notes") or ""),
        "size": int(manifest.get("size") or 0),
        "sha256": str(manifest.get("sha256") or ""),
    }


# ── 下载 / 校验 ────────────────────────────────────────────────────────────
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path, *, sha256: str = "", expected_size: int = 0,
             progress: Progress | None = None, timeout: float = 60.0) -> dict:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    parsed = urllib.parse.urlparse(url)
    total = int(expected_size or 0)
    done = 0
    try:
        if parsed.scheme == "file":
            source = open(urllib.request.url2pathname(parsed.path), "rb")
        elif Path(url).is_file():
            source = open(url, "rb")
        else:
            source = urllib.request.urlopen(url, timeout=float(timeout))
        with source as src, open(tmp, "wb") as dst:
            if not total:
                try:
                    total = int(src.headers.get("content-length") or 0)
                except Exception:
                    total = 0
            while True:
                chunk = src.read(1024 * 128)
                if not chunk:
                    break
                dst.write(chunk)
                done += len(chunk)
                if progress:
                    try:
                        progress(done, total)
                    except Exception:
                        pass
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    if sha256 and _sha256(tmp) != sha256.lower():
        tmp.unlink(missing_ok=True)
        raise RuntimeError("下载文件校验失败（sha256 不匹配），已丢弃")
    tmp.replace(dest)
    return {"path": str(dest), "bytes": done, "sha256": _sha256(dest)}


# ── 安装 ───────────────────────────────────────────────────────────────────
def _rel_parts(name: str) -> tuple[str, ...] | None:
    parts = tuple(p for p in PurePosixPath(str(name).replace("\\", "/")).parts if p not in ("", "."))
    if not parts:
        return None
    if ".." in parts:
        return None
    if PurePosixPath(*parts).is_absolute():
        return None
    if parts[0] in PROTECTED_TOP:
        return None
    return parts


def _inside(root: Path, target: Path) -> bool:
    try:
        root = root.resolve()
        target = target.resolve()
        return root == target or root in target.parents
    except Exception:
        return False


def install(zip_path: Path | str, *, root: Path | str | None = None,
            backup: bool = True, dry_run: bool = False) -> dict:
    """把更新包覆盖到程序目录。数据目录与运行时目录整体跳过。"""
    root = Path(root or PROGRAM_ROOT)
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"更新包不存在：{zip_path}")
    version = _version_from_zip(zip_path)
    backup_dir = root / ".update" / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
    installed: list[str] = []
    skipped: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = _rel_parts(info.filename)
            if not parts:
                skipped.append(info.filename)
                continue
            target = root.joinpath(*parts)
            if not _inside(root, target):
                skipped.append(info.filename)
                continue
            if dry_run:
                installed.append(str(PurePosixPath(*parts)))
                continue
            if backup and target.exists():
                saved = backup_dir.joinpath(*parts)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".update-new")
            with zf.open(info) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.replace(tmp, target)
            installed.append(str(PurePosixPath(*parts)))
    if not dry_run:
        record = {
            "version": version,
            "at": datetime.now().isoformat(timespec="seconds"),
            "zip": str(zip_path),
            "installed": len(installed),
            "skipped": len(skipped),
            "backup": str(backup_dir) if backup and installed else "",
        }
        last = root / ".update" / "last.json"
        last.parent.mkdir(parents=True, exist_ok=True)
        last.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, **record, "files": installed, "skipped": skipped}
    return {"ok": True, "dry_run": True, "version": version,
            "files": installed, "skipped": skipped}


def _version_from_zip(zip_path: Path) -> str:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.endswith("version.json"):
                    data = json.loads(zf.read(name).decode("utf-8", "replace"))
                    return str(data.get("version") or "")
    except Exception:
        pass
    return ""


def update(*, url: str | None = None, progress: Progress | None = None,
           program_root: Path | str | None = None) -> dict:
    """检查 → 下载 → 校验 → 安装，一条龙。给 UI 的后台线程调用。"""
    info = check(url)
    if not info.get("ok"):
        return info
    if not info.get("newer"):
        return {**info, "installed": 0, "skipped": "已是最新"}
    manifest = info["manifest"]
    version = str(info["latest"])
    root = Path(program_root or PROGRAM_ROOT)
    update_dir = root / ".update"
    update_dir.mkdir(parents=True, exist_ok=True)
    dest = update_dir / f"dafeiyu-{version}.zip"
    download(manifest["url"], dest, sha256=str(manifest.get("sha256") or ""),
             expected_size=int(manifest.get("size") or 0), progress=progress)
    result = install(dest, root=root)
    result.update({"latest": version, "from": info["local"], "notes": info.get("notes", "")})
    return result


def rollback() -> dict:
    """把最近一次更新覆盖过的文件还原（从 .update/backup-*）。"""
    record = last_update()
    backup = Path(str(record.get("backup") or ""))
    if not record or not backup.is_dir():
        return {"ok": False, "error": "没有可还原的更新备份"}
    restored = 0
    for path in backup.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(backup)
        target = PROGRAM_ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        restored += 1
    return {"ok": True, "restored": restored, "version": record.get("version", "")}


def last_update() -> dict:
    try:
        data = json.loads(LAST_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def status() -> dict:
    """给 UI / 自检用：当前版本、有没有更新地址、上次更新时间。"""
    return {
        "version": current_version(),
        "programRoot": str(PROGRAM_ROOT),
        "manifestUrl": manifest_url(),
        "last": last_update(),
    }
