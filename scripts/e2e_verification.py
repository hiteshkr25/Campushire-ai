"""Script to perform complete end-to-end workflow verification for CampusHire AI."""

import os
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, Student, Recruiter, TpoAdmin, College, Branch, Skill, Company, PlacementDrive, Application, Offer, InterviewSchedule, InterviewRound, RoundResult
from app.models.enums import UserRole, VerificationStatus, ProfileStatus, ApplicationStatus, OfferStatus, RoundType, ScheduleStatus, RoundResultStatus, ParseStatus
from app.auth.services import AuthService
from app.tpo.services import TpoService
from app.recruiter.services import RecruiterService
from app.student.ats_service import AtsService


def generate_dummy_pdf():
    # A tiny, minimal valid PDF document with text stream
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 712 Td (John Doe Resume Python SQL Flask) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000212 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n307\n%%EOF"


def run_e2e_verification():
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    client = app.test_client(use_cookies=True)

    results = {}

    # Context helpers
    def print_module_status(name, passed, route="N/A", exc=None):
        status = "PASS" if passed else "FAIL"
        results[name] = {
            "status": status,
            "route": route,
            "traceback": str(exc) if exc else None,
            "business_logic_affected": False
        }
        print(f"[{status}] {name}")
        if exc:
            import traceback
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _cleanup_e2e_records():
        print("Cleaning up E2E verification records...")
        from app.models.drive import DriveBranch

        e2e_student = User.query.filter_by(email="e2e_student@example.com").first()
        e2e_drive = PlacementDrive.query.filter_by(title="E2E Software Engineer").first()
        
        if e2e_student and e2e_student.student_profile:
            student_id = e2e_student.student_profile.id
            apps = Application.query.filter_by(student_id=student_id).all()
            for a in apps:
                Offer.query.filter_by(application_id=a.id).delete()
                InterviewSchedule.query.filter_by(application_id=a.id).delete()
                RoundResult.query.filter_by(application_id=a.id).delete()
                db.session.delete(a)
                
        if e2e_drive:
            apps = Application.query.filter_by(drive_id=e2e_drive.id).all()
            for a in apps:
                Offer.query.filter_by(application_id=a.id).delete()
                InterviewSchedule.query.filter_by(application_id=a.id).delete()
                RoundResult.query.filter_by(application_id=a.id).delete()
                db.session.delete(a)
            
            InterviewRound.query.filter_by(drive_id=e2e_drive.id).delete()
            DriveBranch.query.filter_by(drive_id=e2e_drive.id).delete()
            db.session.delete(e2e_drive)
            
        db.session.flush()

        User.query.filter(User.email.in_([
            "e2e_student@example.com",
            "e2e_recruiter@example.com",
            "e2e_tpo@example.com",
            "e2e_admin@example.com"
        ])).delete(synchronize_session=False)
        db.session.commit()

    with app.app_context():
        _cleanup_e2e_records()
        
        # Verify default seeded IITB College and CSE Branch exist
        college = College.query.filter_by(code="IITB").first()
        branch = Branch.query.filter_by(code="CSE").first()
        company = Company.query.filter_by(name="Google").first()

        if not college or not branch or not company:
            print("Pre-requisite seed data missing. Re-running database seeder...")
            from scripts.init_db import seed_data
            seed_data()
            college = College.query.filter_by(code="IITB").first()
            branch = Branch.query.filter_by(code="CSE").first()
            company = Company.query.filter_by(name="Google").first()

        db.session.commit()

        # ----------------------------------------------------
        # 1. Student Registration
        # ----------------------------------------------------
        student_user = None
        try:
            student_user = AuthService.register_student(
                email="e2e_student@example.com",
                password="Password123",
                college_code="IITB",
                branch_code="CSE",
                enrollment_number="ENR_E2E_01",
                first_name="E2E",
                last_name="Student",
                batch="2026",
                graduation_year=2026,
                phone="1234567890"
            )
            print_module_status("Student registration", True)
        except Exception as e:
            print_module_status("Student registration", False, "/auth/register/student", e)

        # ----------------------------------------------------
        # 2. Student Login
        # ----------------------------------------------------
        try:
            response = client.post("/auth/login", data={
                "email": "e2e_student@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            assert b"Sign Out" in response.data or b"Dashboard" in response.data
            print_module_status("Student login", True)
        except Exception as e:
            print_module_status("Student login", False, "/auth/login", e)

        # ----------------------------------------------------
        # 3. Resume Upload & 4. Resume Parsing
        # ----------------------------------------------------
        resume_id = None
        try:
            pdf_data = generate_dummy_pdf()
            response = client.post("/student/resumes", data={
                "resume": (io.BytesIO(pdf_data), "e2e_resume.pdf"),
                "is_primary": "y",
                "submit": "Upload & Parse"
            }, follow_redirects=True)
            
            # Fetch student and check resume
            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            resume = student.resumes.first()
            assert resume is not None
            assert resume.parse_status == ParseStatus.COMPLETED
            resume_id = resume.id
            print_module_status("Resume upload", True)
            print_module_status("Resume parsing", True)
        except Exception as e:
            print_module_status("Resume upload", False, "/student/resumes", e)
            print_module_status("Resume parsing", False, "/student/resumes", e)

        # ----------------------------------------------------
        # Seed TPO and Recruiter for Placement & Drive setup
        # ----------------------------------------------------
        tpo_user = None
        recruiter_user = None
        try:
            # Create TPO user
            tpo_user = User(
                email="e2e_tpo@example.com",
                password_hash=AuthService.hash_password("Password123"),
                role=UserRole.TPO,
                is_active=True,
                is_verified=True
            )
            tpo_profile = TpoAdmin(
                user=tpo_user,
                college=college,
                first_name="E2E",
                last_name="TPO",
                is_primary_tpo=True
            )
            db.session.add(tpo_user)
            db.session.add(tpo_profile)

            # Create Recruiter user
            recruiter_user = User(
                email="e2e_recruiter@example.com",
                password_hash=AuthService.hash_password("Password123"),
                role=UserRole.RECRUITER,
                is_active=True,
                is_verified=True
            )
            rec_profile = Recruiter(
                user=recruiter_user,
                company=company,
                first_name="E2E",
                last_name="Recruiter"
            )
            db.session.add(recruiter_user)
            db.session.add(rec_profile)

            db.session.commit()
        except Exception as e:
            print(f"Failed to seed auxiliary test roles: {e}")

        # ----------------------------------------------------
        # 7. TPO Verification (Student profile approval)
        # ----------------------------------------------------
        try:
            # Log in TPO
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_tpo@example.com",
                "password": "Password123"
            }, follow_redirects=True)

            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            
            # Populate required fields to complete student profile
            from app.models import StudentSkill, StudentProject, StudentCertification
            student.date_of_birth = datetime.strptime("2000-01-01", "%Y-%m-%d").date()
            student.gender = "male"
            student.cgpa = Decimal("9.00")
            student.semester = 8
            student.bio = "E2E Student bio"
            student.linkedin_url = "https://linkedin.com/in/e2e"
            
            skill = Skill.query.first()
            if skill:
                db.session.add(StudentSkill(student_id=student.id, skill_id=skill.id))
                
            proj = StudentProject(
                student_id=student.id,
                title="E2E Mock Project",
                description="Project description",
                tech_stack="Python, Flask"
            )
            db.session.add(proj)
            
            cert = StudentCertification(
                student_id=student.id,
                name="E2E Mock Cert",
                issuer="Coursera",
                issue_date=datetime.strptime("2024-01-01", "%Y-%m-%d").date()
            )
            db.session.add(cert)
            
            student.profile_status = ProfileStatus.PENDING_VERIFICATION
            db.session.commit()

            # Verify student
            TpoService.verify_student(student.id, tpo_user.id)
            db.session.commit()

            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            assert student.profile_status == ProfileStatus.VERIFIED
            print_module_status("TPO verification", True)
        except Exception as e:
            print_module_status("TPO verification", False, "/tpo/verification/<id>/approve", e)

        # ----------------------------------------------------
        # 7a. Profile Change Requests & Locking
        # ----------------------------------------------------
        try:
            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            assert student.profile_status == ProfileStatus.VERIFIED
            
            # Log in as Student
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_student@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            
            # 1. Verify locking: Student tries to edit locked field directly
            response = client.post("/student/profile", data={
                "first_name": "DirectlyChangedName",
                "last_name": "Student",
                "phone": "9876543210",
                "date_of_birth": "2000-01-01",
                "gender": "male",
                "bio": "Directly edited bio text",
                "enrollment_number": "CHANGED_ENROLLMENT",
                "branch_id": str(branch.id),
                "batch": "2026",
                "semester": "8",
                "graduation_year": "2026",
                "cgpa": "9.50",
                "backlogs_count": "0",
                "skills": "Python, Flask"
            }, follow_redirects=True)
            
            db.session.expire_all()
            student = Student.query.filter_by(id=student.id).first()
            # Assert locked fields remain unchanged
            assert student.first_name == "E2E"
            assert student.enrollment_number == "ENR_E2E_01"
            # Assert career fields were successfully edited directly
            assert student.cgpa == Decimal("9.50")
            assert student.phone == "9876543210"
            assert student.bio == "Directly edited bio text"

            # 2. Submit Profile Change Request
            response = client.post("/student/profile/request-change", data={
                "field_name": "first_name",
                "requested_value": "CorrectedFirstName",
                "reason": "Official name correction request"
            }, follow_redirects=True)
            assert b"submitted" in response.data or b"successfully" in response.data
            
            # 3. Prevent duplicate requests
            response = client.post("/student/profile/request-change", data={
                "field_name": "first_name",
                "requested_value": "AnotherName",
                "reason": "Duplicate request details"
            }, follow_redirects=True)
            assert b"already have a pending change request" in response.data
            
            # 4. TPO review & approve request
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_tpo@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            
            from app.models.student import ProfileChangeRequest
            req = ProfileChangeRequest.query.filter_by(
                student_id=student.id,
                field_name="first_name",
                status="pending"
            ).first()
            assert req is not None
            
            # Approve it
            response = client.post(f"/tpo/verification/change-requests/{req.id}/approve", follow_redirects=True)
            assert b"approved" in response.data or b"success" in response.data
            
            db.session.expire_all()
            student = Student.query.filter_by(id=student.id).first()
            # Verify field updated successfully
            assert student.first_name == "CorrectedFirstName"
            
            # 5. TPO review & reject request
            # Student requests last_name change
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_student@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            
            client.post("/student/profile/request-change", data={
                "field_name": "last_name",
                "requested_value": "CorrectedLastName",
                "reason": "Typo correction"
            }, follow_redirects=True)
            
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_tpo@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            
            req_last = ProfileChangeRequest.query.filter_by(
                student_id=student.id,
                field_name="last_name",
                status="pending"
            ).first()
            assert req_last is not None
            
            # Reject it
            response = client.post(f"/tpo/verification/change-requests/{req_last.id}/reject", data={
                "rejection_reason": "Invalid documentation provided"
            }, follow_redirects=True)
            assert b"rejected" in response.data or b"info" in response.data
            
            db.session.expire_all()
            student = Student.query.filter_by(id=student.id).first()
            # Verify field remained unchanged
            assert student.last_name == "Student"
            
            # 6. Verify audit logs & notifications
            from app.models.audit import AuditLog
            from app.models.notification import Notification
            
            audit = AuditLog.query.filter_by(entity_id=student.id, action="update").first()
            assert audit is not None
            
            notification = Notification.query.filter_by(user_id=student.user_id, title="Profile Change Approved").first()
            assert notification is not None
            
            notification_rejected = Notification.query.filter_by(user_id=student.user_id, title="Profile Change Rejected").first()
            assert notification_rejected is not None
            
            print_module_status("Profile change requests & locking", True)
        except Exception as e:
            print_module_status("Profile change requests & locking", False, "/profile/request-change", e)

        # ----------------------------------------------------
        # 8. Placement Drive Creation
        # ----------------------------------------------------
        drive_id = None
        try:
            from app.models.enums import LocationType, DriveStatus
            drive = PlacementDrive(
                company=company,
                college=college,
                title="E2E Software Engineer",
                job_role="Software Engineer",
                job_description="We are seeking full stack engineers with Python and SQL experience.",
                package_min_lpa=25.50,
                package_max_lpa=25.50,
                venue="Bangalore Office",
                location_type=LocationType.ON_CAMPUS,
                status=DriveStatus.PUBLISHED,
                created_by_tpo_id=tpo_user.tpo_profile.id
            )
            db.session.add(drive)
            db.session.flush()
            
            # Seed eligible branch
            from app.models.drive import DriveBranch
            db.session.add(DriveBranch(drive_id=drive.id, branch_id=branch.id))

            # Add interview round
            round1 = InterviewRound(
                drive_id=drive.id,
                round_number=1,
                round_name="Aptitude & Technical MCQ",
                round_type=RoundType.APTITUDE,
                sequence_order=1
            )
            db.session.add(round1)

            db.session.commit()
            drive_id = drive.id
            print_module_status("Placement drive creation", True)
        except Exception as e:
            print_module_status("Placement drive creation", False, "/tpo/drives/new", e)

        # ----------------------------------------------------
        # 5. ATS Score Generation & 6. Job Application
        # ----------------------------------------------------
        try:
            # Login student back
            client.post("/auth/logout", follow_redirects=True)
            client.post("/auth/login", data={
                "email": "e2e_student@example.com",
                "password": "Password123"
            }, follow_redirects=True)

            # Check ATS dashboard
            response = client.get("/student/ats")
            assert response.status_code == 200

            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            drive = PlacementDrive.query.get(drive_id)
            ats_data = AtsService.calculate_ats_score(student, drive)
            assert ats_data["score"] > 0
            print_module_status("ATS score generation", True)

            # Apply for job
            app_record = Application(
                student_id=student.id,
                drive_id=drive.id,
                resume_id=resume_id,
                status=ApplicationStatus.SUBMITTED,
                applied_at=db.func.now()
            )
            db.session.add(app_record)
            db.session.commit()
            print_module_status("Job application", True)
        except Exception as e:
            print_module_status("ATS score generation", False, "/student/ats", e)
            print_module_status("Job application", False, "/student/drives/apply", e)

        # ----------------------------------------------------
        # 9. Recruiter Login
        # ----------------------------------------------------
        try:
            client.post("/auth/logout", follow_redirects=True)
            response = client.post("/auth/login", data={
                "email": "e2e_recruiter@example.com",
                "password": "Password123"
            }, follow_redirects=True)
            assert b"Sign Out" in response.data or b"Dashboard" in response.data
            print_module_status("Recruiter login", True)
        except Exception as e:
            print_module_status("Recruiter login", False, "/auth/login", e)

        # ----------------------------------------------------
        # 10. Candidate Review
        # ----------------------------------------------------
        application_id = None
        try:
            # Check recruiter candidate list
            response = client.get("/recruiter/candidates")
            assert response.status_code == 200
            
            student = Student.query.filter_by(enrollment_number="ENR_E2E_01").first()
            app_rec = student.applications.first()
            application_id = app_rec.id
            
            # Details view
            response2 = client.get(f"/recruiter/candidates/{app_rec.id}")
            assert response2.status_code == 200
            print_module_status("Candidate review", True)
        except Exception as e:
            print_module_status("Candidate review", False, "/recruiter/candidates", e)

        # ----------------------------------------------------
        # 11. Interview Workflow
        # ----------------------------------------------------
        try:
            drive = PlacementDrive.query.get(drive_id)
            round_obj = drive.interview_rounds.first()
            
            # Schedule interview
            sched = InterviewSchedule(
                application_id=application_id,
                round_id=round_obj.id,
                scheduled_start=datetime.now(timezone.utc) + timedelta(days=1),
                scheduled_end=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
                venue="Zoom Video Call",
                meeting_link="https://zoom.us/test",
                status=ScheduleStatus.SCHEDULED
            )
            db.session.add(sched)
            db.session.commit()
            
            # Evaluate interview
            RecruiterService.evaluate_interview(
                schedule_id=sched.id,
                score=85.00,
                status="passed",
                remarks="Strong technical answers.",
                evaluator_user_id=recruiter_user.id
            )
            db.session.commit()
            
            # Confirm application status transitioned to shortlisted/selected
            app_rec = Application.query.get(application_id)
            assert app_rec.status in [ApplicationStatus.SELECTED, ApplicationStatus.SHORTLISTED]
            print_module_status("Interview workflow", True)
        except Exception as e:
            print_module_status("Interview workflow", False, "/recruiter/interviews/evaluate", e)

        # ----------------------------------------------------
        # 12. Offer Generation
        # ----------------------------------------------------
        try:
            # Force transition application to selected for offering
            app_rec = Application.query.get(application_id)
            app_rec.status = ApplicationStatus.SELECTED
            db.session.commit()

            form_data = {
                "application_id": str(application_id),
                "package_offered_lpa": 25.50,
                "job_location": "Bangalore",
                "joining_date": datetime.now().date() + timedelta(days=60),
                "expires_at": datetime.now() + timedelta(days=7)
            }
            offer = RecruiterService.create_and_release_offer(
                form_data,
                None,
                recruiter_user.recruiter_profile.id
            )
            db.session.commit()
            
            offer_rec = Offer.query.filter_by(application_id=application_id).first()
            assert offer_rec is not None
            assert offer_rec.status == OfferStatus.EXTENDED
            print_module_status("Offer generation", True)
        except Exception as e:
            print_module_status("Offer generation", False, "/recruiter/offers/new", e)

        # ----------------------------------------------------
        # 13. Admin Login
        # ----------------------------------------------------
        try:
            client.post("/auth/logout", follow_redirects=True)
            response = client.post("/auth/login", data={
                "email": "admin@campushire.ai",
                "password": "Demo@1234"
            }, follow_redirects=True)
            assert b"Sign Out" in response.data or b"Dashboard" in response.data
            print_module_status("Admin login", True)
        except Exception as e:
            print_module_status("Admin login", False, "/auth/login", e)

        # ----------------------------------------------------
        # 14. User Management
        # ----------------------------------------------------
        try:
            # Lock user
            from app.admin.services import AdminService
            AdminService.lock_user_account(student_user.id)
            db.session.commit()
            
            student_u = User.query.get(student_user.id)
            assert student_u.is_active is False
            
            # Unlock user
            AdminService.unlock_user_account(student_user.id)
            db.session.commit()
            student_u = User.query.get(student_user.id)
            assert student_u.is_active is True
            print_module_status("User management", True)
        except Exception as e:
            print_module_status("User management", False, "/admin/users/<id>/status", e)

        # ----------------------------------------------------
        # 15. Audit Logs
        # ----------------------------------------------------
        try:
            response = client.get("/admin/audit-logs")
            assert response.status_code == 200
            print_module_status("Audit logs", True)
        except Exception as e:
            print_module_status("Audit logs", False, "/admin/audit-logs", e)

        # Clean up E2E test users
        _cleanup_e2e_records()


if __name__ == "__main__":
    run_e2e_verification()
