from database.config import DEFAULT_CONFIG
from database.db_manager import DatabaseManager, logger

# CustomerId hardcoded by the Streamlit app (backend/main.py).
DEMO_CUSTOMER_ID = "123456789"


def main():
    """Main function to set up the database and insert initial data."""
    logger.info("Starting database setup...")

    db_manager = DatabaseManager(DEFAULT_CONFIG)

    if not db_manager.create_database():
        logger.error("Failed to create database")
        return False

    if not db_manager.insert_customer_if_missing(
        customer_id=DEMO_CUSTOMER_ID, full_name="Demo Customer"
    ):
        logger.error("Failed to insert demo customer")
        return False

    # Seed products only when the table is empty, so re-running setup is safe.
    if db_manager.product_count() == 0 and not db_manager.insert_products_from_json():
        logger.error("Failed to insert products")
        return False

    logger.info("Database setup completed successfully")
    return True


if __name__ == "__main__":
    main()
