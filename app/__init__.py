from flask import Flask

from app.database import init_db


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        init_db()

    return app