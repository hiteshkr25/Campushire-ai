import os
import sys
from pathlib import Path

# Insert root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole
from app.models.student import Student, Resume
from app.models.application import Application
from app.models.drive import PlacementDrive
from app.models.enums import ParseStatus
import uuid

def login_client(client, email, password="Demo@1234"):
    client.post("/auth/logout", follow_redirects=True)
    return client.post("/auth/login", data={
        "email": email,
        "password": password
    }, follow_redirects=True)

def test_resume_access():
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    
    with app.app_context():
        print("Starting focused Resume Access Control tests...")
        
        from app.auth.services import AuthService
        
        # 1. Fetch test users
        student_user = User.query.filter_by(email="student.demo@campushire.ai").first()
        tpo_user = User.query.filter_by(email="tpo@geu.edu.in").first()
        recruiter_user = User.query.filter_by(email="recruiter.demo@campushire.ai").first()
        admin_user = User.query.filter_by(email="admin@campushire.ai").first()
        
        # Create another student dynamically
        other_student_user = User.query.filter_by(email="temp.other.student@campushire.ai").first()
        if not other_student_user:
            other_student_user = User(
                email="temp.other.student@campushire.ai",
                password_hash=AuthService.hash_password("Demo@1234"),
                role=UserRole.STUDENT,
                is_active=True,
                is_verified=True
            )
            db.session.add(other_student_user)
            db.session.commit()
        
        if not student_user or not tpo_user or not recruiter_user or not admin_user:
            print("[FAIL] Demo users are required in database. Run init_db.py.")
            sys.exit(1)
            
        student = student_user.student_profile
        recruiter = recruiter_user.recruiter_profile
        
        # Clean any old test resumes for the demo student
        Resume.query.filter_by(student_id=student.id).delete()
        db.session.commit()
        
        # 2. Simulate Resume Upload
        print("Uploading a mock test resume...")
        upload_folder = Path(app.config["RESUME_UPLOAD_FOLDER"])
        student_dir = upload_folder / str(student.id)
        student_dir.mkdir(parents=True, exist_ok=True)
        
        temp_filename = f"test_resume_{uuid.uuid4()}.pdf"
        temp_filepath = student_dir / temp_filename
        with open(temp_filepath, "wb") as f:
            f.write(b"%PDF-1.4 Mock Resume File Content")
            
        resume = Resume(
            student_id=student.id,
            file_name="my_resume.pdf",
            file_path=str(temp_filepath),
            mime_type="application/pdf",
            file_size_bytes=100,
            is_primary=True,
            parse_status=ParseStatus.COMPLETED
        )
        db.session.add(resume)
        db.session.commit()
        print(f"Mock resume created at: {resume.file_path}")
        
        # Make sure student is registered to recruiter's company's drive for authorization
        drive = PlacementDrive.query.filter_by(company_id=recruiter.company_id).first()
        if not drive:
            # Seed mock drive
            drive = PlacementDrive(
                college_id=student.college_id,
                company_id=recruiter.company_id,
                created_by_tpo_id=tpo_user.tpo_profile.id,
                title="Mock Recruiting Drive",
                job_role="Software Engineer",
                job_description="Description...",
                vacancies=5,
                status="published"
            )
            db.session.add(drive)
            db.session.commit()
            
        app_rec = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
        if not app_rec:
            app_rec = Application(
                student_id=student.id,
                drive_id=drive.id,
                resume_id=resume.id,
                status="submitted"
            )
            db.session.add(app_rec)
            db.session.commit()

        client = app.test_client()
        
        # A. Login as Student and download
        print("\nTEST A: Student accessing own resume...")
        login_res = login_client(client, student_user.email)
        assert b"Sign In" not in login_res.data, "Should login student successfully."
        
        res = client.get(f"/student/resumes/{resume.id}/download")
        assert res.status_code == 200, f"Student should download successfully, got: {res.status_code}"
        print("[PASS] Student authorized successfully.")
        
        # B. Login as Recruiter and download
        print("\nTEST B: Recruiter accessing candidate resume...")
        login_res = login_client(client, recruiter_user.email)
        assert b"Sign In" not in login_res.data, "Should login recruiter successfully."
        
        res = client.get(f"/recruiter/candidates/resumes/{resume.id}/download")
        assert res.status_code == 200, f"Recruiter should download candidate resume successfully, got: {res.status_code}"
        print("[PASS] Recruiter authorized successfully.")
        
        # C. Login as TPO and download
        print("\nTEST C: TPO accessing student resume...")
        login_res = login_client(client, tpo_user.email)
        assert b"Sign In" not in login_res.data, "Should login TPO successfully."
        
        res = client.get(f"/student/resumes/{resume.id}/download")
        assert res.status_code == 200, f"TPO should download successfully, got: {res.status_code}"
        print("[PASS] TPO authorized successfully.")
        
        # D. Login as Admin and download
        print("\nTEST D: Admin accessing student resume...")
        login_res = login_client(client, admin_user.email)
        assert b"Sign In" not in login_res.data, "Should login admin successfully."
        
        res = client.get(f"/student/resumes/{resume.id}/download")
        assert res.status_code == 200, f"Admin should download successfully, got: {res.status_code}"
        print("[PASS] Admin authorized successfully.")
        
        # E. Login as Another Student (unauthorized)
        if other_student_user:
            print("\nTEST E: Unauthorized student accessing another student's resume...")
            login_res = login_client(client, other_student_user.email)
            assert b"Sign In" not in login_res.data, "Should login other student successfully."
            
            res = client.get(f"/student/resumes/{resume.id}/download")
            assert res.status_code == 403, f"Should return forbidden 403, got: {res.status_code}"
            print("[PASS] Unauthorized student rejected successfully.")
            
        # F. Missing physical file redirects cleanly instead of 404
        print("\nTEST F: Testing missing physical file handling...")
        # Delete file on disk
        if temp_filepath.exists():
            temp_filepath.unlink()
            
        login_res = login_client(client, student_user.email)
        res = client.get(f"/student/resumes/{resume.id}/download", follow_redirects=True)
        assert res.status_code == 200
        assert b"Resume file is no longer available" in res.data, "Should show clean user message."
        print("[PASS] Missing physical file handled cleanly.")
        
        # G. Invalid resume ID
        print("\nTEST G: Testing invalid resume ID...")
        res = client.get(f"/student/resumes/{uuid.uuid4()}/download")
        assert res.status_code == 404, "Invalid UUID should return 404."
        print("[PASS] Invalid resume ID returns 404 successfully.")

        # Clean up database mock records
        Application.query.filter_by(id=app_rec.id).delete()
        Resume.query.filter_by(id=resume.id).delete()
        if other_student_user:
            User.query.filter_by(id=other_student_user.id).delete()
        db.session.commit()
        
        print("\nAll Resume Access Control Tests Passed Successfully!")

if __name__ == "__main__":
    test_resume_access()
