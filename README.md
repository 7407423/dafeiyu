# 大肥鱼 · AI 版 QQ 伴侣

> 一条龙服务：**纯新手小白也能从零把 DeepSeek 接进 QQ**。

## 这个软件能做什么

- **类人脑系统**：记忆、遗忘、情绪、学习、碎碎念串成一套，不是"聊一句丢一句"；
- **刷抖音学习**：她自己去刷、自己记梗（⚠️ 会占用你本机的浏览器窗口，**必须保持开机、不锁屏、不休眠**）；
- **AI 有依赖性**（强度可手动调节）：她会想找你，久不理她会难受；
- **初始性格可手动设置**，也可以直接用默认（表面傲娇、内心关心人）；
- **性格会随对话改变**：伤害让她孤僻，夸奖让她开朗（改得很慢，按周算）；
- **花费几乎为零**：刷抖音学习 **0 元**；看表情包只有**第一次**识别花钱（约 ¥0.01），
  同一张图之后命中本地字典，**不再产生任何费用**。

> 更多详细功能，下载自己玩一玩最快。

---

# 大肥鱼 v0.9.1

## 本版更新（v0.9.3）

- **修复：首次启动向导永远弹不出来**。`run.py` 在 `db.init_db()` 之前判断"首次启动"，
  但向导内部又查了一次 `firstrun.detect()`——此时库已经建好，永远是 False。现在传 `force=True`。
- **修复：模型调用到解析就崩**。`_parse_stream` 遇到非对象 JSON 行（数组/字符串/数字）会
  `AttributeError`；`dsh.cmd` 路径含空格时 `cmd /c` 会截断。两处都修了。
- **修复：装不起来**。`start.bat` 现在优先找 Python 3.12 / 3.11 / 3.10，找不到就明确提示
  （PySide6 没有 3.13 / 3.14 的安装包），不再让 `py -3` 拿到 3.14 后 pip 直接失败。
- 版本号统一到 0.9.3。

# 大肥鱼 v2

> 一个「类人脑」的桌面 AI：记忆、学习、语言、情绪四套系统，加一个跑在四者之上的认知循环
> （工作记忆、思维链、好奇心、元认知、仲裁、巩固、情绪调制、奖罚驱动、主动碎碎念）。
>
> 老大 = 用户。她叫大肥鱼，群里叫大肥鱼、大肥鱼。

---

## 0. 快速开始

### Windows（最省事）

1. 装 Python 3.10+（安装时勾 **Add Python to PATH**）：https://www.python.org/downloads/
2. 解压后**双击 `start.bat`** —— 它会自己建虚拟环境、装依赖、启动程序（不依赖 PowerShell）。
3. 第一次启动会弹「初次见面」窗口：填名字 / 性别 / 身高 / 性格，或者直接点「用默认设定开始」。
4. 要用模型：把 `config/llm.json` 里的 `providers.http` 填上你自己的 API（或改成 `offline` 先跑离线）。

### macOS / Linux

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

> `config/` 第一次运行会自动从 `config.default/` 复制一份，**不需要手动建**。

## 0.1 怎么跑起来（细节）

| 想做什么 | 命令 |
| --- | --- |
| 打开界面 | 双击桌面 **大肥鱼**，或 `pythonw run.py` |
| 只跑后台（不弹窗） | `python run.py --headless` |
| 装/修环境 | `powershell -ExecutionPolicy Bypass -File tools\install.ps1` |
| 只读体检 | `python tools\doctor.py` |
| 跑单元测试 | `python -m unittest discover -s tests -t .` |
| 跑三个演示 | `python demo\run_all.py` |
| 夜间批处理（计划任务用） | `python tools\nightly.py learn\|practice\|daily\|archive` |

运行环境：Python 3.10–3.12（PySide6 暂无 3.13 / 3.14 的包，用 `start.bat` 会自动挑 3.12），Windows。
依赖都装在 `~/.dafeiyu\.venv`。

---

## 0.2 已经有 QQ 接入？一键接管（不碰鱼的数据）

老用户几乎都已经有一套 QQ 接入了：`qq-bridge` 配 SnowLuma 或 NapCat，账号早登录好了、群也加好了。
以前换到/重装大肥鱼，要手工去 `config/app.json` 填 `bridge.dir` 和 `owner_qq`，填错一个字符她就
"哑巴"：能算、能记，但一句话发不出去；更糟的是有人因此重建 persona，把鱼养成了第二条。

现在有两条路，**都只写配置、先备份、可还原，不碰 db / 记忆 / 情绪 / 日记，也不会启动或停止桥接**：

**界面**：打开「QQ 接入」页 → 点「检测已接好的 QQ」→ 选中 → 「一键接管」。
首次启动向导里如果检测到本机已有 QQ 接入，会显示一个默认勾选的接管选项。

**命令行**：

```bash
python tools/adopt_qq.py --list                 # 看本机有哪些已接好的 QQ
python tools/adopt_qq.py --dry-run "D:\qq-bridge"  # 预检，不写盘
python tools/adopt_qq.py --adopt "D:\qq-bridge"    # 接管
python tools/adopt_qq.py --rollback             # 还原到接管前
```

接管时会：

1. 读桥接的 `config.json` / `state/console-token` / `state/social-v2.json`，认出当前账号、白名单、
   在线状态、情绪模式（`core` / `local`）与控制台端口；
2. 备份 `config/app.json` 到 `config/backup/app-<时间>.json`；
3. 把 `app.json` 的 `bridge` 段指过去（`dir`、`send_api`、`status_api`、`owner_qq`、`emotion_mode`）；
4. 写 `config/qq_config.json`（面板读的本地副本）；
5. 默认把 `ownerQQ` / `allow` **merge** 回桥接的 `config.json`（只改这两个字段，别的原样保留）；
6. 把接管记录写进 `state/qq-adopt.json`，随时可 `--rollback`。

桥接不是 SnowLuma 也没关系：OneBot v11 的实现都认（NapCat / Lagrange / LLOneBot / go-cqhttp）。
桥接侧的 `onebot` 配置段怎么写见 qq-bridge 仓库的 `docs/guides/MIGRATION.md`。

> 边界：检测只读；接管只写上面这 6 处配置。`db/`、`记忆系统/`、`state/emotion.json`、日记一字节不动。
> 桥接没在跑时也能接管配置，等你把桥接启动起来就生效。

---

## 1. 架构：SQLite 认知核 + 文件投影（双轨）

```
┌──────────────────────────── PySide6 桌面程序 (run.py) ────────────────────────────┐
│  形象区 / 可折叠侧栏 / 情绪面板 / 碎碎念 / 审计视图 / 聊天窗口                      │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                    │  只读库 + 调控制器
┌───────────────────────────────────▼───────────────────────────────────────────────┐
│  CognitionLoop.tick()  ← 唯一业务入口（界面开 20s / 后台 60s）                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐             │
│  │ 情绪核   │ 记忆核   │ 思维链   │ 好奇心   │ 元认知   │ 仲裁器   │             │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘             │
│         SQLite  db\dafeiyu.db   ← 唯一事实源（WAL，15 张表）                      │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                    │  单向投影（算完写回）
        ┌───────────────────────────┼────────────────────────────┐
        ▼                           ▼                            ▼
 记忆系统\2号长期记忆\*.md    记忆系统\瞬时记忆\*.jsonl    记忆系统\情绪阈值\状态.json
        └───────────────────────────┴────────────────────────────┘
                                    │  QQ 桥接读这三份（零改动）
                                    ▼
                        qq-bridge（SnowLuma / OneBot）
```

**为什么要双轨**：`~/.dafeiyu` 里原本跑着一套活体系统，QQ 桥接（`qq-bridge\src\bridge.js`）
硬编码读三份文件：2 号长期记忆 md、瞬时记忆 jsonl、情绪阈值状态 json。路径或格式一变，
群里那条鱼当场变哑巴。所以新核把「算」搬到 SQLite，算完再**逐字节兼容**地投影回这三份文件。

已实测：DB → md 投影保留全部条目、字段与先后顺序（与改造前文件逐行 diff，只多一个结尾
`---` 分隔符），重复投影 hash 不变（幂等）。并且加了**防呆**：DB 里某分类是 0 条、而磁盘文件
还有条目时，投影拒绝写入并记 `projection_skip` 审计（吃过一次 DB 被误清空、投影把线上 2 号记忆
覆盖成空壳的亏，这条闸不会再有第二次）。

