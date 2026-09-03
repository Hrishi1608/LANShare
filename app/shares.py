import secrets
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import login_required
from app.database import (
    create_share,
    get_file_by_id,
    get_share_by_id,
    get_share_by_token,
    get_shares_for_user,
    increment_share_downloads,
    log_action,
    revoke_share,
)


shares = Blueprint("shares", __name__)

# How long a link stays valid, in hours. "0" means "never expires".
EXPIRY_OPTIONS = {
    "1": 1,
    "24": 24,
    "168": 168,  # 7 days
    "0": None,
}


def _share_status(share):
    """Return None if the share is usable, or a short reason string if not."""
    if share is None:
        return "not_found"

    if share["revoked"]:
        return "revoked"

    if share["expires_at"]:
        expires_at = datetime.strptime(share["expires_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() > expires_at:
            return "expired"

    if share["max_downloads"] is not None and share["download_count"] >= share["max_downloads"]:
        return "limit_reached"

    return None


@shares.route("/share/new/<int:file_id>", methods=("GET", "POST"))
@login_required
def new(file_id):
    file_row = get_file_by_id(file_id)

    if file_row is None:
        abort(404)

    is_owner = file_row["uploaded_by"] == session.get("user_id")
    is_admin = session.get("role") == "admin"

    if not (is_owner or is_admin):
        abort(403)

    if request.method == "POST":
        expiry_key = request.form.get("expiry", "24")
        password = request.form.get("password", "").strip()
        max_downloads_raw = request.form.get("max_downloads", "").strip()

        expiry_hours = EXPIRY_OPTIONS.get(expiry_key, 24)
        expires_at = None
        if expiry_hours is not None:
            expires_at = (datetime.utcnow() + timedelta(hours=expiry_hours)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        password_hash = None
        if password:
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        max_downloads = None
        if max_downloads_raw.isdigit() and int(max_downloads_raw) > 0:
            max_downloads = int(max_downloads_raw)

        token = secrets.token_urlsafe(16)

        create_share(
            file_id=file_id,
            token=token,
            password_hash=password_hash,
            expires_at=expires_at,
            max_downloads=max_downloads,
            created_by=session.get("user_id"),
        )

        log_action(
            user_id=session.get("user_id"),
            username=session.get("username"),
            action="share_created",
            target=file_row["filename"],
            ip_address=request.remote_addr,
        )

        return redirect(url_for("shares.created", token=token))

    return render_template("share_new.html", file=file_row)


@shares.route("/share/created/<token>")
@login_required
def created(token):
    share = get_share_by_token(token)

    if share is None:
        abort(404)

    share_url = url_for("shares.access", token=token, _external=True)

    return render_template("share_created.html", share=share, share_url=share_url)


@shares.route("/shares")
@login_required
def list_shares():
    is_admin = session.get("role") == "admin"
    user_shares = get_shares_for_user(session.get("user_id"), include_all=is_admin)

    return render_template(
        "shares_list.html",
        shares=user_shares,
        is_admin=is_admin,
        request_host=request.host_url.rstrip("/"),
    )


@shares.route("/shares/<int:share_id>/revoke", methods=("POST",))
@login_required
def revoke(share_id):
    share = get_share_by_id(share_id)

    if share is None:
        abort(404)

    is_owner = share["created_by"] == session.get("user_id")
    is_admin = session.get("role") == "admin"

    if not (is_owner or is_admin):
        abort(403)

    revoke_share(share_id)

    log_action(
        user_id=session.get("user_id"),
        username=session.get("username"),
        action="share_revoked",
        target=f"share#{share_id}",
        ip_address=request.remote_addr,
    )

    flash("Share link revoked.")
    return redirect(url_for("shares.list_shares"))


@shares.route("/s/<token>", methods=("GET", "POST"))
def access(token):
    """Public download endpoint. No login required."""
    share = get_share_by_token(token)

    status = _share_status(share)

    if status is not None:
        return render_template("share_error.html", reason=status), 410 if status != "not_found" else 404

    needs_password = bool(share["password_hash"])

    if needs_password:
        submitted_password = request.form.get("password", "") if request.method == "POST" else None

        if submitted_password is None:
            # No password submitted yet: show the prompt.
            return render_template("share_password.html", token=token)

        if not check_password_hash(share["password_hash"], submitted_password):
            flash("Incorrect password.")
            return render_template("share_password.html", token=token)

    increment_share_downloads(token)

    log_action(
        user_id=None,
        username=None,
        action="share_downloaded",
        target=share["filename"],
        ip_address=request.remote_addr,
    )

    return send_file(
        share["filepath"],
        as_attachment=True,
        download_name=share["filename"],
    )