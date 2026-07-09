from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, URL

class CompanyForm(FlaskForm):
    name = StringField("Company Name", validators=[DataRequired(), Length(max=255)])
    legal_name = StringField("Legal Name", validators=[Optional(), Length(max=255)])
    website = StringField("Website URL", validators=[Optional(), URL(), Length(max=500)])
    industry = StringField("Industry", validators=[Optional(), Length(max=100)])
    company_size = SelectField(
        "Company Size",
        choices=[
            ("", "Select company size"),
            ("1-10", "1-10 employees"),
            ("11-50", "11-50 employees"),
            ("51-200", "51-200 employees"),
            ("201-500", "201-500 employees"),
            ("501-1000", "501-1000 employees"),
            ("1000+", "1000+ employees"),
        ],
        validators=[Optional()],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    hq_city = StringField("HQ City", validators=[Optional(), Length(max=100)])
    hq_country = StringField("HQ Country", validators=[Optional(), Length(max=100)])
    contact_email = StringField("Contact Email", validators=[Optional(), Email(), Length(max=255)])
    verification_status = SelectField(
        "Verification Status",
        choices=[
            ("pending", "Pending Verification"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active / Hiring Partner", default=True)
    submit = SubmitField("Save Company")


class CompanyLogoForm(FlaskForm):
    logo = FileField(
        "Company Logo",
        validators=[
            FileRequired(message="Please select an image file to upload."),
            FileAllowed(["png", "jpg", "jpeg"], message="Only PNG, JPG, and JPEG images are supported."),
        ],
    )
    submit = SubmitField("Upload Logo")


class CompanySearchForm(FlaskForm):
    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional(), Length(max=100)])
    verification = SelectField(
        "Verification",
        choices=[
            ("", "All verification statuses"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        validators=[Optional()],
    )
    active = SelectField(
        "Status",
        choices=[
            ("", "All statuses"),
            ("active", "Active only"),
            ("inactive", "Inactive only"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Search")


# ==========================================
# PLACEMENT DRIVE & ROUNDS FORMS
# ==========================================

class PlacementDriveForm(FlaskForm):
    company_id = SelectField("Hiring Company", validators=[DataRequired()], coerce=str)
    title = StringField("Placement Drive Title", validators=[DataRequired(), Length(max=255)])
    job_role = StringField("Job Role", validators=[DataRequired(), Length(max=255)])
    job_description = TextAreaField("Job Description", validators=[DataRequired(), Length(max=5000)])
    vacancies = IntegerField("Vacancies", validators=[DataRequired(), NumberRange(min=1, max=1000)], default=1)
    
    package_min_lpa = DecimalField("Minimum Package (LPA)", places=2, validators=[Optional(), NumberRange(min=0, max=999)])
    package_max_lpa = DecimalField("Maximum Package (LPA)", places=2, validators=[Optional(), NumberRange(min=0, max=999)])
    
    location_type = SelectField(
        "Job Location Type",
        choices=[
            ("on_campus", "On Campus"),
            ("off_campus", "Off Campus"),
            ("virtual", "Virtual"),
            ("hybrid", "Hybrid"),
        ],
        validators=[DataRequired()],
    )
    venue = StringField("Venue / Address", validators=[Optional(), Length(max=255)])
    meeting_link = StringField("Online Meeting Link", validators=[Optional(), URL(), Length(max=500)])
    
    drive_date = DateField("Drive Date", validators=[Optional()])
    registration_deadline = DateField("Registration Deadline Date", validators=[DataRequired()])
    
    status = SelectField(
        "Drive Status",
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("registration_closed", "Registration Closed"),
            ("ongoing", "Ongoing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        validators=[DataRequired()],
        default="draft"
    )
    
    # Target Selection
    eligible_branches = SelectMultipleField("Eligible Branches", validators=[DataRequired()], coerce=str)
    
    # Eligibility rules
    min_cgpa = DecimalField("Minimum CGPA Requirement", places=2, validators=[Optional(), NumberRange(min=0, max=10)], default=0)
    max_backlogs = IntegerField("Maximum Allowed Backlogs", validators=[Optional(), NumberRange(min=0, max=50)], default=0)
    required_skills = StringField("Required Skills (comma separated)", validators=[Optional(), Length(max=500)])
    batch = StringField("Eligible Batch Year", validators=[Optional(), Length(max=50)])
    
    submit = SubmitField("Save Drive")


class InterviewRoundForm(FlaskForm):
    round_name = StringField("Round Name", validators=[DataRequired(), Length(max=100)])
    round_type = SelectField(
        "Round Type",
        choices=[
            ("aptitude", "Aptitude Round"),
            ("coding", "Coding Round"),
            ("technical", "Technical Interview"),
            ("group_discussion", "Group Discussion"),
            ("hr", "HR Interview"),
            ("managerial", "Managerial Interview"),
            ("other", "Other Evaluation"),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField("Description & Guidelines", validators=[Optional(), Length(max=1000)])
    passing_score = DecimalField("Passing Score (if graded)", places=2, validators=[Optional(), NumberRange(min=0, max=1000)])
    sequence_order = IntegerField("Sequence / Order Number", validators=[DataRequired(), NumberRange(min=1, max=100)])
    is_eliminatory = BooleanField("This round is eliminatory (failed candidates are disqualified)", default=True)
    submit = SubmitField("Save Round")


class TpoDriveSearchForm(FlaskForm):
    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional(), Length(max=100)])
    status = SelectField(
        "Status",
        choices=[
            ("", "All statuses"),
            ("draft", "Draft"),
            ("published", "Published"),
            ("registration_closed", "Registration Closed"),
            ("ongoing", "Ongoing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        validators=[Optional()]
    )
    company_id = SelectField("Company", validators=[Optional()], coerce=str)
    submit = SubmitField("Apply Filters")