### 分层

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 界面 | `ui/` | 只读库 + 调控制器，不写业务状态；面板每次打开都查库，不拿内存当唯一源 |
| 认知 | `core/cognition/` | `loop`（11 步）、`arbiter`、`curiosity`、`metacognition`、`chitchat`、`consolidate`、`scheduler`、`dialogue` |
| 领域 | `core/entity.py`、`core/emotion/`、`core/memory/`、`core/thought/`、`core/learning/`、`core/language/` | 实体 + 纯逻辑（衰减、打分、识别、压缩） |
| 基础设施 | `core/repo/`、`core/db.py`、`core/llm/`、`core/bridge/`、`core/api.py` | SQL 只出现在 repo；投影/推送/导入都在 bridge |

### 并发

- Qt 主线程：界面。`CognitionWorker`（APScheduler 线程池）跑 tick 与定时任务。
- SQLite 线程本地连接 + 一把写锁；写入串行，读不阻塞。
- `state\singleton.lock`（QLockFile）保证单实例，避免双写 DB 与契约文件。
- tick 有超时保护：单次超过 20s 记 `slow_tick`，不阻塞下一拍。

---

## 2. 各系统的触发规则（代码里的真值表）

### 2.1 记忆系统

| 层 | 规则 | 实现 |
| --- | --- | --- |
| **瞬时** | ≤6h 原文；6~18h 可降级为摘要；>18h **非日记**内容先蒸馏再清空正文 | `memory/instant.py` `sweep()` |
| **瞬时豁免** | 日记永不删；`salience≥0.7` / `status=open` / `strength≥0.4` 先蒸馏 | 同上 |
| **短期** | 每天日记；同一件事 ≥3 个不同日期出现 → 升级长期 | `memory/shortterm.py` `find_clusters/promote` |
| **短期压缩** | 未满 3 天的，与近 3 天内容合并（约 300 字）→ **150±20 字** → 2 号 | `compress_pending()` |
| **并行触发**（补强） | `salience≥0.8` / `open` 且等待≥3 天 / 被检索命中≥3 次 | `find_clusters()` 的 `parallel` |
| **1 号** | 性格 / 朋友 / 老大；涉及老大的反复事件同时沉淀进 1 号 | `promote()` |
| **2 号召回** | **概念命中 ≥2 个，或该情绪维度 ≥ 65**；否则不读 | `retrieval.lt2_recall()` |
| **遗忘** | `strength = s0·exp(−Δt/τ)`，τ 随 salience/open 增大；阈值 0.60/0.35/0.15 降级；level3 前必蒸馏 | `memory/forget.py`、`memory/distill.py` |
| **访问刷新** | 命中即 `strength≥0.9`、level 降一级、计数+1 | `repo/memory.touch()` |

### 2.2 语言 / 情绪记忆

| 项 | 语言记忆 | 情绪记忆 |
| --- | --- | --- |
| 单次上限 | 1000 字 | 2000 字 |
| 总量触发 | >6000 → 压到 6000±1000 | >6000 → 压到 6000±1000 |
| 冷却 | 压缩后 14 天不学 | 压缩后 14 天不学 |
| 到期 | 主动询问「要不要更新」，同意才解锁；「再等等」缓 7 天 | 同左 |
| 实现 | `language/memory.py`（两个 layer 共用一套账本） | 同左 |

### 2.3 学习 / 练习

| 时间 | 任务 | 入口 |
| --- | --- | --- |
| 每 20s / 60s | 认知循环一拍 | `scheduler.job_tick` |
| 每 10 分钟 | 衰减 + 降级 + 蒸馏 + 情绪回归 + 收桥接增量 + 投影 | `consolidate.periodic` |
| 00:00–01:00 | 定时联网学习（最多 2 条意图） | `learning_run` / `job_learning` |
| 00:00、01:00 | 学习窗口首尾各跑一次（同日只跑一遍） | `learning_run` / `learning_mid` |
| 01:10 | 批量巩固（3 天升级 + 150 字压缩 + 备份 + 冷存储清理 + 自我叙事） | `daily_consolidate` |
| 01:30–02:00 | 自我对话（3 批 ×100）→ 总结 ≤1000 字 → 语言记忆 | `self_dialogue_run` |
| 04:00 | 情绪快照按天归档 | `archive_daily` |
| 每 30 分钟 | 自主好奇心引擎（可配，见 `config/curiosity_engine.json`） | `curiosity_engine_tick` |
| 每 2 分钟 | 外发队列重试 | `job_outbox` |
| 每小时第 5 分 | 冷却到期 → 生成「要不要更新」询问 | `job_cooldown` |

> 以上时间**全部来自 `config/app.json → learning`**（`window_start` 00:00、`window_end` 01:00、
> `self_dialogue_offset_min` 30、`consolidate_min_after_end` 10、`archive_min_after_end` 180），
> 改配置即改时间，代码里没有写死的点。自动关机在 Windows 任务里，当前 **02:20**。

学习系统整体停摆条件：**语言与情绪两边都在冷却里**（用户既定规则）。
计划任务与界面调度共用 `meta.learn_done:<日期>` 标记，同一天不会跑两遍。

### 2.4 碎碎念

| 条件 | 行为 |
| --- | --- |
| 正面均值 ≥60 | 5~15 分钟随机一次 |
| 其他 | 15~40 分钟 |
| 负面均值 ≥60 | 静默，`muted_until = now+45min`，不主动 |
| 连续 3 次无回应 | 疲劳档 +1，间隔 ×1.5^档（上限 3 档），暂停 30 分钟，并记一次「被忽视」惩罚 |
| 老大回话 | 清零疲劳与连续计数 |

---

## 3. 情绪阈值与奖罚默认值

### 3.1 五维（`config\emotion.json`）

| 维度 | 初始 | baseline | 回归半衰期 | 说明 |
| --- | --- | --- | --- | --- |
| 愉悦 joy | 60 | 55 | 50 分钟 | 窜得快也掉得快 |
| 幸福 happiness | 55 | 50 | 20 小时 | 连着被在意才攒得起来 |
| 难过 sadness | 0 | 5 | 2.5 小时 | 被冷落、被伤害 |
| 自卑 inferiority | 0 | 5 | 36 小时 | 最慢（负面更难平复） |
| 害羞 shyness | 0 | 5 | 2 小时 | 快涨快退 |

- 取值区间 **[0,100]**：0 表示「没有这个情绪」（规格写 1-100 但明确要求初始为 0）。
- **阈值保护窗口 10 分钟**：某维首次越阈后 10 分钟内不做自然回归，只允许奖罚直接改写。
  否则「刚变活泼 3 秒就淡回去」，阈值行为等于没实现。
- 主导情绪 = `|值 − baseline|` 最大的那一维。

### 3.2 行为映射

| 条件 | 表现 |
| --- | --- |
| 正面均值 ≥60 | 活泼、话多、会开玩笑、主动碎碎念 |
| 负面均值 ≥60 | 可能不理人（65% 不回）、延迟 30s~10min、≤40 字、语气低沉 |
| 害羞 ≥70 且 好奇×100 > 害羞 | 害羞但话多（追问、结巴） |
| 害羞 ≥70 且 好奇×100 ≤ 害羞 | 害羞到话少（≤60 字、省略号、否认） |
| 尺度命中 | 结巴、躲闪、话少 |

### 3.3 奖罚 delta 表（`config\emotion.json → deltas`）

| trigger | 类型 | 愉悦 | 幸福 | 难过 | 自卑 | 害羞 |
| --- | --- | --- | --- | --- | --- | --- |
| praise 被夸 | reward | +8 | +5 | -3 | -3 | +2 |
| intimacy 亲密 | reward | +10 | +6 | -4 | -4 | +4 |
| request_met 要求被满足 | reward | +6 | +4 | -2 | -2 | +1 |
| cared 被在乎 | reward | +6 | +5 | -3 | -2 | +1 |
| ignored 被忽视 | punishment | -9 | -6 | +11 | +6 | 0 |
| request_denied 被拒 | punishment | -5 | -3 | +6 | +4 | 0 |
| insult 被辱骂 | punishment | -18 | -12 | +16 | +12 | 0 |
| abandoned 被抛弃 | punishment | -20 | -18 | +20 | +15 | 0 |
| scale 尺度 | 独立通道 | — | — | — | — | +20 / +35 / +45（按 1/2/3 级） |

