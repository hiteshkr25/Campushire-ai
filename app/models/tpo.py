from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import BaseModel


class TpoAdmin(BaseModel):
    __tablename__ = "tpo_admins"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_tpo_admins_user_id"),
        db.Index("idx_tpo_admins_college_id", "college_id"),
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_primary_tpo = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    placement_drives_created = db.relationship(
        "PlacementDrive",
        backref="created_by_tpo",
        foreign_keys="PlacementDrive.created_by_tpo_id",
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
        return f"<TpoAdmin {self.full_name}>"
