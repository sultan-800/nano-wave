from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import get_db, login_manager
from app.forms.login_form import LoginForm
from app.forms.product_form import ProductForm
from app.forms.register_form import RegisterForm

main_bp = Blueprint("main", __name__)
admin_bp = Blueprint("admin", __name__)


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.role = row["role"]

    @property
    def is_admin(self):
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row) if row else None


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


@main_bp.route("/")
def index():
    db = get_db()
    categories = db.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    popular_products = db.execute("SELECT * FROM products ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html", categories=categories, popular_products=popular_products)


@main_bp.route("/catalog")
def catalog():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    db = get_db()

    sql = "SELECT * FROM products WHERE 1=1"
    params = []

    if query:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        pattern = f"%{query}%"
        params.extend([pattern, pattern])

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY id DESC"
    products = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return render_template("catalog.html", products=products, categories=categories, query=query, category=category)


@main_bp.route("/product/<int:product_id>")
def product(product_id):
    db = get_db()
    item = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not item:
        abort(404)
    return render_template("product.html", product=item)


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        db = get_db()
        exists = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?", (form.username.data.strip(), form.email.data.strip())
        ).fetchone()

        if exists:
            flash("Пользователь с таким именем или email уже существует.", "danger")
        else:
            db.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, 'user')
                """,
                (form.username.data.strip(), form.email.data.strip(), generate_password_hash(form.password.data)),
            )
            db.commit()
            flash("Регистрация выполнена успешно. Теперь войдите в аккаунт.", "success")
            from flask import current_app

            current_app.logger.info("User registered: %s (%s)", form.username.data.strip(), form.email.data.strip())
            return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE email = ?", (form.email.data.strip(),)).fetchone()

        if row and check_password_hash(row["password_hash"], form.password.data):
            user = User(row)
            login_user(user)
            from flask import current_app

            current_app.logger.info("User logged in: %s", user.email)
            flash("Вы успешно вошли в систему.", "success")
            return redirect(url_for("main.index"))

        flash("Неверный email или пароль.", "danger")

    return render_template("login.html", form=form)


@main_bp.route("/logout")
@login_required
def logout():
    from flask import current_app

    current_app.logger.info("User logged out: %s", current_user.email)
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/cart")
@login_required
def cart():
    db = get_db()
    rows = db.execute(
        """
        SELECT c.id, c.quantity, p.id AS product_id, p.title, p.price, p.image, p.stock
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        ORDER BY c.id DESC
        """,
        (current_user.id,),
    ).fetchall()
    total = sum(row["price"] * row["quantity"] for row in rows)
    return render_template("cart.html", cart_items=rows, total=total)


@main_bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    db = get_db()
    product_row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product_row:
        abort(404)

    quantity = max(1, int(request.form.get("quantity", 1)))
    existing = db.execute(
        "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ?",
        (current_user.id, product_id),
    ).fetchone()

    if existing:
        new_quantity = existing["quantity"] + quantity
        db.execute("UPDATE cart SET quantity = ? WHERE id = ?", (new_quantity, existing["id"]))
    else:
        db.execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
            (current_user.id, product_id, quantity),
        )
    db.commit()
    flash("Товар добавлен в корзину.", "success")
    return redirect(request.referrer or url_for("main.catalog"))


@main_bp.route("/cart/update/<int:cart_id>", methods=["POST"])
@login_required
def update_cart(cart_id):
    quantity = max(1, int(request.form.get("quantity", 1)))
    db = get_db()
    db.execute("UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?", (quantity, cart_id, current_user.id))
    db.commit()
    flash("Количество товара обновлено.", "info")
    return redirect(url_for("main.cart"))


@main_bp.route("/cart/remove/<int:cart_id>", methods=["POST"])
@login_required
def remove_from_cart(cart_id):
    db = get_db()
    db.execute("DELETE FROM cart WHERE id = ? AND user_id = ?", (cart_id, current_user.id))
    db.commit()
    flash("Товар удален из корзины.", "warning")
    return redirect(url_for("main.cart"))


@main_bp.route("/order/checkout", methods=["POST"])
@login_required
def checkout():
    db = get_db()
    cart_items = db.execute(
        """
        SELECT c.product_id, c.quantity, p.price, p.stock, p.title
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        """,
        (current_user.id,),
    ).fetchall()

    if not cart_items:
        flash("Корзина пуста.", "warning")
        return redirect(url_for("main.cart"))

    for item in cart_items:
        if item["quantity"] > item["stock"]:
            flash(f"Недостаточно товара '{item['title']}' на складе.", "danger")
            return redirect(url_for("main.cart"))

    total = sum(item["price"] * item["quantity"] for item in cart_items)
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cursor = db.execute(
        "INSERT INTO orders (user_id, total_price, created_at) VALUES (?, ?, ?)",
        (current_user.id, total, created_at),
    )
    order_id = cursor.lastrowid

    for item in cart_items:
        db.execute(
            """
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, item["product_id"], item["quantity"], item["price"]),
        )
        db.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (item["quantity"], item["product_id"]),
        )

    db.execute("DELETE FROM cart WHERE user_id = ?", (current_user.id,))
    db.commit()

    from flask import current_app

    current_app.logger.info("Order checkout: user_id=%s order_id=%s total=%.2f", current_user.id, order_id, total)
    flash("Заказ успешно оформлен.", "success")
    return redirect(url_for("main.profile"))


