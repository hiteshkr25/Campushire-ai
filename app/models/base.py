import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


def serialize_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


class SerializationMixin:
    """Mixin providing dict serialization for API and template helpers."""

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        exclude = set(exclude or [])
        if exclude_relationships:
            exclude.update(
                name
                for name, attr in self.__mapper__.relationships.items()
            )

        columns = include or [column.name for column in self.__table__.columns]
        data = {}
        for column_name in columns:
            if column_name in exclude:
                continue
            data[column_name] = serialize_value(getattr(self, column_name))
        return data


class UUIDPrimaryKeyMixin:
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class CreatedAtMixin:
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TimestampMixin(CreatedAtMixin):
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BaseModel(db.Model, UUIDPrimaryKeyMixin, TimestampMixin, SerializationMixin):
    __abstract__ = True


class BaseModelCreatedOnly(db.Model, UUIDPrimaryKeyMixin, CreatedAtMixin, SerializationMixin):
    __abstract__ = True
