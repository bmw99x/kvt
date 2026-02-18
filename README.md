# kvt

A terminal UI for managing Azure Key Vault secrets as `.env` files.

![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue)

⚠️ **EXPERIMENTAL — USE AT YOUR OWN RISK**

This tool is experimental and provided as-is. The author is not responsible for any data loss, accidental deletion, misconfiguration, or other problems that may result from using this tool. Always ensure you have proper backups of your Azure Key Vault secrets and review all changes carefully before committing them to production vaults.

## Features

- Browse, add, edit, and delete secrets across projects and environments
- Multiline secrets (`.env` blobs) displayed and edited as structured key/value tables
- Undo stack for all mutations within a session
- Context switcher to jump between projects and environments
- Search/filter across keys and values
- Clipboard copy for any secret value

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Azure CLI (`az`) — authenticated via `az login` or a service principal

## Install

```bash
uv tool install git+https://github.com/bmw99x/kvt
```

Or clone and install locally:

```bash
git clone https://github.com/bmw99x/kvt
cd kvt
uv tool install .
```

## Configuration

kvt reads `~/.config/kvt/config.json`. The schema maps service names to environments:

```json
{
  "MyApp": {
    "Production": {
      "vault_name": "kv-myapp-prod",
      "subscription_id": "00000000-0000-0000-0000-000000000000",
      "tenant_id": "00000000-0000-0000-0000-000000000001"
    },
    "Staging": {
      "vault_name": "kv-myapp-stg",
      "subscription_id": "00000000-0000-0000-0000-000000000000",
      "tenant_id": "00000000-0000-0000-0000-000000000001"
    }
  }
}
```

A blank config file is created automatically on first run.

### Auto-configure from Azure

`kvt-autoconfig` discovers all Key Vaults across your subscriptions and writes the config for you:

```bash
kvt-autoconfig ~/.config/kvt/config.json
```

Optionally map resource group names to friendlier service names:

```bash
kvt-autoconfig ~/.config/kvt/config.json --service-name-mapping '{"rg-myapp": "MyApp"}'
```

## Usage

```bash
kvt
```

### Keybindings

| Key           | Action                          |
| ------------- | ------------------------------- |
| `j` / `k`     | Move down / up (wraps around)   |
| `g g`         | Jump to top                     |
| `G`           | Jump to bottom                  |
| `i` / `Enter` | Edit selected variable          |
| `r`           | Rename selected variable        |
| `o`           | Add new variable                |
| `d d`         | Delete selected variable        |
| `y`           | Copy value to clipboard         |
| `u`           | Undo last change                |
| `/`           | Search / filter                 |
| `Escape`      | Clear search                    |
| `e` / `Tab`   | Cycle to next environment       |
| `p`           | Open project/environment picker |
| `?`           | Toggle help                     |
| `q`           | Quit                            |

Double-clicking a row also opens the edit modal.

### Multiline secrets

Secrets whose values contain multiple `KEY=value` lines are shown as `[ env ]` badges. Editing them opens a drill-in table where each inner variable can be managed individually. Changes are written back as a single Azure secret.

Available keybindings in multiline view:

| Key           | Action                          |
| ------------- | ------------------------------- |
| `j` / `k`     | Move down / up (wraps around)   |
| `g g`         | Jump to top                     |
| `G`           | Jump to bottom                  |
| `i`           | Edit variable value             |
| `r`           | Rename variable key             |
| `y`           | Copy value to clipboard         |
| `o`           | Add new variable                |
| `d d`         | Delete variable                 |
| `s`           | Save changes                    |
| `q` / `Esc`   | Cancel                          |

## Development

```bash
uv sync
uv run pytest tests/ -q
uv run ty check src/ tests/
```
