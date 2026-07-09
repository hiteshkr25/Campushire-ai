"""CLI script to scan upload folders and purge files not linked in the database."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.student import Resume
from app.models.company import Company
from app.models.application import Offer


def purge_orphans():
    app = create_app(os.environ.get("FLASK_ENV", "production"))
    with app.app_context():
        print("Checking for orphaned files in uploads folders...")

        # 1. Resumes
        resumes_dir = Path("static/uploads/resumes")
        if resumes_dir.exists():
            active_resumes_paths = {Path(r.file_path).resolve() for r in Resume.query.all() if r.file_path}
            for file_path in resumes_dir.rglob("*"):
                if file_path.is_file():
                    if file_path.resolve() not in active_resumes_paths:
                        try:
                            file_path.unlink()
                            print(f"Purged orphaned resume file: {file_path.name}")
                        except Exception as e:
                            print(f"Failed to delete {file_path.name}: {e}")

        # 2. Offers
        offers_dir = Path("static/uploads/offers")
        if offers_dir.exists():
            active_offers_paths = {Path(o.offer_letter_path).resolve() for o in Offer.query.all() if o.offer_letter_path}
            for file_path in offers_dir.glob("*.pdf"):
                if file_path.is_file():
                    if file_path.resolve() not in active_offers_paths:
                        try:
                            file_path.unlink()
                            print(f"Purged orphaned offer letter: {file_path.name}")
                        except Exception as e:
                            print(f"Failed to delete {file_path.name}: {e}")

        # 3. Company Logos
        logos_dir = Path("static/uploads/company_logos")
        if logos_dir.exists():
            active_logos_paths = {Path(c.logo_path).resolve() for c in Company.query.all() if c.logo_path}
            for file_path in logos_dir.glob("*"):
                if file_path.is_file():
                    if file_path.resolve() not in active_logos_paths:
                        try:
                            file_path.unlink()
                            print(f"Purged orphaned logo file: {file_path.name}")
                        except Exception as e:
                            print(f"Failed to delete {file_path.name}: {e}")

        print("Uploads cleanup complete.")


if __name__ == "__main__":
    purge_orphans()
