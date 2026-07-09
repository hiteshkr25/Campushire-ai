from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

from app.extensions import db
from app.models.base import BaseModel, BaseModelCreatedOnly
from app.models.enums import AuditAction


class AuditLog(BaseModelCreatedOnly):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("idx_audit_logs_user_id", "user_id"),
        db.Index("idx_audit_logs_entity", "entity_type", "entity_id"),
        db.Index("idx_audit_logs_created_at", "created_at"),
        db.Index("idx_audit_logs_action", "action"),
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    action = db.Column(
        db.Enum(AuditAction, name="audit_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(UUID(as_uuid=True))
    old_values = db.Column(JSONB)
    new_values = db.Column(JSONB)
    ip_address = db.Column(INET)
    user_agent = db.Column(db.Text)

    def __repr__(self):
        return f"<AuditLog {self.action.value} {self.entity_type}:{self.entity_id}>"


class PlacementStatistic(BaseModel):
    __tablename__ = "placement_statistics"
    __table_args__ = (
        db.UniqueConstraint(
            "college_id",
            "academic_year",
            "branch_id",
            name="uq_placement_statistics",
        ),
        db.Index("idx_placement_statistics_college_year", "college_id", "academic_year"),
    )

    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("branches.id", ondelete="CASCADE"),
    )
    academic_year = db.Column(db.String(9), nullable=False)
    total_students = db.Column(db.Integer, nullable=False, default=0)
    eligible_students = db.Column(db.Integer, nullable=False, default=0)
    placed_students = db.Column(db.Integer, nullable=False, default=0)
    companies_visited = db.Column(db.Integer, nullable=False, default=0)
    drives_conducted = db.Column(db.Integer, nullable=False, default=0)
    highest_package_lpa = db.Column(db.Numeric(8, 2))
    average_package_lpa = db.Column(db.Numeric(8, 2))
    median_package_lpa = db.Column(db.Numeric(8, 2))
    computed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    def __repr__(self):
        return f"<PlacementStatistic {self.academic_year} college={self.college_id}>"
