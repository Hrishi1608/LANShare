from flask import Blueprint, render_template, session


main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template(
        "index.html",
        logged_in="user_id" in session,
        username=session.get("username"),
    )