# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""接管用户已经接好的 QQ 接入（只读发现 + 只写配置，不碰鱼的数据）。

背景：老用户几乎都已经有一套 QQ 接入了 —— qq-bridge 配 SnowLuma / NapCat，或者别的
OneBot v11 实现。换机器、重装、或第一次用大肥鱼时，如果还要手工去 `config/app.json`
填 `bridge.dir` 和 `owner_qq`，填错一个字符她就"哑巴"：能算、能记，但一句话发不出去。
更糟的是有人会因此重建一份 persona，把鱼养成了第二条。

本模块做三件事：

1. **发现**：本机有哪些 qq-bridge 实例（盘上的目录 + 正在跑的 3100 控制台）。
2. **预检**：接管后能不能真的收发 —— 控制台 token、会话 agentToken、ownerQQ、
   桥接当前的情绪模式（core/local）与端口。
3. **接管**：把 `config/app.json` 的 `bridge` 段指过去（先备份，可回滚）；需要时把
   owner / 白名单 merge 回桥接的 `config.json`。

边界（写死在这里，别松）：
- **绝不**读写 `db/`、`记忆系统/`、`state/emotion.json` 等任何"鱼的数据"；
- **绝不**启动/停止桥接（SnowLuma 的 EULA 不允许打包与代启）；
- 所有写入都是"读整份 → 改字段 → 原子写回"，失败就保持原样。
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from . import settings

STATUS_FILE = "qq-adopt.json"
LOCAL_CONFIG = "qq_config.json"
BACKUP_DIR = "backup"
DEFAULT_PORTS = (3100,)
PROBE_TIMEOUT = 1.2


# ── 小工具 ─────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _id_list(value: Any) -> list[int]:
    out = []
    for item in value or []:
        try:
            out.append(int(item))
        except Exception:
            continue
    return sorted(set(out))


def _clean(path: Any) -> str:
    return str(path or "").strip()


# ── 候选目录 ───────────────────────────────────────────────────────────────
def candidates(extra: list[str] | None = None) -> list[Path]:
    """可能放着 qq-bridge 的目录，按可信度排。

    来源：环境变量 → 当前 app.json 已配置的 dir → 程序目录同级 → 家目录 → 常见盘符。
    只返回真正存在的目录由 `looks_like_bridge()` 再筛，这里不判断。
    """
    out: list[Path] = []

    def push(value: Any) -> None:
        raw = _clean(value)
        if not raw:
            return
        try:
            path = Path(raw).expanduser()
        except Exception:
            return
        if path not in out:
            out.append(path)

    push(os.environ.get("DAFEIYU_BRIDGE_DIR"))
    push(os.environ.get("QQ_BRIDGE_HOME"))
    push((settings.app().get("bridge") or {}).get("dir"))
    root = Path(__file__).resolve().parents[1]
    push(root.parent / "qq-bridge")
    push(root / "qq-bridge")
    push(Path.home() / "qq-bridge")
    push(Path.home() / ".qq-bridge")
    for drive in ("C:", "D:", "E:"):
        push(Path(f"{drive}/qq-bridge"))
        push(Path(f"{drive}/大肥鱼/qq-bridge"))
    # 很多人把桥接放在「文档」下（deepseek-harness/qq-bridge、qq-bridge、项目/qq-bridge）。
    # 只扫两层，避免全盘搜索拖慢启动。
    documents = Path.home() / "Documents"
    for pattern in ("qq-bridge", "*/qq-bridge", "*/*/qq-bridge"):
        try:
            for item in documents.glob(pattern):
                push(item)
        except Exception:
            continue
    for item in extra or []:
        push(item)
    return out


def looks_like_bridge(path: Path | str) -> bool:
    """目录像不像一个 qq-bridge（不要求它在跑）。"""
    try:
        root = Path(path)
        if not root.is_dir():
            return False
        cfg = _read_json(root / "config.json", None)
        if not isinstance(cfg, dict):
            return False
        keys = set(cfg)
        if keys & {"consolePort", "socialV2", "snowluma", "onebot", "ownerQQ", "dsh"}:
            return True
        return (root / "src" / "bridge.js").is_file() or (root / "state" / "console-token").is_file()
    except Exception:
        return False


