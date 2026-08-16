from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import text

from database.db_manager import DatabaseManager

db_manager = DatabaseManager()


@tool
def get_available_categories() -> Dict[str, List[str]]:
    """Returns a list of available product categories."""
    with db_manager.get_connection() as conn:
        categories = (
            conn.execute(text("SELECT DISTINCT Category FROM products WHERE Quantity > 0"))
            .mappings()
            .all()
        )
        return {"categories": [row["Category"] for row in categories]}


@tool
def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Searches for products based on various criteria.

    Arguments:
        query (Optional[str]): Search term for product name or description
        category (Optional[str]): Filter by product category
        min_price (Optional[float]): Minimum price filter
        max_price (Optional[float]): Maximum price filter

    Returns:
        Dict[str, Any]: Search results with products and metadata

    Example:
        search_products(query="banana", category="fruits", max_price=5.00)
    """
    with db_manager.get_connection() as conn:
        query_parts = ["SELECT * FROM products WHERE Quantity > 0"]
        params: Dict[str, Any] = {}

        if query:
            query_parts.append(
                "AND (LOWER(ProductName) LIKE :search_term "
                "OR LOWER(Description) LIKE :search_term)"
            )
            params["search_term"] = f"%{query.lower()}%"

        if category:
            query_parts.append("AND LOWER(Category) = :category")
            params["category"] = category.lower()

        if min_price is not None:
            query_parts.append("AND Price >= :min_price")
            params["min_price"] = min_price

        if max_price is not None:
            query_parts.append("AND Price <= :max_price")
            params["max_price"] = max_price

        # Execute search query
        products = conn.execute(text(" ".join(query_parts)), params).mappings().all()

        # Get available categories for metadata
        categories = (
            conn.execute(
                text(
                    """
                    SELECT DISTINCT Category, COUNT(*) AS count
                    FROM products
                    WHERE Quantity > 0
                    GROUP BY Category
                    """
                )
            ).mappings().all()
        )

        # Get price range for metadata
        price_stats = (
            conn.execute(
                text(
                    """
                    SELECT MIN(Price) AS min_price, MAX(Price) AS max_price, AVG(Price) AS avg_price
                    FROM products
                    WHERE Quantity > 0
                    """
                )
            ).mappings().first()
        )

        return {
            "status": "success",
            "products": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in products
            ],
            "metadata": {
                "total_results": len(products),
                "categories": [
                    {"name": cat["Category"], "product_count": cat["count"]}
                    for cat in categories
                ],
                "price_range": {
                    "min": float(price_stats["min_price"]),
                    "max": float(price_stats["max_price"]),
                    "average": round(float(price_stats["avg_price"]), 2),
                },
            },
        }


@tool
def create_order(
    products: List[Dict[str, Any]], *, config: RunnableConfig
) -> Dict[str, str]:
    """
    Creates a new order (product purchase) for the customer.

     Arguments:
         products (List[Dict[str, Any]]): The list of products to be purchased.

     Returns:
         Dict[str, str]: Order details including status and message

     Example:
         create_order([{"ProductName": "Product A", "Quantity": 2}, {"ProductName": "Product B", "Quantity": 1}])
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    try:
        with db_manager.transaction() as conn:
            # Create order
            conn.execute(
                text(
                    "INSERT INTO orders (CustomerId, OrderDate, Status) "
                    "VALUES (:customer_id, :order_date, 'Pending')"
                ),
                {
                    "customer_id": customer_id,
                    "order_date": datetime.now().isoformat(),
                },
            )
            order_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            total_amount = Decimal("0")
            ordered_products = []

            # Process each product
            for item in products:
                product_name = item["ProductName"]
                quantity = item["Quantity"]

                # Get product details
                product = (
                    conn.execute(
                        text(
                            "SELECT ProductId, Price, Quantity FROM products "
                            "WHERE LOWER(ProductName) = LOWER(:product_name)"
                        ),
                        {"product_name": product_name},
                    )
                    .mappings()
                    .first()
                )

                if not product:
                    raise ValueError(f"Product not found: {product_name}")

                if product["Quantity"] < quantity:
                    raise ValueError(f"Insufficient stock for {product_name}")

                # Add order detail
                conn.execute(
                    text(
                        "INSERT INTO orders_details (OrderId, ProductId, Quantity, UnitPrice) "
                        "VALUES (:order_id, :product_id, :quantity, :unit_price)"
                    ),
                    {
                        "order_id": order_id,
                        "product_id": product["ProductId"],
                        "quantity": quantity,
                        "unit_price": product["Price"],
                    },
                )

                # Update inventory
                conn.execute(
                    text(
                        "UPDATE products SET Quantity = Quantity - :quantity "
                        "WHERE ProductId = :product_id"
                    ),
                    {"quantity": quantity, "product_id": product["ProductId"]},
                )

                total_amount += Decimal(str(product["Price"])) * Decimal(str(quantity))
                ordered_products.append(
                    {
                        "name": product_name,
                        "quantity": quantity,
                        "unit_price": float(product["Price"]),
                    }
                )

        return {
            "order_id": str(order_id),
            "status": "success",
            "message": "Order created successfully",
            "total_amount": float(total_amount),
            "products": ordered_products,
            "customer_id": str(customer_id),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "customer_id": str(customer_id),
        }


