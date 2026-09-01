from flask import Blueprint, render_template, session

from app.auth import login_required
from app.database import get_db_connection


main = Blueprint("main", __name__)


@main.route("/")
def home():
    files = []

    if "user_id" in session:
        db = get_db_connection()

        files = db.execute(
            """
            SELECT
                files.id,
                files.filename,
                files.size,
                files.uploaded_at,
                users.username AS uploader
            FROM files
            LEFT JOIN users
                ON files.uploaded_by = users.id
            ORDER BY files.uploaded_at DESC
            """
        ).fetchall()

        db.close()

    return render_template(
        "index.html",
        logged_in="user_id" in session,
        username=session.get("username"),
        files=files,
    )


@main.route("/dashboard")
@login_required
def dashboard():
    return home()