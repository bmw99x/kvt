"""Application-wide constants."""

APP_TITLE = "kvt"
APP_SUBTITLE = "Azure Key Vault · mock"

ENVIRONMENTS: list[str] = ["production", "staging", "development", "local"]
DEFAULT_ENV: str = "staging"

PROJECTS: dict[str, list[str]] = {
    "frontend": ["production", "staging", "development", "local"],
    "backend": ["production", "staging", "development"],
    "infra": ["production", "staging"],
}
DEFAULT_PROJECT: str = "frontend"

# Per-project, per-environment mock secrets.
MOCK_DATA: dict[str, dict[str, dict[str, str]]] = {
    "frontend": {
        "production": {
            "APP_ENV": "production",
            "API_BASE_URL": "https://api.example.com/v2",
            "API_KEY": "sk-live-4fGhJ8kLmNpQrStUvWxYz",
            "CDN_URL": "https://cdn.example.com",
            "SENTRY_DSN": "https://abc123@o987654.ingest.sentry.io/1234567",
            "FEATURE_FLAGS": "payments,analytics,darkmode",
        },
        "staging": {
            "APP_ENV": "staging",
            "API_BASE_URL": "https://staging-api.example.com/v2",
            "API_KEY": "sk-staging-aAbBcCdDeEfF",
            "CDN_URL": "https://staging-cdn.example.com",
            "SENTRY_DSN": "https://stg456@o987654.ingest.sentry.io/9999999",
            "FEATURE_FLAGS": "payments,analytics,darkmode,beta-ui",
            "DEBUG": "true",
        },
        "development": {
            "APP_ENV": "development",
            "API_BASE_URL": "http://localhost:8000/v2",
            "API_KEY": "sk-dev-localonly",
            "DEBUG": "true",
            "HOT_RELOAD": "true",
        },
        "local": {
            "APP_ENV": "local",
            "API_BASE_URL": "http://localhost:8000/v2",
            "DEBUG": "true",
            "MOCK_AUTH": "true",
        },
    },
    "backend": {
        "production": {
            "APP_ENV": "production",
            "DATABASE_URL": "postgres://app_user:p@ssw0rd@db.prod.internal:5432/appdb",
            "DATABASE_POOL_SIZE": "20",
            "REDIS_URL": "redis://:r3d1s_p@ss@cache.prod.internal:6379/0",
            "SECRET_KEY": "s3cr3t-prod-xK9mP2nQ",
            "JWT_SECRET": "jwt-prod-xYz-7a8b9c0d",
            "JWT_EXPIRY_SECONDS": "3600",
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "SMTP_HOST": "smtp.sendgrid.net",
            "SMTP_PORT": "587",
            "SMTP_USER": "apikey",
            "SMTP_PASSWORD": "SG.prod-aBcDeFgH",
            "CORS_ORIGINS": "https://app.example.com,https://admin.example.com",
        },
        "staging": {
            "APP_ENV": "staging",
            "DATABASE_URL": "postgres://app_user:p@ssw0rd@db.stg.internal:5432/appdb_stg",
            "DATABASE_POOL_SIZE": "10",
            "REDIS_URL": "redis://:r3d1s_stg@cache.stg.internal:6379/0",
            "SECRET_KEY": "s3cr3t-stg-xK9mP2nQ",
            "JWT_SECRET": "jwt-stg-xYz-7a8b9c0d",
            "JWT_EXPIRY_SECONDS": "3600",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "CORS_ORIGINS": "https://staging.example.com",
            "LOG_LEVEL": "debug",
        },
        "development": {
            "APP_ENV": "development",
            "DATABASE_URL": "postgres://postgres:postgres@localhost:5432/appdb_dev",
            "DATABASE_POOL_SIZE": "5",
            "REDIS_URL": "redis://localhost:6379/0",
            "SECRET_KEY": "dev-secret-not-safe",
            "JWT_SECRET": "dev-jwt-secret",
            "JWT_EXPIRY_SECONDS": "86400",
            "LOG_LEVEL": "debug",
        },
    },
    "infra": {
        "production": {
            "TF_WORKSPACE": "production",
            "AWS_ACCESS_KEY_ID": "AKIAINFRAPROD1234567",
            "AWS_SECRET_ACCESS_KEY": "infra-prod-secret-key-EXAMPLE",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "DATADOG_API_KEY": "dd-prod-api-key-abc123",
            "DATADOG_APP_KEY": "dd-prod-app-key-xyz789",
            "PAGERDUTY_TOKEN": "pd-prod-token-qwerty",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T00/B00/prod",
        },
        "staging": {
            "TF_WORKSPACE": "staging",
            "AWS_ACCESS_KEY_ID": "AKIAINFRASTG1234567",
            "AWS_SECRET_ACCESS_KEY": "infra-stg-secret-key-EXAMPLE",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "DATADOG_API_KEY": "dd-stg-api-key-abc123",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T00/B00/stg",
        },
    },
}

TABLE_COLUMNS = ("#", "Key", "Value")

HELP_TEXT = """\
 Navigation
 ──────────────────────────────
 j / ↓        Move down
 k / ↑        Move up
 g g          Jump to top
 G            Jump to bottom

 Edit
 ──────────────────────────────
 i / Enter    Edit selected value
 o            Add new variable
 d d          Delete selected variable
 u            Undo last change

 Search
 ──────────────────────────────
 /            Open search
 Escape       Clear search / close

 General
 ──────────────────────────────
 y            Copy value to clipboard
 ?            Toggle this help
 q            Quit\
"""
