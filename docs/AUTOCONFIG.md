# Automatic Configuration with kvt-autoconfig

The `kvt-autoconfig` tool automatically discovers and configures all Azure Key Vaults across your subscriptions.

## Features

- **Azure authentication**: Runs `az login` to authenticate with Azure
- **Subscription discovery**: Fetches all subscriptions you have access to
- **Key Vault enumeration**: Lists all Key Vaults in each subscription
- **Service name generation**: Converts resource group names to Title Case (e.g., `my-resource-group` → `My-Resource-Group`)
- **Environment extraction**: Infers environment from the vault name's last segment (e.g., `kv-frontend-prod` → `prod`)
- **Customizable mapping**: Override auto-generated names using `--service-name-mapping`

## Installation

The tool is available as a script entry point when kvt is installed:

```bash
uv pip install .
# or
pip install .
```

## Usage

### Basic usage
```bash
kvt-autoconfig ~/.config/kvt/config.json
```

### With custom service name mappings
```bash
kvt-autoconfig ~/.config/kvt/config.json --service-name-mapping '{"my-app-rg": "MyApp", "other-rg": "OtherService"}'
```

### With short flag
```bash
kvt-autoconfig ~/.config/kvt/config.json -m '{"my-rg": "MyService"}'
```

### View help
```bash
kvt-autoconfig --help
```

## What it does

1. Logs in with `az login`
2. Fetches all subscriptions
3. For each subscription, lists all Key Vaults and extracts tenant ID
4. Organizes by service name (resource group in Title Case) → environment → vault config
5. Writes the result to the specified `config.json` path

## Output

The tool generates a `config.json` file matching the schema defined in kvt's README:

```json
{
    "<service-name>": {
        "<environment-name>": {
            "vault_name": "kv-myapp-prod",
            "subscription_id": "00000000-0000-0000-0000-000000000000",
            "tenant_id": "00000000-0000-0000-0000-000000000001"
        }
    }
}
```

## Service Name Generation

By default, service names are derived from resource group names using Title Case:
- `my-resource-group` → `My-Resource-Group`
- `frontend_app` → `Frontend_App`
- `myapp` → `Myapp`

To override this behavior, provide a `--service-name-mapping` argument with a JSON dictionary mapping resource group names to desired service names.

## Environment Detection

Environments are extracted from the Key Vault name by taking the last segment after the final hyphen:
- `kv-frontend-prod` → environment: `prod`
- `kv-backend-staging` → environment: `staging`
- `keyvault` → environment: `default`

## Prerequisites

- Azure CLI (`az`) installed and available in PATH
- Azure subscription(s) with access to Key Vaults
- `az login` credentials
