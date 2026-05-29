import logging
import os
import sqlite3
from datetime import datetime

from flask import Flask, g
from flask_login import LoginManager

from app.config import Config

login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Пожалуйста, войдите в систему."
login_manager.login_message_category = "warning"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app_config("DATABASE_PATH"))
        g.db.row_factory = sqlite3.Row
    return g.db


def current_app_config(key):
    from flask import current_app

    return current_app.config[key]


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrate_orders_table(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
    migrations = {
        "phone": "ALTER TABLE orders ADD COLUMN phone TEXT",
        "delivery_address": "ALTER TABLE orders ADD COLUMN delivery_address TEXT",
        "payment_method": "ALTER TABLE orders ADD COLUMN payment_method TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)
    conn.commit()


def init_db(app):
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT,
        category TEXT NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_price REAL NOT NULL,
        created_at TEXT NOT NULL,
        phone TEXT,
        delivery_address TEXT,
        payment_method TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_from_admin INTEGER NOT NULL DEFAULT 0,
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """

    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(schema)
        conn.commit()
        _migrate_orders_table(conn)

        admin = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if not admin:
            from werkzeug.security import generate_password_hash

            conn.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                ("admin", "admin@example.com", generate_password_hash("admin123"), "admin"),
            )
            conn.commit()

        count_row = conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
        if count_row["cnt"] == 0:
            demo_products = [
                ("Смартфон NanoPhone X", "Флагманский смартфон с OLED дисплеем.", 69990, "placeholder.svg", "Смартфоны", 12),
                ("Ноутбук NanoBook Pro", "Легкий ноутбук для работы и учебы.", 94990, "placeholder.svg", "Ноутбуки", 8),
                ("Наушники WavePods", "Беспроводные наушники с шумоподавлением.", 12990, "placeholder.svg", "Аудио", 25),
                ("Смарт-часы NanoWatch", "Часы с мониторингом активности и здоровья.", 15990, "placeholder.svg", "Гаджеты", 15),
            ]
            conn.executemany(
                """
                INSERT INTO products (title, description, price, image, category, stock)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                demo_products,
            )
            conn.commit()


def configure_logging(app):
    os.makedirs(os.path.dirname(app.config["LOG_FILE"]), exist_ok=True)
    logger = logging.getLogger("nanowave")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(app.config["LOG_FILE"], encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False
    app.logger.info("Application started at %s", datetime.utcnow().isoformat())


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    configure_logging(app)
    init_db(app)

    login_manager.init_app(app)
    app.teardown_appcontext(close_db)

    from app.routes import admin_bp, main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_globals():
        return {
            "support_phone": app.config["SUPPORT_PHONE"],
            "support_phone_tel": app.config["SUPPORT_PHONE_TEL"],
        }

    return app
