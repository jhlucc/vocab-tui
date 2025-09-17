# Vocab TUI —— 终端背单词工具（Boss键 + AI讲解）

一个面向命令行/终端的英语词汇学习小工具：支持 **学习模式** 与 **拼写模式**，内置 **Boss 键伪装**（Tab 一键切换到 “tail -f” / “ls -la” 假装界面），支持 **多主题（F6 切换）**，并且可以一键调用 `word_ai.py` 做 **AI 讲解**（可联网检索 Tavily + OpenAI 兼容大模型，或走离线兜底）。还内置 **批量为错题本生成 AI 笔记** 的任务视图。

> 适合：背单词、复习错题、休息一下按 Tab 瞬间“消失”、以及把难词交给 AI “讲透”。

---

## ✨ 功能特性

- **学习模式**：按键极简（`s/w` 上下词、`p` 显示释义、`Space/Enter` 标记“会了”、`x` 标记“不会”、`,` 加入错题本、`r` 打乱、`t` 进拼写模式、`g` AI 讲解）。  
- **拼写模式（中→英）**：中文释义提示，直接敲字母输入，`Enter` 判定、`Backspace` 删除、`F2` 开/关提示、`↑/↓` 跳词、`ESC` 退出。
- **错题本**：把 **加星** 的词，或 **出现过不会** 的词，组成错题集（主菜单可选择“只学错题本”）。
- **统计面板**：总词数、看过/会了/不会/加星计数。
- **Boss 键伪装**（Tab）：两种风格可选
  - `tail -f /var/log/application.log`：滚动产生日志（INFO/DEBUG/WARNING）、当前时间戳。
  - `ls -la`：伪造目录列表（时间戳也是“刚刚更新”的样子）。
  - 可选 `q` 直接退出程序（需在配置中启用 `boss_quit_enabled`）。
- **多主题（F6 切换）**：`mono / green / blue / amber / magenta`，颜色语义固定（标题/单词/正确/警示/音标/正文）。
- **AI 讲解（单词级）**：在学习模式里按 `g`，调用 `word_ai.py` 生成 Markdown 讲解（可联网检索 + LLM，或使用免费后备：dictionaryapi.dev / Wikipedia）。
- **批量生成错题本 AI 笔记**：主菜单第 5 项，显示进度条与实时日志；默认跳过已存在 `ai_notes/<word>.md`。

---

## 🧭 目录结构

```
.
├─ main.py          # 程序入口（curses 包装、主菜单、学习/拼写/AI/批量等）
├─ ui.py            # 终端 UI（主题、弹窗、滚动查看器、批量进度、按键解析）
├─ models.py        # 数据模型（Word / Progress / Stats / AppConfig / UISnapshot / VocabApp）
├─ storage.py       # 本地存储（words.csv / progress.json 的读写与示例创建）
├─ boss.py          # Boss 键伪装屏幕（tail -f / ls -la）
├─ word_ai.py       # AI 讲解脚本（Tavily + OpenAI 兼容；或离线兜底；可 --save）
├─ pyproject.toml   # 打包/依赖/入口脚本（console_script: vocab）
├─ words.csv        # 你的单词表（首启若不存在会自动创建示例）
├─ progress.json    # 学习进度（自动保存）
└─ ai_notes/        # 批量或单次保存的 AI 讲解 Markdown（<word>.md）
```

---

## ⚙️ 安装与运行

### 1) 直接运行（源码）

```bash
python3 main.py
```

- 首次启动如果没有 `words.csv`，会自动创建一个示例。
- 数据文件均在当前目录：`words.csv` 与 `progress.json`。

### 2) 安装为命令（推荐）

支持 Python 3.8+：

```bash
pip install -e .        # 或者使用 pipx 安装到独立环境
vocab                   # 安装后可直接运行命令 vocab
```

> Windows 会自动安装 `windows-curses` 以支持 curses；其他平台使用系统自带 curses。

---

## 🕹️ 操作与快捷键

### 主菜单
1. 开始学习
2. 只学错题本
3. 查看统计
4. 拼写模式（中文→英文）
5. 批量生成错题本 AI 笔记
6. 退出（或 `q`/`ESC` 取消）

- **全局**：`Tab` = Boss 键；`F6` = 切主题

### 学习模式
- `s / w`：下一个 / 上一个
- `p`：显示/隐藏释义
- `Space / Enter`：标记“我会了”
- `x`：标记“我不会”
- `,`：加入错题本（加星）
- `r`：打乱单词顺序
- `t`：进入 **拼写模式**
- `g`：获取 **AI 讲解**
- `h`：打开快捷键帮助
- `q / ESC`：退出当前界面

