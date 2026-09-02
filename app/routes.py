from flask import Blueprint, current_app, render_template, send_file, session

from app.auth import login_required
from app.database import get_db_connection
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