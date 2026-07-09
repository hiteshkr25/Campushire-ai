from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from app.auth.services import AuthService

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(AuthService.get_dashboard_url(current_user))
    return render_template("main/index.html")
