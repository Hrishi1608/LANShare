from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from app.auth import login_required
from app.database import get_db_connection


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
            flash("Please select a file.")
            return redirect(url_for("files.upload"))

        if uploaded_file.filename == "":
            flash("Please select a file.")
            return redirect(url_for("files.upload"))

        if not allowed_file(uploaded_file.filename):
            flash("File type is not supported.")
            return redirect(url_for("files.upload"))

        safe_name = secure_filename(uploaded_file.filename)

        if not safe_name:
            flash("Invalid filename.")
            return redirect(url_for("files.upload"))

        unique_name = f"{uuid4().hex}_{safe_name}"

        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(exist_ok=True)

        file_path = upload_folder / unique_name

        uploaded_file.save(file_path)

        file_size = file_path.stat().st_size

        db = get_db_connection()

        db.execute(
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
        db.close()

        flash(f"{safe_name} uploaded successfully.")
        return redirect(url_for("main.home"))

    return render_template("upload.html")