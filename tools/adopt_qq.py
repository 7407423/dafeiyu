# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# ─────────────────────────────────────────────────────────────────────────────
"""命令行接管已有 QQ 接入（等价于界面「QQ 接入」页的检测 / 一键接管）。

用法：
    python tools/adopt_qq.py --list          # 看看本机有哪些已接好的 QQ
    python tools/adopt_qq.py --status        # 当前接管状态
    python tools/adopt_qq.py --dry-run "D:\\qq-bridge"
    python tools/adopt_qq.py --adopt "D:\\qq-bridge"
    python tools/adopt_qq.py --rollback      # 还原到接管前

只改配置：config/app.json 的 bridge 段、config/qq_config.json、state/qq-adopt.json，
以及（默认）桥接 config.json 里的 ownerQQ / allow。绝不碰 db、记忆、情绪、日记，
也绝不启动或停止桥接。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import qq_adopt  # noqa: E402


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="大肥鱼 · 接管已有的 QQ 接入")
    parser.add_argument("--list", action="store_true", help="列出本机已接好的 QQ 接入")
    parser.add_argument("--status", action="store_true", help="当前接管状态")
    parser.add_argument("--adopt", metavar="DIR", help="接管指定目录的 qq-bridge")
    parser.add_argument("--rollback", action="store_true", help="还原到接管前的配置")
    parser.add_argument("--dry-run", nargs="?", const=True, metavar="DIR",
                        help="只预检不写盘；给 DIR 等价于 --adopt DIR --dry-run")
    parser.add_argument("--no-sync", action="store_true", help="不改桥接 config.json 的 owner/白名单")
    args = parser.parse_args()

    if isinstance(args.dry_run, str):
        args.adopt = args.adopt or args.dry_run
        args.dry_run = True

    if args.list:
        rows = qq_adopt.discover()
        if not rows:
            print("没检测到已接好的 QQ 接入。确认 qq-bridge 目录在常见位置，或设 QQ_BRIDGE_HOME。")
            return 0
        for index, info in enumerate(rows, 1):
            print(f"[{index}] {info['dir']}")
            print(f"    在线：{'是' if info['online'] else '否'}｜QQ：{info['ownerQQ'] or '?'}"
                  f"｜模式：{info['mode'] or '?'}｜情绪：{info['emotionMode']}")
            for warning in info.get("warnings") or []:
                print(f"    ! {warning}")
        return 0

    if args.status:
        _print(qq_adopt.status(include_candidates=False))
        return 0

    if args.rollback:
        _print(qq_adopt.rollback())
        return 0

    if args.adopt:
        try:
            result = qq_adopt.adopt(args.adopt, sync_bridge=not args.no_sync, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"接管失败：{exc}")
            return 1
        _print(result)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
