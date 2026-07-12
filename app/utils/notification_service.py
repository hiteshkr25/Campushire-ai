from datetime import datetime, timezone
import uuid
from app.extensions import db
from app.models.notification import Notification
from app.models.enums import NotificationType

class NotificationService:
    @staticmethod
    def get_icon(category):
        # Maps categories to FontAwesome icons
        icon_mapping = {
            "Profile": "fa-solid fa-user-gear text-info",
            "Resume": "fa-solid fa-file-pdf text-primary",
            "Placement Drive": "fa-solid fa-briefcase text-success",
            "Interview": "fa-solid fa-calendar-check text-warning",
            "Offer": "fa-solid fa-award text-success",
            "Security": "fa-solid fa-shield-halved text-danger",
            "System": "fa-solid fa-circle-info text-secondary",
        }
        return icon_mapping.get(category, "fa-solid fa-circle-info text-secondary")

    @classmethod
    def enrich_notification(cls, notification):
        if not notification:
            return notification

        # Determine Category
        category = "System"
        val = notification.entity_type
        if val:
            val_lower = val.lower()
            if "student" in val_lower or "profile" in val_lower or "user" in val_lower:
                category = "Profile"
            elif "resume" in val_lower:
                category = "Resume"
            elif "drive" in val_lower or "placement" in val_lower:
                category = "Placement Drive"
            elif "interview" in val_lower or "round" in val_lower or "schedule" in val_lower:
                category = "Interview"
            elif "offer" in val_lower:
                category = "Offer"
            elif "security" in val_lower or "auth" in val_lower:
                category = "Security"

        # Determine Priority
        priority = "low"
        t = notification.notification_type
        if t:
            t_val = t.value.lower() if hasattr(t, "value") else str(t).lower()
            if "error" in t_val:
                priority = "high"
            elif "warning" in t_val:
                priority = "medium"

        # Determine Icon Class
        icon_class = cls.get_icon(category)

        # Dynamically set attributes on the notification object in memory
        notification.category = category
        notification.priority = priority
        notification.icon_class = icon_class
        return notification

    @classmethod
    def create_notification(cls, user_id, title, message, notification_type=NotificationType.INFO, entity_type=None, entity_id=None, action_url=None):
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        return cls.enrich_notification(notification)

    @classmethod
    def get_dropdown_notifications(cls, user_id, limit=10):
        # Fetch up to limit, prioritize unread notifications first, then newest first
        unread = Notification.query.filter_by(user_id=user_id, is_read=False)\
            .order_by(Notification.created_at.desc()).limit(limit).all()
        
        read = []
        if len(unread) < limit:
            read = Notification.query.filter_by(user_id=user_id, is_read=True)\
                .order_by(Notification.created_at.desc()).limit(limit - len(unread)).all()
        
        results = unread + read
        for item in results:
            cls.enrich_notification(item)
        return results

    @classmethod
    def get_paginated_notifications(cls, user_id, page=1, per_page=10):
        # Use Flask-SQLAlchemy pagination, sorted newest first
        pagination = Notification.query.filter_by(user_id=user_id)\
            .order_by(Notification.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        for item in pagination.items:
            cls.enrich_notification(item)
        return pagination

    @classmethod
    def mark_read(cls, notification_id):
        notification = Notification.query.filter_by(id=notification_id).first()
        if notification and not notification.is_read:
            notification.mark_read()
            db.session.commit()
        return cls.enrich_notification(notification)

    @classmethod
    def mark_all_read(cls, user_id):
        unread_notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
        now = datetime.now(timezone.utc)
        for notification in unread_notifications:
            notification.is_read = True
            notification.read_at = now
        db.session.commit()