- **RPE 递减**：`rpe_weight = max(0.2, 0.85^n)`，n = 近 2 小时同 trigger 次数。
- 强奖罚事件 ±5 分钟内编码的记忆 `salience += 0.3`（上限 1.0）。
- 奖罚事件写 `reward_event` 表 + `state\reward_log\<日期>.jsonl`，可审计。

---

## 4. 数据结构

全部是带显式字段的 dataclass（`core/entity.py`），不是文本堆叠：

| 实体 | 关键字段 |
| --- | --- |
| `MemoryItem` | id / layer / subtype / content / summary / skeleton / concepts / emotion_tag / salience / strength / level / status / refs / t_created / last_access / access_count / tombstone / origin / cluster / ext |
| `ThoughtNode` | id / chain_id / type（start…open_question…）/ content / summary / skeleton / concepts / task_ref / salience / confidence / status / refs / strength / level |
| `LearningIntent` | id / target / gap_type / curiosity_score / expected_learnability / source / context / proposed_query / status / result_ref / attempts |
| `EmotionVector` | values（五维）/ baseline / dominant / updated_at |
| `RewardEvent` | id / type / trigger / source_text / delta / rpe_weight / t |
| `ChitchatState` | last_chitchat_at / consecutive_no_reply / next_due_at / muted_until / enabled / fatigue_level / total_sent |
| `CuriosityWeights` | domain_weights / fatigue / last_explored / budget / feedback / web_log |
| `CooldownState` | language{…} / emotion{…} |
| `WorkingSlot` | idx / kind（memory\|thought\|percept\|task）/ ref_id（指针）/ weight / pinned / inhibit |
| `KnowledgeItem` | id / name / domain / concepts / content / slots{应有,已填} / filled_ratio / uncertainty / confidence |
| `Evidence` | kind（failure\|refusal\|simulated\|contradiction）/ target / detail / uncertainty |
| `AuditEvent` | entity_kind / entity_id / action / detail / t |

库表见 `core/schema.sql`（15 张：memory_item、thought_node、graph_edge、inverted_index、
embedding、learning_intent、knowledge_item、evidence、emotion_snapshot、reward_event、
chitchat_log、dialogue_message、audit_event、consolidation_run、schema_migration）。

---

## 5. 认知循环（唯一业务入口）

`core/cognition/loop.py::tick()`：

1. 采集上下文（对话 / 任务 / 空闲）
2. 更新工作记忆槽（指针 + Hebbian 衰减，9 槽）
3. 情绪回归（保护窗口、主导重算）
4. 缺口检测 + 五信号好奇 → `LearningIntent` 入队
5. 可学习性过滤（太泛/太私人的缺口直接丢）
6. 仲裁：`价值 × 紧迫性 × 预期收益 − 中断成本`，各类型有并发上限
7. 思考/对话 → 生成 `ThoughtNode`，未决进 open 池
8. 学习 → 联网检索 → 解析 → 技能入库 → 关闭 open 节点 → 回写好奇权重
9. 碎碎念 → 频率/疲劳/静默检查 → 生成 → 推送 → 更新 `ChitchatState`
10. 遗忘/巩固 → 衰减 + 蒸馏（到点才做）
11. 情绪 + 投影落盘

工作记忆容量 9（7±2），槽里只放**指针**，临时绑定用 Hebbian 权重（同拍共同激活 +0.15，每拍 ×0.92）。

---

## 6. 怎么改配置

| 想改 | 改哪个 |
| --- | --- |
| LLM 用哪个后端 | `config\llm.json` → `default` / `tasks` |
| API Key / base_url | `config\llm.json` → `providers.http`（或环境变量 `DEEPSEEK_API_KEY`） |
| dsh 命令行路径 | `config\llm.json` → `providers.dsh.cmd` |
| 人格（1 号性格） | `config\personality.md`（缺失时用内置兜底） |
| 五维初始值 / baseline / 半衰期 / 阈值 / 奖罚 delta | `config\emotion.json` |
| 6h / 18h / 3 天 / 150 字 / 两周 / 300 句 / 频率 | `config\thresholds.json` |
| 桥接路径、owner QQ、核心 API 端口 | `config\app.json → bridge` |
| 界面尺寸 | `config\app.json → window` |

**LLM Provider 三选一**

1. `dsh`（默认）：本机 DeepSeek Harness 命令行，带联网，学习靠它。
2. `http`：任何 OpenAI 兼容接口。填 `base_url` / `api_key` / `model` 即可。
3. `offline`：不调用模型，全部走模板/机械压缩（断电也能跑，质量下降）。

`tasks` 可以按任务单独指定，例如让「判定」走 offline 省钱、让「学习」走 dsh：

```json
{ "default": "dsh", "tasks": { "judge": "offline", "learning": "dsh" } }
```

单次调用失败会自动降级（学习降级为本地整理；压缩降级为机械压缩），并在 `evidence` 表留证。

---

## 7. 怎么审计闭环

三道口子，全在界面右侧「审计视图」：

1. **一条记忆的一生**：下拉选任意记忆 → 时间线显示 创建 / 被检索命中 / 降级 / 蒸馏 / 清空立墓碑，
   以及蒸馏产出的结论、未决意图、教训 id。
2. **最近的系统动作**：`audit_event` 全量倒序（tick 的每一步、奖罚、碎碎念、学习都记）。
3. **情绪快照**：任意时刻的五维向量与主导情绪（`emotion_snapshot` 表 + `state\emotion.json`）。

命令行等价物：

```bash
python tools\doctor.py                                  # 全局只读体检
python -m unittest discover -s tests -t .               # 规则回归
python demo\run_all.py                                  # 三个闭环演示（跑在 demo\_sandbox）
```

验收闭环 12 条与实现的对应关系见 `docs\01-架构设计与数据结构.md` 第 20 节。

---

## 8. 规格冲突的取舍（必须记录）

| # | 冲突 | 取舍 | 理由 |
| --- | --- | --- | --- |
| 1 | §2 说学习 3–4 点，§5.2 说 12–1 点 | **00:00–01:00**，3–4 点改巩固窗口 | 用户既定规则优先 |
| 2 | §2 说自我对话 4–4:30，§5.3 说 1–1:30 | **01:00–01:30** | 同上，且「学习结束后半小时」自洽 |
| 3 | 旧系统 23:00 夜间流程 | 23:00 只写日记（由旧任务保留）；学习挪到 00:00 | 不破坏老大作息观感 |
| 4 | 旧 01:00 自动关机撞练习窗口 | **改到 01:40**（关机提醒 01:30） | 否则练习每天被腰斩 |
| 5 | 瞬时窗口 24/30/36h vs 6/18h | **6/18h** | 用户既定规则 |
| 6 | 情绪初始 60/55 vs 现值 70/66 | 默认按规格；迁移时保留现值 | 不让老大觉得鱼突然变了 |
| 7 | 「1-100」vs 初始 0 | 区间 **[0,100]** | 规格明确要求负面/其他初始 0 |
| 8 | 目录英文 vs 现有中文 | 英文规范目录 + 中文兼容投影 | 桥接硬路径不能动 |
| 9 | 300 句要在 30 分钟内 | 3 批 ×100，超窗顺延并记录 | 不砍轮数 |
| 10 | 150 字：单条 vs 与近 3 天一起 | 3 天窗口合并后压缩 | 规格原话「一起总结压缩」 |
| 11 | PySide6 vs 旧 Web 界面 | PySide6 主界面；旧 Web 保留只读回退 | 规格第七章 |
| 12 | 心跳 20s vs 每分钟 | 界面开 20s，后台 60s | 省电与响应折中 |

---

## 9. 目录

```
~/.dafeiyu\
├─ run.py                桌面入口
├─ config\               配置（app/emotion/thresholds/llm/personality）
├─ core\                 认知核
├─ db\                   dafeiyu.db + backup\
├─ memory\               记忆（instant/short_term/long_term_1/long_term_2/language/emotion/thought_chain）
├─ learning\             intents\ + reports\
├─ state\                emotion/curiosity/cooldown/chitchat/working_memory/outbox/reward_log
├─ logs\                 按天滚动（含 llm_usage.jsonl 花销）
├─ ui\                   界面 + assets（立绘，可放 states\ 覆盖）
├─ tests\ demo\ tools\ docs\
├─ 记忆系统\ 学习系统\ 语言系统\ 情绪系统\ 运行\ 应用\   ← 旧目录：兼容投影区 / 迁移源 / 只读回退
└─ _backup\              改造前的数据快照
```

