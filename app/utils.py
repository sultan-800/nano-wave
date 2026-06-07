import os

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_product_image(file_storage, image_name):
    if not file_storage or not file_storage.filename:
        return image_name.strip() if image_name else ""

    if not allowed_image(file_storage.filename):
        return None

    original_ext = file_storage.filename.rsplit(".", 1)[1].lower()
    base_name = (image_name or "").strip()

    if base_name:
        if "." in base_name:
            filename = secure_filename(base_name)
        else:
            filename = f"{secure_filename(base_name)}.{original_ext}"
    else:
        filename = secure_filename(file_storage.filename)

    if not filename:
        return None

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))
    return filename


def build_like_search(query, *columns):
    if not query:
        return "", []
    clauses = []
    params = []
    pattern = f"%{query}%"
    for column in columns:
        if column == "id":
            clauses.append("CAST(id AS TEXT) LIKE ?")
        else:
            clauses.append(f"{column} LIKE ?")
        params.append(pattern)
    return f" AND ({' OR '.join(clauses)})", params
