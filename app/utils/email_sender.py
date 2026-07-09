import logging
import smtplib
from email.message import EmailMessage

from flask import current_app, render_template, url_for

logger = logging.getLogger(__name__)


def send_email(subject, recipients, text_body, html_body=None):
    if not recipients:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if current_app.config.get("MAIL_SUPPRESS_SEND") or current_app.testing:
        logger.info("Email suppressed — To: %s | Subject: %s", recipients, subject)
        logger.debug("Email body: %s", text_body)
        return True

    try:
        with smtplib.SMTP(
            current_app.config["MAIL_SERVER"],
            current_app.config["MAIL_PORT"],
        ) as server:
            if current_app.config.get("MAIL_USE_TLS"):
                server.starttls()
            username = current_app.config.get("MAIL_USERNAME")
            password = current_app.config.get("MAIL_PASSWORD")
            if username and password:
                server.login(username, password)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipients)
        return False


def send_password_reset_email(user, token):
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    subject = f"{current_app.config['APP_NAME']} — Reset your password"
    text_body = render_template(
        "emails/password_reset.txt",
        user=user,
        reset_url=reset_url,
        app_name=current_app.config["APP_NAME"],
    )
    html_body = render_template(
        "emails/password_reset.html",
        user=user,
        reset_url=reset_url,
        app_name=current_app.config["APP_NAME"],
    )
    return send_email(subject, [user.email], text_body, html_body)
