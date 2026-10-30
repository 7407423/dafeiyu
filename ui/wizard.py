# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""首次启动向导：给自己捏一个「她」（名字 / 性别 / 身高 / 性格）。

只在**第一次**启动出现（`core.firstrun.detect()`）；已经在跑的实例永远不会看到这个窗口。
直接点「用默认设定开始」也能进 —— 默认就是「大肥鱼 + 傲娇壳 + 温柔心」。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QVBoxLayout)

from core import firstrun, qq_adopt

WELCOME = (
    "第一次见面，先给「她」定个样子吧。\n"
    "这些设定会写进她的 1 号长期记忆（自我认知 + 性格设定），以后她自己也知道自己是谁。\n"
    "不填也能用：直接点下面「用默认设定开始」。"
)


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("大肥鱼 · 初次见面")
        self.setMinimumWidth(560)
        # 别用系统默认白底：主题是深色，白底会让标题白字看不见（实测截出来就是一片白）
        self.setStyleSheet(
            "QDialog{background:#0d141d;}"
            "QLabel{color:#cfe0f5;font-size:13px;}"
            "QLabel#Title{font-size:18px;font-weight:700;color:#e6eefc;}"
            "QLabel#Hint{color:#8fa6c4;font-size:12px;}"
            "QLineEdit,QComboBox,QTextEdit{background:#131c28;color:#e6eefc;border:1px solid #24344a;"
            "border-radius:6px;padding:5px 6px;font-size:13px;}"
            "QComboBox QAbstractItemView{background:#131c28;color:#e6eefc;}"
            "QPushButton{background:#1b2735;color:#dbe7f6;border:1px solid #26374c;border-radius:6px;"
            "padding:6px 14px;font-size:13px;}"
            "QPushButton#Primary{background:#2563eb;border-color:#3b82f6;color:#ffffff;}"
            "QPushButton:hover{background:#22334a;}"
        )
        self._result: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        head = QLabel("给大肥鱼起个名字、定个性格")
        head.setObjectName("Title")
        layout.addWidget(head)

        intro = QLabel(WELCOME)
        intro.setWordWrap(True)
        intro.setObjectName("Hint")
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(8)
        self.name = QLineEdit(firstrun.DEFAULTS["name"])
        self.gender = QComboBox()
        self.gender.addItems(["暂未设置", "女", "男", "其他"])
        self.height = QLineEdit(firstrun.DEFAULTS["height"])
        self.height.setPlaceholderText("例如 168cm；不填就是「暂未设置」")
        form.addRow("名字", self.name)
        form.addRow("性别", self.gender)
        form.addRow("身高", self.height)
        layout.addLayout(form)

        # 本机如果已经有 QQ 接入（qq-bridge + SnowLuma / NapCat），顺手接过来：
        # 不接管的话，她只能离线自己玩，用户还得去 app.json 手填 bridge.dir。
        self.adopt_dir = ""
        self._found: list[dict] = []
        try:
            self._found = qq_adopt.discover(timeout=0.6)
        except Exception:
            self._found = []
        self.adopt_check = None
        if self._found:
            first = self._found[0]
            self.adopt_check = QCheckBox(
                f"检测到本机已有 QQ 接入（{first['dir']}｜QQ {first.get('ownerQQ') or '?'}），启动后自动接管")
            self.adopt_check.setChecked(True)
            layout.addWidget(self.adopt_check)

        layout.addWidget(QLabel("性格"))
        self.template = QComboBox()
        for title, _text in firstrun.TEMPLATES:
            self.template.addItem(title)
        self.template.currentIndexChanged.connect(self._fill_template)
        layout.addWidget(self.template)

        self.personality = QTextEdit()
        self.personality.setPlainText(firstrun.TEMPLATES[0][1])
        self.personality.setMinimumHeight(90)
        layout.addWidget(self.personality)

        tip = QLabel("提示：性格写得越具体，她越像「那个人」；以后想改，直接编辑 config/personality.md。")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        row = QHBoxLayout()
        row.addStretch(1)
        self.skip = QPushButton("用默认设定开始")
        self.skip.clicked.connect(self._accept_defaults)
        row.addWidget(self.skip)
        self.ok = QPushButton("就这样开始")
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._accept)
        row.addWidget(self.ok)
        layout.addLayout(row)

    def _fill_template(self, index: int) -> None:
        if 0 <= index < len(firstrun.TEMPLATES):
            self.personality.setPlainText(firstrun.TEMPLATES[index][1])

    def _collect(self) -> dict:
        if self.adopt_check is not None and self.adopt_check.isChecked() and self._found:
            self.adopt_dir = str(self._found[0]["dir"])
        return {
            "name": (self.name.text() or "").strip() or firstrun.DEFAULTS["name"],
            "gender": self.gender.currentText() or firstrun.DEFAULTS["gender"],
            "height": (self.height.text() or "").strip() or firstrun.DEFAULTS["height"],
            "personality": (self.personality.toPlainText() or "").strip()
            or firstrun.DEFAULTS["personality"],
        }

    def _accept(self) -> None:
        self._result = self._collect()
        self.accept()

    def _accept_defaults(self) -> None:
        self._result = dict(firstrun.DEFAULTS)
        self.accept()

    def result_profile(self) -> dict:
        return self._result or dict(firstrun.DEFAULTS)


def run_if_needed(app, force: bool = False) -> dict | None:
    """需要时弹向导并落盘；不需要就返回 None。

    force=True：调用方已经判断过"首次启动"（run.py 是在 db.init_db() **之前**判断的），
    这里不要再查一次 —— 建库之后 `firstrun.detect()` 永远是 False，向导会永远弹不出来。
    """
    if not force:
        try:
            if not firstrun.detect():
                return None
        except Exception:
            return None
    try:
        wizard = SetupWizard()
        wizard.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        wizard.show()
        app.processEvents()
        accepted = wizard.exec() == QDialog.Accepted
        prof = wizard.result_profile() if accepted else dict(firstrun.DEFAULTS)
        applied = firstrun.apply(prof)
        if getattr(wizard, "adopt_dir", ""):
            try:
                qq_adopt.adopt(wizard.adopt_dir)
            except Exception:
                # 接管失败不影响首次设定；用户之后可以在「QQ 接入」面板里再点一次
                pass
        return applied
    except Exception as error:  # noqa: BLE001
        try:
            return firstrun.apply(dict(firstrun.DEFAULTS))
        except Exception:
            return {"ok": False, "error": str(error)}
