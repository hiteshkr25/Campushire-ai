import os
import uuid
import json
from decimal import Decimal
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.decorators import role_required
from app.extensions import db
from app.models.college import Branch, Skill
from app.models.enums import ParseStatus, ProfileStatus, UserRole, OfferStatus
from app.models.application import Offer
from app.models.student import Resume, StudentCertification, StudentProject, StudentSkill
from app.student.forms import (
    ApplicationForm,
    ApplicationSearchForm,
    DriveSearchForm,
    ResumeUploadForm,
    StudentCertificationForm,
    StudentProfileForm,
    StudentProjectForm,
    ProfileChangeRequestForm,
)
from app.exceptions import ApplicationNotFoundError, DriveNotFoundError, StudentServiceError
from app.student.services import ApplicationService, DriveService, WITHDRAWABLE_STATUSES

student_bp = Blueprint("student", __name__)


@student_bp.route("/dashboard")
@role_required(UserRole.STUDENT)
def dashboard():
    from app.student.ats_service import AtsService
    from app.utils.notification_service import NotificationService
    from app.models.application import Application, InterviewSchedule, Offer, ApplicationStatus, ScheduleStatus, OfferStatus
    from app.models.student import Resume, Student
    from app.models.enums import ProfileStatus
    from app.models.drive import PlacementDrive
    from sqlalchemy.orm import joinedload
    from datetime import datetime

    # Preload student with verifier
    student = Student.query.options(joinedload(Student.verifier)).filter_by(user_id=current_user.id).first_or_404()

    # Preload all related collections into preloaded_data dict to avoid N+1 queries
    preloaded_data = {}
    preloaded_data["applications"] = Application.query.options(
        joinedload(Application.drive).joinedload(PlacementDrive.company)
    ).filter_by(student_id=student.id).all()
    
    preloaded_data["resumes"] = Resume.query.filter_by(student_id=student.id).all()
    preloaded_data["skills"] = StudentSkill.query.options(joinedload(StudentSkill.skill)).filter_by(student_id=student.id).all()
    preloaded_data["projects"] = StudentProject.query.filter_by(student_id=student.id).all()
    preloaded_data["certifications"] = StudentCertification.query.filter_by(student_id=student.id).all()
    
    preloaded_data["schedules"] = InterviewSchedule.query.join(Application)\
        .options(joinedload(InterviewSchedule.round))\
        .filter(Application.student_id == student.id).all()
        
    preloaded_data["offers"] = Offer.query.join(Application)\
        .options(joinedload(Offer.application).joinedload(Application.drive).joinedload(PlacementDrive.company))\
        .filter(Application.student_id == student.id).all()

    summary = ApplicationService.summary(student, preloaded_applications=preloaded_data["applications"])
    recent_applications = ApplicationService.recent_active(student, limit=5, preloaded_applications=preloaded_data["applications"])
    
    # Pre-load primary resume and checklist data to avoid duplicate queries
    primary_resume = AtsService._primary_or_latest_resume(student, resumes=preloaded_data["resumes"])
    profile_completion, checklist_data = _profile_completion_data(student, preloaded_data=preloaded_data)
    
    ats_info = AtsService.calculate_dashboard_score(student, resume=primary_resume)
    ats_checklist = AtsService.build_dashboard_checklist(
        student, profile_completion, resume=primary_resume, checklist_data=checklist_data
    )

    # Fetch recent database notifications for the widget
    recent_db_notifications = NotificationService.get_dropdown_notifications(current_user.id, limit=3)

    # Gather chronological placement events
    events = []
    
    # 1. Profile Created
    if student.created_at:
        events.append({
            "title": "Profile Submitted",
            "time": student.created_at,
            "description": "Your student profile was created in the system."
        })
        
    # 2. Profile Verification
    if student.verified_at:
        if student.profile_status == ProfileStatus.VERIFIED:
            events.append({
                "title": "Profile Verified",
                "time": student.verified_at,
                "description": f"Verified by {student.verifier_name}."
            })
        elif student.profile_status == ProfileStatus.REJECTED:
            events.append({
                "title": "Profile Verification Rejected",
                "time": student.verified_at,
                "description": f"Rejected by {student.verifier_name}."
            })

    # 3. Resumes (sorted in Python memory)
    resumes_sorted = sorted(preloaded_data["resumes"], key=lambda r: r.created_at or datetime.min)
    for r in resumes_sorted:
        events.append({
            "title": "Resume Uploaded" if r.is_primary else "Resume Added",
            "time": r.uploaded_at or r.created_at,
            "description": f"Uploaded resume: {r.file_name}."
        })

    # 4. Applications & Status updates (from preloaded applications)
    for app in preloaded_data["applications"]:
        co_name = app.drive.company.name if app.drive and app.drive.company else "Drive"
        role = app.drive.job_role if app.drive else "Role"
        
        events.append({
            "title": f"Applied to {co_name}",
            "time": app.applied_at or app.created_at,
            "description": f"Submitted application for {role}."
        })
        
        if app.status in (ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_IN_PROGRESS, ApplicationStatus.SELECTED, ApplicationStatus.PLACED):
            status_desc = {
                ApplicationStatus.SHORTLISTED: "You have been shortlisted for the drive pipeline.",
                ApplicationStatus.INTERVIEW_IN_PROGRESS: "Your interviews are currently in progress.",
                ApplicationStatus.SELECTED: "You have been selected for the position.",
                ApplicationStatus.PLACED: "Congratulations! Placement process is complete."
            }.get(app.status, f"Application moved to status: {app.status.value.replace('_', ' ').title()}.")
            
            events.append({
                "title": f"Shortlisted at {co_name}" if app.status == ApplicationStatus.SHORTLISTED else f"Status: {app.status.value.replace('_', ' ').title()}",
                "time": app.status_updated_at or app.applied_at or app.created_at,
                "description": f"{status_desc} for {role}."
            })

    # 5. Interviews (from preloaded schedules)
    for s in preloaded_data["schedules"]:
        r_name = s.round.round_name if s.round else "Interview"
        events.append({
            "title": "Interview Scheduled",
            "time": s.created_at,
            "description": f"Scheduled for {r_name} on {s.scheduled_start.strftime('%d %b, %I:%M %p')}."
        })
        if s.status == ScheduleStatus.COMPLETED:
            events.append({
                "title": "Interview Completed",
                "time": s.updated_at,
                "description": f"Completed {r_name} round."
            })

    # 6. Offers (from preloaded offers)
    for o in preloaded_data["offers"]:
        co_name = o.application.drive.company.name if o.application and o.application.drive and o.application.drive.company else "Company"
        if o.created_at or o.extended_at:
            events.append({
                "title": "Offer Generated",
                "time": o.extended_at or o.created_at,
                "description": f"Extended by {co_name} for {o.package_offered_lpa} LPA."
            })
        if o.status == OfferStatus.ACCEPTED:
            events.append({
                "title": "Offer Accepted",
                "time": o.responded_at or o.updated_at,
                "description": f"Accepted offer from {co_name}."
            })
            events.append({
                "title": "Placement Completed",
                "time": o.responded_at or o.updated_at,
                "description": "Congratulations! You have been successfully placed."
            })
        elif o.status == OfferStatus.DECLINED:
            events.append({
                "title": "Offer Declined",
                "time": o.responded_at or o.updated_at,
                "description": f"Declined offer from {co_name}."
            })

    # Sort events chronologically descending
    events = sorted(events, key=lambda x: x["time"], reverse=True)

    return render_template(
        "portals/student_dashboard.html",
        application_summary=summary,
        recent_applications=recent_applications,
        profile_completion=profile_completion,
        ats_info=ats_info,
        ats_checklist=ats_checklist,
        recent_db_notifications=recent_db_notifications,
        events=events,
    )


