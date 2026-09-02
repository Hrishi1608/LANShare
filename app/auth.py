from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import get_db_connection, log_action


auth = Blueprint("auth", __name__)


@auth.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("register.html")

        db = get_db_connection()

        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if existing_user:
            db.close()
            flash("Username already exists.")
            return render_template("register.html")

        password_hash = generate_password_hash(
            password,
            method="pbkdf2:sha256",
        )

        cursor = db.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            """,
            (username, password_hash),
        )

        db.commit()

        new_user_id = cursor.lastrowid

        db.close()

        log_action(
            user_id=new_user_id,
            username=username,
            action="register",
            ip_address=request.remote_addr,
        )

        flash("Registration successful. Please log in.")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db_connection()

        user = db.execute(
            """
            SELECT id, username, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        db.close()

        if user is None or not check_password_hash(
            user["password_hash"],
            password,
        ):
            log_action(
                user_id=None,
                username=username,
                action="login_failed",
                ip_address=request.remote_addr,
            )
            flash("Invalid username or password.")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        log_action(
            user_id=user["id"],
            username=user["username"],
            action="login",
            ip_address=request.remote_addr,
        )

        return redirect(url_for("main.home"))

    return render_template("login.html")


@auth.route("/logout")
def logout():
    user_id = session.get("user_id")
    username = session.get("username")

    session.clear()

    log_action(
        user_id=user_id,
        username=username,
        action="logout",
        ip_address=request.remote_addr,
    )

    flash("You have been logged out.")
    return redirect(url_for("main.home"))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please log in to access that page.")
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view