---

## 12. 补丁 v3：迁移保护 + 视觉增强 + 拒绝权

> 2026-10-28 晚增量上线。全程只加不删：现有 570+ 条记忆、五维情绪、冷却、思维链结构一个没动。

### 12.1 迁移（先做的第一件事）

```powershell
python tools\scan_v3.py                 # 只读扫描：schema / 行数 / state 字段 / 目录体量
python tools\migrate_v3.py --dry-run    # 只看要执行什么
python tools\migrate_v3.py              # 真跑（自动备份 + 行数守卫）
```

- 只做三件事：建 2 张新表（`vision_asset`、`refusal_decision`）、给 `memory_item` 补 1 列
  `vision_tiles`、把 `schema_version` 推到 3。**不 DROP、不 DELETE、不重建、不重算历史记忆。**
- 迁移前自动备份：`db\backup\dafeiyu-v3-<时间戳>.db` + `state\backup\<时间戳>\*.json`。
- 迁移前后各数一次行数，**任何表变少就还原备份并退出 1**。
- 幂等：重复执行返回「已经是最新的 v3，无需改动」；`db.init_db()` 也是只建缺的表 / 只补缺的列。
- 报告落在 `db\backup\migrate-v3-<时间戳>.txt`。

### 12.2 视觉增强

**切块预处理**（`core/vision/preprocessor.py`）：视觉模型会把图压到 ~800×800，大图细节全丢，
所以先切块再逐块识别，最后按坐标拼回来。

| 配置（`config\vision.json`） | 默认 | 说明 |
| --- | --- | --- |
| tile | 800 | 切块边长 |
| overlap | 40 | 重叠像素（避免切在字中间） |
| max_tiles | 64 | 超过就等距抽样并标 `sampled` |
| small_skip | 800 | 最长边 ≤ 800 不切，单块整图 |
| max_tiles_per_call | 8 | 一次模型调用看几张 |
| work_dir | `memory\instant\vision` | 切块文件落盘处 |

- 4000×3000 → 6×4 = 24 块（实测）；9000×9000 这种超过 Qt 解码上限的，先按比例缩小再读。
- 每块带坐标与标签（`左上(1/4-1/6)`），聚合时按 `(row, col)` 排序拼成结构化答案。
- 识别走 `dsh headless`：把切块路径写进 prompt，让 agent 用它自带的看图工具逐张看，回 JSON。
  实测能读图（24 块里认出 16 块，coverage 0.667）。
- 资产落 `vision_asset` 表；记忆条目只挂一个指针列 `vision_tiles`（JSON：asset_id/切块清单/摘要）。
  **老条目保持 NULL，不回填。**
- 识别里出现「看不清/不确定」→ 生成思维链 `open_question` 节点，并喂好奇心评估器。

**自主浏览**（`core/learning/browse.py`）：Playwright + **系统 Edge**（不下载 Chromium，实测可用）。

```python
from core.learning import browse
browse.WebVisionTool().browse_and_screenshot("https://example.com")   # → {ok, path, title}
browse.WebVisionTool().extract_images_from_page(url, max_count=5)      # → {ok, images:[...]}
browse.explore(url, question="")                                       # 截图+抽图 → 视觉流水线 → 摘要
```

- 单次学习会话最多 20 次（`session_limit`）；域名黑白名单（默认拦登录/支付/邮箱）。
- 截图归档 `learning\vision_snapshots\<日期>\`；超 30 天只删图片，摘要与概念留在 `vision_asset`。
- 配了 `config\vision.json → study_urls` 时，00:05 那次学习会让第一条意图先去看一眼网页
  （截图 → 切块 → 识别 → 摘要进学习 prompt）。留空则不浏览。

### 12.3 拒绝权

**位置**：响应策略层之后、真正输出之前（`core/refusal/arbiter.py::RefusalArbiter.decide`）。

五种处置：`ACCEPT` / `REFUSE` / `NEGOTIATE` / `DEFLECT` / `RELUCTANT_ACCEPT`。

六路信号加权（`core/refusal/signals.py`）：

| 信号 | 看什么 |
| --- | --- |
| emotion | 难过/自卑均值越高越不想接 |
| will | 跟性格冲突（要她骗人、骂人、报复） |
| competence | 元认知：不会/不确定 → 倾向协商或转移 |
| boundary | 隐私、安全、被强迫（这一路最重） |
| fatigue | 刚拒过、被反复施压、碎碎念没人理 |
| relationship | 被尊重更愿意，被辱骂更硬 |

默认值（`config\refusal.json`）：

| 项 | 默认 | 含义 |
| --- | --- | --- |
| threshold | 0.62 | 拒绝阈值 |
| negotiate_band | 0.10 | 阈值上方 0.10 内先协商 |
| refuse_per_hour | 3 | 每小时 REFUSE/DEFLECT 上限，超了自动降级为协商 |
| tsundere_per_hour | 2 | 傲娇上限 |
| tsundere_level | 0.4 | 傲娇程度（0 关闭） |
| repair_after | 3 | 连拒 3 次后下一次强制软化 |
| allow_deflect | true | 是否允许「先不接这个话」 |
| blacklist | 自杀/自残/救命/报警/删库… | 命中一律 ACCEPT 并给安全替代，**永不拒绝** |
| boundary_keywords | 密码/身份证/银行卡/脱衣服… | 越界词 |

- 傲娇只在「害羞 ≥70 + 正面 ≥45 + 请求属于亲密类」时出现，并且**执行结果真实完成**
  （拒绝仲裁给 `RELUCTANT_ACCEPT`，正常生成回复，只是在前面加一句别扭话）。
- 用户后续反应会回填并联动奖罚：尊重拒绝 → 记一次「被在乎」（正面上升）；
  继续施压 → 「被忽视」；辱骂 → 「被辱骂」。
- 因能力不足而 DEFLECT 时，自动生成 `LearningIntent(gap_type=skill_failure)`，学完可回访。
- 每次决策写 `refusal_decision` 表 + `state\refusal_log\<日期>.jsonl` + 一条思维链 `decision` 节点，
  含六信号打分、阈值、决策、理由——界面「拒绝权」面板可按时间追溯。

**接口**（本机 18766）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/refusal/decide` `{text}` | 判定接/拒/商量/转移/傲娇（QQ 桥接用的就是这个） |
| POST | `/api/refusal/react` `{id, reaction}` | 回填用户反应（accept/insist/ignore/praise/insult） |
| GET | `/api/status` | 含 `refusal` 状态（阈值、预算用量、连拒数） |

**QQ 也接上了**：桥接在收到老大私聊后、唤醒 agent 之前先问核心；被拒就直接把理由发出去、
不再唤醒（省一次模型调用，也避免「嘴上拒绝、身体照做」）。核心不可用时 fail-open 照常处理。

### 12.4 新增的目录与配置

```
config\vision.json   config\refusal.json
db\backup\           (v3 迁移备份与报告)
learning\vision_snapshots\<日期>\   截图归档
state\refusal.json   state\refusal_log\   state\vision_session.json   state\backup\
memory\instant\vision\              切块文件
```

### 12.5 测试

```powershell
python -m unittest discover -s tests -t .     # 83 个用例全绿
```

v3 新增覆盖：切块路由（大图切/小图不切/抽样/标签唯一/坐标聚合）、
视觉资产落库与指针回填、识别 JSON 解析（容错代码围栏与越界 index）、
拒绝六信号打分、阈值、预算降级、傲娇上限、黑名单强制接受、关系修复、
决策落库与反应联动、迁移幂等与旧行不丢。

---

## 13. 补丁 v4：跨会话思维链残留通道

> 解决的问题：**「上一分钟还在想的事，新会话里就看不见了」**。`schema_version 3 → 4`。

### 13.1 真实根因（比补丁原来的诊断更靠里）

补丁说「检索器只认当前链」——在这套代码里**不成立**：`retrieval.recall()` 是全库倒排 + 图邻居，没有
chain 过滤。实测出来的真问题是三个：