### 拼写模式（中文→英文）
- 直接敲字母输入；`Enter` 判定；`Backspace` 删除
- `F2` 开/关提示（显示目标单词首尾字母和长度）
- `↑/↓` 前后切换；`ESC` 退出

### 滚动查看/批量任务界面
- 滚动：`↑/↓`、`PgUp/PgDn`、`Home/End`
- 关闭：`q / ESC / .`
- 其他：`F6` 切主题；`Tab` 老板键（返回后可继续）

---

## 🧠 AI 讲解（`word_ai.py`）

既可在 TUI 中按 `g` 调用，也可直接命令行使用：

```bash
python word_ai.py <WORD> --plain             # 以纯文本输出（适合 TUI 弹窗）
python word_ai.py <WORD> --save              # 保存为 ai_notes/<word>.md
python word_ai.py <WORD> --search auto       # 联网检索（auto/tavily/off）
python word_ai.py <WORD> --model gpt-4o-mini # 指定 OpenAI 兼容模型
```

### 环境变量 / .env
- `OPENAI_API_KEY`（必需，若用 LLM）
- `OPENAI_BASE_URL` 或 `OPENAI_API_BASE`（可选，默认 `https://api.openai.com`）
- `OPENAI_MODEL`（可选，默认 `gpt-4o-mini`）
- `TAVILY_API_KEY`（可选，用于联网检索）

`.env` 的查找顺序：**可执行文件所在目录 → 脚本所在目录 → 当前工作目录**。也可以直接用系统环境变量。

### 联网/离线策略
- 优先用 **Tavily** 做检索，拼装参考链接/摘要，并作为 LLM 提示的一部分；
- 若无 Tavily 或 LLM，降级到 **dictionaryapi.dev** 与 **Wikipedia** 的免费接口，生成结构化讲解（含音标/词义/摘要/例句/练习/参考）。
- `--save` 时写入 `ai_notes/<word>.md`；`--plain` 可去除 Markdown 标题用于 TUI。

---

## 🗂️ 数据文件

- **`words.csv`**：列包含 `word, meaning, phonetic, example`。可自行维护；程序会按 CSV 逐行解析。
- **`progress.json`**：自动保存每个单词的 `seen/known/unknown/starred` 统计。
- **错题本**：由“加星 或 出现过不会”的词构成，可以在主菜单选择“只学错题本”。

首次运行若缺少 `words.csv`，会自动生成一个示例 CSV，便于快速体验。

---

## 🎨 主题与 Boss 键

- **主题**：`F6` 循环切换 `mono / green / blue / amber / magenta`；颜色语义固定：
  - `1=标题`、`2=单词`、`3=释义/正确`、`4=警示/错误`、`5=音标`、`6=文本`
- **Boss 键（Tab）**：立即进入“伪装界面”
  - `tail -f`：不断滚动最新日志，含时间戳/级别/消息；
  - `ls -la`：显示仿真的目录文件清单与近期时间；
  - `q` 直接退出（需在配置里开启 `boss_quit_enabled`）。

---

## 📦 依赖与要求

- Python **3.8+**
- 运行时依赖：`requests`  
- Windows 平台：自动安装 `windows-curses` 以支持 curses

安装好后将 `vocab` 暴露为全局命令（`[project.scripts]`）。

---

## 🧩 扩展/定制

- 主题与 Boss 样式可在代码中的 `AppConfig` 默认值里修改，或自行扩展为持久化配置。
- 想要“更像在摸鱼”：可以调整 `boss.py` 中的日志模板或 `ls` 文件列表；
- 也可以把 `word_ai.py` 的提示词/格式改成你自己的讲解风格，或替换为你的 LLM 服务端点。

---

## 🐞 常见问题

- **Windows 运行报错：** 请确认安装了 `windows-curses`（按上面的安装步骤会自动处理）。
- **按下 Tab 没反应：** 你的终端可能对 `KEY_TAB/KEY_BTAB` 兼容性不同，程序已做多种兼容；若仍有问题，可在不同终端尝试。
- **AI 讲解“超时/失败”：** 可能是网络、Key 或模型不可用；可重试、换镜像、或使用 `--search off` 走离线兜底。
- **`words.csv` 格式问题：** 确认列名拼写正确；程序会打印解析失败提示。

---

## 📝 许可证

MIT License（详见 `pyproject.toml`）。

---

## 🙏 致谢

- [dictionaryapi.dev](https://dictionaryapi.dev/)
- [Wikipedia REST API](https://www.mediawiki.org/wiki/API:REST_API)  
- [Tavily Search API](https://www.tavily.com/)
