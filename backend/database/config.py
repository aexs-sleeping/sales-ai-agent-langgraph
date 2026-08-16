import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# backend/ directory (paths are anchored here, not on the current working directory).
_BACKEND_DIR = Path(__file__).resolve().parents[1]

# Load credentials from the repo-root .env file (never hardcode them in code).
load_dotenv(_BACKEND_DIR.parent / ".env")


@dataclass
class DatabaseConfig:
    """Database connection and seed data configuration."""

    db_name: str
    host: str
    port: int
    user: str
    password: str
    schema_path: Optional[str] = None
    products_path: Optional[str] = None


def get_config() -> DatabaseConfig:
    """Build the configuration from the MYSQL_* environment variables."""
    password = os.getenv("MYSQL_PASSWORD", "")
    if not password:
        raise ValueError(
            "MYSQL_PASSWORD is not set. Copy env-example to .env and fill in the "
            "MySQL credentials before running."
        )
    return DatabaseConfig(
        db_name=os.getenv("MYSQL_DB", "store"),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=password,
        schema_path=str(_BACKEND_DIR / "db" / "schemas.sql"),
        products_path=str(_BACKEND_DIR / "db" / "products.json"),
    )


# Default configuration
DEFAULT_CONFIG = get_config()
