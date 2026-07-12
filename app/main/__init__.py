from flask import Blueprint, redirect, render_template, url_for, request, flash
from flask_login import current_user, login_required
from app.auth.services import AuthService
from app.utils.notification_service import NotificationService
from app.models.notification import Notification

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(AuthService.get_dashboard_url(current_user))
    return render_template("main/index.html")


@main_bp.route("/notifications/<uuid:notification_id>")
@login_required
def click_notification(notification_id):
    notify = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if notify:
        NotificationService.mark_read(notify.id)
        if notify.action_url:
            return redirect(notify.action_url)
    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/notifications/<uuid:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notify = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if notify:
        NotificationService.mark_read(notify.id)
        flash("Notification marked as read.", "success")
    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    NotificationService.mark_all_read(current_user.id)
    flash("All notifications marked as read.", "success")
    return redirect(request.referrer or url_for("main.index"))
