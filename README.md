# why

[中文](#中文) · [English](#english)

## 中文

`why` 是面向 Bash 和 zsh 的轻量 Shell 诊断助手。它在本地记录命令、目录、退出码和耗时，并结合上下文解释失败原因；不会执行 AI 生成的命令。

### 安装与启用

```bash
python -m pip install .
eval "$(why init bash)"  # Bash
eval "$(why init zsh)"   # zsh
```

将对应的 `eval` 命令加入 `~/.bashrc` 或 `~/.zshrc` 可永久启用。

### 使用

```bash
why history                         # 查看当前会话历史
why inspect                         # 预览将发送的诊断上下文
why                                 # 诊断最近一次失败
why inspect --event 42              # 预览指定事件
why diagnose --event 42 --output build.err "为什么编译失败？"
why diagnose --output -             # 从 stdin 读取错误输出
```

`why` 不会自动捕获 stdout/stderr；可通过 `--output FILE|-` 主动提供。错误输出有长度限制，并按不可信数据处理。

### 配置

默认配置文件为 `~/.config/why/config.toml`：

```toml
[llm]
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "your-model"

[storage]
retention_days = 30
max_events_per_session = 5000
```

数据库默认位于 `~/.local/share/why/why.db`。可通过 `WHY_CONFIG_PATH`、`WHY_DB_PATH` 和 `WHY_LLM_*` 环境变量覆盖配置。

### 隐私、存储与清理

命令在写入 SQLite 前会脱敏，发送诊断前再次脱敏；数据库权限为仅所有者可读写。脱敏属于尽力保护，请避免直接在命令行输入密钥。诊断会把脱敏后的命令、目录、系统及 Git 状态发送到配置的 LLM 端点，建议先运行 `why inspect`。

数据库自动迁移并使用 WAL 模式。命令通过后台进程原子写入，以减少提示符延迟。保留策略自动执行，值为 `0` 时关闭对应限制：

```bash
why prune
why prune --days 7 --max-events 1000
why prune --session
```

### 开发

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python benchmarks/recording.py
.venv/bin/python -m build --wheel --no-isolation
```

Arch Linux 开发包可在 `packaging/arch` 中运行 `paru -Bi .` 构建安装。

## English

`why` is a lightweight shell diagnosis assistant for Bash and zsh. It records commands, directories, exit codes, and duration locally, then uses that context to explain failures. It never executes AI-generated commands.

### Install and enable

```bash
python -m pip install .
eval "$(why init bash)"  # Bash
eval "$(why init zsh)"   # zsh
```

Add the matching `eval` command to `~/.bashrc` or `~/.zshrc` to enable it permanently.

### Usage

```bash
why history                         # Show history for this session
why inspect                         # Preview diagnosis context
why                                 # Diagnose the latest failure
why inspect --event 42              # Preview a selected event
why diagnose --event 42 --output build.err "Why did compilation fail?"
why diagnose --output -             # Read error output from stdin
```

`why` does not capture stdout/stderr automatically. Supply it explicitly with `--output FILE|-`. Attached output is bounded and treated as untrusted data.

### Configuration

The default configuration file is `~/.config/why/config.toml`:

```toml
[llm]
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "your-model"

[storage]
retention_days = 30
max_events_per_session = 5000
```

The database defaults to `~/.local/share/why/why.db`. Override settings with `WHY_CONFIG_PATH`, `WHY_DB_PATH`, or the `WHY_LLM_*` environment variables.

### Privacy, storage, and retention

Commands are redacted before SQLite storage and again before diagnosis. The database is owner-only. Redaction is best effort, so avoid typing secrets directly on the command line. Diagnosis sends redacted commands, directories, system details, and Git state to the configured LLM endpoint; use `why inspect` to preview them first.

The database migrates automatically and uses WAL mode. Events are written atomically in the background to reduce prompt latency. Retention runs automatically; `0` disables a limit:

```bash
why prune
why prune --days 7 --max-events 1000
why prune --session
```

### Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python benchmarks/recording.py
.venv/bin/python -m build --wheel --no-isolation
```

On Arch Linux, build the development package from `packaging/arch` with `paru -Bi .`.