@main_bp.route("/profile")
@login_required
def profile():
    db = get_db()
    orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,),
    ).fetchall()
    return render_template("profile.html", orders=orders)


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    db = get_db()
    stats = {
        "products": db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"],
        "users": db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
        "orders": db.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"],
        "revenue": db.execute("SELECT COALESCE(SUM(total_price), 0) AS s FROM orders").fetchone()["s"],
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/products", methods=["GET", "POST"])
@login_required
@admin_required
def admin_products():
    db = get_db()
    form = ProductForm()
    edit_id = request.args.get("edit")
    edit_product = None

    if edit_id:
        edit_product = db.execute("SELECT * FROM products WHERE id = ?", (edit_id,)).fetchone()
        if edit_product and request.method == "GET":
            form.title.data = edit_product["title"]
            form.description.data = edit_product["description"]
            form.price.data = edit_product["price"]
            form.image.data = edit_product["image"]
            form.category.data = edit_product["category"]
            form.stock.data = edit_product["stock"]

    if form.validate_on_submit():
        from flask import current_app

        if edit_product:
            db.execute(
                """
                UPDATE products
                SET title = ?, description = ?, price = ?, image = ?, category = ?, stock = ?
                WHERE id = ?
                """,
                (
                    form.title.data.strip(),
                    form.description.data.strip(),
                    float(form.price.data),
                    form.image.data.strip() if form.image.data else "",
                    form.category.data.strip(),
                    form.stock.data,
                    edit_product["id"],
                ),
            )
            db.commit()
            current_app.logger.info("Admin updated product id=%s", edit_product["id"])
            flash("Товар обновлен.", "success")
        else:
            db.execute(
                """
                INSERT INTO products (title, description, price, image, category, stock)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    form.title.data.strip(),
                    form.description.data.strip(),
                    float(form.price.data),
                    form.image.data.strip() if form.image.data else "",
                    form.category.data.strip(),
                    form.stock.data,
                ),
            )
            db.commit()
            current_app.logger.info("Admin created product: %s", form.title.data.strip())
            flash("Товар добавлен.", "success")
        return redirect(url_for("admin.admin_products"))

    products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin/products.html", products=products, form=form, edit_product=edit_product)


@admin_bp.route("/products/delete/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()

    from flask import current_app

    current_app.logger.info("Admin deleted product id=%s", product_id)
    flash("Товар удален.", "warning")
    return redirect(url_for("admin.admin_products"))


@admin_bp.route("/users")
@login_required
@admin_required
def admin_users():
    db = get_db()
    users = db.execute("SELECT id, username, email, role FROM users ORDER BY id DESC").fetchall()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/orders")
@login_required
@admin_required
def admin_orders():
    db = get_db()
    orders = db.execute(
        """
        SELECT o.id, o.total_price, o.created_at, u.username, u.email
        FROM orders o
        JOIN users u ON u.id = o.user_id
        ORDER BY o.created_at DESC
        """
    ).fetchall()
    return render_template("admin/orders.html", orders=orders)
