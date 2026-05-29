from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import get_db, login_manager
from app.forms.checkout_form import CheckoutForm
from app.forms.login_form import LoginForm
from app.forms.product_form import ProductForm
from app.forms.register_form import RegisterForm
from app.forms.support_form import SupportMessageForm
from app.utils import build_like_search, save_product_image

main_bp = Blueprint("main", __name__)
admin_bp = Blueprint("admin", __name__)

AUTH_REQUIRED_MESSAGE = (
    "Вы не авторизированы! Для этой вкладки войдите или зарегистрируйтесь."
)
PAYMENT_LABELS = {
    "cash": "Наличными при получении",
    "card": "Банковская карта",
    "sbp": "СБП",
}


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


def require_auth_or_redirect():
    if not current_user.is_authenticated:
        flash(AUTH_REQUIRED_MESSAGE, "auth-required")
        return redirect(request.referrer or url_for("main.index"))
    return None


@main_bp.route("/")
def index():
    db = get_db()
    categories = db.execute(
        "SELECT DISTINCT category FROM products WHERE stock > 0 ORDER BY category"
    ).fetchall()
    popular_products = db.execute(
        "SELECT * FROM products WHERE stock > 0 ORDER BY id DESC LIMIT 6"
    ).fetchall()
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

    sql += " ORDER BY CASE WHEN stock > 0 THEN 0 ELSE 1 END, id DESC"
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
            cursor = db.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, 'user')
                """,
                (form.username.data.strip(), form.email.data.strip(), generate_password_hash(form.password.data)),
            )
            db.commit()
            row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            login_user(User(row))
            from flask import current_app

            current_app.logger.info("User registered: %s (%s)", form.username.data.strip(), form.email.data.strip())
            current_app.logger.info("User logged in: %s", row["email"])
            flash("Регистрация выполнена успешно. Вы вошли в аккаунт.", "success")
            return redirect(url_for("main.index"))

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
def cart():
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

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
def add_to_cart(product_id):
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

    db = get_db()
    product_row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product_row:
        abort(404)

    if product_row["stock"] <= 0:
        flash("Товар отсутствует на складе.", "warning")
        return redirect(request.referrer or url_for("main.catalog"))

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


def _get_cart_items(db):
    return db.execute(
        """
        SELECT c.product_id, c.quantity, p.price, p.stock, p.title
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        """,
        (current_user.id,),
    ).fetchall()


@main_bp.route("/order/checkout", methods=["GET", "POST"])
def checkout():
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

    db = get_db()
    cart_items = _get_cart_items(db)

    if not cart_items:
        flash("Корзина пуста.", "warning")
        return redirect(url_for("main.cart"))

    for item in cart_items:
        if item["quantity"] > item["stock"]:
            flash(f"Недостаточно товара '{item['title']}' на складе.", "danger")
            return redirect(url_for("main.cart"))

    total = sum(item["price"] * item["quantity"] for item in cart_items)
    form = CheckoutForm()

    if form.validate_on_submit():
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor = db.execute(
            """
            INSERT INTO orders (
                user_id, total_price, created_at, phone, delivery_address, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                current_user.id,
                total,
                created_at,
                form.phone.data.strip(),
                form.delivery_address.data.strip(),
                form.payment_method.data,
            ),
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

        current_app.logger.info(
            "Order checkout: user_id=%s order_id=%s total=%.2f payment=%s",
            current_user.id,
            order_id,
            total,
            form.payment_method.data,
        )
        flash("Заказ успешно оформлен.", "success")
        return redirect(url_for("main.profile"))

    display_items = db.execute(
        """
        SELECT c.quantity, p.title, p.price
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        """,
        (current_user.id,),
    ).fetchall()
    return render_template("checkout.html", form=form, cart_items=display_items, total=total)


@main_bp.route("/profile")
def profile():
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

    db = get_db()
    orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,),
    ).fetchall()
    return render_template("profile.html", orders=orders, payment_labels=PAYMENT_LABELS)