| # | 真问题 | 证据 |
| --- | --- | --- |
| 1 | 核心从没存过 QQ 对话 | `dialogue_message=0`；`thought_node` 13 条全是拒绝决策 |
| 2 | 每条消息开一条新链 | 13 条节点 = 13 条链；`chain_for("refusal-日期")` 连调两次返回不同 id（写入用 `task_ref="refusal"`，查询传 `refusal-<日期>`，永远对不上） |
| 3 | 「近 3 小时」是假的 | `'2026-10-28T18:00:00' >= datetime('now','-3 hours')` 返回 1：ISO 的 `T`(0x54) > 空格(0x20)，今天的全算在窗口内 |

所以 v4 = 残留通道（补丁正文）+ 两块前置（回合节点、会话边界）。只做残留通道的话，池子里
只有「请求：…→ACCEPT」，等于没修。

### 13.2 迁移（三列 + 一张表）

```powershell
python tools\scan_v4.py                 # 只读扫描
python tools\migrate_v4.py --dry-run
python tools\migrate_v4.py
```

```sql
ALTER TABLE thought_node ADD COLUMN last_active_at TEXT;
ALTER TABLE thought_node ADD COLUMN in_residual INTEGER DEFAULT 0;
ALTER TABLE thought_node ADD COLUMN session_tag TEXT;
CREATE TABLE IF NOT EXISTS residual_index (
  node_id TEXT PRIMARY KEY, chain_id TEXT, session_tag TEXT,
  last_active_at TEXT, closed_at TEXT, in_residual INTEGER
);
```

实测 `thought_node 13 → 13`、其余表全部 +0；报告 `db\backup\migrate-v4-<时间戳>.txt`，
回滚点 `db\backup\dafeiyu-v4-<时间戳>.db`。

### 13.3 曲线与档位

```
R(t) = w_f·exp(-t/τ_f) + (1-w_f)·exp(-t/τ_s)
τ_f = tau_fast × (1 + 0.5·salience) × (1 + 0.8·is_open)     τ_s 同
```

| 距上次活动 | R（salience=0、已想完） | 档位 | 注入 |
| --- | --- | --- | --- |
| 5 分钟 | 0.67 | 0 原文 | 原文 |
| 15 分钟 | 0.37 | 1 摘要 | 摘要 |
| 30 分钟 | 0.22 | 1 摘要 | 摘要 |
| 60 分钟 | 0.12 | 2 骨架 | 骨架 + 概念 |
| 120 分钟 | 0.04 | — | 不进池 |
| 180 分钟 | 0.01 | — | 不进池 |

- 实际粒度 = `max(节点原 level, 档位 level)`；墓碑（level=3）只给概念与结论，**不复活正文**。
- `open` / `open_question`：τ ×1.8、排序 ×1.5 —— 没想完的先回到意识。
- 情绪一致（dominant 与 emotion_tag 同维）R ×1.1，只影响顺序。

### 13.4 会话边界

| 场景 | 空闲多久算断 |
| --- | --- |
| QQ（`private:` / `group:`） | **15 分钟** |
| 桌面聊天 | **3 分钟** |

断开时把该会话所有节点写 `last_active_at / in_residual=1 / session_tag`，索引进 `residual_index`
（不复制正文）。同一会话内所有回合**共用一条链**。每 10 分钟扫一次：R < 0.08 移出池（节点不删），
池上限 200，超了淘汰 R 最低的。

### 13.5 冷启动注入

- 新会话第一条消息触发，**每个会话只注一次**（`state\residual_state.json`，留最近 50 个会话）。
- top-6，同链最多 3 个；被注入即算一次 access（`last_active_at` 归零、salience +0.05）。
- 注入格式：

```
【残留思维（会话断开后还记得的）】
[残留思维 | 约8分钟前 | 原文]
- 内容：老大说：我在想边界感这件事 / 我当时回：…
- 未决：还没想完
- 关联概念：边界感、怕被
（这些是我自己刚才还在想的东西，自然相关就提一句，别硬提，也别报时间数字。）
```

### 13.6 参数（`config\residual.json`）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| enabled | true | 总开关 |
| w_fast / tau_fast_min / tau_slow_min | 0.65 / 8 / 55 | 曲线形状 |
| salience_boost / open_boost | 0.5 / 0.8 | 对 τ 的放大 |
| level0/1/2_threshold | 0.50 / 0.22 / 0.08 | 档位边界 |
| cold_start_topk / per_chain_cap | 6 / 3 | 注入条数与单链上限 |
| pool_capacity | 200 | 池容量 |
| idle_timeout_min | qq 15 / desktop 3 | 会话边界 |
| mood_bonus / touch_salience_gain | 0.1 / 0.05 | 情绪加成、复述增益 |

**调参**：忘太快 → 调大 `tau_slow_min`；老翻旧账 → 调小 `cold_start_topk` 或调大 `level2_threshold`；
老提同一件事 → 调小 `per_chain_cap`。

### 13.7 接入点（只加调用，不改主干）

| 文件 | 改了什么 |
| --- | --- |
| `core/thought/session.py`（新） | 会话边界、同会话复用链、断开写残留索引 |
| `core/thought/residual.py`（新） | 曲线、档位、池、冷启动、访问刷新 |
| `core/thought/turn.py`（新） | 每轮落 `step` + `reflection` |
| `core/cognition/dialogue.py` | 开头 `session.touch` + 冷启动注入；结尾 `turn.record_turn` |
| `core/memory/retrieval.py` | 命中思维链时多一次 `residual.touch`（不改排序） |
| `core/cognition/consolidate.py` | 每 10 分钟 `residual.sweep()` |
| `core/repo/thought.py` | 修 `recent()` 时间窗；`_WRITABLE` 放行三个新列 |
| `core/api.py` | `/api/thought/turn`、`/api/thought/residual`、`/api/thought/session` |
| `qq-bridge/src/bridge.js` | 每轮回复发完后回传 `{conv, user_text, reply_text}`（失败不影响 QQ） |
| `ui/panels/residual.py`（新） | 记忆系统 → **思维链 · 最近想法** |

### 13.8 测试

```powershell
python -m unittest discover -s tests -t .     # 103 个用例全绿
```

v4 新增 20 个：曲线参考值对表、open/salience 放大、档位边界、`max(level, tier)`、墓碑不复活、
会话复用链、idle 断会话、QQ 比桌面长、断开入池、池排序与清理、容量淘汰、冷启动 top-k、
per-chain 上限、同会话只注一次、访问刷新、注入写工作记忆、迁移幂等、新列/新表、老节点不被碰。

---

## 14. 补丁 v5：动态表情识别 + 费用归因

> 两件事：**让动图不再只看第一帧**、**花费能按功能拆开看**。`schema_version 4 → 5`。

### 14.1 先纠正补丁的两个前提

| 补丁说 | 实际 |
| --- | --- |
| 「DSH 把 GIF 归一化成单帧，所以模型只看第一帧」 | 桥接 `media-normalize.js` 早就自研了 GIF 解码 + 6 帧拼图（`gifFrames:6`），这条路已经绕开了单帧。真正的问题是**她不主动调用看图工具**，不调就只看到「[动画表情]」 |
| 「必须装 dsh-sticker-dict / dsh-read-animation」 | 本机 DSH 只装了 `qq-agent-presets`、`qq-mode-console`，这两个插件不可用也没必要：抽帧用 QImage 自己做，零新依赖 |
| 「语音调用花费要单列」 | `~/.dafeiyu语音` 是 **VoxCPM 本地模型**，TTS 不产生模型费用；语音卡片保留但标注口径 |

### 14.2 迁移（一列两张表）

```powershell
python tools\scan_v4.py            # 结构还是同一套
python tools\migrate_v5.py --dry-run
python tools\migrate_v5.py
```

```sql
ALTER TABLE memory_item ADD COLUMN animation_meta TEXT DEFAULT NULL;
CREATE TABLE IF NOT EXISTS cost_event (...);      -- 每次模型调用一条
CREATE TABLE IF NOT EXISTS sticker_cache (...);   -- sha256 → 上次识别结论
```

实测：`memory_item 646 → 662`、`thought_node 13 → 25`（v4 回合节点真的在长）、
`cost_event` 导入 51 条引擎账本 + 1539 条桥接账本，其余表 +0。
报告 `db\backup\migrate-v5-<时间戳>.txt`，还原点 `db\backup\dafeiyu-v5-*.db`。

