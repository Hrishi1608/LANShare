import os
from pathlib import Path

from flask import Flask

from app.database import init_db


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "dev-secret-key-change-this",
    )

    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

    # Maximum upload size: 16 MB for the MVP.
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    UPLOAD_FOLDER.mkdir(exist_ok=True)

    from app.auth import auth
    from app.files import files
    from app.routes import main

    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(files, url_prefix="/files")

    with app.app_context():
        init_db()

    return app