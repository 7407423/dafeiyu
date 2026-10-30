# 给 AI 安装助手看的说明（AI_INSTALL）

> 你可以把这一整段直接交给任意 AI 编程助手，让它在你机器上装好并跑通大肥鱼。
> 关键前提：**全程不要用 PowerShell**（有些机器 `pwsh` 是坏的，会报 `0xC0000142`）。用 `cmd`。

## 0. 环境要求

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10/11（macOS/Linux 见文末） |
| Python | 3.10 – 3.12（PySide6 暂无 3.13 / 3.14 包），且 `python` 或 `py -3` 在 PATH 里 |
| 网络 | 能访问 pypi（装依赖） |
| 不需要 | 不需要 git / gh / PowerShell / 管理员权限 |

## 1. 安装（三步）

```cmd
:: 解压后进入目录（把路径换成你解压出来的位置）
cd /d D:\dafeiyu

:: 一键安装 + 启动（会自己建 .venv、装依赖、弹界面）
start.bat
```

`start.bat` 做的事（也可以手动一条条跑，效果一样）：

```cmd
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

## 2. 验证是否装好（AI 用这个判断，不要只看窗口有没有弹）

```cmd
.venv\Scripts\python.exe -c "import PySide6, apscheduler; print('deps ok')"
.venv\Scripts\python.exe -c "import core.settings as s; s.ensure_dirs(); print('config ok', s.CONFIG)"
```

第二条命令会**自动生成 `config\`**（从 `config.default\` 复制 14 个 json）。
再确认目录里出现了：`config\app.json`、`db\dafeiyu.db`、`logs\`。

## 3. 第一次启动

双击 `start.bat`（或跑 `run.py`）后会弹「初次见面」窗口：
填名字 / 性别 / 身高 / 性格，或者直接点「用默认设定开始」。
设定会写进 `config\personality.md` 和 1 号长期记忆（自我认知 + 性格设定）。

> 想跳过界面、只看能不能起：`.venv\Scripts\python.exe run.py --headless`（会一直跑，Ctrl+C 结束）。

## 4. 接模型（不接也能跑，只是她不会说话）

1. 打开 `config\llm.json`；
2. 把 `providers.http` 填上你自己的 OpenAI 兼容接口：
   ```json
   "http": {
     "base_url": "https://api.deepseek.com/v1",
     "api_key": "你的 key",
     "model": "deepseek-chat",
     "timeout_seconds": 120,
     "temperature": 0.8
   }
   ```
3. 把 `default` 改成 `"http"`，并把 `tasks` 里那几项也都写成 `"http"`；
4. 重启程序。

## 5. 接 QQ（可选；已经有 QQ 接入的，一键接管）

本机如果已经跑着 `qq-bridge`（SnowLuma / NapCat / 其它 OneBot v11 实现都行），不用重配：

1. 打开「QQ 接入」页；
2. 点「检测已接好的 QQ」→ 选中 → 「一键接管」；
3. 或者命令行：

```cmd
.venv\Scripts\python.exe tools\adopt_qq.py --list
.venv\Scripts\python.exe tools\adopt_qq.py --adopt "D:\qq-bridge"
```

接管只改配置、先备份、可还原（`--rollback`），不碰记忆 / 情绪 / 日记，也不会启动或停止桥接。
没有桥接也能用：软件本身是桌面 AI，界面里可以对话。

## 5.1 升级到新版本

- 界面：右下角「下载新版本」→ 检查 → 下载 → 安装 → 提示重启。
- 没有更新地址时，会提示去 `config\app.json` 填 `update_url`（指向发布目录里的 `update.json`）。
- 更新只覆盖程序代码；`config\`、`db\`、`state\`、`记忆系统\`、`logs\`、`learning\` 一个字节不动，
  旧代码备份在 `.update\backup-*\`，可用 `core.updater.rollback()` 还原。
- 发版用 `python tools\release.py --version <版本>`，产物在 `dist\`。

## 6. 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| `start.bat` 一闪而过 | 在 cmd 里手动跑 `.venv\Scripts\python.exe run.py`，看报错 |
| `ModuleNotFoundError: core.xxx` | 解压不完整（别只解压一部分），重新完整解压 |
| `pip install` 很慢/失败 | 换镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 报 `0xC0000142` / pwsh 起不来 | 别用 PowerShell，一律用 `cmd` 或双击 `start.bat` |
| 界面没弹 | 看 `logs\YYYY-MM-DD.log` 最后几行 |
| 想要更多日志 | 用 `.venv\Scripts\python.exe run.py`（前台运行，直接看输出） |

## 7. macOS / Linux

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 8. 卸载

删掉整个目录即可。所有数据都在这个目录里（`db/`、`state/`、`memory/`、`config/`），
不会写到系统其它位置。
