from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# backend/ directory (paths are anchored here, not on the current working directory).
_BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    db_name: str
    db_path: str
    schema_path: Optional[str] = None
    products_path: Optional[str] = None


# Default configuration
DEFAULT_CONFIG = DatabaseConfig(
    db_name="store.db",
    db_path=str(_BACKEND_DIR / "db" / "store.db"),
    schema_path=str(_BACKEND_DIR / "db" / "schemas.sql"),
    products_path=str(_BACKEND_DIR / "db" / "products.json"),
)