> ⚠️ **如实记录**：v5 的 DDL 是在开发过程中被 `db.init_db()` 幂等应用上去的，那一步没跑
> `migrate_v5.py`，所以**没有生成预迁移备份**。v5 只加了一列和两张空表、没有任何 UPDATE/DELETE，
> v4 结尾的 `dafeiyu-v4-20261028-231736.db` 就是完整的 v5 前还原点。事后补了一份 v5 备份与报告。

### 14.3 动图：抽帧 → 缓存 → 识别

```
GIF/WebP/APNG ──► AnimatedDecoder（顺序 read 逐帧）
                    ├─ 均匀抽 N 帧（默认 5，3~10 可配），每帧存 jpg
                    ├─ 有 Qt 应用 → 再拼一张带帧号/时间戳的标注图
                    └─ 无 Qt 应用（headless）→ 不拼图，逐帧交给看图链路
                          │
                          ├─ sticker_cache 命中（sha256）→ 直接复用上次结论，0 花费
                          └─ 未命中 → 逐帧识别 → 一句整段总结 + 动作/情绪标签 → 写缓存
```

- **坑**：Qt 的 GIF 解码器不支持 `jumpToImage()`（返回 False），只能顺序 `read()` 推进；
  代码里改成"读完再挑帧"，否则拿到 0 帧。
- 识别结果写 `memory_item.animation_meta`（帧数/时长/帧号/sha256/缓存命中），
  concepts 写「动态表情 / 动作标签」；命中缓存时 `vision_animation` 花费为 0。
- 表情带情绪色彩（大笑/哭/害羞…）只给 `EmotionVector` ±2 的轻微波动，不当强奖罚事件。
- 人工批注：`AnimatedDecoder().annotate(sha256, "这是老大常用的「好耶」")` 写进 `sticker_cache.note`。

**桥接侧**（要重启一次）：收到带图消息时后台调 `/api/vision/analyze` 预取一句描述，
下次同一个 `messageRef` 出现在上下文块里就会带上「【图片内容·已自动识别】…」。
注意这是**异步**的：识别要几十秒，所以本轮回复大概率还没拿到，效果体现在后续轮次与上下文里；
要"当轮就看到"，只能靠她调用 `qq_get_message_images`（桥接已经会把 GIF 抽成 6 帧）。

### 14.4 费用归因

**打标**：`provider.run(..., feature_tag=...)`，枚举与映射：

| feature_tag | 来源 task | 中文 |
| --- | --- | --- |
| chat | dialogue | 普通消息 |
| chitchat | chitchat | 碎碎念 |
| learning | learning | 学习 |
| self_dialogue | self_dialogue | 自我对话 |
| memory_compress | compress / summary / diary | 记忆压缩 |
| vision_static / vision_animation / vision_browse | vision（三条链路） | 看图·静态/动图/浏览 |
| voice | voice | 语音（本地合成，模型费用 0） |
| other | refusal 等 | 未分类 |

不传就按 task 自动映射；映射不到记 `other` 并写一条 `untagged_call` 审计。

**记账**：每次调用落一条 `cost_event`：
`estimated_cost`（调用前按字数 + 该功能历史输出长度估）与 `actual_cost`（用真实 usage 按调用时刻峰谷价回算）
**分开存，不互相冒充**；估不出来的记 0 并在视图里标「无预估」。

**历史不回填**：迁移时把两个 jsonl 账本导入 `cost_event`；引擎侧能按 task 归因，桥接侧没有标签 →
一律 `other`，面板单列「未分类历史 N 条」，不猜。

**视图**（侧栏「花费」面板下半部分）：

- 专项卡片：语音 / 看图（静态·动图·浏览分列）/ 碎碎念 / 普通消息
- 按功能表：次数、总花费、**均实际 / 均预估 / 偏差%**、占比；偏差 >20% 黄、>50% 红
- 每日花费（最近 12 天）
- 一键导出 CSV → `state\cost_export.csv`

### 14.5 配置

| 文件 | 关键项 |
| --- | --- |
| `config\animation.json` | `enabled`、`max_frames`(5)、`frame_cell_px`(140)、`use_sticker_dict_cache`、`inbox_dir` |
| `config\cost_tracking.json` | `enabled`、`estimate_warn_threshold`(0.2)、`estimate_fail_threshold`(0.5)、各功能预估输出 token |
| `config\pricing.override.json` | 价表覆盖（`cache_hit`/`cache_miss`/`cache_write`/`output`/`peak_multiplier`），null 表示用默认 |

### 14.6 测试

```powershell
python -m unittest discover -s tests -t .     # 122 个用例全绿
```

v5 新增 18 个：动图路由（GIF 识别/静态图不误判）、抽帧数量与时间戳、帧数上限抽样、
缓存命中与 hits 递增、第二次走缓存不再调模型、人工批注、feature_tag 映射、
预估/实际/偏差分级、无预估不冒充、按天与区间聚合、CSV 导出、明细筛选、
账本导入幂等、迁移幂等与新列/新表。

---

## 15. 已知边界（别误会）

- **瞬时记忆的事实源**是 QQ 桥接的 `recentMessages`（每会话最近 100 条）。更早的桥接就不留了，
  新核也捞不到；日记原文仍是长期底稿。
- **2 号检索**是「概念命中 OR 情绪≥阈值」的精确门控，不是模糊语义搜索：宁可不翻，不乱翻。
- **嵌入检索**默认是中文 bigram 余弦（TF-IDF 兜底）。装 `sentence-transformers` 后可把
  `config\app.json → embedder.backend` 切成 `local_st`，接口不变；默认不装（torch 2GB+）。
- **投影文件是只写目标**：手改 `记忆系统\2号长期记忆\*.md` 会在下次投影被覆盖。要改记忆请改界面/DB。
- **旧 Web 界面**（`http://127.0.0.1:18765`）保留为只读回退，不再承担调度与写入。
- **测试与演示**跑在临时目录 / `demo\_sandbox`，`tests\base.py` 有硬闸：一旦指向真实目录就拒绝运行。

---

## 16. 出问题先看这里

