from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import BaseModel
from app.models.enums import (
    ApplicationStatus,
    OfferStatus,
    RoundResultStatus,
    RoundType,
    ScheduleStatus,
)


class Application(BaseModel):
    __tablename__ = "applications"
    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="uq_applications_student_drive"),
        db.Index("idx_applications_student_id", "student_id"),
        db.Index("idx_applications_drive_id", "drive_id"),
        db.Index("idx_applications_status", "status"),
        db.Index("idx_applications_drive_status", "drive_id", "status"),
        db.Index("idx_applications_applied_at", "applied_at"),
    )

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    drive_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("placement_drives.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resume_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("resumes.id", ondelete="SET NULL"),
    )
    status = db.Column(
        db.Enum(ApplicationStatus, name="application_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ApplicationStatus.DRAFT,
    )
    cover_note = db.Column(db.Text)
    applied_at = db.Column(db.DateTime(timezone=True))
    status_updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    round_results = db.relationship(
        "RoundResult",
        backref="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    interview_schedules = db.relationship(
        "InterviewSchedule",
        backref="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    offer = db.relationship(
        "Offer",
        backref="application",
        uselist=False,
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Application student={self.student_id} drive={self.drive_id}>"


class InterviewRound(BaseModel):
    __tablename__ = "interview_rounds"
    __table_args__ = (
        db.UniqueConstraint("drive_id", "round_number", name="uq_interview_rounds_drive_number"),
        db.UniqueConstraint("drive_id", "sequence_order", name="uq_interview_rounds_drive_sequence"),
        db.Index("idx_interview_rounds_drive_id", "drive_id"),
    )

    drive_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("placement_drives.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number = db.Column(db.SmallInteger, nullable=False)
    round_name = db.Column(db.String(100), nullable=False)
    round_type = db.Column(
        db.Enum(RoundType, name="round_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RoundType.OTHER,
    )
    description = db.Column(db.Text)
    passing_score = db.Column(db.Numeric(5, 2))
    sequence_order = db.Column(db.SmallInteger, nullable=False)
    is_eliminatory = db.Column(db.Boolean, nullable=False, default=True)

    round_results = db.relationship(
        "RoundResult",
        backref="round",
        passive_deletes=True,
        lazy="dynamic",
    )
    interview_schedules = db.relationship(
        "InterviewSchedule",
        backref="round",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<InterviewRound {self.round_name} (#{self.round_number})>"


class RoundResult(BaseModel):
    __tablename__ = "round_results"
    __table_args__ = (
        db.UniqueConstraint("application_id", "round_id", name="uq_round_results_application_round"),
        db.Index("idx_round_results_application_id", "application_id"),
        db.Index("idx_round_results_round_id", "round_id"),
        db.Index("idx_round_results_status", "result_status"),
    )

    application_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("interview_rounds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_status = db.Column(
        db.Enum(RoundResultStatus, name="round_result_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RoundResultStatus.SCHEDULED,
    )
    score = db.Column(db.Numeric(5, 2))
    max_score = db.Column(db.Numeric(5, 2), default=100)
    remarks = db.Column(db.Text)
    evaluated_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("recruiters.id", ondelete="SET NULL"),
    )
    evaluated_at = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return f"<RoundResult application={self.application_id} round={self.round_id}>"


class InterviewSchedule(BaseModel):
    __tablename__ = "interview_schedule"
    __table_args__ = (
        db.Index("idx_interview_schedule_application_id", "application_id"),
        db.Index("idx_interview_schedule_round_id", "round_id"),
        db.Index("idx_interview_schedule_start", "scheduled_start"),
        db.Index("idx_interview_schedule_status", "status"),
    )

    application_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("interview_rounds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scheduled_start = db.Column(db.DateTime(timezone=True), nullable=False)
    scheduled_end = db.Column(db.DateTime(timezone=True), nullable=False)
    venue = db.Column(db.String(255))
    meeting_link = db.Column(db.String(500))
    status = db.Column(
        db.Enum(ScheduleStatus, name="schedule_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ScheduleStatus.SCHEDULED,
    )
    rescheduled_from = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("interview_schedule.id", ondelete="SET NULL"),
    )
    notified_at = db.Column(db.DateTime(timezone=True))

    previous_schedule = db.relationship(
        "InterviewSchedule",
        remote_side="InterviewSchedule.id",
        foreign_keys=[rescheduled_from],
        backref=db.backref("rescheduled_children", lazy="dynamic"),
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<InterviewSchedule application={self.application_id} start={self.scheduled_start}>"


class Offer(BaseModel):
    __tablename__ = "offers"
    __table_args__ = (
        db.UniqueConstraint("application_id", name="uq_offers_application_id"),
        db.Index("idx_offers_status", "status"),
        db.Index("idx_offers_application_id", "application_id"),
    )

    application_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    extended_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("recruiters.id", ondelete="RESTRICT"),
        nullable=False,
    )
    package_offered_lpa = db.Column(db.Numeric(8, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    job_location = db.Column(db.String(255))
    joining_date = db.Column(db.Date)
    offer_letter_path = db.Column(db.String(1000))
    status = db.Column(
        db.Enum(OfferStatus, name="offer_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OfferStatus.DRAFT,
    )
    extended_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    responded_at = db.Column(db.DateTime(timezone=True))
    response_note = db.Column(db.Text)

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        default_exclude = {"offer_letter_path"}
        exclude = set(exclude or []) | default_exclude
        return super().to_dict(
            exclude=exclude,
            include=include,
            exclude_relationships=exclude_relationships,
        )

    def __repr__(self):
        return f"<Offer application={self.application_id} status={self.status.value}>"
