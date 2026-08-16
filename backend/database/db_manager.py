import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from database.config import DEFAULT_CONFIG, DatabaseConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations including setup, connection, and data insertion."""

    def __init__(self, config: DatabaseConfig = DEFAULT_CONFIG):
        self.config = config
        self._engine: Optional[Engine] = None

    def _server_engine_url(self) -> URL:
        """URL without a default database (used for CREATE DATABASE)."""
        return URL.create(
            "mysql+pymysql",
            username=self.config.user,
            password=self.config.password,
            host=self.config.host,
            port=self.config.port,
            query={"charset": "utf8mb4"},
        )

    def _engine_url(self) -> URL:
        return self._server_engine_url().set(database=self.config.db_name)

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._engine_url(), pool_pre_ping=True)
        return self._engine

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Context manager for read-only database connections."""
        with self._get_engine().connect() as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Generator[Connection, None, None]:
        """Context manager for a write transaction (commit on success, rollback on error)."""
        with self._get_engine().begin() as conn:
            yield conn

    def create_database(self) -> bool:
        """
        Creates the database (if needed) and sets up the schema.

        Returns:
            bool: True if database creation was successful, False otherwise.
        """
        try:
            self._create_db_if_not_exists()

            # Execute schema if provided
            if self.config.schema_path:
                return self.execute_sql_file(self.config.schema_path)
            return True

        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False

    def _create_db_if_not_exists(self) -> None:
        # Connect without selecting a database
        server_engine = create_engine(self._server_engine_url())
        try:
            with server_engine.connect() as conn:
                conn.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{self.config.db_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
                conn.commit()
        finally:
            server_engine.dispose()

    def execute_sql_file(self, file_path: str) -> bool:
        """
        Executes SQL statements from a file (statements split on ';').

        Args:
            file_path (str): Path to the SQL file.

        Returns:
            bool: True if execution was successful, False otherwise.
        """
        try:
            sql_script = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"SQL file not found: {file_path}")
            return False

        try:
            with self.transaction() as conn:
                for statement in sql_script.split(";"):
                    if statement.strip():
                        conn.execute(text(statement))
            logger.info(f"SQL script executed successfully from {file_path}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error executing SQL script: {e}")
            return False

    def insert_product(
        self,
        product_name: str,
        category: str,
        description: str,
        price: float,
        quantity: int,
    ) -> bool:
        """
        Inserts a single product into the database.

        Args:
            product_name (str): Name of the product
            category (str): Product category
            description (str): Product description
            price (float): Product price
            quantity (int): Available quantity

        Returns:
            bool: True if insertion was successful, False otherwise.
        """
        query = text(
            """
            INSERT INTO products (ProductName, Category, Description, Price, Quantity)
            VALUES (:name, :category, :description, :price, :quantity)
            """
        )
        try:
            with self.transaction() as conn:
                conn.execute(
                    query,
                    {
                        "name": product_name.lower(),
                        "category": category.lower(),
                        "description": description,
                        "price": price,
                        "quantity": quantity,
                    },
                )
            logger.info(f"Successfully inserted product: {product_name}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error inserting product {product_name}: {e}")
            return False

    def insert_products_from_json(self, file_path: Optional[str] = None) -> bool:
        """
        Inserts products from a JSON file into the database.

        Args:
            file_path (str, optional): Path to JSON file. Uses config path if None.

        Returns:
            bool: True if all insertions were successful, False otherwise.
        """
        file_path = file_path or self.config.products_path
        if not file_path:
            logger.error("No products file path provided")
            return False

        try:
            df = pd.read_json(file_path)
        except ValueError as e:
            logger.error(f"Failed to load JSON file: {e}")
            return False

        success = True
        for _, row in df.iterrows():
            product_success = self.insert_product(
                product_name=row.get("product_name"),
                category=row.get("category"),
                description=row.get("description"),
                price=row.get("price"),
                quantity=row.get("quantity"),
            )
            success = success and product_success

        if success:
            logger.info("All products inserted successfully")
        return success

    def insert_customer_if_missing(
        self, customer_id: str, full_name: str, email: str = ""
    ) -> bool:
        """
        Inserts a customer unless a row with the same CustomerId already exists.

        Returns:
            bool: True if the customer exists afterwards, False on error.
        """
        try:
            with self.transaction() as conn:
                existing = conn.execute(
                    text("SELECT CustomerId FROM customers WHERE CustomerId = :cid"),
                    {"cid": customer_id},
                ).fetchone()
                if existing is None:
                    conn.execute(
                        text(
                            "INSERT INTO customers (CustomerId, FullName, Email) "
                            "VALUES (:cid, :name, :email)"
                        ),
                        {"cid": customer_id, "name": full_name, "email": email},
                    )
                    logger.info(f"Successfully inserted customer: {customer_id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error inserting customer {customer_id}: {e}")
            return False

    def product_count(self) -> int:
        """Returns the number of rows in the products table."""
        with self.get_connection() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
