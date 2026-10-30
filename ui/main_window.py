# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""主窗口（v12 4.2）：QStackedWidget 双视图 + 右侧功能栏。

视图一：左形象 + 左下消耗情况 + 右上刷新 + 右下修复/下载新版本。
视图二：左小形象 + 中（标题/附栏/内容）+ 右功能栏 + 修复。
桌面对话默认隐藏（调试入口 Ctrl+Shift+D），对话在 QQ。
"""

from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtCore import QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressDialog, QVBoxLayout, QWidget,
)

from core import db, settings, updater
from core.cognition import loop
from core.emotion import vector
from ui.chat import ChatPanel
from ui.shell import Shell


class UpdateWorker(QThread):
    """后台下载 + 安装，避免下载时卡住界面。"""

    progress = Signal(int, int)
    done = Signal(dict)
    failed = Signal(str)

    def run(self) -> None:  # noqa: D401
        try:
            result = updater.update(progress=lambda done, total: self.progress.emit(int(done), int(total)))
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("大肥鱼 · 大肥鱼")
        icon_path = settings.ASSETS / "大肥鱼.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        size = settings.app().get("window", {})
        want_w = int(size.get("width", 1240))
        want_h = int(size.get("height", 880))
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            width = min(want_w, screen.width() - 120)
            height = min(want_h, screen.height() - 100)
            self.setGeometry(screen.left() + (screen.width() - width) // 2,
                             screen.top() + (screen.height() - height) // 2,
                             width, height)
        else:
            self.resize(want_w, want_h)
        self.setMinimumSize(min(int(size.get("min_width", 1000)), 1000),
                            min(int(size.get("min_height", 700)), 700))

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 8)
        outer.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("大肥鱼")
        title.setObjectName("Title")
        sub = QLabel("记忆 · 学习 · 语言 · 情绪 ｜ 认知循环每 20 秒一拍")
        sub.setObjectName("Subtitle")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(sub)
        head.addStretch(1)
        outer.addLayout(head)

        self.shell = Shell()
        self.shell.update_handler = self.check_update
        outer.addWidget(self.shell, 1)

        self.chat = ChatPanel()
        self.chat.hide()
        outer.addWidget(self.chat)
        try:
            from PySide6.QtGui import QKeySequence, QShortcut

            self._chat_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
            self._chat_shortcut.activated.connect(self.toggle_chat)
        except Exception:
            self._chat_shortcut = None

        self._status = QLabel("")
        self._status.setObjectName("Hint")
        outer.addWidget(self._status)

        self.fast = QTimer(self)
        self.fast.timeout.connect(self._refresh_live)
        self.fast.start(2000)
        self.slow = QTimer(self)
        self.slow.timeout.connect(self._refresh_slow)
        self.slow.start(15000)
        self._refresh_live()
        self._refresh_slow()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_centered", False):
            self._centered = True
            screen = self.screen().availableGeometry() if self.screen() else None
            if screen is not None:
                geo = self.frameGeometry()
                geo.moveCenter(screen.center())
                self.move(max(screen.left(), geo.left()), max(screen.top(), geo.top()))

    # ── 调试对话 ──
    def toggle_chat(self) -> bool:
        visible = not self.chat.isVisible()
        self.chat.setVisible(visible)
        if visible:
            self.chat.setMinimumHeight(240)
        self._status.setText("调试对话已打开（仅本地，不影响 QQ）" if visible
                             else "调试对话已收起")
        return visible

    # ── 修复 / 更新 ──
    def repair(self) -> None:
        text = self.shell.repair()
        box = QMessageBox(self)
        box.setWindowTitle("修复自检")
        box.setText("自检结果")
        box.setDetailedText(text)
        box.setIcon(QMessageBox.Information if "需要看" not in text else QMessageBox.Warning)
        box.exec()

    def check_update(self) -> None:
        info = updater.check()
        if not info.get("ok"):
            QMessageBox.information(self, "检查更新",
                                    f"当前版本 {info.get('local')}\n{info.get('error') or '检查更新失败'}")
            return
        if not info.get("newer"):
            QMessageBox.information(self, "检查更新", f"当前已是最新版本（{info.get('local')}）。")
            return
        notes = (info.get("notes") or "").strip()
        text = (f"发现新版本 {info.get('latest')}（当前 {info.get('local')}）"
                + (f"\n\n{notes}" if notes else "")
                + "\n\n现在下载并安装吗？\n只替换程序代码，不碰配置、记忆、情绪、日记。")
        if QMessageBox.question(self, "发现新版本", text) != QMessageBox.Yes:
            return
        self._start_update()

    def _start_update(self) -> None:
        self._progress = QProgressDialog("正在下载新版本…", "隐藏", 0, 100, self)
        self._progress.setWindowTitle("下载新版本")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._worker = UpdateWorker(self)
        self._worker.progress.connect(self._on_update_progress)
        self._worker.done.connect(self._on_update_done)
        self._worker.failed.connect(self._on_update_failed)
        self._worker.start()
        self._progress.show()

    def _on_update_progress(self, done: int, total: int) -> None:
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(done)
        else:
            self._progress.setValue(min(99, self._progress.value() + 1))

    def _on_update_done(self, result: dict) -> None:
        try:
            self._progress.close()
        except Exception:
            pass
        if not result.get("ok"):
            QMessageBox.warning(self, "更新失败", str(result.get("error") or "未知原因"))
            return
        version = result.get("latest") or result.get("version") or ""
        text = (f"已更新到 {version}（覆盖 {result.get('installed', 0)} 个文件）。\n"
                "重启后生效。\n\n现在重启大肥鱼吗？")
        box = QMessageBox(self)
        box.setWindowTitle("更新完成")
        box.setText(text)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes)
        if box.exec() == QMessageBox.Yes:
            self._restart_app()

    def _on_update_failed(self, message: str) -> None:
        try:
            self._progress.close()
        except Exception:
            pass
        QMessageBox.warning(self, "更新失败", f"下载或安装失败：{message}\n\n原来的程序没有被改动。")

    def _restart_app(self) -> None:
        """退出并延迟 2 秒重启（先让单实例锁释放，再用同一个解释器拉起 run.py）。"""
        root = str(updater.PROGRAM_ROOT)
        python = sys.executable or "pythonw"
        command = f'timeout /t 2 >nul & start "" "{python}" "{root}\\run.py"'
        QProcess.startDetached("cmd", ["/c", command], root)
        QApplication.quit()

    # ── 刷新 ──
    def _refresh_live(self) -> None:
        try:
            st = vector.status()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"情绪读取失败：{exc}")
            return
        activity = loop.status()
        state, caption = self._avatar_state(st, activity)
        hint = (f"主导情绪：{st['dominant_cn']}｜正面 {st['positive']:.0f} 负面 {st['negative']:.0f} "
                f"害羞 {st['values']['shyness']:.0f}｜保护中：{', '.join(st['protected']) or '无'}")
        self.shell.set_avatar(state, caption, hint)
        self._status.setText(
            f"她在：{activity.get('note') or activity.get('kind', 'idle')}｜"
            f"DB {db.stats().get('memory_item', 0)} 条记忆｜{settings.ROOT}")

    def _refresh_slow(self) -> None:
        try:
            self.shell.refresh_all()
        except Exception:
            pass

    def _avatar_state(self, st: dict, activity: dict) -> tuple[str, str]:
        kind = str(activity.get("kind") or "")
        if kind in ("learn", "study"):
            return "study", "在学东西"
        if kind in ("open_thought", "task"):
            return "think", "在想事"
        try:
            from core.refusal import store as refusal_store
            from core.text import parse_iso

            rows = refusal_store.recent(1)
            if rows:
                when = parse_iso(rows[0].get("t") or "")
                fresh = when and (datetime.now() - when).total_seconds() < 180
                if fresh and rows[0]["decision"] in ("REFUSE", "DEFLECT"):
                    return "refuse", "刚拒绝了"
                if fresh and rows[0]["decision"] == "RELUCTANT_ACCEPT":
                    return "reluctant", "嘴上不情愿"
        except Exception:
            pass
        if st["behavior"]["negative_high"]:
            return "sad", "不想说话"
        if st["behavior"]["shy_high"]:
            return "shy", "有点不好意思"
        if st["behavior"]["positive_high"]:
            return "lively", "心情不错"
        return "calm", "平静"
