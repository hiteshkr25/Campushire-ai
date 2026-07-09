from sqlalchemy.dialects.postgresql import CITEXT

from app.extensions import db
from app.models.base import BaseModel, BaseModelCreatedOnly


class College(BaseModel):
    __tablename__ = "colleges"
    __table_args__ = (
        db.UniqueConstraint("code", name="uq_colleges_code"),
        db.Index("idx_colleges_is_active", "is_active"),
    )

    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    university = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), nullable=False, default="India")
    contact_email = db.Column(CITEXT)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    branches = db.relationship(
        "Branch",
        backref="college",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    students = db.relationship(
        "Student",
        backref="college",
        passive_deletes=True,
        lazy="dynamic",
    )
    tpo_admins = db.relationship(
        "TpoAdmin",
        backref="college",
        passive_deletes=True,
        lazy="dynamic",
    )
    placement_drives = db.relationship(
        "PlacementDrive",
        backref="college",
        passive_deletes=True,
        lazy="dynamic",
    )
    announcements = db.relationship(
        "Announcement",
        backref="college",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    placement_statistics = db.relationship(
        "PlacementStatistic",
        backref="college",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<College {self.code}: {self.name}>"


class Branch(BaseModel):
    __tablename__ = "branches"
    __table_args__ = (
        db.UniqueConstraint("college_id", "code", name="uq_branches_college_code"),
        db.Index("idx_branches_college_id", "college_id"),
    )

    college_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    degree = db.Column(db.String(100))
    duration_years = db.Column(db.SmallInteger)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    students = db.relationship(
        "Student",
        backref="branch",
        passive_deletes=True,
        lazy="dynamic",
    )
    drive_branches = db.relationship(
        "DriveBranch",
        backref="branch",
        passive_deletes=True,
        lazy="dynamic",
    )
    placement_statistics = db.relationship(
        "PlacementStatistic",
        backref="branch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Branch {self.code}: {self.name}>"


class Skill(BaseModelCreatedOnly):
    __tablename__ = "skills"
    __table_args__ = (db.UniqueConstraint("name", name="uq_skills_name"),)

    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))

    student_skills = db.relationship(
        "StudentSkill",
        backref="skill",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Skill {self.name}>"
