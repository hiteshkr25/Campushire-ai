import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError

from app.utils.constants import PASSWORD_MIN_LENGTH


def _password_complexity(form, field):
    password = field.data or ""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one digit.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
        render_kw={"placeholder": "you@college.edu", "autocomplete": "email"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={"placeholder": "Enter your password", "autocomplete": "current-password"},
    )
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign In")


class StudentRegistrationForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), _password_complexity],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    college_code = StringField(
        "College Code",
        validators=[
            DataRequired(),
            Length(max=20),
            Regexp(r"^[A-Za-z0-9_-]+$", message="Invalid college code format."),
        ],
    )
    branch_code = StringField(
        "Branch Code",
        validators=[
            DataRequired(),
            Length(max=20),
            Regexp(r"^[A-Za-z0-9_-]+$", message="Invalid branch code format."),
        ],
    )
    enrollment_number = StringField(
        "Enrollment Number",
        validators=[DataRequired(), Length(max=50)],
    )
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=100)])
    batch = StringField("Batch", validators=[DataRequired(), Length(max=20)])
    graduation_year = IntegerField(
        "Graduation Year",
        validators=[DataRequired()],
    )
    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Regexp(r"^[+]?[0-9]{10,15}$", message="Enter a valid phone number."),
        ],
    )
    submit = SubmitField("Create Student Account")

    def validate_graduation_year(self, field):
        if field.data and not (2000 <= field.data <= 2100):
            raise ValidationError("Graduation year must be between 2000 and 2100.")


class RecruiterRegistrationForm(FlaskForm):
    email = StringField(
        "Work Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), _password_complexity],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    company_name = StringField(
        "Company Name",
        validators=[DataRequired(), Length(max=255)],
    )
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=100)])
    designation = StringField("Designation", validators=[Optional(), Length(max=100)])
    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Regexp(r"^[+]?[0-9]{10,15}$", message="Enter a valid phone number."),
        ],
    )
    submit = SubmitField("Create Recruiter Account")


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New Password",
        validators=[DataRequired(), _password_complexity],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired()],
    )
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), _password_complexity],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Update Password")
