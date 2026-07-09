from sqlalchemy.dialects.postgresql import CITEXT, UUID

from app.extensions import db
from app.models.base import BaseModel
from app.models.enums import VerificationStatus


class Company(BaseModel):
    __tablename__ = "companies"
    __table_args__ = (
        db.UniqueConstraint("name", name="uq_companies_name"),
        db.Index("idx_companies_verification_status", "verification_status"),
        db.Index("idx_companies_is_active", "is_active"),
    )

    name = db.Column(db.String(255), nullable=False)
    legal_name = db.Column(db.String(255))
    website = db.Column(db.String(500))
    industry = db.Column(db.String(100))
    company_size = db.Column(db.String(50))
    description = db.Column(db.Text)
    hq_city = db.Column(db.String(100))
    hq_country = db.Column(db.String(100), default="India")
    contact_email = db.Column(CITEXT)
    verification_status = db.Column(
        db.Enum(VerificationStatus, name="verification_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )

    recruiters = db.relationship(
        "Recruiter",
        backref="company",
        passive_deletes=True,
        lazy="dynamic",
    )
    placement_drives = db.relationship(
        "PlacementDrive",
        backref="company",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Company {self.name}>"


class Recruiter(BaseModel):
    __tablename__ = "recruiters"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_recruiters_user_id"),
        db.Index("idx_recruiters_company_id", "company_id"),
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_primary_contact = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    round_results_evaluated = db.relationship(
        "RoundResult",
        backref="evaluator",
        foreign_keys="RoundResult.evaluated_by",
        passive_deletes=True,
        lazy="dynamic",
    )
    offers_extended = db.relationship(
        "Offer",
        backref="extender",
        foreign_keys="Offer.extended_by",
        passive_deletes=True,
        lazy="dynamic",
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        data = super().to_dict(
            exclude=exclude,
            include=include,
            exclude_relationships=exclude_relationships,
        )
        data["full_name"] = self.full_name
        return data

    def __repr__(self):
        return f"<Recruiter {self.full_name}>"
