"""Automatically configure kvt by discovering Azure Key Vaults across subscriptions."""

import json
import subprocess
import sys
from pathlib import Path

import typer

from kvt.config import AzureEnv

app = typer.Typer(
    help="Automatically configure kvt by discovering Azure Key Vaults",
    no_args_is_help=True,
)

# Module-level defaults for Typer arguments
_CONFIG_PATH_HELP = "Path to config.json file to write"
_SERVICE_NAME_MAPPING_HELP = (
    'JSON dict mapping resource group names to service names. Example: \'{"my-rg": "MyService"}\''
)


def run_command(cmd: list[str]) -> str:
    """Execute a command and return its output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        typer.echo(f"Error running command: {' '.join(cmd)}", err=True)
        typer.echo(f"stderr: {e.stderr}", err=True)
        sys.exit(1)


def login_to_azure() -> None:
    """Authenticate with Azure CLI."""
    typer.echo("Logging in to Azure...")
    run_command(["az", "login"])
    typer.echo("Successfully logged in to Azure")


def get_subscriptions() -> list[dict[str, str]]:
    """Get all subscriptions the user has access to."""
    typer.echo("Fetching subscriptions...")
    output = run_command(["az", "account", "list", "--query", "[].{id:id, name:name}"])
    subscriptions = json.loads(output)
    typer.echo(f"Found {len(subscriptions)} subscription(s)")
    return subscriptions


def set_subscription(subscription_id: str) -> None:
    """Set the current subscription."""
    run_command(["az", "account", "set", "--subscription", subscription_id])


def get_keyvaults() -> list[dict[str, str]]:
    """Get all key vaults in the current subscription."""
    output = run_command(
        [
            "az",
            "keyvault",
            "list",
            "--query",
            "[].{name:name, id:id, resourceGroup:resourceGroup}",
        ]
    )
    return json.loads(output)


def get_tenant_id(subscription_id: str) -> str:
    """Get the tenant ID for a subscription."""
    output = run_command(
        [
            "az",
            "account",
            "show",
            "--subscription",
            subscription_id,
            "--query",
            "tenantId",
            "-o",
            "tsv",
        ]
    )
    return output


def resource_group_to_service_name(resource_group: str) -> str:
    """Convert resource group name to Title case (each word capitalized)."""
    parts = []
    current = []

    for char in resource_group:
        if char in ("-", "_"):
            if current:
                parts.append(("".join(current), char))
                current = []
        else:
            current.append(char)

    if current:
        parts.append(("".join(current), None))

    result = ""
    for part, sep in parts:
        result += part.capitalize()
        if sep:
            result += sep

    return result


def populate_config(
    service_name_mapping: dict[str, str] | None = None,
) -> dict[str, dict[str, AzureEnv]]:
    """
    Discover and populate configuration for all key vaults across subscriptions.

    Args:
        service_name_mapping: Optional dict to override auto-generated service names.
                             Maps resource group names to service names.

    Returns:
        Dictionary matching the kvt config schema
    """
    if service_name_mapping is None:
        service_name_mapping = {}

    config: dict[str, dict[str, AzureEnv]] = {}

    subscriptions = get_subscriptions()

    for subscription in subscriptions:
        sub_id = subscription["id"]
        sub_name = subscription["name"]

        typer.echo(f"\nProcessing subscription: {sub_name} ({sub_id})")
        set_subscription(sub_id)

        keyvaults = get_keyvaults()

        if not keyvaults:
            typer.echo("  No key vaults found in this subscription")
            continue

        tenant_id = get_tenant_id(sub_id)

        for vault in keyvaults:
            vault_name = vault["name"]
            resource_group = vault["resourceGroup"]

            # Determine service name
            if resource_group in service_name_mapping:
                service_name = service_name_mapping[resource_group]
            else:
                service_name = resource_group_to_service_name(resource_group)

            # Extract environment from vault name (e.g., "kv-frontend-prod" -> "prod")
            vault_parts = vault_name.split("-")
            environment = vault_parts[-1] if len(vault_parts) > 1 else "default"

            typer.echo(f"  Found vault: {vault_name} -> service={service_name}, env={environment}")

            # Initialize service if not exists
            if service_name not in config:
                config[service_name] = {}

            # Add environment configuration
            config[service_name][environment] = AzureEnv(
                vault_name=vault_name,
                subscription_id=sub_id,
                tenant_id=tenant_id,
            )

    return config


@app.command()
def main(
    config_path: Path = typer.Argument(  # noqa: B008
        ...,
        help=_CONFIG_PATH_HELP,
    ),
    service_name_mapping: str = typer.Option(  # noqa: B008
        "{}",
        "--service-name-mapping",
        "-m",
        help=_SERVICE_NAME_MAPPING_HELP,
    ),
) -> None:
    """Automatically configure kvt with Azure Key Vault configurations."""
    # Parse service name mapping
    try:
        mapping = json.loads(service_name_mapping)
    except json.JSONDecodeError as e:
        typer.echo(f"Error parsing service-name-mapping JSON: {e}", err=True)
        sys.exit(1)

    # Authenticate
    login_to_azure()

    # Discover and populate
    config = populate_config(mapping)

    # Save to config.json
    config_path.parent.mkdir(parents=True, exist_ok=True)

    typer.echo(f"\nWriting configuration to {config_path}...")
    payload = {
        service: {env_name: azure_env.model_dump() for env_name, azure_env in envs.items()}
        for service, envs in config.items()
    }
    config_path.write_text(json.dumps(payload, indent=2))

    typer.echo("\nConfiguration saved successfully!")
    typer.echo(f"Found {len(config)} service(s)")
    for service_name, environments in config.items():
        typer.echo(f"  {service_name}: {', '.join(environments.keys())}")