# ── 读桥接现状 ─────────────────────────────────────────────────────────────
def probe_status(port: int, console_token: str = "", timeout: float = PROBE_TIMEOUT) -> dict | None:
    """读 qq-bridge 控制台的 /api/status；不在跑就返回 None（绝不抛异常）。"""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{int(port)}/api/status")
        if console_token:
            req.add_header("x-console-token", console_token)
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def inspect(path: Path | str, *, timeout: float = PROBE_TIMEOUT) -> dict:
    """只读检查一个桥接目录：配置、token、账号、在线状态、接管风险。"""
    root = Path(path)
    info: dict[str, Any] = {
        "dir": str(root),
        "exists": root.is_dir(),
        "looksLikeBridge": looks_like_bridge(root),
        "online": False,
        "consolePort": 3100,
        "consoleToken": "",
        "hasConsoleToken": False,
        "hasAgentToken": False,
        "ownerQQ": "",
        "allow": {"private": [], "groups": []},
        "emotionMode": "local",
        "corePort": 18766,
        "onebotKind": "",
        "homeDir": "",
        "mode": "",
        "role": "",
        "warnings": [],
    }
    if not info["exists"]:
        info["warnings"].append(f"目录不存在：{root}")
        return info

    cfg = _read_json(root / "config.json", {})
    if not isinstance(cfg, dict):
        cfg = {}
    info["consolePort"] = _int(cfg.get("consolePort"), 3100) or 3100
    info["ownerQQ"] = str(cfg.get("ownerQQ") or "").strip()
    allow = cfg.get("allow") if isinstance(cfg.get("allow"), dict) else {}
    info["allow"] = {
        "private": _id_list(allow.get("private") or allow.get("privates")),
        "groups": _id_list(allow.get("groups") or allow.get("group")),
    }
    dafeiyu = cfg.get("dafeiyu") if isinstance(cfg.get("dafeiyu"), dict) else {}
    info["emotionMode"] = "core" if str(dafeiyu.get("emotionMode") or "local") == "core" else "local"
    info["corePort"] = _int(dafeiyu.get("corePort"), 18766) or 18766

    onebot = cfg.get("onebot") if isinstance(cfg.get("onebot"), dict) else None
    snow = cfg.get("snowluma") if isinstance(cfg.get("snowluma"), dict) else None
    chosen = onebot or snow or {}
    info["onebotKind"] = str(chosen.get("kind") or ("snowluma" if snow else "onebot"))
    info["homeDir"] = _clean(chosen.get("homeDir") or chosen.get("launcherPath"))

    info["consoleToken"] = _text(root / "state" / "console-token")
    info["hasConsoleToken"] = bool(info["consoleToken"])

    social = _read_json(root / "state" / "social-v2.json", {})
    conversations = (social or {}).get("conversations") if isinstance(social, dict) else {}
    conv = (conversations or {}).get(f"private:{info['ownerQQ']}") if info["ownerQQ"] else None
    info["hasAgentToken"] = bool(isinstance(conv, dict) and conv.get("agentToken"))

    status = probe_status(info["consolePort"], info["consoleToken"], timeout=timeout)
    if status:
        info["online"] = True
        info["ownerQQ"] = str(status.get("ownerQQ") or info["ownerQQ"] or "").strip()
        info["mode"] = str(status.get("mode") or "")
        info["role"] = str(status.get("role") or "")
        info["allow"] = {
            "private": _id_list(status.get("allowPrivate") or info["allow"]["private"]),
            "groups": _id_list(status.get("allowGroups") or info["allow"]["groups"]),
        }

    # ── 接管风险提示（不阻断，只让人知道接管后会缺什么）──
    if not info["online"]:
        info["warnings"].append("桥接当前没在运行：可以接管配置，但要把桥接启动起来才会真正收发")
    if not info["hasConsoleToken"]:
        info["warnings"].append("没有 state/console-token：控制台身份缺失，发私聊/查状态会被 401")
    if info["online"] and not info["hasAgentToken"]:
        info["warnings"].append("state/social-v2.json 里没有这个会话的 agentToken：二代会 401，先去群/私聊说一句话生成")
    if not info["ownerQQ"]:
        info["warnings"].append("桥接里没有 ownerQQ：接管后需要补一个，否则她不认老大")
    if info["emotionMode"] == "core":
        info["warnings"].append(
            f"桥接已把情绪交给大肥鱼核心（127.0.0.1:{info['corePort']}）：接管时要确认大肥鱼本体的端口一致，否则情绪会回退本地算"
        )
    return info


