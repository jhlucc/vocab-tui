# vocab-tui

# 环境变量与 `.env` 配置指南

本文说明 **vocab-tui** 如何读取联网与大模型相关的密钥，以及在不同系统/打包方式下的推荐做法。

## 可配置的变量

- `OPENAI_API_KEY` — OpenAI 兼容接口的 API Key  
- `OPENAI_BASE_URL` — OpenAI 兼容接口的 Base URL（也兼容同义名 `OPENAI_API_BASE`）  
- `TAVILY_API_KEY` — Tavily Web 搜索 API Key

> 提示：`word_ai.py` 同时支持 **环境变量** 与 **`.env` 文件**，且**环境变量优先**。

## 读取优先级与查找顺序

1. **环境变量**：进程环境中的变量先于其他方式。
2. **`.env` 文件**（首次命中即生效）：
   1) **可执行文件所在目录**（例如 `vocab.exe` 同目录）  
   2) **脚本所在目录**（`word_ai.py` 所在目录）  
   3) **当前工作目录**

`.env` 文件内容示例：
```dotenv
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com
# 也兼容 OPENAI_API_BASE
TAVILY_API_KEY=tvly-xxxx
```

## 一次性（当前终端有效）设置

### macOS / Linux（bash/zsh）
```bash
export OPENAI_API_KEY="sk-xxxx"
export OPENAI_BASE_URL="https://api.openai.com"
export TAVILY_API_KEY="tvly-xxxx"
vocab
```

### Windows PowerShell
```powershell
$env:OPENAI_API_KEY="sk-xxxx"
$env:OPENAI_BASE_URL="https://api.openai.com"
$env:TAVILY_API_KEY="tvly-xxxx"
vocab
```

### Windows CMD
```bat
set OPENAI_API_KEY=sk-xxxx
set OPENAI_BASE_URL=https://api.openai.com
set TAVILY_API_KEY=tvly-xxxx
vocab
```

## 永久设置（每次打开终端自动生效）

### macOS / Linux
把下面三行写入 `~/.zshrc` 或 `~/.bashrc`：
```bash
export OPENAI_API_KEY="sk-xxxx"
export OPENAI_BASE_URL="https://api.openai.com"
export TAVILY_API_KEY="tvly-xxxx"
```
保存后执行 `source ~/.zshrc`（或重开终端）。

### Windows（用户环境变量）
```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY","sk-xxxx","User")
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL","https://api.openai.com","User")
[Environment]::SetEnvironmentVariable("TAVILY_API_KEY","tvly-xxxx","User")
```

## 给 `.exe`/命令做“带密钥的启动器”（不改系统变量）

### Windows：`vocab-launcher.cmd`
与 `vocab.exe` 放在同一目录：
```bat
@echo off
set OPENAI_API_KEY=sk-xxxx
set OPENAI_BASE_URL=https://api.openai.com
set TAVILY_API_KEY=tvly-xxxx
start "" "%~dp0vocab.exe"
```

### macOS/Linux：`vocab-launcher`
```bash
#!/usr/bin/env bash
export OPENAI_API_KEY="sk-xxxx"
export OPENAI_BASE_URL="https://api.openai.com"
export TAVILY_API_KEY="tvly-xxxx"
exec vocab   # 或 ./vocab、./vocab.exe、python3 main.py
```
给可执行权限：`chmod +x vocab-launcher`。

## 和 TUI 的关系（如何触发 AI 讲解）

- 在学习画面按 **`g`**，程序会调用 `word_ai.py` 获取讲解（会继承上述环境变量；若未设置则读取 `.env`）。
- 未配置密钥也可用：脚本会自动回退到 **DictionaryAPI + Wikipedia**，只是效果会比联网 + 模型弱一些。

## PyInstaller 打包注意事项

- `vocab.exe` 会继承**系统/用户变量**；若未设置，将在 **exe 同目录** 查找 `.env`。  
- 打包命令示例：
  ```bash
  pyinstaller -F -n vocab main.py
  ```
- 如需将默认词库打包进 exe，可以加 `--add-data`，不过一般建议把 `words.csv` 与 `vocab.exe` 放到同一目录，便于替换更新。

## 故障排查（FAQ）

- **没有联网结果或 401/403**：检查 `OPENAI_API_KEY`/`TAVILY_API_KEY` 是否正确、有配额；代理/网关是否设置在 `OPENAI_BASE_URL`。  
- **程序看不到你的变量**：在同一终端里先 `echo $OPENAI_API_KEY`（PowerShell 用 `$env:OPENAI_API_KEY`）确认变量可见；或在 `vocab-launcher` 中设置后再启动。  
- **.env 不生效**：确认文件放对目录（优先 exe 同目录），键=值无引号/或成对引号，行首无空格。

---

以上设置好后，直接启动 `vocab`，在学习画面按 `g` 体验 AI 讲解即可。祝学习顺利！
