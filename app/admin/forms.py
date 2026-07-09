from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, BooleanField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo


class UserManagementForm(FlaskForm):
    # Core User fields
    email = StringField("Email Address", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[Optional(), Length(min=6, max=255)])
    role = SelectField("System Role", choices=[
        ("student", "Student"),
        ("recruiter", "Recruiter"),
        ("tpo", "TPO Admin"),
        ("admin", "System Admin")
    ], validators=[DataRequired()])
    is_active = BooleanField("Account Active (Enabled)", default=True)
    is_verified = BooleanField("Verified Profile Status", default=True)

    # Student Profile fields
    student_college_id = SelectField("Student College", validators=[Optional()])
    student_branch_id = SelectField("Student Branch", validators=[Optional()])
    student_enrollment_number = StringField("Enrollment Number", validators=[Optional()])
    student_first_name = StringField("First Name", validators=[Optional()])
    student_last_name = StringField("Last Name", validators=[Optional()])
    student_batch = StringField("Admission Batch Year (e.g., 2023-2027)", validators=[Optional()])
    student_graduation_year = IntegerField("Graduation Year", validators=[Optional()])
    student_phone = StringField("Phone Number", validators=[Optional()])

    # Recruiter Profile fields
    recruiter_company_id = SelectField("Recruiter Company", validators=[Optional()])
    recruiter_first_name = StringField("First Name", validators=[Optional()])
    recruiter_last_name = StringField("Last Name", validators=[Optional()])
    recruiter_designation = StringField("Corporate Designation", validators=[Optional()])
    recruiter_phone = StringField("Phone Number", validators=[Optional()])

    # TPO Profile fields
    tpo_college_id = SelectField("TPO College", validators=[Optional()])
    tpo_first_name = StringField("First Name", validators=[Optional()])
    tpo_last_name = StringField("Last Name", validators=[Optional()])
    tpo_designation = StringField("Academic Designation", validators=[Optional()])
    tpo_department = StringField("Department", validators=[Optional()])
    tpo_phone = StringField("Phone Number", validators=[Optional()])


class BulkImportForm(FlaskForm):
    import_file = FileField(
        "Upload CSV User Roster",
        validators=[
            DataRequired(),
            FileAllowed(["csv"], "Only CSV file uploads are allowed.")
        ]
    )


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=6, max=255, message="Password must be at least 6 characters.")
        ]
    )
