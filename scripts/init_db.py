"""Idempotent database bootstrap for CampusHire AI.

Safe to run against a completely empty PostgreSQL database, or against an
existing one with data already in it:

    python scripts/init_db.py

What it does, in order:
1. Enables required Postgres extensions (pgcrypto, citext).
2. Creates any tables that don't exist yet (`db.create_all()` — never drops
   or alters existing tables/columns).
3. Detects and repairs legacy-cased enum values left behind by older schema
   versions (see `scripts/db_maintenance.py` for why this is needed).
4. Seeds/updates baseline reference data (colleges, branches, skills,
   companies) and demo login accounts for every role, plus one sample
   placement drive — never creating duplicates, always converging existing
   records to the values in `scripts/demo_data.py`.

Demo credentials are documented in `docs/DEMO_CREDENTIALS.md`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from scripts.db_maintenance import migrate_legacy_enum_values
from scripts.seed_helpers import (
    seed_demo_accounts,
    seed_demo_drive,
    seed_reference_data,
)


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def should_seed_demo_data():
    """Demo/reference data (sample colleges, companies, and login accounts
    with known passwords) is seeded by default in development, but NEVER in
    production unless explicitly opted into with SEED_DEMO_DATA=true — a
    predictable admin-capable account is a real security risk in a live
    deployment. Schema creation and enum repair always run regardless."""
    if _truthy(os.environ.get("SEED_DEMO_DATA", "")):
        return True
    return os.environ.get("FLASK_ENV", "development").strip().lower() != "production"


def seed_data():
    """Backward/forward-compatible entry point used by other scripts
    (e.g. scripts/e2e_verification.py) that need reference + demo data
    present without re-running schema/enum maintenance."""
    lines = []
    lines.extend(seed_reference_data())
    lines.extend(seed_demo_accounts())
    lines.append(seed_demo_drive())
    return lines


def main():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        db.session.execute(db.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        db.session.execute(db.text("CREATE EXTENSION IF NOT EXISTS citext;"))
        db.session.commit()

        db.create_all()
        print("Database tables validated.")

        repaired = migrate_legacy_enum_values(db.engine)
        if repaired:
            print("Repaired legacy enum values:")
            for line in repaired:
                print(f"  - {line}")
        else:
            print("Enum values validated — no legacy data found.")

        if should_seed_demo_data():
            for line in seed_data():
                print(line)
            print("\nDatabase initialization completed successfully.")
            print("Demo credentials: see docs/DEMO_CREDENTIALS.md")
        else:
            print(
                "\nSkipping demo/reference data seeding (FLASK_ENV=production). "
                "Set SEED_DEMO_DATA=true to seed demo accounts anyway."
            )
            print("\nDatabase initialization completed successfully.")


if __name__ == "__main__":
    main()