def _get_order_items(db, order_id):
    return db.execute(
        """
        SELECT oi.quantity, oi.price, p.id AS product_id, p.title, p.image
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    ).fetchall()


@main_bp.route("/order/<int:order_id>")
def order_detail(order_id):
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, current_user.id),
    ).fetchone()
    if not order:
        abort(404)

    items = _get_order_items(db, order_id)
    return render_template(
        "order_detail.html",
        order=order,
        items=items,
        payment_labels=PAYMENT_LABELS,
        is_admin_view=False,
    )


@main_bp.route("/support", methods=["GET", "POST"])
def support():
    redirect_response = require_auth_or_redirect()
    if redirect_response:
        return redirect_response

    db = get_db()
    form = SupportMessageForm()
    if form.validate_on_submit():
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            INSERT INTO support_messages (user_id, message, is_from_admin, is_read, created_at)
            VALUES (?, ?, 0, 0, ?)
            """,
            (current_user.id, form.message.data.strip(), created_at),
        )
        db.commit()
        current_app.logger.info("Support message from user_id=%s", current_user.id)
        flash("Сообщение отправлено. Мы ответим в ближайшее время.", "success")
        return redirect(url_for("main.support"))

    messages = db.execute(
        """
        SELECT * FROM support_messages
        WHERE user_id = ?
        ORDER BY created_at ASC
        """,
        (current_user.id,),
    ).fetchall()
    return render_template("support.html", form=form, messages=messages)


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
    unread_support = db.execute(
        """
        SELECT COUNT(*) AS c FROM support_messages
        WHERE is_from_admin = 0 AND is_read = 0
        """
    ).fetchone()["c"]
    recent_support = db.execute(
        """
        SELECT sm.*, u.username
        FROM support_messages sm
        JOIN users u ON u.id = sm.user_id
        WHERE sm.is_from_admin = 0
        ORDER BY sm.created_at DESC
        LIMIT 5
        """
    ).fetchall()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        unread_support=unread_support,
        recent_support=recent_support,
    )


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
        image_filename = form.image.data.strip() if form.image.data else ""
        if form.image_file.data:
            saved = save_product_image(form.image_file.data, image_filename)
            if saved is None:
                flash("Некорректный файл изображения.", "danger")
                return redirect(request.url)
            image_filename = saved
        elif not image_filename and edit_product:
            image_filename = edit_product["image"] or ""
        elif not image_filename:
            image_filename = "placeholder.svg"

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
                    image_filename,
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
                    image_filename,
                    form.category.data.strip(),
                    form.stock.data,
                ),
            )
            db.commit()
            current_app.logger.info("Admin created product: %s", form.title.data.strip())
            flash("Товар добавлен.", "success")
        return redirect(url_for("admin.admin_products"))

    search_q = request.args.get("q", "").strip()
    filter_category = request.args.get("filter_category", "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    clause, clause_params = build_like_search(
        search_q, "id", "title", "description", "category", "image", "price", "stock"
    )
    sql += clause
    params.extend(clause_params)
    if filter_category:
        sql += " AND category = ?"
        params.append(filter_category)
    sql += " ORDER BY id DESC"
    products = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return render_template(
        "admin/products.html",
        products=products,
        form=form,
        edit_product=edit_product,
        search_q=search_q,
        filter_category=filter_category,
        categories=categories,
    )


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
    search_q = request.args.get("q", "").strip()
    filter_role = request.args.get("filter_role", "").strip()
    sql = "SELECT id, username, email, role FROM users WHERE 1=1"
    params = []
    clause, clause_params = build_like_search(search_q, "id", "username", "email", "role")
    sql += clause
    params.extend(clause_params)
    if filter_role:
        sql += " AND role = ?"
        params.append(filter_role)
    sql += " ORDER BY id DESC"
    users = db.execute(sql, params).fetchall()
    return render_template("admin/users.html", users=users, search_q=search_q, filter_role=filter_role)


@admin_bp.route("/orders")
@login_required
@admin_required
def admin_orders():
    db = get_db()
    search_q = request.args.get("q", "").strip()
    filter_payment = request.args.get("filter_payment", "").strip()
    sql = """
        SELECT o.id, o.user_id, o.total_price, o.created_at, o.phone, o.delivery_address,
               o.payment_method, u.username, u.email
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE 1=1
    """
    params = []
    if search_q:
        pattern = f"%{search_q}%"
        sql += """
            AND (
                CAST(o.id AS TEXT) LIKE ? OR CAST(o.user_id AS TEXT) LIKE ?
                OR o.created_at LIKE ? OR CAST(o.total_price AS TEXT) LIKE ?
                OR COALESCE(o.phone, '') LIKE ? OR COALESCE(o.delivery_address, '') LIKE ?
                OR COALESCE(o.payment_method, '') LIKE ?
                OR u.username LIKE ? OR u.email LIKE ?
            )
        """
        params.extend([pattern] * 9)
    if filter_payment:
        sql += " AND o.payment_method = ?"
        params.append(filter_payment)
    sql += " ORDER BY o.created_at DESC"
    orders = db.execute(sql, params).fetchall()
    return render_template(
        "admin/orders.html",
        orders=orders,
        payment_labels=PAYMENT_LABELS,
        search_q=search_q,
        filter_payment=filter_payment,
    )


@admin_bp.route("/order/<int:order_id>")
@login_required
@admin_required
def admin_order_detail(order_id):
    db = get_db()
    order = db.execute(
        """
        SELECT o.*, u.username, u.email
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()
    if not order:
        abort(404)
    items = _get_order_items(db, order_id)
    return render_template(
        "order_detail.html",
        order=order,
        items=items,
        payment_labels=PAYMENT_LABELS,
        is_admin_view=True,
    )


@admin_bp.route("/support", methods=["GET", "POST"])
@login_required
@admin_required
def admin_support():
    db = get_db()
    user_id = request.args.get("user_id", type=int)
    form = SupportMessageForm()

    if user_id and form.validate_on_submit():
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            INSERT INTO support_messages (user_id, message, is_from_admin, is_read, created_at)
            VALUES (?, ?, 1, 1, ?)
            """,
            (user_id, form.message.data.strip(), created_at),
        )
        db.execute(
            "UPDATE support_messages SET is_read = 1 WHERE user_id = ? AND is_from_admin = 0",
            (user_id,),
        )
        db.commit()
        current_app.logger.info("Admin support reply to user_id=%s", user_id)
        flash("Ответ отправлен.", "success")
        return redirect(url_for("admin.admin_support", user_id=user_id))

    conversations = db.execute(
        """
        SELECT u.id, u.username, u.email,
               MAX(sm.created_at) AS last_message_at,
               SUM(CASE WHEN sm.is_from_admin = 0 AND sm.is_read = 0 THEN 1 ELSE 0 END) AS unread_count
        FROM users u
        INNER JOIN support_messages sm ON sm.user_id = u.id
        GROUP BY u.id
        ORDER BY last_message_at DESC
        """
    ).fetchall()

    messages = []
    selected_user = None
    if user_id:
        selected_user = db.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if selected_user:
            db.execute(
                "UPDATE support_messages SET is_read = 1 WHERE user_id = ? AND is_from_admin = 0",
                (user_id,),
            )
            db.commit()
            messages = db.execute(
                """
                SELECT * FROM support_messages
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()

    return render_template(
        "admin/support.html",
        conversations=conversations,
        messages=messages,
        selected_user=selected_user,
        form=form,
    )
