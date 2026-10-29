# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""主界面外壳（v12 4.2）：QStackedWidget 双视图。

视图一（主页）：左侧大形象 + 左下消耗情况；右侧功能栏，右下「修复 / 下载新版本」；右上「刷新」。
视图二（详情）：左侧小形象；中间垂直三分（标题 / 附栏 / 内容）；右侧功能栏 + 底部「修复」。
"""

from __future__ import annotations

import json
import socket
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from core import cost, db, settings
from core.entity import Layer
from ui.avatar import AvatarWidget
from ui.panels.audit import AuditPanel
from ui.panels.chitchat import ChitchatPanel
from ui.panels.cost import CostPanel
from ui.panels.curiosity_engine import CuriosityEnginePanel
from ui.panels.emotion import EmotionPanel
from ui.panels.language import BookPanel
from ui.panels.learning import LearningPanel
from ui.panels.memory import (BookView, DiaryView, InstantView, Lt1View, Lt2View, PendingView)
from ui.panels.qqbridge import QQBridgePanel
from ui.panels.refusal import RefusalPanel
from ui.panels.relationship import RelationshipPanel
from ui.panels.residual import ResidualView
from ui.panels.stickers import StickerPanel
from ui.panels.memewiki import MemeWikiPanel
from ui.panels.about import AboutPanel
from ui.panels.webstudy import WebStudyPanel
from ui.widgets import hint_label

SIDEBAR_W = 150


def _money(v: float) -> str:
    return f"¥{v:.2f}" if abs(v) >= 0.01 else f"¥{v:.3f}"


class FunctionBar(QWidget):
    """右侧功能栏：上面列功能，底部放 修复 / 下载新版本。"""

    def __init__(self, on_open, on_repair, on_update, *, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_W)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        title = QLabel("功能栏")
        title.setObjectName("Subtitle")
        layout.addWidget(title)

        self.buttons: dict[str, QPushButton] = {}
        for key, label in FUNCTIONS:
            btn = QPushButton(label)
            btn.setObjectName("Function")
            btn.clicked.connect(lambda _=False, k=key: on_open(k))
            layout.addWidget(btn)
            self.buttons[key] = btn
        layout.addStretch(1)

        self.repair = QPushButton("修复")
        self.repair.clicked.connect(on_repair)
        layout.addWidget(self.repair)
        if not compact:
            self.update_btn = QPushButton("下载新版本")
            self.update_btn.clicked.connect(on_update)
            layout.addWidget(self.update_btn)
        else:
            self.update_btn = None


FUNCTIONS = [
    ("memory", "记忆"),
    ("learning", "学习"),
    ("language", "语言"),
    ("emotion", "情绪"),
    ("cost", "花费"),
    ("chitchat", "碎碎念"),
    ("refusal", "拒绝权"),
    ("audit", "审计"),
    ("qq", "QQ 接入"),
]


class HomePage(QWidget):
    def __init__(self, shell: "Shell", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(6)
        top = QHBoxLayout()
        top.addStretch(1)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(shell.refresh_all)
        top.addWidget(self.refresh_btn)
        left.addLayout(top)

        self.avatar = AvatarWidget()
        left.addWidget(self.avatar, 1)
        self.avatar_hint = hint_label("")
        left.addWidget(self.avatar_hint)

        strip = QFrame()
        strip.setObjectName("CostStrip")
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(12, 8, 12, 8)
        sl.setSpacing(14)
        cap = QLabel("消耗使用情况")
        cap.setObjectName("Subtitle")
        sl.addWidget(cap)
        self.day = QLabel("今天")
        sl.addWidget(self.day)
        self.total = QLabel("¥0.00")
        self.total.setObjectName("Title")
        sl.addWidget(self.total)
        self.calls = QLabel("0 次")
        sl.addWidget(self.calls)
        sl.addStretch(1)
        self.note = QLabel("")
        self.note.setObjectName("Hint")
        sl.addWidget(self.note)
        left.addWidget(strip)

        layout.addLayout(left, 1)
        self.bar = FunctionBar(shell.open_detail, shell.repair, shell.check_update)
        layout.addWidget(self.bar)


class DetailPage(QWidget):
    def __init__(self, shell: "Shell", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(4)
        self.avatar = AvatarWidget()
        self.avatar.setFixedWidth(230)
        self.avatar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left.addWidget(self.avatar, 1)
        self.avatar_hint = hint_label("")
        self.avatar_hint.setWordWrap(True)
        left.addWidget(self.avatar_hint)
        holder = QWidget()
        holder.setLayout(left)
        holder.setFixedWidth(230)
        layout.addWidget(holder)

        middle = QVBoxLayout()
        middle.setSpacing(6)
        head = QHBoxLayout()
        self.back = QPushButton("← 返回")
        self.back.clicked.connect(shell.go_home)
        head.addWidget(self.back)
        self.title = QLabel("")
        self.title.setObjectName("Title")
        head.addWidget(self.title)
        head.addStretch(1)
        middle.addLayout(head)

        body = QSplitter(Qt.Vertical)
        body.setChildrenCollapsible(False)

        self.items = QListWidget()
        self.items.setMinimumHeight(0)
        self.items.currentRowChanged.connect(self._pick)
        body.addWidget(self.items)

        self.stack = QStackedWidget()
        body.addWidget(self.stack)
        body.setSizes([140, 620])
        self.splitter = body
        middle.addWidget(body, 1)
        layout.addLayout(middle, 1)

        self.bar = FunctionBar(shell.open_detail, shell.repair, shell.check_update, compact=True)
        layout.addWidget(self.bar)

        self._views: list[QWidget] = []
        self._module = ""

    def show_module(self, key: str, title: str, views: list[tuple[str, QWidget]]) -> None:
        self._module = key
        self.title.setText(title)
        self.items.clear()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        self._views = []
        for label, widget in views:
            self.items.addItem(QListWidgetItem(label))
            self.stack.addWidget(widget)
            self._views.append(widget)
        # 子栏目列表的高度跟着条目走：一个栏目就整块收起（否则顶部永远留一块空白，
        # 打开任何面板第一眼都是「一块空卡片」——老大反馈的「看不明白」就是这个）。
        if len(views) <= 1:
            self.items.setVisible(False)
            self.items.setMaximumHeight(0)
            self.splitter.setSizes([0, 640])
        else:
            self.items.setVisible(True)
            rows_height = min(150, 12 + 26 * len(views))
            self.items.setMinimumHeight(rows_height)
            self.items.setMaximumHeight(rows_height)
            self.splitter.setSizes([rows_height, max(240, 640 - rows_height)])
        if views:
            self.items.setCurrentRow(0)
        for btn_key, btn in self.bar.buttons.items():
            btn.setProperty("active", "true" if btn_key == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _pick(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            self.refresh_current()

    def refresh_current(self) -> None:
        index = self.stack.currentIndex()
        if 0 <= index < len(self._views):
            try:
                self._views[index].refresh()
            except Exception:
                pass

    def current_view(self) -> QWidget | None:
        index = self.stack.currentIndex()
        return self._views[index] if 0 <= index < len(self._views) else None


class Shell(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels = build_panels()
        self.home = HomePage(self)
        self.detail = DetailPage(self)
        self.addWidget(self.home)
        self.addWidget(self.detail)
        self.setCurrentWidget(self.home)

    # ── 导航 ──
    def go_home(self) -> None:
        self.setCurrentWidget(self.home)
        self.refresh_all()

    def open_detail(self, key: str) -> None:
        title, views = self.panels.get(key, ("", []))
        if not views:
            return
        self.detail.show_module(key, title, views)
        self.setCurrentWidget(self.detail)
        self.detail.refresh_current()

    # ── 刷新 ──
    def refresh_all(self) -> None:
        self.refresh_home()
        if self.currentWidget() is self.detail:
            self.detail.refresh_current()

    def refresh_home(self) -> None:
        try:
            data = cost.summary()
            today = data["today"]
            self.home.total.setText(_money(today["total"]))
            self.home.calls.setText(f"{today['turns']} 轮聊天")
            self.home.note.setText(
                f"私聊 {_money(today['private'])}｜群 {_money(today['group'])}"
                f"｜后台 {_money(today['engine'])}")
        except Exception:
            self.home.note.setText("花费读不到")
        self.home.day.setText(datetime.now().strftime("%m-%d"))

    def set_avatar(self, state: str, caption: str, hint: str) -> None:
        for page in (self.home, self.detail):
            try:
                page.avatar.set_state(state, caption)
                page.avatar_hint.setText(hint)
            except Exception:
                pass

    # ── 维护 ──
    def repair(self) -> str:
        lines = []
        checks = []

        try:
            db.q1("SELECT 1")
            checks.append(("数据库连接", True, f"{db.stats().get('memory_item', 0)} 条记忆"))
        except Exception as exc:  # noqa: BLE001
            checks.append(("数据库连接", False, str(exc)))

        try:
            settings.write_state("repair_probe.json", {"at": datetime.now().isoformat()})
            settings.read_state("repair_probe.json", {})
            checks.append(("状态文件读写", True, "state/ 可写可读"))
        except Exception as exc:  # noqa: BLE001
            checks.append(("状态文件读写", False, str(exc)))

        port = int((settings.app().get("core_api") or {}).get("port", 18766))
        checks.append(_probe_http(f"本机 API :{port}", f"http://127.0.0.1:{port}/api/status"))
        checks.append(_probe_http("QQ 桥接 :3100", "http://127.0.0.1:3100/api/status",
                                  bridge_dir() / "state" / "console-token"))

        try:
            import core_ethos

            ok = core_ethos.verify()["ok"]
            checks.append(("灵魂锚点", ok, "完好" if ok else "被修改（已回退内置副本）"))
        except Exception as exc:  # noqa: BLE001
            checks.append(("灵魂锚点", False, str(exc)))

        for name, ok, detail in checks:
            lines.append(f"{'✓' if ok else '✗'} {name}：{detail}")
        bad = sum(1 for _n, ok, _d in checks if not ok)
        lines.insert(0, "全部通过。" if bad == 0 else f"{bad} 项需要看：")
        return "\n".join(lines)

    def check_update(self) -> str:
        local = str((settings.app().get("version") or "0.1.0"))
        url = str((settings.app().get("update_url") or "")).strip()
        if not url:
            return (f"当前版本 {local}\n没有配置更新地址（config/app.json → update_url），"
                    f"按本地版本算已是最新。")
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            latest = str(data.get("version") or "")
            if latest and latest != local:
                return f"发现新版本 {latest}（当前 {local}）\n{data.get('url') or ''}"
            return f"当前已是最新版本（{local}）"
        except Exception as exc:  # noqa: BLE001
            return f"检查更新失败：{exc}\n当前版本 {local}"


def _probe_http(name: str, url: str, token_file: Path | None = None) -> tuple[str, bool, str]:
    req = urllib.request.Request(url)
    if token_file is not None:
        try:
            req.add_header("x-console-token", token_file.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read(64)
        return (name, True, "通")
    except Exception as exc:  # noqa: BLE001
        return (name, False, f"不通（{exc}）")


def bridge_dir() -> Path:
    return Path(str((settings.app().get("bridge") or {}).get("dir") or ""))


def build_panels() -> dict[str, tuple[str, list[tuple[str, QWidget]]]]:
    """每个功能 = (标题, [(附栏条目, 内容控件)])。"""
    lt1 = Lt1View()
    lt2 = Lt2View()
    diary = DiaryView()
    pending = PendingView()
    instant = InstantView()
    lang_mem = BookView(Layer.LANGUAGE.value)
    emo_mem = BookView(Layer.EMOTION.value)
    residual = ResidualView()
    stickers = StickerPanel()
    meme_wiki = MemeWikiPanel()
    about = AboutPanel()
    web_study = WebStudyPanel()
    learning = LearningPanel()
    engine = CuriosityEnginePanel()
    lang_book = BookPanel(Layer.LANGUAGE.value)
    emotion = EmotionPanel()
    relation = RelationshipPanel()
    cost_panel = CostPanel()
    chitchat = ChitchatPanel()
    refusal = RefusalPanel()
    audit = AuditPanel()
    qq = QQBridgePanel()

    return {
        "memory": ("记忆系统", [
            ("1号长期记忆", lt1), ("2号长期记忆", lt2), ("短期 · 日记本", diary),
            ("短期 · 待总结", pending), ("瞬时记忆", instant),
            ("语言记忆", lang_mem), ("情绪记忆", emo_mem), ("思维链 · 最近想法", residual), ("表情字典", stickers), ("梗百科", meme_wiki), ("刷抖音学梗", web_study),
        ]),
        "learning": ("学习系统", [("意图队列与报告", learning), ("好奇心引擎", engine)]),
        "language": ("语言系统", [("语言账本", lang_book)]),
        "emotion": ("情绪系统", [("当前情绪", emotion), ("关系与索取度", relation),
                                ("情绪记忆（账本）", emo_mem)]),
        "cost": ("花费", [("总览与按功能归因", cost_panel)]),
        "chitchat": ("碎碎念", [("碎碎念", chitchat)]),
        "refusal": ("拒绝权", [("拒绝记录与设置", refusal)]),
        "audit": ("审计视图", [("审计事件", audit), ("关于与许可", about)]),
        "qq": ("QQ 接入", [("接入向导与状态", qq)]),
    }