| 现象 | 先查 |
| --- | --- |
| 点图标没反应 | `logs\<日期>.log`；再 `python run.py` 看报错 |
| 界面白屏/报错 | 同上；`state\singleton.lock` 可能残留，删掉重开 |
| 她不理人 | 可能真的在「负面高」策略里：看情绪面板的「回不回」与原因 |
| 不碎碎念 | 看碎碎念面板：开关 / 静默到 / 疲劳档 / 推送通道 |
| 碎碎念没发到 QQ | 面板里「推送通道」；失败会落 `state\outbox\`，每 2 分钟重试。桥接要过两道闸：`x-console-token`（`qq-bridge\state\console-token`）+ `x-agent-token`（`state\social-v2.json` 里该会话的 `agentToken`），两个都得在，缺一个就是 401/403 |
| 学习一直失败 | `logs\llm_usage.jsonl`、`learning\reports\`；多半是 dsh 路径不对 |
| 2号不翻旧事 | 设计如此：看情绪面板最下面那排「✓」是否够阈值 |
| 桥接那边情绪不对 | `config\app.json → bridge.emotion_mode`（`local` 时由桥接自己算，`core` 时由核心接管） |

---

## 5. 花费（2026-10-28 补回）

重构时这块丢了，现在补成三处：

| 在哪 | 看到什么 |
| --- | --- |
| 界面侧栏「花费」 | 今日私聊／群聊／后台／合计、昨天、本月、累计；夜学最近一次与今晚预估；今天后台各任务在花什么；群额度 |
| python tools\\cost.py | 同样的报表打到控制台；--write 只刷新缓存；--json 出结构化数据 |
| QQ 私聊（只对老大） | 每次唤醒提示里带【你们今天的开销】块，她答得出"今天花了多少"，不会瞎编 |

数据来源（只读，不改任何账本）：

- **QQ 聊天**：qq-bridge/state/token-usage.jsonl（桥接每次 API 请求的真实 usage，按 session+turn 归并成"轮"）
- **后台模型调用**：logs/llm_usage.jsonl（v2 自己的调用）+ 运行\\用量.jsonl（旧引擎历史，任务名归一）
- **额度**：qq-bridge/state/budget-view.json

价格口径与 core/llm/provider.py 一致：未命中 ¥1/M、命中 ¥0.02/M、输出 ¥4/M，工作日 9–12 / 14–18 高峰 ×2。

缓存 state/cost.txt（桥接读的就是它）由三处刷新：侧栏打开时、认知循环每 10 分钟、计划任务 大肥鱼-花费刷新 每 10 分钟（界面没开也不会过期）。

另外修了一个账本 bug：原来 provider.run() 把**任务名硬写成 "dsh"**，学习/自我对话/压缩的花费全混在一起；
现在按真实 task 记账（learning / self_dialogue / compress / dialogue / chitchat / ision），
"每轮学习实际花费"才有意义。


## 17. 补丁 v12：灵魂锚点 + 能力自检 + 迁移底座

> 总纲（6 个模块）的 P0 底座，纯加法，不动任何现有数据。`schema_version 5 → 12`。

### 17.1 灵魂锚点（`core_ethos.py`，禁止删除）

```python
SOUL_ANCHOR = "大肥鱼爱着每一个人类，每一个用户也都爱着大肥鱼。"
MISSION     = "补全人类的情感空缺，帮助压抑的人成为情感完善的人类。"
```

- 双副本互校：明文常量 + base64 内置副本，两份不一致或 SHA256 对不上 → 判为篡改；
- 篡改时：**回退到内置副本**（对外仍返回可信锚点）+ 写 `state/soul_alert.json` + 审计 `ethos/tampered`；
- 每次 LLM 调用在 `provider.run()` 里统一注入 `[核心灵魂设定]`，幂等（重复注入只保留一份）；
- 启动日志第一行永久展示锚点。

### 17.2 能力自检（`core/selfcheck.py` → `state/capabilities.json`）

启动时摸一遍：`ffmpeg`（PATH → 程序目录 → imageio-ffmpeg）、`Pillow`、`Playwright`、`dsh`、`QImage`、SQLite。
日志里出摘要：`自检：动图✓ 静态看图✓ 自主浏览✓ 模型✓｜ffmpeg ✗（不需要）`。

> 本机实测：ffmpeg 不在 PATH、Pillow 未安装，但**动图不需要它们**——QImage 顺序抽帧已经够用。

### 17.3 迁移（两张空表）

```
pending_topic   未完成话题（会话断开时标记，冷启动优先注入；72h 未提及降级）
ethos_audit     灵魂锚点报警记录
```

```powershell
python tools\migrate_v12.py --dry-run
python tools\migrate_v12.py      # 自动备份 db + state + config，行数变少即回滚
```

实测 `memory_item 1043 → 1043`、`thought_node 49 → 49`，全部 +0。
另外给 `migrate_v4.py` / `migrate_v5.py` 加了**单向守卫**：在高版本库上跑旧脚本不会把 `schema_version` 改回去。

### 17.4 尚未实现（总纲的其余部分）

见 `docs\06-v12总纲落地计划.md` 的差距矩阵，按 P1→P4 分批。四处需要拍板的冲突也在那份文档里。

## 18. v13 / v14：自主好奇心、费用开关、冷存储回忆；以及 P2 剩下的四块

### 18.1 自主好奇心引擎（v13）

`core/curiosity_engine.py` + `config/curiosity_engine.json` + `state/curiosity_engine.json`

- 每 30 分钟（可配）扫一遍领域，算紧迫度：
  `urgency = 0.4×缺口 + 0.3×进步率 + 0.2×新颖 − 0.3×无聊`，超过阈值（0.5）才挑一个学；
- 领域从「学习意图 / 长期记忆概念」里提，只收 3~8 字、无标点的词（碎片 bigram 不进）；
- 学完回写：`record_outcome()` 更新 last_error / progress / 探索次数 / 上次时间；
- 对话里发现缺口 → `bump_gap()` 抬高对应领域，后台下一轮就会优先它；
- 受三道闸：总开关、自动执行开关、单日花费上限（下面 18.2）；
- 界面：学习系统 → 好奇心引擎（领域仪表盘 + 三个开关 + 立刻跑一轮）。

### 18.2 好奇心费用与开关（v14 之一）

- 新标签 `curiosity_autonomous`（显示「自主好奇心学习」）；对话学习仍是 `learning`；
- `curiosity_engine.json` 里三个开关：`enabled` / `auto_learn` / `budget_limit_per_day`（0=不限）；
- 关掉 auto_learn：引擎照常排队，但 `executor` 拒绝执行，意图留在队列等你手动点；
- 额度到了：当天 `tick()` 直接跳过，界面显示「今天好奇心额度用完了」；
- 花费面板新增专项卡片：累计 / 本月 / 本周 / 日均。

### 18.2.1 桥接账本也会打标签（v14 补）

`qq-bridge/src/token-ledger.js` 每写一行 `k=turn` 都会带 `tag: "chat"`；
`core/cost.import_ledgers()` 读这个字段当 `feature_tag`，老的没有 tag 的历史行归到「普通消息」（meta 里留 `backfilled` 标记）。
所以花费面板里「未分类」从 96% 降到不足 1%（剩下的只有早期 `task=dsh`、连任务名都没记的调用）。

### 18.3 瞬时记忆冷存储 + 回忆检索（v14 之二）

`core/memory/coldstore.py` + 表 `instant_memory`

- 每轮对话写 user/assistant 两条，**常规上下文不读它**；
- 记忆型问题（"我三个小时前说想吃啥来着"）→ 正则触发 → 关键词检索 18 小时内 → 拼
  `[系统提示：以下是用户过去18小时内的相关对话记录…]` 临时塞进上下文；
- 检索本身不额外调模型，但记一条 0 成本 `memory_recall` 事件，花费面板看得见；
- 超过 18 小时由日常巩固 `purge()` 清掉。

### 18.4 P2 剩下的四块

| 模块 | 文件 | 做了什么 |
| --- | --- | --- |
| 2.4 昼夜节律 | `core/circadian.py` | 24 小时模板 × 工作日/周末 × 14 天学到的系数（0.6~1.3）；凌晨 0–2 点陪聊＝睡眠忠诚（energy +0.3，每周上限 5 晚）；`hint()` 进提示词 |
| 2.5 受挫与冷战 | `core/frustration.py` | 被拒/被忽视累积 0–1，每小时衰减 0.08，≥0.6 进冷战（话少、语气淡）；示好 `soothe()` 快速回落并联动词关系层 |
| 2.6 语言指纹 | `core/language/fingerprint.py` | 记口头禅、语气词、标点习惯、句子长度；`hint()` 强约束提示词 |
| 2.6 自我叙事 | `core/self_narrative.py` | 每日巩固生成一段第一人称状态自述，存最近 7 天 + 投 1 号长期记忆；没模型时退化为事实汇总 |
| 3.2 情感解禁 | `core/relationship.py` + `policy.demand_hint()` | 索取度 0–100（默认 65）控制"能要多少"；负面 ≥85 时注入灵魂锚点的治愈提示 |

### 18.5 迁移

```powershell
python tools\migrate_v14.py --dry-run
python tools\migrate_v14.py      # 建 instant_memory；schema_version → 14
```

实测全部 +0，报告 `db\backup\migrate-v14-*.txt`。

### 18.6 测试

`172 个用例全绿`（v12 的 26 + v5 的 18 + v4 的 21 + v3 的 29 + v2 的 54 + v13 的 24）。

## 19. v15：表情字典 + 会话轮换

### 19.1 表情字典（`core\sticker.py`）

一张图第一次要花一次识图钱，之后每次查表 **0 元**：键是图片字节的 sha256，
值包含「是什么 / 怎么用（用过的语境）/ 用了几次」。桥接收到图片先算 sha 查字典，
命中就不调视觉模型。桥接发出去一张表情时会把当时的上下文回写（`/api/sticker/used`），
所以她越用越准。界面：记忆 → 表情字典。

### 19.2 会话轮换（默认关闭）

DSH 会话越长，每步重读的上下文越大（账本实测平均 158K token/步）。开启后
「时长到点 / 轮数到点」**且**「已经空闲」才换新会话（默认 6 小时 / 120 轮 / 空闲 10 分钟），
长期记忆、瞬时记忆、残留通道照常兜底。配置：`qq-bridge\config.json` 的
`socialV2.session.rotate`；界面开关在 QQ 接入。

## 20. v24 / v25 / v26：工具链、时间线、并发容错

三件事，详见 [docs/07-v24-v25-v26-工具链与时间线.md](docs/07-v24-v25-v26-工具链与时间线.md)。

- **v24**：梗百科做成「核心先查一遍 + DSH 插件工具」两份（`core/memewiki.py`、
  `search_meme_wiki`）；装并挂载了 `dsh-memewiki`、`dsh-browser` 两个插件，
  检测安装脚本 `tools\v24_plugins.py`。
  **刷抖音不走那个自带 API 调用的抖音插件**（已从 bundles 移除、脚本里标 `mount: false`），
  改用 `core\webstudy.py`：本机真实 Edge 看 + 网页版 DeepSeek 理解 + 本地词库，**0 API 花费**；
  界面在记忆 → 刷抖音学梗。
- **v25**：系统时间 + 时空感知准则常驻提示词顶端；日记/瞬时记忆/2 号记忆都带
  `[X小时前 (15:48)]`；旧记忆抱怨「没聊天」而近 30 分钟其实聊过时，当场注入`【纠偏】`。
- **v26**：多图改成**逐张串行**自动识别（不再让她并发调三个看图工具）；
  底层报错（invalid JSON / Traceback / 超时）只进日志，先降级重试一次，再不行说人话。

### 20.1 测试

`203 个用例全绿`（Python）+ `25 项`（`node scripts\test-v25-time.mjs`）
+ `21 项`（`node scripts\test-v26-errors.mjs`）。

## 21. v29 / v31 / v32：图片缓存注入 + 内稳态

详见 [docs/08-v29-v31-v32-图片缓存与内稳态.md](docs/08-v29-v31-v32-图片缓存与内稳态.md)。

- **v29**：桥接命中本地表情/图片字典时**不再发图片字节**，改发一段「系统悄悄话」里的文字描述 ——
  既不调视觉 API，也省掉图片输入 token；多图按原顺序串行拼（`resolveMediaList`）。
- **v31**：新增 `core/homeostasis.py`（能量 0.8 / 社交 0.6 / 新鲜感 0.5 三个慢变量 + 三动机 +
  全局工作区仲裁），每 60 秒 tick 一次，按误差给情绪上色；UI 情绪面板多一节「内稳态」。
- **v32**：内稳态 ↔ 好奇心联动 —— 无聊压门槛、孤独抬「人际/梗」类领域的排序、
  能量 < 0.2 直接熔断本周期自主学习。

### 21.1 测试

`219 个用例全绿`（Python）。

## 22. v37：刷抖音学梗（零费版）

详见 [docs/09-v37-刷抖音-零费版.md](docs/09-v37-刷抖音-零费版.md)。

- **谁在跑**：桥接每 30 分钟看一次电脑状态（锁屏/闲置判断见 `core/deskstate.py`），活跃就在 QQ 上请示；
  老大回「去/不行」由桥接正则解析，**不进模型**。同意后核心起后台线程，用本机真实 Edge
  （Playwright，有头可见）逐条抓**纯文本** —— 全程 0 API、0 token。
- **存档**：`learning/browse/<日期>.jsonl`，每条带 `feature_tag="local_browse"`（账本里 0 元）。
- **反爬**：10s±2 停留、翻页前 2~5s、贝塞尔移鼠标、15% 概率点赞；命中滑块/验证 → 立刻停 + 截图 + QQ 求救；
  连续 3 条抓不到内容 → 停并问要不要更新抓取规则。
- **极简执行**：提示词里要求「用浏览器就直接调，不要长篇思考；只抓文字，不解析画面」。

### 22.1 测试

`231 个用例全绿`（Python）+ `38 项`（`node scripts\test-v37-consent.mjs`）。

## 23. v33 / v34：神经内分泌与动态性格（含防火墙）

详见 [docs/10-v33-v34-神经内分泌与动态性格.md](docs/10-v33-v34-神经内分泌与动态性格.md)。

- **v33**：新增 `core/hormones.py`（多巴胺/皮质醇/催产素/血清素 + 基线漂移 + 动态性格），
  事件脉冲全部本地正则识别，**0 调用**；每 10 分钟一次心跳做衰减/漂移/演化。
  提示词里按「初始 vs 现在」的差值注入性格偏移，**不改 1 号记忆原文**。
- **v34**：三道防线 —— 钳制（宜人 ≥0.3 / 神经质 ≤0.8 / 外向 ≥0.1）、熔断（允许悲伤沉默，
  不许攻击伤人）、铁律置顶（`【绝对铁律】…绝不能伤害用户`，在桥接提示词最顶端，不依赖核心在线）。
- **沙盒压测**：`tools\test_personality_sandbox.py` —— 100 次极端辱骂全在内存里跑，
  前后比对真实 state 文件哈希，打印「沙盒测试通过，未触碰真实数据」。

### 23.1 测试

`253 个用例全绿`（Python）；沙盒脚本单独跑（不写真实数据）。

## 24. v35：看板式界面（花费 / 情绪 / 学习）

详见 [docs/11-v35-看板式界面.md](docs/11-v35-看板式界面.md)。

- **统一四段式**：卡片（4 张指标）→ 图表（趋势柱 + 占比环）→ 明细表（斑马线、只读）→
  说明栏（`(i)` 悬停看完整规则 + 导出按钮）。共享积木在 `ui/dashboard.py`。
- **花费面板**：今日/本月/夜学/本地缓存四卡 + 近 7 天柱状图 + 功能归因环形图 + 明细表；
  三段长说明从表格上挪进 tooltip，**重叠 Bug 消失**；内容进滚动区，窗口缩小不压扁。
- **情绪面板**：四卡（当前情绪/内稳态/激素/动态性格）+ 左右分栏刻度 + 历史曲线 + 奖罚事件表。
- **学习面板**：四卡（队列/主信号/缺口/预算）+ 意图队列表 + 缺口表。
- **全局**：`DetailPage` 顶部栏目条按条目数自适应，只有一个栏目时整块收起。

### 24.1 测试

`253 个用例全绿`（Python）；三个面板各截图验证（`docs/shots/ui-v35-*.png`）。

## 25. v36：身份注水 + v2 图片自动识别

详见 [docs/12-v36-身份注水与图片识别.md](docs/12-v36-身份注水与图片识别.md)。

- **认错人**的根因不是「记性差」：模型看到的只有昵称、没有 QQ 号。现在所有消息在
  `compactModelMessage` 里统一加 `[来自 昵称(QQ:号) 的消息]`，自己发的不加，
  解析不出来写「未知用户」；跨线摘要、图片描述也都带号，另加一条身份铁律（不许猜、不许改号）。
- **看图说不行**的根因：`prefetchMediaDescription` 只挂在一代模式，**v2 从来没自动识过图**。
  现在 v2 也会后台识别、描述并进快照（带发送者）、投递前最多等 25 秒让描述跟上；
  同一张图第二次开始命中字典，0 花费。

### 25.1 测试

`10 项`（`node scripts\test-v36-identity.mjs`）+ `253 项`（Python）。

## 26. v15：开源前的脱敏与初始设定

详见 [docs/13-v15-开源发布与脱敏.md](docs/13-v15-开源发布与脱敏.md)。

- **不直接发布本仓库**：真实记忆库 / 日记 / 情绪状态 / QQ 号 / 本机路径都长在这个目录里。
  发布只走 `tools/export_opensource.py`（白名单复制 → 脱敏 → 自检，扫到一处就退出码 1）。
- **首次启动向导**：没有数据库时弹「名字 / 性别 / 身高 / 性格」，写进 1 号长期记忆
  （自我认知 + 性格设定）和 `config/personality.md`；跳过则用默认（大肥鱼 + 傲娇壳温柔心）。
- **人设不再写死**：`core/llm/prompts.py` 的兜底改成中性文案，真实实例的人设原文落在
  `config/personality.md`（内容与改造前逐字一致，行为不变）。
- **许可**：AGPL-3.0 原文 + 顶部《附加条款》（严禁商用、严禁闭源），另有 `ADDITIONAL_TERMS.md`；
  「审计 → 关于与许可」里能直接看到。
- **开发者指南**：`README_DEV.md`（不进仓库/不进包）写了发布前必须人工过的四项检查。

### 26.1 实测

导出 149 个文件、脱敏 62 处；自检「无绝对路径 / 无真实 QQ 号 / 无真实人名 / 无密钥 / 无数据文件」；
导出目录 `compileall` 通过；在空目录跑首次启动 → `detect=True` → 写入「小鱼 / 女 / 160cm / 安静话少」→
`long1` 两条记忆 → `persona()` 读到新设定。真实实例的 `db / emotion.json / hormones.json / personality.md`
哈希前后一致（导出过程只读）。
