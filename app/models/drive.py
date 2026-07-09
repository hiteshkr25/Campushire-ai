from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import BaseModel, BaseModelCreatedOnly
from app.models.enums import (
    DriveStatus,
    EligibilityOperator,
    EligibilityRuleType,
    LocationType,
)


class PlacementDrive(BaseModel):
    __tablename__ = "placement_drives"
    __table_args__ = (
        db.Index("idx_placement_drives_company_id", "company_id"),
        db.Index("idx_placement_drives_college_id", "college_id"),
        db.Index("idx_placement_drives_status", "status"),
        db.Index("idx_placement_drives_college_status", "college_id", "status"),
        db.Index("idx_placement_drives_registration_deadline", "registration_deadline"),
    )

    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_tpo_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tpo_admins.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    job_role = db.Column(db.String(255), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    package_min_lpa = db.Column(db.Numeric(8, 2))
    package_max_lpa = db.Column(db.Numeric(8, 2))
    currency = db.Column(db.String(3), nullable=False, default="INR")
    vacancies = db.Column(db.Integer, nullable=False, default=1)
    drive_date = db.Column(db.Date)
    registration_deadline = db.Column(db.DateTime(timezone=True))
    status = db.Column(
        db.Enum(DriveStatus, name="drive_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DriveStatus.DRAFT,
    )
    location_type = db.Column(
        db.Enum(LocationType, name="location_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LocationType.ON_CAMPUS,
    )
    venue = db.Column(db.String(255))
    meeting_link = db.Column(db.String(500))
    published_at = db.Column(db.DateTime(timezone=True))

    drive_branches = db.relationship(
        "DriveBranch",
        backref="drive",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    eligibility_rules = db.relationship(
        "EligibilityRule",
        backref="drive",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    interview_rounds = db.relationship(
        "InterviewRound",
        backref="drive",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    applications = db.relationship(
        "Application",
        backref="drive",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<PlacementDrive {self.title}>"


class DriveBranch(BaseModelCreatedOnly):
    __tablename__ = "drive_branches"
    __table_args__ = (
        db.UniqueConstraint("drive_id", "branch_id", name="uq_drive_branches"),
        db.Index("idx_drive_branches_drive_id", "drive_id"),
        db.Index("idx_drive_branches_branch_id", "branch_id"),
    )

    drive_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("placement_drives.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    def __repr__(self):
        return f"<DriveBranch drive={self.drive_id} branch={self.branch_id}>"


class EligibilityRule(BaseModel):
    __tablename__ = "eligibility_rules"
    __table_args__ = (
        db.Index("idx_eligibility_rules_drive_id", "drive_id"),
        db.Index("idx_eligibility_rules_value_gin", "rule_value", postgresql_using="gin"),
    )

    drive_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("placement_drives.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_type = db.Column(
        db.Enum(EligibilityRuleType, name="eligibility_rule_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    operator = db.Column(
        db.Enum(EligibilityOperator, name="eligibility_operator", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    rule_value = db.Column(JSONB, nullable=False)
    is_mandatory = db.Column(db.Boolean, nullable=False, default=True)
    display_order = db.Column(db.SmallInteger, nullable=False, default=0)

    def __repr__(self):
        return f"<EligibilityRule {self.rule_type.value} drive={self.drive_id}>"
