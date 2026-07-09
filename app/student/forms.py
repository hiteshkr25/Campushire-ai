from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, Regexp, URL, ValidationError


PHONE_VALIDATORS = [
    Optional(),
    Regexp(r"^[+]?[0-9]{10,15}$", message="Enter a valid phone number."),
]


class StudentProfileForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=100)])
    phone = StringField("Phone", validators=PHONE_VALIDATORS)
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    gender = SelectField(
        "Gender",
        choices=[("", "Select gender"), ("female", "Female"), ("male", "Male"), ("non_binary", "Non-binary"), ("prefer_not_to_say", "Prefer not to say")],
        validators=[Optional()],
    )
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1500)])
    linkedin_url = StringField("LinkedIn URL", validators=[Optional(), URL(), Length(max=500)])
    github_url = StringField("GitHub URL", validators=[Optional(), URL(), Length(max=500)])

    enrollment_number = StringField("Enrollment Number", validators=[DataRequired(), Length(max=50)])
    branch_id = SelectField("Branch", validators=[DataRequired()])
    batch = StringField("Batch", validators=[DataRequired(), Length(max=20)])
    semester = IntegerField("Semester", validators=[Optional(), NumberRange(min=1, max=12)])
    graduation_year = IntegerField("Graduation Year", validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    cgpa = DecimalField("CGPA", places=2, validators=[Optional(), NumberRange(min=0, max=10)])
    backlogs_count = IntegerField("Backlogs", validators=[InputRequired(), NumberRange(min=0, max=50)])

    skills = TextAreaField("Skills", validators=[Optional(), Length(max=1500)])
    submit = SubmitField("Save Profile")

    def validate_date_of_birth(self, field):
        if field.data and field.data >= date.today():
            raise ValidationError("Date of birth must be in the past.")


class StudentProjectForm(FlaskForm):
    title = StringField("Project Title", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    tech_stack = StringField("Tech Stack", validators=[Optional(), Length(max=500)])
    project_url = StringField("Project URL", validators=[Optional(), URL(), Length(max=500)])
    repository_url = StringField("Repository URL", validators=[Optional(), URL(), Length(max=500)])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    is_ongoing = BooleanField("This project is ongoing")
    submit = SubmitField("Save Project")

    def validate_end_date(self, field):
        if self.start_date.data and field.data and field.data < self.start_date.data:
            raise ValidationError("End date cannot be before start date.")
        if self.is_ongoing.data and field.data:
            raise ValidationError("Ongoing projects should not have an end date.")


class StudentCertificationForm(FlaskForm):
    name = StringField("Certification Name", validators=[DataRequired(), Length(max=255)])
    issuer = StringField("Issuer", validators=[DataRequired(), Length(max=255)])
    credential_id = StringField("Credential ID", validators=[Optional(), Length(max=100)])
    credential_url = StringField("Credential URL", validators=[Optional(), URL(), Length(max=500)])
    issue_date = DateField("Issue Date", validators=[DataRequired()])
    expiry_date = DateField("Expiry Date", validators=[Optional()])
    submit = SubmitField("Save Certification")

    def validate_issue_date(self, field):
        if field.data and field.data > date.today():
            raise ValidationError("Issue date cannot be in the future.")

    def validate_expiry_date(self, field):
        if self.issue_date.data and field.data and field.data < self.issue_date.data:
            raise ValidationError("Expiry date cannot be before issue date.")


class ResumeUploadForm(FlaskForm):
    resume = FileField(
        "Resume File",
        validators=[
            FileRequired(message="Upload a PDF or DOCX resume."),
            FileAllowed(["pdf", "docx"], message="Only PDF and DOCX files are supported."),
        ],
    )
    is_primary = BooleanField("Set as active resume")
    submit = SubmitField("Upload Resume")


class DriveSearchForm(FlaskForm):
    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional(), Length(max=120)])
    location_type = SelectField(
        "Location",
        choices=[
            ("", "All locations"),
            ("on_campus", "On campus"),
            ("off_campus", "Off campus"),
            ("virtual", "Virtual"),
            ("hybrid", "Hybrid"),
        ],
        validators=[Optional()],
    )
    min_package = DecimalField(
        "Minimum package (LPA)",
        places=2,
        validators=[Optional(), NumberRange(min=0, max=999)],
    )
    eligibility = SelectField(
        "Eligibility",
        choices=[
            ("", "All drives"),
            ("eligible", "Eligible only"),
            ("not_eligible", "Not eligible"),
        ],
        validators=[Optional()],
    )
    sort = SelectField(
        "Sort by",
        choices=[
            ("deadline", "Registration deadline"),
            ("package", "Highest package"),
            ("newest", "Recently published"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Apply Filters")


class ApplicationForm(FlaskForm):
    resume_id = SelectField("Resume", validators=[DataRequired()], coerce=str)
    cover_note = TextAreaField("Cover note", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Submit Application")


class ApplicationSearchForm(FlaskForm):
    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional(), Length(max=120)])
    status = SelectField(
        "Status",
        choices=[
            ("", "All statuses"),
            ("submitted", "Submitted"),
            ("under_review", "Under review"),
            ("shortlisted", "Shortlisted"),
            ("interview_in_progress", "Interview in progress"),
            ("selected", "Selected"),
            ("offered", "Offered"),
            ("placed", "Placed"),
            ("rejected", "Rejected"),
            ("withdrawn", "Withdrawn"),
            ("not_selected", "Not selected"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Apply Filters")


class ProfileChangeRequestForm(FlaskForm):
    field_name = SelectField(
        "Field to Change",
        choices=[
            ("first_name", "First Name"),
            ("last_name", "Last Name"),
            ("date_of_birth", "Date of Birth"),
            ("gender", "Gender"),
            ("enrollment_number", "Enrollment Number"),
            ("branch_id", "Branch"),
            ("batch", "Batch"),
            ("graduation_year", "Graduation Year"),
            ("email", "Official College Email"),
        ],
        validators=[DataRequired()],
    )
    requested_value = StringField("Requested Value", validators=[DataRequired(), Length(max=500)])
    reason = TextAreaField("Reason for Change", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Submit Request")