def _student_or_404():
    student = current_user.student_profile
    if not student:
        abort(404)
    return student


def _uuid_or_404(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        abort(404)


def _branch_choices(student):
    branches = (
        Branch.query.filter_by(college_id=student.college_id, is_active=True)
        .order_by(Branch.name.asc())
        .all()
    )
    return [(str(branch.id), f"{branch.name} ({branch.code})") for branch in branches]


def _skills_text(student, skills_list=None):
    if skills_list is None:
        skill_links = student.skills.order_by(StudentSkill.created_at.asc()).all()
    else:
        from datetime import datetime
        skill_links = sorted(skills_list, key=lambda s: s.created_at or datetime.min)
    return ", ".join(link.skill.name for link in skill_links if link.skill)


def _sync_skills(student, raw_skills):
    names = []
    seen = set()
    for item in (raw_skills or "").replace("\n", ",").split(","):
        name = " ".join(item.strip().split())
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            names.append(name[:100])

    StudentSkill.query.filter_by(student_id=student.id).delete(synchronize_session=False)
    for name in names:
        skill = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
        if not skill:
            skill = Skill(name=name)
            db.session.add(skill)
            db.session.flush()
        db.session.add(StudentSkill(student_id=student.id, skill_id=skill.id, proficiency=3))


def _profile_completion_data(student, preloaded_data=None):
    from app.models.student import StudentSkill, StudentProject, StudentCertification, Resume
    if preloaded_data is not None:
        has_skills = len(preloaded_data.get("skills", [])) > 0
        has_projects = len(preloaded_data.get("projects", [])) > 0
        has_certs = len(preloaded_data.get("certifications", [])) > 0
        has_resumes = len(preloaded_data.get("resumes", [])) > 0
    else:
        counts = db.session.query(
            db.session.query(StudentSkill).filter_by(student_id=student.id).exists(),
            db.session.query(StudentProject).filter_by(student_id=student.id).exists(),
            db.session.query(StudentCertification).filter_by(student_id=student.id).exists(),
            db.session.query(Resume).filter_by(student_id=student.id).exists()
        ).first()
        has_skills, has_projects, has_certs, has_resumes = counts if counts else (False, False, False, False)

    checks = [
        student.first_name,
        student.last_name,
        student.phone,
        student.date_of_birth,
        student.gender,
        student.cgpa is not None,
        student.graduation_year,
        student.batch,
        student.semester,
        student.bio,
        student.linkedin_url or student.github_url,
        has_skills,
        has_projects,
        has_certs,
        has_resumes,
    ]
    completion = round((sum(1 for item in checks if item) / len(checks)) * 100)

    checklist = {
        "skills": has_skills,
        "projects": has_projects,
        "certifications": has_certs,
        "resumes": has_resumes
    }
    return completion, checklist


def _profile_completion(student, preloaded_data=None):
    return _profile_completion_data(student, preloaded_data=preloaded_data)[0]


@student_bp.route("/profile", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def profile():
    from app.models.student import Student
    from sqlalchemy.orm import joinedload
    
    student = Student.query.options(joinedload(Student.verifier)).filter_by(user_id=current_user.id).first_or_404()
    
    # Preload all related collections to avoid N+1 queries
    preloaded_data = {}
    preloaded_data["skills"] = StudentSkill.query.options(joinedload(StudentSkill.skill)).filter_by(student_id=student.id).all()
    preloaded_data["projects"] = StudentProject.query.filter_by(student_id=student.id).order_by(StudentProject.created_at.desc()).all()
    preloaded_data["certifications"] = StudentCertification.query.filter_by(student_id=student.id).order_by(StudentCertification.issue_date.desc()).all()
    preloaded_data["resumes"] = Resume.query.filter_by(student_id=student.id).all()
    
    from app.models.student import ProfileChangeRequest
    change_requests = ProfileChangeRequest.query.filter_by(student_id=student.id).order_by(ProfileChangeRequest.created_at.desc()).all()
    
    form = StudentProfileForm(obj=student)
    form.branch_id.choices = _branch_choices(student)
    if request.method == "GET":
        form.branch_id.data = str(student.branch_id)
        form.skills.data = _skills_text(student, skills_list=preloaded_data["skills"])

    if form.validate_on_submit():
        try:
            # Contact/Career fields are always editable
            student.phone = form.phone.data or None
            student.bio = form.bio.data or None
            student.linkedin_url = form.linkedin_url.data or None
            student.github_url = form.github_url.data or None
            
            # Fields that are locked ONLY after verification
            if student.profile_status != ProfileStatus.VERIFIED:
                student.first_name = form.first_name.data
                student.last_name = form.last_name.data
                student.date_of_birth = form.date_of_birth.data
                student.gender = form.gender.data or None
                student.enrollment_number = form.enrollment_number.data
                student.branch_id = uuid.UUID(form.branch_id.data)
                student.batch = form.batch.data
                student.graduation_year = form.graduation_year.data

            # Academic/Career metrics are always editable
            student.semester = form.semester.data
            student.cgpa = Decimal(form.cgpa.data) if form.cgpa.data is not None else None
            student.backlogs_count = form.backlogs_count.data

            if student.profile_status == ProfileStatus.INCOMPLETE:
                if student.is_profile_complete():
                    student.profile_status = ProfileStatus.PENDING_VERIFICATION
                    flash("Your profile is complete and has been submitted for TPO verification.", "success")
                else:
                    flash("Profile saved, but it is not complete yet. Please complete all sections before requesting verification.", "warning")
            _sync_skills(student, form.skills.data)
            db.session.commit()
            
            if student.profile_status == ProfileStatus.VERIFIED:
                flash("Profile updated. Verified academic details are locked and cannot be edited.", "info")
            else:
                flash("Profile updated successfully.", "success")
            return redirect(url_for("student.profile"))
        except Exception:
            db.session.rollback()
            flash("Unable to update profile. Please try again.", "danger")

    return render_template(
        "student/profile.html",
        form=form,
        student=student,
        projects=preloaded_data["projects"],
        certifications=preloaded_data["certifications"],
        profile_completion=_profile_completion(student, preloaded_data=preloaded_data),
        change_requests=change_requests,
    )


def _project_or_404(project_id):
    student = _student_or_404()
    project = StudentProject.query.filter_by(id=_uuid_or_404(project_id), student_id=student.id).first_or_404()
    return student, project


@student_bp.route("/profile/projects/new", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def create_project():
    student = _student_or_404()
    form = StudentProjectForm()
    if form.validate_on_submit():
        project = StudentProject(student_id=student.id)
        form.populate_obj(project)
        db.session.add(project)
        db.session.commit()
        flash("Project added successfully.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student/project_form.html", form=form, title="Add Project")


@student_bp.route("/profile/projects/<project_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def edit_project(project_id):
    student, project = _project_or_404(project_id)
    form = StudentProjectForm(obj=project)
    if form.validate_on_submit():
        form.populate_obj(project)
        db.session.commit()
        flash("Project updated successfully.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student/project_form.html", form=form, title="Edit Project")


@student_bp.route("/profile/projects/<project_id>/delete", methods=["POST"])
@role_required(UserRole.STUDENT)
def delete_project(project_id):
    student, project = _project_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "info")
    return redirect(url_for("student.profile"))


def _certification_or_404(certification_id):
    student = _student_or_404()
    certification = StudentCertification.query.filter_by(id=_uuid_or_404(certification_id), student_id=student.id).first_or_404()
    return student, certification


@student_bp.route("/profile/certifications/new", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def create_certification():
    student = _student_or_404()
    form = StudentCertificationForm()
    if form.validate_on_submit():
        certification = StudentCertification(student_id=student.id)
        form.populate_obj(certification)
        db.session.add(certification)
        db.session.commit()
        flash("Certification added successfully.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student/certification_form.html", form=form, title="Add Certification")


@student_bp.route("/profile/certifications/<certification_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def edit_certification(certification_id):
    student, certification = _certification_or_404(certification_id)
    form = StudentCertificationForm(obj=certification)
    if form.validate_on_submit():
        form.populate_obj(certification)
        db.session.commit()
        flash("Certification updated successfully.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student/certification_form.html", form=form, title="Edit Certification")


@student_bp.route("/profile/certifications/<certification_id>/delete", methods=["POST"])
@role_required(UserRole.STUDENT)
def delete_certification(certification_id):
    student, certification = _certification_or_404(certification_id)
    db.session.delete(certification)
    db.session.commit()
    flash("Certification deleted.", "info")
    return redirect(url_for("student.profile"))


def _resume_upload_dir(student):
    upload_root = Path(current_app.config["RESUME_UPLOAD_FOLDER"])
    return upload_root / str(student.id)


def _resume_or_404(resume_id):
    student = _student_or_404()
    resume = Resume.query.filter_by(id=_uuid_or_404(resume_id), student_id=student.id).first_or_404()
    return student, resume


def _allowed_resume(file_storage):
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_extensions = current_app.config.get("ALLOWED_RESUME_EXTENSIONS", {"pdf", "docx"})
    allowed_mimes = current_app.config.get(
        "ALLOWED_RESUME_MIME_TYPES",
        {
            "application/pdf",
            "application/x-pdf",
            "application/octet-stream",
            "binary/octet-stream",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        },
    )
    ext_ok = extension in allowed_extensions
    mime_ok = file_storage.mimetype in allowed_mimes
    current_app.logger.debug(
        "Resume validation: filename=%r ext=%r mime=%r ext_ok=%s mime_ok=%s",
        filename, extension, file_storage.mimetype, ext_ok, mime_ok,
    )
    return ext_ok and mime_ok


def _resume_mime(filename):
    return (
        "application/pdf"
        if filename.lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@student_bp.route("/resumes", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def resumes():
    student = _student_or_404()
    form = ResumeUploadForm()
    if form.validate_on_submit():
        file = form.resume.data
        current_app.logger.info(
            "Resume upload attempt: user=%s filename=%r mimetype=%r",
            current_user.id, file.filename, file.mimetype,
        )

        if not _allowed_resume(file):
            current_app.logger.warning(
                "Resume validation failed: filename=%r mimetype=%r",
                file.filename, file.mimetype,
            )
            flash("Only PDF and DOCX resumes are supported.", "danger")
            return redirect(url_for("student.resumes"))

        current_app.logger.info("Resume validation passed: filename=%r", file.filename)

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        max_size = current_app.config.get("MAX_RESUME_SIZE_BYTES", 10 * 1024 * 1024)
        if file_size <= 0 or file_size > max_size:
            flash("Resume must be between 1 byte and 10 MB.", "danger")
            return redirect(url_for("student.resumes"))

        original_name = secure_filename(file.filename)
        extension = original_name.rsplit(".", 1)[-1].lower()
        stored_name = f"{uuid.uuid4()}.{extension}"
        upload_dir = _resume_upload_dir(student)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / stored_name

        try:
            file.save(file_path)
            current_app.logger.info("Resume file saved: path=%s size=%d bytes", file_path, file_size)

            should_be_primary = form.is_primary.data or student.resumes.count() == 0
            if should_be_primary:
                Resume.query.filter_by(student_id=student.id, is_primary=True).update({"is_primary": False})
                db.session.flush()
            resume = Resume(
                student_id=student.id,
                file_name=original_name,
                file_path=str(file_path),
                mime_type=_resume_mime(original_name),
                file_size_bytes=file_size,
                is_primary=should_be_primary,
                parse_status=ParseStatus.PENDING,
            )
            db.session.add(resume)
            db.session.commit()
            current_app.logger.info("Resume DB record created: id=%s", resume.id)

            try:
                from app.student.resume_parser import ResumeParserService
                current_app.logger.info("Starting parser for resume id=%s", resume.id)
                ResumeParserService.parse_and_save_resume(resume.id)
                current_app.logger.info("Parser completed for resume id=%s", resume.id)
                flash("Resume uploaded and parsed successfully.", "success")
            except Exception as parse_err:
                current_app.logger.warning(
                    "Auto-parse failed for resume id=%s: %s", resume.id, parse_err
                )
                flash("Resume uploaded but automatic parsing failed. You can re-parse it manually.", "warning")

            return redirect(url_for("student.resumes"))
        except Exception as save_err:
            current_app.logger.error("Resume upload error: %s", save_err, exc_info=True)
            db.session.rollback()
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            flash("Unable to upload resume. Please try again.", "danger")

    resumes = student.resumes.order_by(Resume.uploaded_at.desc(), Resume.created_at.desc()).all()
    return render_template("student/resumes.html", form=form, resumes=resumes)


@student_bp.route("/resumes/<resume_id>/preview")
@role_required(UserRole.STUDENT, UserRole.TPO)
def preview_resume(resume_id):
    resume = Resume.query.get_or_404(_uuid_or_404(resume_id))
    
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        if not student or resume.student_id != student.id:
            abort(403)
    elif current_user.role == UserRole.TPO:
        from app.tpo.services import TpoService
        TpoService.validate_college_access(resume)
        
    file_path = Path(resume.file_path)
    if not file_path.exists():
        abort(404)
    if resume.mime_type == "application/pdf":
        return send_file(file_path, mimetype=resume.mime_type, as_attachment=False, download_name=resume.file_name)
    return render_template("student/resume_preview.html", resume=resume)


@student_bp.route("/resumes/<resume_id>/download")
@role_required(UserRole.STUDENT, UserRole.TPO)
def download_resume(resume_id):
    resume = Resume.query.get_or_404(_uuid_or_404(resume_id))
    
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        if not student or resume.student_id != student.id:
            abort(403)
    elif current_user.role == UserRole.TPO:
        from app.tpo.services import TpoService
        TpoService.validate_college_access(resume)
        
    file_path = Path(resume.file_path)
    if not file_path.exists():
        abort(404)
    return send_file(file_path, mimetype=resume.mime_type, as_attachment=True, download_name=resume.file_name)


@student_bp.route("/resumes/<resume_id>/activate", methods=["POST"])
@role_required(UserRole.STUDENT)
def activate_resume(resume_id):
    student, resume = _resume_or_404(resume_id)
    try:
        Resume.query.filter_by(student_id=student.id, is_primary=True).update({"is_primary": False})
        db.session.flush()
        resume.is_primary = True
        db.session.commit()
        flash("Active resume updated.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to set active resume. Please try again.", "danger")
    return redirect(url_for("student.resumes"))


@student_bp.route("/resumes/<resume_id>/delete", methods=["POST"])
@role_required(UserRole.STUDENT)
def delete_resume(resume_id):
    student, resume = _resume_or_404(resume_id)
    was_primary = resume.is_primary
    file_path = Path(resume.file_path)
    try:
        db.session.delete(resume)
        db.session.flush()
        if was_primary:
            next_resume = student.resumes.order_by(Resume.uploaded_at.desc(), Resume.created_at.desc()).first()
            if next_resume:
                next_resume.is_primary = True
        db.session.commit()
        file_path.unlink(missing_ok=True)
        flash("Resume deleted.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to delete resume. Please try again.", "danger")
    return redirect(url_for("student.resumes"))


def _application_status_badge(status):
    mapping = {
        "submitted": "primary",
        "under_review": "info",
        "shortlisted": "success",
        "interview_in_progress": "warning",
        "selected": "success",
        "offered": "success",
        "placed": "success",
        "rejected": "danger",
        "withdrawn": "secondary",
        "not_selected": "secondary",
        "draft": "secondary",
    }
    value = status.value if hasattr(status, "value") else status
    return mapping.get(value, "secondary")


def _drive_or_404(drive_id):
    student = _student_or_404()
    try:
        return student, DriveService.get_for_student(student, _uuid_or_404(drive_id))
    except DriveNotFoundError:
        abort(404)


def _application_or_404(application_id):
    student = _student_or_404()
    try:
        return student, ApplicationService.get_for_student(student, _uuid_or_404(application_id))
    except ApplicationNotFoundError:
        abort(404)


def _resume_choices(student):
    resumes = student.resumes.order_by(Resume.is_primary.desc(), Resume.uploaded_at.desc()).all()
    return [(str(resume.id), f"{resume.file_name}{' (Active)' if resume.is_primary else ''}") for resume in resumes]


@student_bp.route("/drives")
@role_required(UserRole.STUDENT)
def drives():
    from app.models.student import Student, StudentSkill, StudentProject, StudentCertification
    from sqlalchemy.orm import joinedload
    
    student = Student.query.options(joinedload(Student.verifier)).filter_by(user_id=current_user.id).first_or_404()
    
    # Preload related collections for completion checks to avoid duplicate queries
    preloaded_data = {}
    preloaded_data["skills"] = StudentSkill.query.options(joinedload(StudentSkill.skill)).filter_by(student_id=student.id).all()
    preloaded_data["projects"] = StudentProject.query.filter_by(student_id=student.id).all()
    preloaded_data["certifications"] = StudentCertification.query.filter_by(student_id=student.id).all()
    preloaded_data["resumes"] = Resume.query.filter_by(student_id=student.id).all()
    
    form = DriveSearchForm(request.args, meta={"csrf": False})
    
    # Calculate profile completion and locking
    profile_completion, comp_checklist = _profile_completion_data(student, preloaded_data=preloaded_data)
    is_verified = student.profile_status == ProfileStatus.VERIFIED
    locked = not (profile_completion == 100 and is_verified)
    
    checklist = {
        "personal": bool(student.first_name and student.last_name and student.phone and student.date_of_birth and student.gender and student.bio),
        "academic": bool(student.cgpa is not None and student.graduation_year and student.batch and student.semester),
        "resume": comp_checklist["resumes"],
        "skills": comp_checklist["skills"],
        "projects": comp_checklist["projects"],
        "verification": is_verified
    }
    
    if locked:
        drive_items = []
    else:
        preloaded_skills = {
            link.skill.name.strip().lower()
            for link in preloaded_data["skills"]
            if link.skill and link.skill.name
        }
        drive_items = DriveService.list_for_student(
            student,
            q=form.q.data,
            location_type=form.location_type.data or None,
            min_package=form.min_package.data,
            eligibility_filter=form.eligibility.data or None,
            sort=form.sort.data or "deadline",
            student_skills=preloaded_skills
        )
        
    return render_template(
        "student/drives.html",
        form=form,
        drive_items=drive_items,
        status_badge=_application_status_badge,
        locked=locked,
        profile_completion=profile_completion,
        checklist=checklist,
        student=student
    )


@student_bp.route("/drives/<drive_id>")
@role_required(UserRole.STUDENT)
def drive_detail(drive_id):
    student, drive_item = _drive_or_404(drive_id)
    apply_form = ApplicationForm()
    apply_form.resume_id.choices = _resume_choices(student)
    if not apply_form.resume_id.choices:
        apply_form.resume_id.choices = [("", "Upload a resume first")]

    primary_resume = student.resumes.filter_by(is_primary=True).first()
    if primary_resume:
        apply_form.resume_id.data = str(primary_resume.id)

    return render_template(
        "student/drive_detail.html",
        drive_item=drive_item,
        apply_form=apply_form,
        status_badge=_application_status_badge,
    )


@student_bp.route("/drives/<drive_id>/apply", methods=["POST"])
@role_required(UserRole.STUDENT)
def apply_drive(drive_id):
    student = _student_or_404()
    apply_form = ApplicationForm()
    apply_form.resume_id.choices = _resume_choices(student)
    if not apply_form.validate_on_submit():
        flash("Please correct the application form and try again.", "danger")
        return redirect(url_for("student.drive_detail", drive_id=drive_id))

    try:
        application = ApplicationService.apply(
            student,
            _uuid_or_404(drive_id),
            resume_id=_uuid_or_404(apply_form.resume_id.data),
            cover_note=apply_form.cover_note.data,
        )
        flash("Application submitted successfully.", "success")
        return redirect(url_for("student.application_detail", application_id=application.id))
    except StudentServiceError as exc:
        flash(exc.message, "danger")
    except Exception:
        db.session.rollback()
        flash("Unable to submit application. Please try again.", "danger")
    return redirect(url_for("student.drive_detail", drive_id=drive_id))


@student_bp.route("/applications")
@role_required(UserRole.STUDENT)
def applications():
    student = _student_or_404()
    form = ApplicationSearchForm(request.args, meta={"csrf": False})
    history = ApplicationService.list_for_student(
        student,
        status=form.status.data or None,
        q=form.q.data,
    )
    summary = ApplicationService.summary(student)
    return render_template(
        "student/applications.html",
        form=form,
        applications=history,
        summary=summary,
        status_badge=_application_status_badge,
    )


@student_bp.route("/applications/<application_id>")
@role_required(UserRole.STUDENT)
def application_detail(application_id):
    student, application = _application_or_404(application_id)
    drive_item = DriveService.get_for_student(student, application.drive_id)

    return render_template(
        "student/application_detail.html",
        application=application,
        drive_item=drive_item,
        can_withdraw=application.status in WITHDRAWABLE_STATUSES,
        status_badge=_application_status_badge,
    )


@student_bp.route("/applications/<application_id>/withdraw", methods=["POST"])
@role_required(UserRole.STUDENT)
def withdraw_application(application_id):
    student = _student_or_404()
    try:
        ApplicationService.withdraw(student, _uuid_or_404(application_id))
        flash("Application withdrawn successfully.", "info")
        return redirect(url_for("student.applications"))
    except StudentServiceError as exc:
        flash(exc.message, "danger")
    except Exception:
        db.session.rollback()
        flash("Unable to withdraw application. Please try again.", "danger")
    return redirect(url_for("student.application_detail", application_id=application_id))


@student_bp.route("/applications/<application_id>/offer/accept", methods=["POST"])
@role_required(UserRole.STUDENT)
def accept_offer(application_id):
    student = _student_or_404()
    app_uuid = _uuid_or_404(application_id)
    application = ApplicationService.get_for_student(student, app_uuid)
    offer = Offer.query.filter_by(application_id=application.id, status=OfferStatus.EXTENDED).first_or_404()
    
    response_note = request.form.get("response_note", "").strip()
    try:
        from app.recruiter.services import RecruiterService
        RecruiterService.record_offer_response(offer.id, OfferStatus.ACCEPTED.value, response_note)
        flash("Congratulations! You have successfully accepted the offer.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Unable to accept offer: {str(exc)}", "danger")
        
    return redirect(url_for("student.application_detail", application_id=application_id))


@student_bp.route("/applications/<application_id>/offer/decline", methods=["POST"])
@role_required(UserRole.STUDENT)
def decline_offer(application_id):
    student = _student_or_404()
    app_uuid = _uuid_or_404(application_id)
    application = ApplicationService.get_for_student(student, app_uuid)
    offer = Offer.query.filter_by(application_id=application.id, status=OfferStatus.EXTENDED).first_or_404()
    
    response_note = request.form.get("response_note", "").strip()
    try:
        from app.recruiter.services import RecruiterService
        RecruiterService.record_offer_response(offer.id, OfferStatus.DECLINED.value, response_note)
        flash("You have declined the offer.", "warning")
    except Exception as exc:
        db.session.rollback()
        flash(f"Unable to decline offer: {str(exc)}", "danger")
        
    return redirect(url_for("student.application_detail", application_id=application_id))


@student_bp.route("/resumes/<resume_id>/parsed", methods=["GET"])
@role_required(UserRole.STUDENT, UserRole.TPO)
def view_parsed_resume(resume_id):
    resume = Resume.query.get_or_404(_uuid_or_404(resume_id))
    
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        if not student or resume.student_id != student.id:
            abort(403)
    elif current_user.role == UserRole.TPO:
        from app.tpo.services import TpoService
        TpoService.validate_college_access(resume)

    parsed_data = {}
    if resume.parsed_text:
        try:
            parsed_data = json.loads(resume.parsed_text)
        except Exception:
            parsed_data = {}

    return render_template(
        "student/resume_parsed.html",
        resume=resume,
        parsed_data=parsed_data.get("structured_data", {}) if "structured_data" in parsed_data else parsed_data
    )


@student_bp.route("/resumes/<resume_id>/reparse", methods=["POST"])
@role_required(UserRole.STUDENT, UserRole.TPO)
def reparse_resume(resume_id):
    resume = Resume.query.get_or_404(_uuid_or_404(resume_id))
    
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        if not student or resume.student_id != student.id:
            abort(403)
    elif current_user.role == UserRole.TPO:
        from app.tpo.services import TpoService
        TpoService.validate_college_access(resume)

    try:
        from app.student.resume_parser import ResumeParserService
        ResumeParserService.parse_and_save_resume(resume.id)
        flash("Resume successfully parsed.", "success")
    except Exception:
        flash("Parsing failed. Please verify PDF file integrity.", "danger")

    if current_user.role == UserRole.TPO:
        return redirect(url_for("tpo.review_student", student_id=resume.student_id))
    return redirect(url_for("student.resumes"))


@student_bp.route("/ats", methods=["GET"])
@role_required(UserRole.STUDENT)
def ats_dashboard():
    student = _student_or_404()
    
    # Get active drives list
    from app.student.services import DriveService
    from app.student.ats_service import AtsService
    from app.models.drive import PlacementDrive
    from app.models.enums import DriveStatus, EligibilityRuleType
    from app.models.application import Application
    from decimal import Decimal
    import json
    
    # Limit to student's own college
    drives = PlacementDrive.query.filter(
        PlacementDrive.college_id == student.college_id,
        PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])
    ).all()
    
    resume = AtsService._primary_or_latest_resume(student)
    
    parsed_envelope = None
    if resume and resume.parsed_text:
        try:
            parsed_envelope = json.loads(resume.parsed_text)
        except Exception:
            pass
    
    # Fetch student's applications for these drives in a single query
    apps = Application.query.filter(
        Application.student_id == student.id,
        Application.drive_id.in_([d.id for d in drives])
    ).all()
    app_map = {app.drive_id: app for app in apps}
    
    # Pre-fetch all eligibility rules for these drives in a single query
    from app.models.drive import EligibilityRule
    from collections import defaultdict
    drive_ids = [d.id for d in drives]
    rules_map = defaultdict(list)
    if drive_ids:
        rules_list = EligibilityRule.query.filter(EligibilityRule.drive_id.in_(drive_ids)).all()
        for rule in rules_list:
            rules_map[rule.drive_id].append(rule)

    # Pre-fetch student's skills with names in a single query
    from app.models.student import StudentSkill
    from sqlalchemy.orm import joinedload
    student_skills_loaded = StudentSkill.query.options(joinedload(StudentSkill.skill))\
        .filter_by(student_id=student.id).all()
    student_skills = {
        link.skill.name.strip().lower()
        for link in student_skills_loaded
        if link.skill and link.skill.name
    }
    
    drives_with_ats = []
    for d in drives:
        app = app_map.get(d.id)
        if app and app.ats_score is not None and app.ats_data is not None:
            try:
                ats_data = json.loads(app.ats_data)
            except Exception:
                ats_data = {}
            score = float(app.ats_score)
            missing_count = len(ats_data.get("missing_skills", []))
        else:
            ats_data = AtsService.calculate_ats_score(
                student, d, resume=resume, drive_rules=rules_map.get(d.id), student_skills=student_skills, parsed_envelope=parsed_envelope
            )
            score = ats_data["score"]
            missing_count = len(ats_data["missing_skills"])
            if app:
                try:
                    app.ats_score = Decimal(str(score))
                    # compute match_score
                    required_skills = []
                    skills_rule = next((r for r in rules_map.get(d.id) if r.rule_type == EligibilityRuleType.REQUIRED_SKILL), None)
                    if skills_rule and isinstance(skills_rule.rule_value, dict):
                        required_skills = skills_rule.rule_value.get("value", [])
                    if required_skills:
                        matching = sum(1 for s in required_skills if s.strip().lower() in student_skills)
                        match_score = round((matching / len(required_skills) * 100), 2)
                    else:
                        match_score = 75.0
                    app.match_score = Decimal(str(match_score))
                    app.ats_data = json.dumps(ats_data)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    
        drives_with_ats.append({
            "drive": d,
            "ats_score": score,
            "missing_count": missing_count
        })

    return render_template(
        "student/ats_dashboard.html",
        drives=drives_with_ats,
        student=student
    )


@student_bp.route("/ats/drive/<uuid:drive_id>", methods=["GET"])
@role_required(UserRole.STUDENT)
def view_ats_details(drive_id):
    student = _student_or_404()
    from app.models.drive import PlacementDrive
    drive = PlacementDrive.query.get_or_404(drive_id)
    
    from app.models.application import Application
    app = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
    
    import json
    from decimal import Decimal
    from app.student.ats_service import AtsService
    from app.models.enums import EligibilityRuleType
    
    if app and app.ats_score is not None and app.ats_data is not None:
        try:
            ats_data = json.loads(app.ats_data)
        except Exception:
            ats_data = AtsService.calculate_ats_score(student, drive)
    else:
        ats_data = AtsService.calculate_ats_score(student, drive)
        if app:
            try:
                app.ats_score = Decimal(str(ats_data["score"]))
                # compute match_score
                required_skills = []
                skills_rule = drive.eligibility_rules.filter_by(rule_type=EligibilityRuleType.REQUIRED_SKILL).first()
                if skills_rule and isinstance(skills_rule.rule_value, dict):
                    required_skills = skills_rule.rule_value.get("value", [])
                student_skills = {
                    s_skill.skill.name.strip().lower()
                    for s_skill in student.skills.all()
                    if s_skill.skill and s_skill.skill.name
                }
                if required_skills:
                    matching = sum(1 for s in required_skills if s.strip().lower() in student_skills)
                    match_score = round((matching / len(required_skills) * 100), 2)
                else:
                    match_score = 75.0
                app.match_score = Decimal(str(match_score))
                app.ats_data = json.dumps(ats_data)
                db.session.commit()
            except Exception:
                db.session.rollback()

    return render_template(
        "student/ats_details.html",
        drive=drive,
        ats_data=ats_data,
        student=student
    )


@student_bp.route("/profile/request-change", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def request_profile_change():
    student = _student_or_404()
    if student.profile_status != ProfileStatus.VERIFIED:
        flash("You can only request profile changes after your profile has been verified.", "warning")
        return redirect(url_for("student.profile"))

    form = ProfileChangeRequestForm()
    
    from app.models.college import Branch
    branches = Branch.query.filter_by(college_id=student.college_id).all()
    branch_choices = [(str(b.id), b.name) for b in branches]
    
    if form.validate_on_submit():
        field = form.field_name.data
        req_val = form.requested_value.data.strip()
        reason = form.reason.data.strip()
        
        # Check duplicate pending request
        from app.models.student import ProfileChangeRequest
        existing = ProfileChangeRequest.query.filter_by(
            student_id=student.id,
            field_name=field,
            status="pending"
        ).first()
        
        if existing:
            flash(f"You already have a pending change request for the field '{field.replace('_', ' ').title()}'. Please wait for TPO review.", "danger")
            return redirect(url_for("student.profile"))
            
        old_val = ""
        if field == "email":
            old_val = student.user.email
        elif field == "branch_id":
            old_val = str(student.branch_id)
        else:
            old_val = str(getattr(student, field, ""))
            
        req = ProfileChangeRequest(
            student_id=student.id,
            field_name=field,
            old_value=old_val,
            requested_value=req_val,
            reason=reason,
            status="pending"
        )
        db.session.add(req)
        
        # Dispatch system notification
        from app.models.notification import Notification, NotificationType
        notification = Notification(
            user_id=student.user_id,
            title="Profile Change Request Submitted",
            message=f"Your request to change the field '{field.replace('_', ' ').title()}' to '{req_val}' has been submitted for TPO review.",
            notification_type=NotificationType.INFO,
            entity_type="student",
            entity_id=student.id
        )
        db.session.add(notification)
        db.session.commit()
        
        flash("Profile change request submitted successfully to the Training & Placement Office.", "success")
        return redirect(url_for("student.profile"))
        
    return render_template("student/request_change.html", form=form, student=student, branch_choices=branch_choices)


@student_bp.route("/notifications")
@role_required(UserRole.STUDENT)
def notifications_page():
    student = _student_or_404()
    from app.utils.notification_service import NotificationService
    page = request.args.get("page", 1, type=int)
    pagination = NotificationService.get_paginated_notifications(current_user.id, page=page, per_page=10)
    return render_template(
        "student/notifications.html",
        pagination=pagination,
        student=student
    )


@student_bp.route("/profile/resubmit", methods=["POST"])
@role_required(UserRole.STUDENT)
def resubmit_profile():
    student = _student_or_404()
    if (student.rejection_count or 0) >= 3:
        flash("Your profile has been rejected 3 times. You can no longer resubmit for verification. Please contact the Training & Placement Office.", "danger")
        return redirect(url_for("student.profile"))

    if student.profile_status != ProfileStatus.REJECTED:
        flash("You can only resubmit a rejected profile.", "warning")
        return redirect(url_for("student.profile"))

    if not student.is_profile_complete():
        flash("Your profile is not complete yet. Please complete all sections before requesting verification.", "warning")
        return redirect(url_for("student.profile"))

    from app.utils.notification_service import NotificationService
    from app.models.enums import NotificationType
    
    try:
        # Completely reset reviewer metadata & status
        student.profile_status = ProfileStatus.PENDING_VERIFICATION
        student.rejection_reason = None
        student.verified_by = None
        student.verified_at = None

        # Create notification
        NotificationService.create_notification(
            user_id=student.user_id,
            title="Profile Resubmitted",
            message="Your profile has been successfully resubmitted for verification.",
            notification_type=NotificationType.INFO,
            entity_type="student",
            entity_id=student.id
        )
        db.session.commit()
        flash("Your profile has been successfully resubmitted for TPO verification.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during profile resubmission: {str(e)}", exc_info=True)
        flash("An error occurred while resubmitting your profile. Please try again.", "danger")
    
    return redirect(url_for("student.profile"))