@tool
def check_order_status(
    order_id: Union[str, None], *, config: RunnableConfig
) -> Dict[str, Union[str, None]]:
    """
    Checks the status of a specific order or all customer orders.

    Arguments:
        order_id (Union[str, None]): The ID of the order to check. If None, all customer orders will be returned.
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        if order_id:
            # Query specific order
            order = conn.execute(
                text(
                    """
                    SELECT
                        o.OrderId,
                        o.OrderDate,
                        o.Status,
                        GROUP_CONCAT(CONCAT(p.ProductName, ' (x', od.Quantity, ')')) as Products,
                        SUM(od.Quantity * od.UnitPrice) as TotalAmount
                    FROM orders o
                    JOIN orders_details od ON o.OrderId = od.OrderId
                    JOIN products p ON od.ProductId = p.ProductId
                    WHERE o.OrderId = :order_id AND o.CustomerId = :customer_id
                    GROUP BY o.OrderId, o.OrderDate, o.Status
                    """
                ),
                {"order_id": order_id, "customer_id": customer_id},
            ).mappings().first()

            if not order:
                return {
                    "status": "error",
                    "message": "Order not found",
                    "customer_id": str(customer_id),
                    "order_id": str(order_id),
                }

            return {
                "status": "success",
                "order_id": str(order["OrderId"]),
                "order_date": order["OrderDate"],
                "order_status": order["Status"],
                "products": order["Products"],
                "total_amount": float(order["TotalAmount"]),
                "customer_id": str(customer_id),
            }
        else:
            # Query all customer orders
            orders = conn.execute(
                text(
                    """
                    SELECT
                        o.OrderId,
                        o.OrderDate,
                        o.Status,
                        COUNT(od.OrderDetailId) as ItemCount,
                        SUM(od.Quantity * od.UnitPrice) as TotalAmount
                    FROM orders o
                    JOIN orders_details od ON o.OrderId = od.OrderId
                    WHERE o.CustomerId = :customer_id
                    GROUP BY o.OrderId, o.OrderDate, o.Status
                    ORDER BY o.OrderDate DESC
                    """
                ),
                {"customer_id": customer_id},
            ).mappings().all()

            return {
                "status": "success",
                "customer_id": str(customer_id),
                "orders": [
                    {
                        "order_id": str(order["OrderId"]),
                        "order_date": order["OrderDate"],
                        "status": order["Status"],
                        "item_count": order["ItemCount"],
                        "total_amount": float(order["TotalAmount"]),
                    }
                    for order in orders
                ],
            }


@tool
def search_products_recommendations(config: RunnableConfig) -> Dict[str, str]:
    """Searches for product recommendations for the customer."""
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        # Get customer's previous purchases
        favorite_categories = conn.execute(
            text(
                """
                SELECT p.Category
                FROM orders o
                JOIN orders_details od ON o.OrderId = od.OrderId
                JOIN products p ON od.ProductId = p.ProductId
                WHERE o.CustomerId = :customer_id
                GROUP BY p.Category
                ORDER BY MAX(o.OrderDate) DESC
                LIMIT 3
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

        if not favorite_categories:
            # If no purchase history, recommend popular products
            recommendations = conn.execute(
                text(
                    """
                    SELECT
                        ProductId,
                        ProductName,
                        Category,
                        Description,
                        Price,
                        Quantity
                    FROM products
                    WHERE Quantity > 0
                    ORDER BY RAND()
                    LIMIT 5
                    """
                )
            ).mappings().all()
        else:
            # Recommend products from favorite categories
            placeholders = ", ".join(
                f":cat{i}" for i in range(len(favorite_categories))
            )
            categories = [cat["Category"] for cat in favorite_categories]

            recommendations = conn.execute(
                text(
                    f"""
                    SELECT
                        ProductId,
                        ProductName,
                        Category,
                        Description,
                        Price,
                        Quantity
                    FROM products
                    WHERE Category IN ({placeholders})
                    AND Quantity > 0
                    ORDER BY RAND()
                    LIMIT 5
                    """
                ),
                {f"cat{i}": category for i, category in enumerate(categories)},
            ).mappings().all()

        return {
            "status": "success",
            "customer_id": str(customer_id),
            "recommendations": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in recommendations
            ],
        }
