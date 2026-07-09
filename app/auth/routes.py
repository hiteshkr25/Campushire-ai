from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.auth.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    RecruiterRegistrationForm,
    ResetPasswordForm,
    StudentRegistrationForm,
)
from app.auth.services import AuthService
from app.decorators import anonymous_required, get_client_ip
from app.exceptions import AuthError
from app.extensions import db
from app.utils.url_helpers import is_safe_redirect_url

from . import auth_bp


def _client_meta():
    return {
        "ip_address": get_client_ip(),
        "user_agent": request.headers.get("User-Agent"),
    }


@auth_bp.route("/login", methods=["GET", "POST"])
@anonymous_required
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = AuthService.authenticate(
                form.email.data,
                form.password.data,
                **_client_meta(),
            )
            AuthService.login(
                user,
                remember=form.remember.data,
                **_client_meta(),
            )
            session.permanent = True
            flash("Welcome back!", "success")
            next_url = request.args.get("next")
            if next_url and is_safe_redirect_url(next_url):
                return redirect(next_url)
            return redirect(AuthService.get_dashboard_url(user))
        except AuthError as exc:
            flash(exc.message, "danger")
        except Exception:
            db.session.rollback()
            flash("Unable to sign in. Please try again.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register/student", methods=["GET", "POST"])
@anonymous_required
def register_student():
    form = StudentRegistrationForm()
    if form.validate_on_submit():
        try:
            user = AuthService.register_student(
                email=form.email.data,
                password=form.password.data,
                college_code=form.college_code.data,
                branch_code=form.branch_code.data,
                enrollment_number=form.enrollment_number.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                batch=form.batch.data,
                graduation_year=form.graduation_year.data,
                phone=form.phone.data,
            )
            flash(
                "Account created successfully. Please sign in after TPO verification.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except AuthError as exc:
            flash(exc.message, "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(e)
            flash(f"Registration failed: {str(e)}", "danger")

    return render_template("auth/register_student.html", form=form)


@auth_bp.route("/register/recruiter", methods=["GET", "POST"])
@anonymous_required
def register_recruiter():
    form = RecruiterRegistrationForm()
    if form.validate_on_submit():
        try:
            AuthService.register_recruiter(
                email=form.email.data,
                password=form.password.data,
                company_name=form.company_name.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                designation=form.designation.data,
                phone=form.phone.data,
            )
            flash(
                "Recruiter account created. You can sign in after admin approval.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except AuthError as exc:
            flash(exc.message, "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(e)
            flash(f"Registration failed: {str(e)}", "danger")

    return render_template("auth/register_recruiter.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    AuthService.logout(current_user, **_client_meta())
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@anonymous_required
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            AuthService.request_password_reset(form.email.data, **_client_meta())
        except Exception:
            db.session.rollback()
        flash(
            "If an account exists for that email, a password reset link has been sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@anonymous_required
def reset_password(token):
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            AuthService.reset_password(
                token,
                form.password.data,
                **_client_meta(),
            )
            flash("Your password has been updated. Please sign in.", "success")
            return redirect(url_for("auth.login"))
        except AuthError as exc:
            flash(exc.message, "danger")
        except Exception:
            db.session.rollback()
            flash("Unable to reset password. Please request a new link.", "danger")

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            AuthService.change_password(
                current_user,
                form.current_password.data,
                form.new_password.data,
                **_client_meta(),
            )
            flash("Password updated successfully.", "success")
            return redirect(AuthService.get_dashboard_url(current_user))
        except AuthError as exc:
            flash(exc.message, "danger")
        except Exception:
            db.session.rollback()
            flash("Unable to update password. Please try again.", "danger")

    return render_template("auth/change_password.html", form=form)
