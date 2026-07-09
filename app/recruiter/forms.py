from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, DateTimeLocalField, TextAreaField, DecimalField, DateField
from wtforms.validators import DataRequired, Optional, URL, Length, NumberRange


class InterviewScheduleForm(FlaskForm):
    drive_id = SelectField("Placement Drive", validators=[DataRequired()], coerce=str)
    round_id = SelectField("Interview Round", validators=[DataRequired()], coerce=str)
    application_id = SelectField("Candidate Profile", validators=[DataRequired()], coerce=str)
    scheduled_start = DateTimeLocalField("Start Time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    scheduled_end = DateTimeLocalField("End Time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    venue = StringField("Venue / Physical Location", validators=[Optional(), Length(max=255)])
    meeting_link = StringField("Virtual Meeting Link", validators=[Optional(), URL(), Length(max=500)])


class InterviewEvaluationForm(FlaskForm):
    status = SelectField(
        "Evaluation Status",
        choices=[
            ("passed", "Pass"),
            ("failed", "Fail"),
            ("on_hold", "Hold"),
            ("absent", "Absent")
        ],
        validators=[DataRequired()]
    )
    score = DecimalField("Awarded Score", validators=[Optional(), NumberRange(min=0, max=100)])
    remarks = TextAreaField("Recruiter Remarks / Feedback", validators=[Optional()])


class OfferForm(FlaskForm):
    application_id = SelectField("Select Selected Candidate", validators=[DataRequired()], coerce=str)
    package_offered_lpa = DecimalField("Annual CTC Package (LPA)", validators=[DataRequired(), NumberRange(min=0.1, max=100.0)])
    job_location = StringField("Job Work Location", validators=[DataRequired(), Length(max=255)])
    joining_date = DateField("Tentative Joining Date", format="%Y-%m-%d", validators=[DataRequired()])
    expires_at = DateTimeLocalField("Offer Expiration Date & Time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    offer_letter = FileField(
        "Upload Offer Letter PDF",
        validators=[
            Optional(),
            FileAllowed(["pdf"], "Only PDF offer letters are allowed.")
        ]
    )


class OfferResponseForm(FlaskForm):
    status = SelectField(
        "Response Outcome",
        choices=[
            ("accepted", "Accept Offer"),
            ("declined", "Decline / Reject Offer")
        ],
        validators=[DataRequired()]
    )
    response_note = TextAreaField("Response Feedback / Remarks", validators=[Optional()])
