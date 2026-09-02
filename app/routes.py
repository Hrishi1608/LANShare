from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from app.auth import admin_required, login_required
from app.database import (
    count_admins,
    get_all_users,
    get_db_connection,
    get_user_by_id,
    log_action,
    set_user_role,
)
from app.network import get_hostname, get_local_ip
from app.qrcode_util import generate_qr_png
from app.stats import get_dashboard_stats


main = Blueprint("main", __name__)


@main.route("/")
def home():
    files = []
    local_ip = get_local_ip()
    hostname = get_hostname()
    stats = None

    if "user_id" in session:
        db = get_db_connection()

        files = db.execute(
            """
            SELECT
                files.id,
                files.filename,
                files.size,
                files.uploaded_at,
                files.sha256,
                users.username AS uploader
            FROM files
            LEFT JOIN users
                ON files.uploaded_by = users.id
            ORDER BY files.uploaded_at DESC
            """
        ).fetchall()

        db.close()

        stats = get_dashboard_stats(current_app.config["UPLOAD_FOLDER"])

    return render_template(
        "index.html",
        logged_in="user_id" in session,
        username=session.get("username"),
        role=session.get("role"),
        files=files,
        local_ip=local_ip,
        hostname=hostname,
        stats=stats,
    )


@main.route("/dashboard")
@login_required
def dashboard():
    return home()


@main.route("/history")
@login_required
def history():
    db = get_db_connection()

    transfers = db.execute(
        """
        SELECT
            transfers.id,
            files.filename,
            transfers.transfer_type,
            transfers.status,
            transfers.size,
            transfers.started_at,
            transfers.completed_at
        FROM transfers
        LEFT JOIN files
            ON transfers.file_id = files.id
        ORDER BY transfers.id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "history.html",
        transfers=transfers,
    )


@main.route("/network")
@login_required
def network():
    return render_template(
        "network.html",
        local_ip=get_local_ip(),
        hostname=get_hostname(),
    )


@main.route("/qr-code.png")
@login_required
def qr_code():
    local_ip = get_local_ip()
    lan_url = f"http://{local_ip}:5000"

    buffer = generate_qr_png(lan_url)

    return send_file(buffer, mimetype="image/png")


@main.route("/audit")
@admin_required
def audit():
    db = get_db_connection()

    logs = db.execute(
        """
        SELECT id, username, action, target, ip_address, created_at
        FROM audit_log
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()

    db.close()

    return render_template("audit.html", logs=logs)


@main.route("/admin/users")
@admin_required
def admin_users():
    users = get_all_users()

    return render_template(
        "admin_users.html",
        users=users,
        current_user_id=session.get("user_id"),
    )


@main.route("/admin/users/<int:user_id>/role", methods=("POST",))
@admin_required
def admin_users_update(user_id):
    new_role = request.form.get("role", "").strip()

    if new_role not in ("admin", "user"):
        flash("Invalid role.")
        return redirect(url_for("main.admin_users"))

    target_user = get_user_by_id(user_id)

    if target_user is None:
        flash("User not found.")
        return redirect(url_for("main.admin_users"))

    # Prevent locking everyone out of the admin panel: don't allow demoting
    # the last remaining admin, whether that's yourself or someone else.
    if target_user["role"] == "admin" and new_role == "user" and count_admins() <= 1:
        flash("Can't demote the last remaining admin.")
        return redirect(url_for("main.admin_users"))

    set_user_role(user_id, new_role)

    log_action(
        user_id=session.get("user_id"),
        username=session.get("username"),
        action="role_change",
        target=f"{target_user['username']} -> {new_role}",
        ip_address=request.remote_addr,
    )

    # If an admin changes their own role, refresh the session immediately
    # so the change takes effect without requiring a re-login.
    if user_id == session.get("user_id"):
        session["role"] = new_role

    flash(f"Updated {target_user['username']}'s role to {new_role}.")
    return redirect(url_for("main.admin_users"))