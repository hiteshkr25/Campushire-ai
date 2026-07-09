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
    student = _student_or_404()
    from app.student.ats_service import AtsService
    summary = ApplicationService.summary(student)
    recent_applications = ApplicationService.recent_active(student, limit=5)
    profile_completion = _profile_completion(student)
    ats_info = AtsService.calculate_dashboard_score(student)
    ats_checklist = AtsService.build_dashboard_checklist(student, profile_completion)
    return render_template(
        "portals/student_dashboard.html",
        application_summary=summary,
        recent_applications=recent_applications,
        profile_completion=profile_completion,
        ats_info=ats_info,
        ats_checklist=ats_checklist,
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


def _skills_text(student):
    skill_links = student.skills.order_by(StudentSkill.created_at.asc()).all()
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


def _profile_completion(student):
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
        student.skills.count() > 0,
        student.projects.count() > 0,
        student.certifications.count() > 0,
        student.resumes.count() > 0,
    ]
    return round((sum(1 for item in checks if item) / len(checks)) * 100)


@student_bp.route("/profile", methods=["GET", "POST"])
@role_required(UserRole.STUDENT)
def profile():
    student = _student_or_404()
    form = StudentProfileForm(obj=student)
    form.branch_id.choices = _branch_choices(student)
    if request.method == "GET":
        form.branch_id.data = str(student.branch_id)
        form.skills.data = _skills_text(student)

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

    projects = student.projects.order_by(StudentProject.created_at.desc()).all()
    certifications = student.certifications.order_by(StudentCertification.issue_date.desc()).all()
    
    from app.models.student import ProfileChangeRequest
    change_requests = student.change_requests.order_by(ProfileChangeRequest.created_at.desc()).all()
    
    return render_template(
        "student/profile.html",
        form=form,
        student=student,
        projects=projects,
        certifications=certifications,
        profile_completion=_profile_completion(student),
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
@role_required(UserRole.STUDENT)
def preview_resume(resume_id):
    student, resume = _resume_or_404(resume_id)
    file_path = Path(resume.file_path)
    if not file_path.exists():
        abort(404)
    if resume.mime_type == "application/pdf":
        return send_file(file_path, mimetype=resume.mime_type, as_attachment=False, download_name=resume.file_name)
    return render_template("student/resume_preview.html", resume=resume)


@student_bp.route("/resumes/<resume_id>/download")
@role_required(UserRole.STUDENT)
def download_resume(resume_id):
    student, resume = _resume_or_404(resume_id)
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
    student = _student_or_404()
    form = DriveSearchForm(request.args, meta={"csrf": False})
    
    # Calculate profile completion and locking
    profile_completion = _profile_completion(student)
    is_verified = student.profile_status == ProfileStatus.VERIFIED
    locked = not (profile_completion == 100 and is_verified)
    
    checklist = {
        "personal": bool(student.first_name and student.last_name and student.phone and student.date_of_birth and student.gender and student.bio),
        "academic": bool(student.cgpa is not None and student.graduation_year and student.batch and student.semester),
        "resume": student.resumes.count() > 0,
        "skills": student.skills.count() > 0,
        "projects": student.projects.count() > 0,
        "verification": is_verified
    }
    
    if locked:
        drive_items = []
    else:
        drive_items = DriveService.list_for_student(
            student,
            q=form.q.data,
            location_type=form.location_type.data or None,
            min_package=form.min_package.data,
            eligibility_filter=form.eligibility.data or None,
            sort=form.sort.data or "deadline",
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
@role_required(UserRole.STUDENT)
def view_parsed_resume(resume_id):
    student = _student_or_404()
    resume = Resume.query.filter_by(id=_uuid_or_404(resume_id), student_id=student.id).first_or_404()

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
@role_required(UserRole.STUDENT)
def reparse_resume(resume_id):
    student = _student_or_404()
    resume = Resume.query.filter_by(id=_uuid_or_404(resume_id), student_id=student.id).first_or_404()

    try:
        from app.student.resume_parser import ResumeParserService
        ResumeParserService.parse_and_save_resume(resume.id)
        flash("Resume successfully parsed.", "success")
    except Exception:
        flash("Parsing failed. Please verify PDF file integrity.", "danger")

    return redirect(url_for("student.resumes"))


@student_bp.route("/ats", methods=["GET"])
@role_required(UserRole.STUDENT)
def ats_dashboard():
    student = _student_or_404()
    
    # Get active drives list
    from app.student.services import DriveService
    from app.student.ats_service import AtsService
    from app.models.drive import PlacementDrive
    from app.models.enums import DriveStatus
    
    drives = PlacementDrive.query.filter(
        PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])
    ).all()
    
    drives_with_ats = []
    for d in drives:
        ats_data = AtsService.calculate_ats_score(student, d)
        drives_with_ats.append({
            "drive": d,
            "ats_score": ats_data["score"],
            "missing_count": len(ats_data["missing_skills"])
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
    
    from app.student.ats_service import AtsService
    ats_data = AtsService.calculate_ats_score(student, drive)

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
