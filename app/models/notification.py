from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import BaseModel, BaseModelCreatedOnly
from app.models.enums import AnnouncementAudience, NotificationType


class Notification(BaseModelCreatedOnly):
    __tablename__ = "notifications"
    __table_args__ = (
        db.Index("idx_notifications_user_id", "user_id"),
        db.Index("idx_notifications_user_unread", "user_id", "created_at"),
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.Enum(NotificationType, name="notification_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=NotificationType.INFO,
    )
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(UUID(as_uuid=True))
    action_url = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime(timezone=True))

    def mark_read(self):
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)

    def __repr__(self):
        return f"<Notification {self.title} user={self.user_id}>"


class Announcement(BaseModel):
    __tablename__ = "announcements"
    __table_args__ = (
        db.Index("idx_announcements_college_id", "college_id"),
        db.Index("idx_announcements_published_at", "published_at"),
        db.Index("idx_announcements_audience", "target_audience"),
    )

    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
    )
    created_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target_audience = db.Column(
        db.Enum(AnnouncementAudience, name="announcement_audience", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AnnouncementAudience.ALL,
    )
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    expires_at = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return f"<Announcement {self.title}>"
