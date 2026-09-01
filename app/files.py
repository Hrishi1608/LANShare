from pathlib import Path
from uuid import uuid4

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
from werkzeug.utils import secure_filename

from app.auth import login_required
from app.database import get_db_connection, log_transfer


files = Blueprint("files", __name__)


ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "zip",
}


def allowed_file(filename):
    """Return True when the filename has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@files.route("/upload", methods=("GET", "POST"))
@login_required
def upload():
    if request.method == "POST":
        uploaded_file = request.files.get("file")

        if uploaded_file is None:
            log_transfer(
                file_id=None,
                transfer_type="upload",
                status="failed",
            )
            flash("Please select a file.")
            return redirect(url_for("files.upload"))

        if uploaded_file.filename == "":
            log_transfer(
                file_id=None,
                transfer_type="upload",
                status="failed",
            )
            flash("Please select a file.")
            return redirect(url_for("files.upload"))

        if not allowed_file(uploaded_file.filename):
            log_transfer(
                file_id=None,
                transfer_type="upload",
                status="failed",
            )
            flash("File type is not supported.")
            return redirect(url_for("files.upload"))

        safe_name = secure_filename(uploaded_file.filename)

        if not safe_name:
            log_transfer(
                file_id=None,
                transfer_type="upload",
                status="failed",
            )
            flash("Invalid filename.")
            return redirect(url_for("files.upload"))

        unique_name = f"{uuid4().hex}_{safe_name}"

        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(exist_ok=True)

        file_path = upload_folder / unique_name

        uploaded_file.save(file_path)

        file_size = file_path.stat().st_size

        db = get_db_connection()

        cursor = db.execute(
            """
            INSERT INTO files (filename, filepath, size, uploaded_by)
            VALUES (?, ?, ?, ?)
            """,
            (
                safe_name,
                str(file_path),
                file_size,
                session["user_id"],
            ),
        )

        db.commit()

        file_id = cursor.lastrowid

        db.close()

        log_transfer(
            file_id=file_id,
            transfer_type="upload",
            status="completed",
            size=file_size,
        )

        flash(f"{safe_name} uploaded successfully.")
        return redirect(url_for("main.home"))

    return render_template("upload.html")


@files.route("/download/<int:file_id>")
@login_required
def download(file_id):
    db = get_db_connection()

    file_record = db.execute(
        """
        SELECT id, filename, filepath
        FROM files
        WHERE id = ?
        """,
        (file_id,),
    ).fetchone()

    db.close()

    if file_record is None:
        log_transfer(
            file_id=None,
            transfer_type="download",
            status="failed",
        )
        flash("File not found.")
        return redirect(url_for("main.home"))

    file_path = Path(file_record["filepath"])

    if not file_path.is_file():
        log_transfer(
            file_id=file_record["id"],
            transfer_type="download",
            status="failed",
        )
        flash("The requested file is no longer available.")
        return redirect(url_for("main.home"))

    log_transfer(
        file_id=file_record["id"],
        transfer_type="download",
        status="completed",
        size=file_path.stat().st_size,
    )

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_record["filename"],
    )


@files.route("/delete/<int:file_id>", methods=("POST",))
@login_required
def delete(file_id):
    db = get_db_connection()

    file_record = db.execute(
        """
        SELECT id, filename, filepath, uploaded_by
        FROM files
        WHERE id = ?
        """,
        (file_id,),
    ).fetchone()

    if file_record is None:
        db.close()
        flash("File not found.")
        return redirect(url_for("main.home"))

    if file_record["uploaded_by"] != session["user_id"]:
        db.close()
        flash("You are not authorized to delete this file.")
        return redirect(url_for("main.home"))

    file_path = Path(file_record["filepath"])

    if file_path.is_file():
        file_path.unlink()

    db.execute(
        "DELETE FROM files WHERE id = ?",
        (file_id,),
    )

    db.commit()
    db.close()

    flash(f"{file_record['filename']} deleted successfully.")
    return redirect(url_for("main.home"))