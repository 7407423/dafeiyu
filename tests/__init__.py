"""测试包。

这里第一件事就把 DAFEIYU_HOME 指到临时目录，**必须**在任何 `core` 导入之前。
（曾经因为 test_arbiter 先 import core，导致 settings.ROOT 锁到真实目录，
测试清理时误删了线上的 state/emotion.json——这个文件的顺序就是防止再犯。）
"""

from . import base  # noqa: F401
