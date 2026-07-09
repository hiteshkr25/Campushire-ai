"""Shared database maintenance helpers used by init_db.py and reset_demo_data.py.

Handles the one thing db.create_all() cannot do for you: once a Postgres ENUM
type exists, SQLAlchemy will never alter its labels again. If an earlier
version of a model defined an Enum column without `values_callable` (so
SQLAlchemy used the Python member *names*, e.g. "APPROVED"), the enum type in
the database is permanently stuck with those labels — even after the model is
fixed to use the lowercase `.value` strings. Any INSERT/UPDATE using the new
lowercase value then fails with:

    invalid input value for enum verification_status: "approved"

`migrate_legacy_enum_values()` detects this drift and repairs it automatically:
1. Adds the correct lowercase label to the Postgres enum type if missing.
2. Rewrites any existing rows still holding the legacy (mismatched-case) label.

It is safe to run on every startup — a healthy database with correctly-cased
enums is a no-op.
"""

from sqlalchemy import text

from app.models.enums import (
    AnnouncementAudience,
    ApplicationStatus,
    AuditAction,
    DriveStatus,
    EligibilityOperator,
    EligibilityRuleType,
    LocationType,
    NotificationType,
    OfferStatus,
    ParseStatus,
    ProfileStatus,
    RoundResultStatus,
    RoundType,
    ScheduleStatus,
    UserRole,
    VerificationStatus,
)

# (postgres_enum_type_name, python_enum_class, table_name, column_name)
ENUM_COLUMN_MAP = [
    ("user_role", UserRole, "users", "role"),
    ("profile_status", ProfileStatus, "students", "profile_status"),
    ("verification_status", VerificationStatus, "companies", "verification_status"),
    ("drive_status", DriveStatus, "placement_drives", "status"),
    ("location_type", LocationType, "placement_drives", "location_type"),
    ("eligibility_rule_type", EligibilityRuleType, "eligibility_rules", "rule_type"),
    ("eligibility_operator", EligibilityOperator, "eligibility_rules", "operator"),
    ("application_status", ApplicationStatus, "applications", "status"),
    ("round_type", RoundType, "interview_rounds", "round_type"),
    ("round_result_status", RoundResultStatus, "round_results", "result_status"),
    ("schedule_status", ScheduleStatus, "interview_schedule", "status"),
    ("offer_status", OfferStatus, "offers", "status"),
    ("notification_type", NotificationType, "notifications", "notification_type"),
    ("announcement_audience", AnnouncementAudience, "announcements", "target_audience"),
    ("parse_status", ParseStatus, "resumes", "parse_status"),
    ("audit_action", AuditAction, "audit_logs", "action"),
]


def _existing_enum_labels(conn, type_name):
    rows = conn.execute(
        text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = :type_name"
        ),
        {"type_name": type_name},
    )
    return {row[0] for row in rows}


def _table_exists(conn, table_name):
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :table_name"
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def migrate_legacy_enum_values(engine):
    """Detect Postgres enum labels that don't match the current Python enum's
    lowercase values (legacy uppercase/mixed-case labels) and repair them."""
    repaired = []

    for type_name, enum_cls, table_name, column_name in ENUM_COLUMN_MAP:
        current_values = {member.value for member in enum_cls}

        with engine.connect() as conn:
            existing_labels = _existing_enum_labels(conn, type_name)

        if not existing_labels:
            continue  # enum type not created yet — db.create_all() will make it correctly

        legacy_labels = existing_labels - current_values
        if not legacy_labels:
            continue

        for legacy_label in legacy_labels:
            correct_value = next(
                (v for v in current_values if v.lower() == legacy_label.lower()),
                None,
            )
            if not correct_value:
                # Unrecognized/unmapped label — leave it alone, not our concern.
                continue

            # 1. Ensure the correct lowercase label exists on the type.
            #    ALTER TYPE ... ADD VALUE cannot run inside a multi-statement
            #    transaction on Postgres < 12, so use an autocommit connection.
            if correct_value not in existing_labels:
                escaped_value = correct_value.replace("'", "''")
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as autocommit_conn:
                    autocommit_conn.execute(
                        text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{escaped_value}'")
                    )

            # 2. Rewrite existing rows still holding the legacy label.
            with engine.connect() as conn:
                if not _table_exists(conn, table_name):
                    continue

            with engine.begin() as conn:
                result = conn.execute(
                    text(
                        f"UPDATE {table_name} SET {column_name} = :new_value "
                        f"WHERE {column_name}::text = :legacy_value"
                    ),
                    {"new_value": correct_value, "legacy_value": legacy_label},
                )
                if result.rowcount:
                    repaired.append(
                        f"{table_name}.{column_name}: {result.rowcount} row(s) migrated "
                        f"'{legacy_label}' -> '{correct_value}'"
                    )

    return repaired
