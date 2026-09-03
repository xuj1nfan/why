# why

`why` is a lightweight, zsh/Bash-oriented shell diagnosis assistant with local
shell memory. It observes shell events and is intended to explain failures
with their surrounding context; it never executes AI-generated commands.

## Development status

The first implementation pass contains the local SQLite memory layer and the
CLI used by shell hooks:

```bash
python -m why --help
why history
why init zsh
why init bash
why inspect
```

Enable the integration in the shell you use:

```bash
eval "$(why init zsh)"   # zsh
eval "$(why init bash)"  # Bash
```

The database defaults to `~/.local/share/why/why.db`. Set `WHY_DB_PATH` to use
a different database, which is useful for tests and development.

To enable diagnosis, configure an OpenAI-compatible endpoint:

The default config file is `~/.config/why/config.toml`; set `WHY_CONFIG_PATH`
to use another location.

```toml
[llm]
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "your-model"
```

Then export the API key through the configured environment variable. The key
is never included in the prompt or stored in shell memory.

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

A plain `pacman -S` installation requires a
configured binary repository or a downloaded package file.

## Local development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```
