"""大肥鱼 · 桌面入口。

用法：
    python run.py              打开界面（同时跑认知循环与调度）
    python run.py --headless   只跑后台（不弹窗，适合演示/测试）

启动顺序：配置 → 建库 → 单实例锁 → 情绪向量 → 调度器 → 本机 API → 界面。
任何一步失败都不静默：写 logs/ 并在界面上说清楚。
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import db, settings  # noqa: E402


def _log(message: str) -> None:
    settings.ensure_dirs()
    path = settings.LOGS / f"{datetime.now():%Y-%m-%d}.log"
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%H:%M:%S}] {message}\n")
    except Exception:
        pass


def _single_instance():
    """返回 (lock, ok)。用 QLockFile，避免双开双写 DB 与契约文件。"""
    from PySide6.QtCore import QLockFile

    lock = QLockFile(str(settings.STATE / "singleton.lock"))
    lock.setStaleLockTime(30_000)
    ok = lock.tryLock(200)
    return lock, ok


def boot(headless: bool = False) -> int:
    settings.ensure_dirs()
    db.init_db()
    from core.emotion import vector
    from core.cognition import scheduler
    from core import selfcheck
    from core import api

    # 第一行日志固定展示灵魂锚点（v12 要求），之后再做能力自检与启动
    try:
        import core_ethos

        soul = core_ethos.alarm_once()
        _log(f"{soul['message']}｜{soul['anchor']}")
        if not soul["ok"]:
            _log(f"⚠️ 灵魂锚点校验失败 expected={soul['expected']} actual={soul['actual']}")
    except Exception as exc:  # noqa: BLE001
        _log(f"灵魂锚点加载失败：{exc}")

    try:
        caps = selfcheck.write()
        _log(selfcheck.summary() + (f"｜缺：{caps['missing']}" if caps.get("missing") else ""))
    except Exception as exc:  # noqa: BLE001
        _log(f"自检失败：{exc}")

    vector.load()
    _log(f"开始启动 headless={headless} db={db.DB_PATH}")
    if settings.app().get("bridge", {}).get("emotion_mode") == "core":
        try:
            api.start()
        except Exception as exc:  # noqa: BLE001
            _log(f"本机 API 启动失败：{exc}")
    scheduler.set_app_mode(not headless)
    scheduler.start()
    _log(f"启动完成 headless={headless} db={db.DB_PATH}")

    if headless:
        import time

        try:
            while True:
                time.sleep(3)
        except KeyboardInterrupt:
            pass
        finally:
            scheduler.stop()
            api.stop()
        return 0

    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    qss = settings.UI / "theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    lock, ok = _single_instance()
    if not ok:
        QMessageBox.information(None, "大肥鱼已经在运行", "桌面上已经有一个大肥鱼窗口了，去用那个。")
        return 0

    # 首次启动：先让她有个名字和性格（已存在的实例 detect() 为 False，直接跳过）
    try:
        from core import firstrun

        if firstrun.detect():
            _log("首次启动：进入初始设定向导")
            from ui import wizard

            out = wizard.run_if_needed(app)
            _log(f"初始设定已落盘：{(out or {}).get('profile')}")
    except Exception as exc:  # noqa: BLE001
        _log(f"初始设定向导跳过（不影响启动）：{exc}")

    from ui.main_window import MainWindow

    # v12 3.1：开屏黑屏淡入手写体金句 3 秒（不挡操作，动画结束自动关）
    splash = None
    try:
        from ui.splash import SoulSplash

        splash = SoulSplash(seconds=3.0)
        splash.play()
    except Exception as exc:  # noqa: BLE001
        _log(f"开屏没起来（不影响使用）：{exc}")
        splash = None

    window = MainWindow()
    window.show()
    if splash is not None:
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(3200, splash.close)
        except Exception:
            pass

    def _bye():
        try:
            scheduler.stop()
            api.stop()
            vector.save(vector.current())
        finally:
            lock.unlock()

    app.aboutToQuit.connect(_bye)
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="大肥鱼")
    parser.add_argument("--headless", action="store_true", help="只跑后台，不弹窗")
    parser.add_argument("--no-scheduler", action="store_true", help="不启动定时任务（调试用）")
    args = parser.parse_args()
    try:
        if args.no_scheduler:
            settings.ensure_dirs()
            db.init_db()
            from ui.main_window import MainWindow  # noqa: F401
        return boot(headless=args.headless)
    except Exception:  # noqa: BLE001
        _log("启动失败：\n" + traceback.format_exc())
        if not args.headless:
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox

                app = QApplication(sys.argv)
                QMessageBox.critical(None, "大肥鱼启动失败", traceback.format_exc()[-1200:])
            except Exception:
                pass
        else:
            print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
