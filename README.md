# why

`why` is a lightweight, zsh/Bash-oriented shell diagnosis assistant with local
shell memory. It observes shell events and is intended to explain failures
with their surrounding context; it never executes AI-generated commands.

## Usage

Inspect recorded commands, preview diagnosis context, or diagnose the latest
failed command:

```bash
why history
why inspect
why
```

Enable the integration in the shell you use:

```bash
eval "$(why init zsh)"   # zsh
eval "$(why init bash)"  # Bash
```

The database defaults to `~/.local/share/why/why.db`. Set `WHY_DB_PATH` to use
a different database, which is useful for tests and development.

History output includes event IDs. Select one event and optionally attach
captured stderr or a build log:

```bash
why inspect --event 42 --output build.err
why diagnose --event 42 --output build.err "Why is this header missing?"
some-command 2>error.log
why diagnose --output error.log
```

Use `--output -` to read error output from stdin. Attached output is bounded,
treated as untrusted data, and passed through the same credential redaction as
command history.

To enable diagnosis, configure an OpenAI-compatible endpoint:

The default config file is `~/.config/why/config.toml`; set `WHY_CONFIG_PATH`
to use another location.

```toml
[llm]
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "your-model"

[storage]
retention_days = 30
max_events_per_session = 5000
```

Then export the API key through the configured environment variable. The
configured key is used only for request authentication and is not deliberately
included in shell memory or diagnosis prompts.

## Privacy and security

`why` stores command text in a local SQLite database with owner-only
permissions. Common inline credential forms—such as token environment
variables, authorization headers, credential-bearing URLs, and password
flags—are redacted before storage and again before diagnosis. This is
best-effort protection, so avoid entering secrets directly on the command
line.

Diagnosis sends the redacted recent commands, working directories, OS, and Git
state to the configured OpenAI-compatible endpoint. Run `why inspect` first to
preview that context without making a network request.

## Storage and performance

The database schema is migrated automatically and currently uses SQLite WAL
mode for concurrent terminals. Completed commands are written atomically by a
background recorder, so the prompt does not wait for Python startup or disk
I/O. Before the next command begins, the hook waits for any still-pending
recorder to preserve ordering and read-after-write consistency.

Retention runs with each background write. A value of `0` disables that
specific limit. Apply the configured policy manually, or override it once:

```bash
why prune
why prune --days 7 --max-events 1000
why prune --session
```

## Development

Create an isolated environment and install the test and build tools:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python benchmarks/recording.py
```

The tests use temporary databases and do not require an API key or network
access. Build a wheel with
`.venv/bin/python -m build --wheel --no-isolation`.

## Arch Linux

An Arch package definition is included in `packaging/arch`. Build and install
the current development version locally with `paru`:

```bash
cd packaging/arch
paru -Bi .
```

After the package is published to the AUR, install it with `paru`:

```bash
paru -S why-git
```
