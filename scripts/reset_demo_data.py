"""Delete and recreate ONLY the demo/seed data defined in scripts/demo_data.py.

Use this to get demo accounts back to a known-good state without touching
any real student/recruiter/TPO data a user has created in the same database.

    python scripts/reset_demo_data.py

Identification of "demo data" is intentionally strict — only records that
exactly match the emails/names/codes in `scripts/demo_data.py` are touched.
If a demo record has real data hanging off it (e.g. a real student applied
to the demo drive, or a real recruiter registered under the demo company),
deletion of that specific record is skipped with a warning rather than
cascading into non-demo data.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.application import Application
from app.models.college import Branch, College, Skill
from app.models.company import Company
from app.models.drive import PlacementDrive
from app.models.user import User
from scripts.demo_data import (
    DEMO_ACCOUNTS,
    DEMO_COLLEGES,
    DEMO_COMPANIES,
    DEMO_DRIVE,
    DEMO_SKILLS,
)
from scripts.seed_helpers import seed_demo_accounts, seed_demo_drive, seed_reference_data


def _safe_delete(obj, label):
    """Delete a single ORM object; roll back and warn instead of raising if
    something else in the database still depends on it."""
    try:
        db.session.delete(obj)
        db.session.commit()
        print(f"Deleted {label}")
        return True
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any FK/DB error should just skip
        db.session.rollback()
        print(f"Skipped deleting {label}: still referenced by other data ({exc.__class__.__name__})")
        return False


def delete_demo_data():
    print("Removing existing demo data (if any)...")

    # 1. Demo placement drive — matched on its full demo identity (title +
    #    college + company), not title alone, so a real drive that happens to
    #    share the same title is never touched. Delete dependent applications
    #    first (RESTRICT FK).
    demo_college = College.query.filter_by(code=DEMO_DRIVE["college_code"]).first()
    demo_company = Company.query.filter(
        db.func.lower(Company.name) == DEMO_DRIVE["company_name"].lower()
    ).first()
    drive = None
    if demo_college and demo_company:
        drive = PlacementDrive.query.filter_by(
            title=DEMO_DRIVE["title"],
            college_id=demo_college.id,
            company_id=demo_company.id,
        ).first()
    if drive:
        apps = Application.query.filter_by(drive_id=drive.id).all()
        for app_row in apps:
            _safe_delete(app_row, f"Application {app_row.id} on demo drive")
        _safe_delete(drive, f"Placement Drive '{drive.title}'")

    # 2. Demo login accounts (cascades to their role profile via ORM relationship).
    # Delete student applications first to prevent ON DELETE RESTRICT FK errors.
    demo_student_data = DEMO_ACCOUNTS.get("student")
    if demo_student_data:
        demo_student_user = User.query.filter_by(email=demo_student_data["email"]).first()
        if demo_student_user and demo_student_user.student_profile:
            student = demo_student_user.student_profile
            apps = Application.query.filter_by(student_id=student.id).all()
            for app_row in apps:
                _safe_delete(app_row, f"Application {app_row.id} for demo student")

    for account in DEMO_ACCOUNTS.values():
        user = User.query.filter_by(email=account["email"]).first()
        if user:
            _safe_delete(user, f"User {account['email']}")

    # 3. Demo companies.
    for comp_data in DEMO_COMPANIES:
        company = Company.query.filter(db.func.lower(Company.name) == comp_data["name"].lower()).first()
        if company:
            _safe_delete(company, f"Company '{company.name}'")

    # 4. Demo colleges. Branches are deleted explicitly first: `Branch` has a
    #    RESTRICT foreign key to `colleges`, and the ORM's `cascade="all,
    #    delete-orphan"` on a `lazy="dynamic"` relationship does not reliably
    #    flush child deletes before the parent DELETE statement.
    for c_data in DEMO_COLLEGES:
        college = College.query.filter_by(code=c_data["code"]).first()
        if not college:
            continue
        branches = Branch.query.filter_by(college_id=college.id).all()
        all_branches_deleted = True
        for branch in branches:
            if not _safe_delete(branch, f"Branch '{branch.code}' ({college.code})"):
                all_branches_deleted = False
        if all_branches_deleted:
            _safe_delete(college, f"College '{college.code}'")
        else:
            print(f"Skipped deleting College '{college.code}': branches still in use")

    # 5. Demo skills.
    for sk_name in DEMO_SKILLS:
        skill = Skill.query.filter_by(name=sk_name).first()
        if skill:
            _safe_delete(skill, f"Skill '{sk_name}'")


def main():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        delete_demo_data()

        print("\nRecreating demo data...")
        for line in seed_reference_data():
            print(line)
        for line in seed_demo_accounts():
            print(line)
        print(seed_demo_drive())

        print("\nDemo data reset completed successfully.")
        print("Demo credentials: see docs/DEMO_CREDENTIALS.md")


if __name__ == "__main__":
    main()
