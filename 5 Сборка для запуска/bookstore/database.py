from __future__ import annotations

import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from bookstore.config import (
    DB_PATH,
    PLACEHOLDER_IMAGE_PATH,
    SCHEMA_PATH,
    UPLOADED_IMAGES_DIR,
)
from bookstore.documents import generate_required_documents
from bookstore.importer import (
    ProductSeed,
    UserSeed,
    build_client_accounts,
    load_orders,
    load_pickup_points,
    load_products,
    load_staff_users,
    resolve_import_image,
)


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS manufacturers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    discount REAL NOT NULL DEFAULT 0 CHECK (discount >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    description TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    manufacturer_id INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id)
);

CREATE TABLE IF NOT EXISTS pickup_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS order_statuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number INTEGER NOT NULL UNIQUE,
    order_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    pickup_code TEXT NOT NULL,
    pickup_point_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    status_id INTEGER NOT NULL,
    FOREIGN KEY (pickup_point_id) REFERENCES pickup_points(id),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (status_id) REFERENCES order_statuses(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


@dataclass(slots=True)
class SessionUser:
    id: int
    full_name: str
    login: str
    role_name: str


class Database:
    def __init__(self) -> None:
        UPLOADED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_PATH.write_text(SCHEMA_SQL.strip() + "\n", encoding="utf-8")
        self._ensure_database()
        self._migrate_image_paths()
        generate_required_documents()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def _ensure_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA_SQL)
            product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if product_count == 0:
                self._seed_database(connection)

    def _seed_database(self, connection: sqlite3.Connection) -> None:
        roles = ["Гость", "Клиент", "Менеджер", "Администратор"]
        connection.executemany("INSERT INTO roles(name) VALUES (?)", [(role,) for role in roles])

        orders = load_orders()
        staff_users = load_staff_users()
        client_users = build_client_accounts(orders)
        all_users = staff_users + client_users

        role_ids = {
            row["name"]: row["id"]
            for row in connection.execute("SELECT id, name FROM roles")
        }

        connection.executemany(
            """
            INSERT INTO users(full_name, login, password, role_id)
            VALUES (?, ?, ?, ?)
            """,
            [(user.full_name, user.login, user.password, role_ids[user.role]) for user in all_users],
        )

        products = load_products()
        self._insert_reference_values(connection, "categories", sorted({product.category for product in products}))
        self._insert_reference_values(connection, "suppliers", sorted({product.supplier for product in products}))
        self._insert_reference_values(connection, "manufacturers", sorted({product.manufacturer for product in products}))
        self._insert_reference_values(connection, "pickup_points", load_pickup_points())
        self._insert_reference_values(connection, "order_statuses", sorted({order.status for order in orders}))

        category_ids = self._lookup_id_map(connection, "categories")
        supplier_ids = self._lookup_id_map(connection, "suppliers")
        manufacturer_ids = self._lookup_id_map(connection, "manufacturers")

        for product in products:
            image_path = self._store_seed_image(product)
            connection.execute(
                """
                INSERT INTO products(
                    article, name, unit, price, discount, stock, description, image_path,
                    category_id, supplier_id, manufacturer_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.article,
                    product.name,
                    product.unit,
                    product.price,
                    product.discount,
                    product.stock,
                    product.description,
                    image_path,
                    category_ids[product.category],
                    supplier_ids[product.supplier],
                    manufacturer_ids[product.manufacturer],
                ),
            )

        users_by_name = {
            row["full_name"]: row["id"]
            for row in connection.execute("SELECT id, full_name FROM users")
        }
        pickup_point_ids = {
            index: row["id"]
            for index, row in enumerate(connection.execute("SELECT id FROM pickup_points ORDER BY id"), start=1)
        }
        status_ids = self._lookup_id_map(connection, "order_statuses")
        product_rows = {
            row["article"]: row
            for row in connection.execute("SELECT id, article, price FROM products")
        }

        for order in orders:
            connection.execute(
                """
                INSERT INTO orders(
                    order_number, order_date, delivery_date, pickup_code, pickup_point_id, customer_id, status_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_number,
                    order.order_date,
                    order.delivery_date,
                    order.pickup_code,
                    pickup_point_ids[order.pickup_point_index],
                    users_by_name[order.customer_name],
                    status_ids[order.status],
                ),
            )
            order_id = connection.execute(
                "SELECT id FROM orders WHERE order_number = ?",
                (order.order_number,),
            ).fetchone()["id"]
            for article, quantity in order.items:
                if article not in product_rows:
                    continue
                product_row = product_rows[article]
                connection.execute(
                    """
                    INSERT INTO order_items(order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order_id, product_row["id"], quantity, product_row["price"]),
                )

    def _insert_reference_values(self, connection: sqlite3.Connection, table_name: str, values: list[str]) -> None:
        column_name = "address" if table_name == "pickup_points" else "name"
        connection.executemany(
            f"INSERT INTO {table_name}({column_name}) VALUES (?)",
            [(value,) for value in values],
        )

    def _lookup_id_map(self, connection: sqlite3.Connection, table_name: str) -> dict[str, int]:
        column_name = "address" if table_name == "pickup_points" else "name"
        return {
            row[column_name]: row["id"]
            for row in connection.execute(f"SELECT id, {column_name} FROM {table_name}")
        }

    def _store_seed_image(self, product: ProductSeed) -> str | None:
        source_path = resolve_import_image(product.image_name)
        if source_path is None:
            return None
        return self._copy_image_to_storage(source_path, keep_name=source_path.name)

    def _copy_image_to_storage(self, source_path: Path, keep_name: str | None = None) -> str:
        target_name = keep_name or f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
        target_path = UPLOADED_IMAGES_DIR / target_name
        with Image.open(source_path) as image:
            resized_image = image.convert("RGB")
            resized_image.thumbnail((300, 200))
            resized_image.save(target_path)
        return str(target_path.relative_to(DB_PATH.parent.parent))

    def authenticate(self, login: str, password: str) -> SessionUser | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.full_name, users.login, roles.name AS role_name
                FROM users
                JOIN roles ON roles.id = users.role_id
                WHERE users.login = ? AND users.password = ?
                """,
                (login.strip(), password.strip()),
            ).fetchone()
        if row is None:
            return None
        return SessionUser(
            id=row["id"],
            full_name=row["full_name"],
            login=row["login"],
            role_name=row["role_name"],
        )

    def guest_user(self) -> SessionUser:
        return SessionUser(id=0, full_name="Гость", login="", role_name="Гость")

    def get_demo_accounts(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT users.full_name, users.login, users.password, roles.name AS role_name
                FROM users
                JOIN roles ON roles.id = users.role_id
                WHERE roles.name IN ('Клиент', 'Менеджер', 'Администратор')
                GROUP BY roles.name
                ORDER BY CASE roles.name
                    WHEN 'Клиент' THEN 1
                    WHEN 'Менеджер' THEN 2
                    ELSE 3
                END
                """
            ).fetchall()

    def get_products(
        self,
        search_text: str = "",
        discount_filter: str = "Все диапазоны",
        sort_field: str = "name",
        sort_descending: bool = False,
    ) -> list[sqlite3.Row]:
        order_column = {
            "name": "products.name",
            "price": "products.price",
            "stock": "products.stock",
        }.get(sort_field, "products.name")
        conditions: list[str] = []
        parameters: list[object] = []

        if search_text.strip():
            search_value = f"%{search_text.strip().lower()}%"
            conditions.append(
                """
                (
                    lower(products.article) LIKE ?
                    OR lower(products.name) LIKE ?
                    OR lower(categories.name) LIKE ?
                    OR lower(products.description) LIKE ?
                    OR lower(manufacturers.name) LIKE ?
                    OR lower(suppliers.name) LIKE ?
                    OR lower(products.unit) LIKE ?
                )
                """
            )
            parameters.extend([search_value] * 7)

        if discount_filter in {"Все диапазоны", "all", ""}:
            pass
        elif discount_filter == "0-12.99":
            conditions.append("products.discount BETWEEN 0 AND 12.99")
        elif discount_filter == "13-16.99":
            conditions.append("products.discount BETWEEN 13 AND 16.99")
        elif discount_filter == "17+":
            conditions.append("products.discount >= 17")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        direction = "DESC" if sort_descending else "ASC"

        query = f"""
            SELECT
                products.id,
                products.article,
                products.name,
                products.unit,
                products.price,
                products.discount,
                products.stock,
                products.description,
                products.image_path,
                categories.name AS category_name,
                suppliers.name AS supplier_name,
                manufacturers.name AS manufacturer_name
            FROM products
            JOIN categories ON categories.id = products.category_id
            JOIN suppliers ON suppliers.id = products.supplier_id
            JOIN manufacturers ON manufacturers.id = products.manufacturer_id
            {where_clause}
            ORDER BY {order_column} {direction}, products.name ASC
        """
        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def get_reference_data(self) -> dict[str, list[sqlite3.Row]]:
        with self._connect() as connection:
            return {
                "categories": connection.execute("SELECT id, name FROM categories ORDER BY name").fetchall(),
                "suppliers": connection.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall(),
                "manufacturers": connection.execute("SELECT id, name FROM manufacturers ORDER BY name").fetchall(),
                "pickup_points": connection.execute("SELECT id, address FROM pickup_points ORDER BY id").fetchall(),
                "statuses": connection.execute("SELECT id, name FROM order_statuses ORDER BY name").fetchall(),
                "clients": connection.execute(
                    """
                    SELECT users.id, users.full_name
                    FROM users
                    JOIN roles ON roles.id = users.role_id
                    WHERE roles.name = 'Клиент'
                    ORDER BY users.full_name
                    """
                ).fetchall(),
            }

    def get_product_by_id(self, product_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    products.*,
                    categories.name AS category_name,
                    suppliers.name AS supplier_name,
                    manufacturers.name AS manufacturer_name
                FROM products
                JOIN categories ON categories.id = products.category_id
                JOIN suppliers ON suppliers.id = products.supplier_id
                JOIN manufacturers ON manufacturers.id = products.manufacturer_id
                WHERE products.id = ?
                """,
                (product_id,),
            ).fetchone()

    def save_product(self, payload: dict[str, object], new_image_path: Path | None = None) -> None:
        self._validate_product_payload(payload)
        with self._connect() as connection:
            category_id = self._get_or_create_reference(connection, "categories", str(payload["category_name"]))
            supplier_id = self._get_or_create_reference(connection, "suppliers", str(payload["supplier_name"]))
            manufacturer_id = self._get_or_create_reference(connection, "manufacturers", str(payload["manufacturer_name"]))

            stored_image_path = payload.get("image_path")
            if new_image_path is not None:
                old_path = payload.get("image_path")
                stored_image_path = self._copy_image_to_storage(new_image_path)
                self._delete_uploaded_image_if_possible(old_path)

            record = (
                str(payload["article"]).strip(),
                str(payload["name"]).strip(),
                str(payload["unit"]).strip(),
                float(payload["price"]),
                float(payload["discount"]),
                int(payload["stock"]),
                str(payload["description"]).strip(),
                stored_image_path,
                category_id,
                supplier_id,
                manufacturer_id,
            )

            if payload.get("id"):
                connection.execute(
                    """
                    UPDATE products
                    SET article = ?, name = ?, unit = ?, price = ?, discount = ?, stock = ?,
                        description = ?, image_path = ?, category_id = ?, supplier_id = ?, manufacturer_id = ?
                    WHERE id = ?
                    """,
                    (*record, int(payload["id"])),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO products(
                        article, name, unit, price, discount, stock, description, image_path,
                        category_id, supplier_id, manufacturer_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    record,
                )

    def delete_product(self, product_id: int) -> None:
        with self._connect() as connection:
            in_order = connection.execute(
                "SELECT 1 FROM order_items WHERE product_id = ? LIMIT 1",
                (product_id,),
            ).fetchone()
            if in_order:
                raise ValueError("Товар нельзя удалить, потому что он присутствует в заказе.")

            row = connection.execute("SELECT image_path FROM products WHERE id = ?", (product_id,)).fetchone()
            connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            if row:
                self._delete_uploaded_image_if_possible(row["image_path"])

    def get_orders(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    orders.id,
                    orders.order_number,
                    orders.order_date,
                    orders.delivery_date,
                    orders.pickup_code,
                    pickup_points.address AS pickup_address,
                    order_statuses.name AS status_name,
                    users.full_name AS customer_name,
                    COALESCE(SUM(order_items.quantity * order_items.unit_price), 0) AS total_amount
                FROM orders
                JOIN pickup_points ON pickup_points.id = orders.pickup_point_id
                JOIN order_statuses ON order_statuses.id = orders.status_id
                JOIN users ON users.id = orders.customer_id
                LEFT JOIN order_items ON order_items.order_id = orders.id
                GROUP BY orders.id
                ORDER BY orders.order_number
                """
            ).fetchall()

    def get_order_by_id(self, order_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    orders.*,
                    pickup_points.address AS pickup_address,
                    order_statuses.name AS status_name,
                    users.full_name AS customer_name
                FROM orders
                JOIN pickup_points ON pickup_points.id = orders.pickup_point_id
                JOIN order_statuses ON order_statuses.id = orders.status_id
                JOIN users ON users.id = orders.customer_id
                WHERE orders.id = ?
                """,
                (order_id,),
            ).fetchone()

    def get_order_items_text(self, order_id: int) -> str:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT products.article, products.name, order_items.quantity
                FROM order_items
                JOIN products ON products.id = order_items.product_id
                WHERE order_items.order_id = ?
                ORDER BY order_items.id
                """,
                (order_id,),
            ).fetchall()
        return ", ".join(f"{row['article']}, {row['quantity']}" for row in rows)

    def save_order(self, payload: dict[str, object]) -> None:
        items = self._parse_order_items(str(payload["items_text"]))
        with self._connect() as connection:
            pickup_point_id = int(payload["pickup_point_id"])
            customer_id = int(payload["customer_id"])
            status_id = int(payload["status_id"])

            if payload.get("id"):
                connection.execute(
                    """
                    UPDATE orders
                    SET order_number = ?, order_date = ?, delivery_date = ?, pickup_code = ?,
                        pickup_point_id = ?, customer_id = ?, status_id = ?
                    WHERE id = ?
                    """,
                    (
                        int(payload["order_number"]),
                        str(payload["order_date"]),
                        str(payload["delivery_date"]),
                        str(payload["pickup_code"]).strip(),
                        pickup_point_id,
                        customer_id,
                        status_id,
                        int(payload["id"]),
                    ),
                )
                order_id = int(payload["id"])
                connection.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            else:
                connection.execute(
                    """
                    INSERT INTO orders(
                        order_number, order_date, delivery_date, pickup_code, pickup_point_id, customer_id, status_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(payload["order_number"]),
                        str(payload["order_date"]),
                        str(payload["delivery_date"]),
                        str(payload["pickup_code"]).strip(),
                        pickup_point_id,
                        customer_id,
                        status_id,
                    ),
                )
                order_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

            for article, quantity in items:
                product_row = connection.execute(
                    "SELECT id, price FROM products WHERE article = ?",
                    (article,),
                ).fetchone()
                if product_row is None:
                    raise ValueError(f"Товар с артикулом {article} не найден.")
                connection.execute(
                    """
                    INSERT INTO order_items(order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order_id, product_row["id"], quantity, product_row["price"]),
                )

    def delete_order(self, order_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM orders WHERE id = ?", (order_id,))

    def next_order_number(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(order_number), 0) + 1 AS next_number FROM orders").fetchone()
        return int(row["next_number"])

    def next_product_id(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM products").fetchone()
        return int(row["next_id"])

    def resolve_image_path(self, stored_path: str | None) -> Path:
        if not stored_path:
            return PLACEHOLDER_IMAGE_PATH
        candidate = DB_PATH.parent.parent / stored_path
        if candidate.exists():
            return candidate
        normalized = str(stored_path).replace("data\\images\\", "5 Сборка для запуска\\images\\")
        candidate = DB_PATH.parent.parent / normalized
        if candidate.exists():
            return candidate
        return PLACEHOLDER_IMAGE_PATH

    def _migrate_image_paths(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, image_path FROM products WHERE image_path IS NOT NULL AND image_path != ''"
            ).fetchall()
            updates: list[tuple[str, int]] = []
            for row in rows:
                image_path = str(row["image_path"])
                if image_path.startswith("data\\images\\"):
                    new_path = image_path.replace("data\\images\\", "5 Сборка для запуска\\images\\", 1)
                    updates.append((new_path, int(row["id"])))
            if updates:
                connection.executemany(
                    "UPDATE products SET image_path = ? WHERE id = ?",
                    updates,
                )

    def _validate_product_payload(self, payload: dict[str, object]) -> None:
        if not str(payload["article"]).strip():
            raise ValueError("Укажите артикул товара.")
        if not str(payload["name"]).strip():
            raise ValueError("Укажите наименование товара.")
        if not str(payload["unit"]).strip():
            raise ValueError("Укажите единицу измерения.")
        if float(payload["price"]) < 0:
            raise ValueError("Цена не может быть отрицательной.")
        if int(payload["stock"]) < 0:
            raise ValueError("Количество на складе не может быть отрицательным.")
        if float(payload["discount"]) < 0:
            raise ValueError("Скидка не может быть отрицательной.")

    def _get_or_create_reference(self, connection: sqlite3.Connection, table_name: str, name: str) -> int:
        row = connection.execute(
            f"SELECT id FROM {table_name} WHERE name = ?",
            (name.strip(),),
        ).fetchone()
        if row:
            return int(row["id"])
        connection.execute(f"INSERT INTO {table_name}(name) VALUES (?)", (name.strip(),))
        return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def _delete_uploaded_image_if_possible(self, stored_path: object) -> None:
        if not stored_path:
            return
        candidate = DB_PATH.parent.parent / str(stored_path)
        if candidate.exists() and candidate.parent == UPLOADED_IMAGES_DIR:
            candidate.unlink()

    def _parse_order_items(self, items_text: str) -> list[tuple[str, int]]:
        raw_parts = [part.strip() for part in items_text.split(",") if part.strip()]
        if len(raw_parts) == 0 or len(raw_parts) % 2 != 0:
            raise ValueError("Строка товаров заказа должна содержать пары: артикул, количество.")
        items: list[tuple[str, int]] = []
        for index in range(0, len(raw_parts), 2):
            article = raw_parts[index]
            quantity = int(raw_parts[index + 1])
            if quantity <= 0:
                raise ValueError("Количество товара в заказе должно быть больше нуля.")
            items.append((article, quantity))
        return items