def discover(extra: list[str] | None = None, *, timeout: float = PROBE_TIMEOUT) -> list[dict]:
    """列出本机所有像 QQ 接入的目录（在线优先）。只读，不写任何东西。"""
    rows = []
    seen = set()
    for path in candidates(extra):
        try:
            key = str(path.resolve()).lower()
        except Exception:
            key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if not looks_like_bridge(path):
            continue
        rows.append(inspect(path, timeout=timeout))
    rows.sort(key=lambda item: (not item.get("online"), not item.get("hasConsoleToken"), item["dir"].lower()))
    return rows


# ── 接管 ───────────────────────────────────────────────────────────────────
def plan(directory: Path | str, *, timeout: float = PROBE_TIMEOUT) -> dict:
    """算出接管后的配置，不写盘。UI 预检与 dry-run 都用它。"""
    info = inspect(directory, timeout=timeout)
    app = settings.app() or {}
    before = dict(app.get("bridge") or {})
    port = info["consolePort"]
    owner = info["ownerQQ"] or str(before.get("owner_qq") or "")
    next_bridge = dict(before)
    next_bridge.update(
        {
            "enabled": True,
            "dir": info["dir"],
            "send_api": f"http://127.0.0.1:{port}/api/send/private",
            "status_api": f"http://127.0.0.1:{port}/api/status",
            "owner_qq": owner,
            "core_emotion_api_port": info["corePort"],
            "emotion_mode": info["emotionMode"],
        }
    )
    return {"info": info, "before": before, "after": next_bridge, "warnings": list(info["warnings"])}


def adopt(directory: Path | str, *, sync_bridge: bool = True, dry_run: bool = False) -> dict:
    """接管一个已经接好的 QQ 接入。

    只写三处：`config/app.json`（bridge 段）、`config/qq_config.json`（面板读的本地副本）、
    `state/qq-adopt.json`（接管记录，用于回滚）。`sync_bridge=True` 时额外把 owner/白名单
    merge 回桥接的 `config.json`（只改这两个字段，别的原样保留）。

    鱼的数据（db / 记忆系统 / 情绪 / 日记）一个字节都不碰。
    """
    info = inspect(directory)
    if not info["exists"] or not info["looksLikeBridge"]:
        raise FileNotFoundError(f"不像 qq-bridge 目录：{directory}")
    plan_data = plan(directory)
    result: dict[str, Any] = {
        "ok": True,
        "dry_run": bool(dry_run),
        "dir": info["dir"],
        "before": plan_data["before"],
        "after": plan_data["after"],
        "warnings": plan_data["warnings"],
        "backup": "",
        "synced": {},
    }
    if dry_run:
        return result

    backup = _backup_app()
    app = settings.app() or {}
    app = {**app, "bridge": plan_data["after"]}
    settings.save("app", app)

    _write_json(
        settings.CONFIG / LOCAL_CONFIG,
        {
            "owner_qq": plan_data["after"].get("owner_qq") or "",
            "allow": info["allow"],
            "updated_at": _now(),
            "adopted_from": info["dir"],
        },
    )

    if sync_bridge:
        try:
            result["synced"] = _sync_bridge(info)
        except Exception as exc:  # noqa: BLE001
            result["warnings"].append(f"同步桥接配置失败（不影响接管）：{exc}")

    settings.write_state(
        STATUS_FILE,
        {
            "dir": info["dir"],
            "at": _now(),
            "backup": str(backup) if backup else "",
            "before": plan_data["before"],
            "after": plan_data["after"],
            "synced": result["synced"],
        },
    )
    result["backup"] = str(backup) if backup else ""
    return result


