import os

from flask import Flask

from app.database import init_db


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

    from app.auth import auth
    from app.routes import main

    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix="/auth")

    with app.app_context():
        init_db()

    return app