def rollback() -> dict:
    """还原到接管前的 app.json bridge 段。只动配置，不动鱼的数据。"""
    record = settings.read_state(STATUS_FILE, {}) or {}
    if not record:
        return {"ok": False, "error": "没有接管记录"}
    backup = Path(str(record.get("backup") or ""))
    app = settings.app() or {}
    if backup.is_file():
        data = _read_json(backup, None)
        if not isinstance(data, dict):
            return {"ok": False, "error": f"备份文件坏了：{backup}"}
        settings.save("app", data)
        restored = str(backup)
    else:
        app = {**app, "bridge": record.get("before") or {}}
        settings.save("app", app)
        restored = "before"
    settings.write_state(STATUS_FILE, {**record, "rolled_back_at": _now()})
    return {"ok": True, "restored": restored}


def status(*, include_candidates: bool = False, timeout: float = PROBE_TIMEOUT) -> dict:
    """当前接管状态（给 UI/自检用）。默认不扫候选目录，避免界面每次刷新都等探测。"""
    app_bridge = settings.app().get("bridge") or {}
    directory = _clean(app_bridge.get("dir"))
    record = settings.read_state(STATUS_FILE, {}) or {}
    info = inspect(directory, timeout=timeout) if directory else None
    out = {
        "dir": directory,
        "adopted": bool(record),
        "adopted_at": record.get("at", ""),
        "online": bool(info and info["online"]),
        "ownerQQ": (info or {}).get("ownerQQ") or str(app_bridge.get("owner_qq") or ""),
        "emotionMode": (info or {}).get("emotionMode") or app_bridge.get("emotion_mode") or "local",
        "hasConsoleToken": bool(info and info["hasConsoleToken"]),
        "hasAgentToken": bool(info and info["hasAgentToken"]),
        "warnings": list((info or {}).get("warnings") or []),
    }
    if include_candidates:
        found = discover(timeout=timeout)
        out["candidates"] = found
        out["candidateCount"] = len(found)
    return out


# ── 内部：备份 / 同步 ──────────────────────────────────────────────────────
def _backup_app() -> Path | None:
    src = settings.CONFIG / "app.json"
    if not src.is_file():
        return None
    folder = settings.CONFIG / BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"app-{datetime.now():%Y%m%d-%H%M%S}.json"
    shutil.copy2(src, target)
    return target


def _sync_bridge(info: dict) -> dict:
    """把 ownerQQ 与白名单 merge 回桥接 config.json；只改这两个字段。"""
    path = Path(info["dir"]) / "config.json"
    cfg = _read_json(path, {})
    if not isinstance(cfg, dict):
        raise ValueError("桥接 config.json 不是对象")
    changes: dict[str, Any] = {}
    owner = _clean(info.get("ownerQQ"))
    if owner:
        owner_int = _int(owner, 0)
        if owner_int and cfg.get("ownerQQ") != owner_int:
            cfg["ownerQQ"] = owner_int
            changes["ownerQQ"] = owner_int
    allow = cfg.get("allow") if isinstance(cfg.get("allow"), dict) else {}
    wanted = info.get("allow") or {}
    for key in ("private", "groups"):
        values = _id_list(wanted.get(key))
        if values and allow.get(key) != values:
            allow[key] = values
            changes[f"allow.{key}"] = values
    if changes:
        cfg["allow"] = allow
        cfg.setdefault("allowAllWhenEmpty", False)
        _write_json(path, cfg)
    return changes
