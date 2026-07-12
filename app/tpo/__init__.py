import uuid
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, render_template, abort, current_app, flash, redirect, request, url_for, make_response
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models.company import Company
from app.models.college import Branch
from app.models.student import Student
from app.models.drive import PlacementDrive
from app.models.application import InterviewRound, Application, RoundResult
from app.models.notification import Announcement
from app.models.enums import UserRole, VerificationStatus, DriveStatus, ProfileStatus, AnnouncementAudience
from app.tpo.services import TpoService
from app.tpo.forms import (
    CompanyForm,
    CompanyLogoForm,
    CompanySearchForm,
    PlacementDriveForm,
    InterviewRoundForm,
    TpoDriveSearchForm
)

tpo_bp = Blueprint("tpo", __name__)


@tpo_bp.app_context_processor
def inject_logo_helpers():
    def get_company_logo_url(company_id):
        upload_dir = Path(current_app.root_path) / "static" / "uploads" / "company_logos"
        for ext in ["png", "jpg", "jpeg"]:
            if (upload_dir / f"{company_id}.{ext}").exists():
                return url_for("static", filename=f"uploads/company_logos/{company_id}.{ext}")
        return None
    return dict(get_company_logo_url=get_company_logo_url)


@tpo_bp.route("/dashboard")
@role_required(UserRole.TPO)
def dashboard():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    college_id = tpo_admin.college_id

    # Fetch dashboard data
    stats = TpoService.get_dashboard_stats(college_id)
    drive_stats = TpoService.get_drive_status_stats(college_id)
    recent_offers = TpoService.get_recent_offers(college_id, limit=5)
    yearly_trends = TpoService.get_yearly_placement_trends(college_id)
    branch_stats = TpoService.get_branch_placement_stats(college_id)
    package_dist = TpoService.get_package_distribution(college_id)
    company_stats = TpoService.get_company_placement_stats(college_id)
    recent_drives = TpoService.get_recent_drives(college_id, limit=5)
    pending_students = TpoService.get_pending_verifications_list(college_id, limit=5)

    return render_template(
        "portals/tpo_dashboard.html",
        stats=stats,
        drive_stats=drive_stats,
        recent_offers=recent_offers,
        yearly_trends=yearly_trends,
        branch_stats=branch_stats,
        package_dist=package_dist,
        company_stats=company_stats,
        recent_drives=recent_drives,
        pending_students=pending_students
    )


# ==========================================
# COMPANY MANAGEMENT ROUTES
# ==========================================

@tpo_bp.route("/companies", methods=["GET"])
@role_required(UserRole.TPO)
def companies():
    search_form = CompanySearchForm(request.args, meta={"csrf": False})
    
    q = search_form.q.data
    verification = search_form.verification.data
    active = search_form.active.data

    companies_list = TpoService.get_companies_list(q=q, verification=verification, active=active)
    overall_stats = TpoService.get_company_overall_stats()

    return render_template(
        "tpo/companies.html",
        companies=companies_list,
        search_form=search_form,
        stats=overall_stats
    )


@tpo_bp.route("/companies/new", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def create_company():
    form = CompanyForm()
    if form.validate_on_submit():
        try:
            company = Company(
                name=form.name.data.strip(),
                legal_name=form.legal_name.data.strip() if form.legal_name.data else None,
                website=form.website.data.strip() if form.website.data else None,
                industry=form.industry.data.strip() if form.industry.data else None,
                company_size=form.company_size.data if form.company_size.data else None,
                description=form.description.data.strip() if form.description.data else None,
                hq_city=form.hq_city.data.strip() if form.hq_city.data else None,
                hq_country=form.hq_country.data.strip() if form.hq_country.data else "India",
                contact_email=form.contact_email.data.strip().lower() if form.contact_email.data else None,
                verification_status=VerificationStatus(form.verification_status.data),
                is_active=form.is_active.data
            )
            
            if company.verification_status == VerificationStatus.APPROVED:
                company.verified_at = db.func.now()
                company.verified_by = current_user.id
                
            db.session.add(company)
            db.session.commit()
            flash(f"Company '{company.name}' added successfully.", "success")
            return redirect(url_for("tpo.companies"))
        except Exception:
            db.session.rollback()
            flash("Unable to create company. Please check details and try again.", "danger")
            
    return render_template("tpo/company_form.html", form=form, title="Add Company")


@tpo_bp.route("/companies/<uuid:company_id>", methods=["GET"])
@role_required(UserRole.TPO)
def view_company(company_id):
    company = Company.query.get_or_404(company_id)
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    college_id = tpo_admin.college_id

    # Fetch stats and history
    company_stats = TpoService.get_company_stats(college_id, company_id)
    history = TpoService.get_company_recruitment_history(college_id, company_id)
    logo_form = CompanyLogoForm()

    return render_template(
        "tpo/company_profile.html",
        company=company,
        stats=company_stats,
        history=history,
        logo_form=logo_form
    )


@tpo_bp.route("/companies/<uuid:company_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def edit_company(company_id):
    company = Company.query.get_or_404(company_id)
    form = CompanyForm(obj=company)
    
    if request.method == "GET":
        form.verification_status.data = company.verification_status.value

    if form.validate_on_submit():
        try:
            company.name = form.name.data.strip()
            company.legal_name = form.legal_name.data.strip() if form.legal_name.data else None
            company.website = form.website.data.strip() if form.website.data else None
            company.industry = form.industry.data.strip() if form.industry.data else None
            company.company_size = form.company_size.data if form.company_size.data else None
            company.description = form.description.data.strip() if form.description.data else None
            company.hq_city = form.hq_city.data.strip() if form.hq_city.data else None
            company.hq_country = form.hq_country.data.strip() if form.hq_country.data else "India"
            company.contact_email = form.contact_email.data.strip().lower() if form.contact_email.data else None
            
            new_status = VerificationStatus(form.verification_status.data)
            if new_status != company.verification_status:
                company.verification_status = new_status
                if new_status == VerificationStatus.APPROVED:
                    company.verified_at = db.func.now()
                    company.verified_by = current_user.id
                else:
                    company.verified_at = None
                    company.verified_by = None
                    
            company.is_active = form.is_active.data
            
            db.session.commit()
            flash(f"Company '{company.name}' updated successfully.", "success")
            return redirect(url_for("tpo.view_company", company_id=company.id))
        except Exception:
            db.session.rollback()
            flash("Unable to update company details. Please try again.", "danger")
            
    return render_template("tpo/company_form.html", form=form, title="Edit Company", company=company)


@tpo_bp.route("/companies/<uuid:company_id>/logo", methods=["POST"])
@role_required(UserRole.TPO)
def upload_company_logo(company_id):
    company = Company.query.get_or_404(company_id)
    form = CompanyLogoForm()
    
    if form.validate_on_submit():
        file = form.logo.data
        upload_dir = Path(current_app.root_path) / "static" / "uploads" / "company_logos"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine extension
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        
        # Delete old logo files for this company if they exist (different extensions)
        for old_ext in ["png", "jpg", "jpeg"]:
            old_file = upload_dir / f"{company_id}.{old_ext}"
            old_file.unlink(missing_ok=True)
            
        stored_name = f"{company_id}.{ext}"
        file_path = upload_dir / stored_name
        
        try:
            file.save(file_path)
            flash("Company logo uploaded successfully.", "success")
        except Exception:
            flash("Unable to save company logo. Please try again.", "danger")
    else:
        for error in form.logo.errors:
            flash(error, "danger")
            
    return redirect(url_for("tpo.view_company", company_id=company_id))


@tpo_bp.route("/companies/<uuid:company_id>/delete", methods=["POST"])
@role_required(UserRole.TPO)
def delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    company_name = company.name
    try:
        # Delete associated logo file if exists
        upload_dir = Path(current_app.root_path) / "static" / "uploads" / "company_logos"
        for ext in ["png", "jpg", "jpeg"]:
            logo_file = upload_dir / f"{company_id}.{ext}"
            logo_file.unlink(missing_ok=True)
            
        db.session.delete(company)
        db.session.commit()
        flash(f"Company '{company_name}' deleted.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to delete company. It may have placement drive records referencing it.", "danger")
        
    return redirect(url_for("tpo.companies"))


# ==========================================
# PLACEMENT DRIVE MANAGEMENT ROUTES
# ==========================================

@tpo_bp.route("/drives", methods=["GET"])
@role_required(UserRole.TPO)
def drives():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    college_id = tpo_admin.college_id
    search_form = TpoDriveSearchForm(request.args, meta={"csrf": False})
    
    # Populate companies choices dynamically
    companies_list = Company.query.order_by(Company.name.asc()).all()
    search_form.company_id.choices = [("", "All Companies")] + [(str(c.id), c.name) for c in companies_list]
    
    q = search_form.q.data
    status = search_form.status.data
    company_id = search_form.company_id.data

    drives_list = TpoService.get_drives_list(college_id, q=q, status=status, company_id=company_id)
    drive_stats = TpoService.get_drive_status_stats(college_id)

    return render_template(
        "tpo/drives.html",
        drives=drives_list,
        search_form=search_form,
        stats=drive_stats
    )


@tpo_bp.route("/drives/new", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def create_drive():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    form = PlacementDriveForm()
    
    # Populate company choices
    companies_list = Company.query.filter_by(is_active=True).order_by(Company.name.asc()).all()
    form.company_id.choices = [("", "Select hiring company")] + [(str(c.id), c.name) for c in companies_list]
    
    # Populate branch choices
    branches_list = Branch.query.filter_by(college_id=tpo_admin.college_id, is_active=True).order_by(Branch.name.asc()).all()
    form.eligible_branches.choices = [(str(b.id), f"{b.name} ({b.code})") for b in branches_list]

    if form.validate_on_submit():
        try:
            drive_data = {
                "company_id": form.company_id.data,
                "title": form.title.data,
                "job_role": form.job_role.data,
                "job_description": form.job_description.data,
                "vacancies": form.vacancies.data,
                "package_min_lpa": form.package_min_lpa.data,
                "package_max_lpa": form.package_max_lpa.data,
                "location_type": form.location_type.data,
                "venue": form.venue.data,
                "meeting_link": form.meeting_link.data,
                "drive_date": form.drive_date.data,
                "registration_deadline": form.registration_deadline.data,
                "status": form.status.data,
                "eligible_branches": form.eligible_branches.data,
                "min_cgpa": form.min_cgpa.data,
                "max_backlogs": form.max_backlogs.data,
                "required_skills": form.required_skills.data,
                "batch": form.batch.data
            }
            drive = TpoService.create_placement_drive(tpo_admin, drive_data)
            flash(f"Placement drive '{drive.title}' created successfully.", "success")
            return redirect(url_for("tpo.view_drive", drive_id=drive.id))
        except Exception:
            db.session.rollback()
            flash("Unable to create placement drive. Please verify details and try again.", "danger")

    return render_template("tpo/drive_form.html", form=form, title="Create Placement Drive")


@tpo_bp.route("/drives/<uuid:drive_id>", methods=["GET"])
@role_required(UserRole.TPO)
def view_drive(drive_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)

    stats = TpoService.get_drive_details_stats(drive_id)
    applicants = TpoService.get_drive_applicants(drive_id)
    rounds = TpoService.get_drive_rounds(drive_id)
    
    # Calculate round stats
    rounds_data = []
    for r in rounds:
        registered_count = r.interview_schedules.count()
        passed_count = db.session.query(db.func.count(RoundResult.id)).filter_by(round_id=r.id, result_status=db.text("'passed'")).scalar() or 0
        rounds_data.append({
            "round": r,
            "registered": registered_count,
            "passed": passed_count
        })

    round_form = InterviewRoundForm()

    return render_template(
        "tpo/drive_detail.html",
        drive=stats["drive"],
        total_applicants=stats["total_applicants"],
        shortlisted=stats["shortlisted"],
        placed_count=stats["placed_count"],
        selection_rate=stats["selection_rate"],
        rules_summary=stats["rules_summary"],
        applicants=applicants,
        rounds=rounds_data,
        round_form=round_form
    )


@tpo_bp.route("/drives/<uuid:drive_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def edit_drive(drive_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    drive = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive)
    
    # Load rules summary
    stats = TpoService.get_drive_details_stats(drive_id)
    rules = stats["rules_summary"]

    form = PlacementDriveForm(obj=drive)
    
    # Populate company choices
    companies_list = Company.query.filter_by(is_active=True).order_by(Company.name.asc()).all()
    form.company_id.choices = [("", "Select hiring company")] + [(str(c.id), c.name) for c in companies_list]
    
    # Populate branch choices
    branches_list = Branch.query.filter_by(college_id=tpo_admin.college_id, is_active=True).order_by(Branch.name.asc()).all()
    form.eligible_branches.choices = [(str(b.id), f"{b.name} ({b.code})") for b in branches_list]

    if request.method == "GET":
        form.company_id.data = str(drive.company_id)
        form.status.data = drive.status.value
        form.location_type.data = drive.location_type.value
        form.eligible_branches.data = [str(db_branch.branch_id) for db_branch in drive.drive_branches.all()]
        
        # Populate rules
        form.min_cgpa.data = rules["min_cgpa"]
        form.max_backlogs.data = rules["max_backlogs"]
        form.required_skills.data = rules["skills"]
        form.batch.data = rules["batch"]

    if form.validate_on_submit():
        try:
            drive_data = {
                "company_id": form.company_id.data,
                "title": form.title.data,
                "job_role": form.job_role.data,
                "job_description": form.job_description.data,
                "vacancies": form.vacancies.data,
                "package_min_lpa": form.package_min_lpa.data,
                "package_max_lpa": form.package_max_lpa.data,
                "location_type": form.location_type.data,
                "venue": form.venue.data,
                "meeting_link": form.meeting_link.data,
                "drive_date": form.drive_date.data,
                "registration_deadline": form.registration_deadline.data,
                "status": form.status.data,
                "eligible_branches": form.eligible_branches.data,
                "min_cgpa": form.min_cgpa.data,
                "max_backlogs": form.max_backlogs.data,
                "required_skills": form.required_skills.data,
                "batch": form.batch.data
            }
            TpoService.update_placement_drive(drive.id, drive_data)
            flash(f"Placement drive '{drive.title}' updated successfully.", "success")
            return redirect(url_for("tpo.view_drive", drive_id=drive.id))
        except Exception:
            db.session.rollback()
            flash("Unable to update placement drive. Please try again.", "danger")

    return render_template("tpo/drive_form.html", form=form, title="Edit Placement Drive", drive=drive)


@tpo_bp.route("/drives/<uuid:drive_id>/clone", methods=["POST"])
@role_required(UserRole.TPO)
def clone_drive(drive_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)
    try:
        cloned = TpoService.clone_placement_drive(drive_id, tpo_admin.id)
        flash(f"Placement drive cloned successfully as '{cloned.title}' in Draft status.", "success")
        return redirect(url_for("tpo.view_drive", drive_id=cloned.id))
    except Exception:
        db.session.rollback()
        flash("Unable to clone placement drive. Please try again.", "danger")
    return redirect(url_for("tpo.drives"))


@tpo_bp.route("/drives/<uuid:drive_id>/delete", methods=["POST"])
@role_required(UserRole.TPO)
def delete_drive(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive)
    title = drive.title
    try:
        db.session.delete(drive)
        db.session.commit()
        flash(f"Placement drive '{title}' deleted successfully.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to delete placement drive. Active student applications exist.", "danger")
    return redirect(url_for("tpo.drives"))


@tpo_bp.route("/drives/<uuid:drive_id>/status/<status>", methods=["POST"])
@role_required(UserRole.TPO)
def change_drive_status(drive_id, status):
    drive = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive)
    try:
        new_status = DriveStatus(status)
        drive.status = new_status
        if new_status == DriveStatus.PUBLISHED:
            drive.published_at = db.func.now()
        db.session.commit()
        flash(f"Drive status updated to '{new_status.value.replace('_', ' ').title()}'.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to change drive status. Please try again.", "danger")
    return redirect(url_for("tpo.view_drive", drive_id=drive.id))


@tpo_bp.route("/drives/<uuid:drive_id>/rounds", methods=["POST"])
@role_required(UserRole.TPO)
def add_round(drive_id):
    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)
    form = InterviewRoundForm()
    if form.validate_on_submit():
        try:
            round_data = {
                "round_name": form.round_name.data,
                "round_type": form.round_type.data,
                "description": form.description.data,
                "passing_score": form.passing_score.data,
                "sequence_order": form.sequence_order.data,
                "is_eliminatory": form.is_eliminatory.data
            }
            TpoService.add_interview_round(drive_id, round_data)
            flash("Interview round added successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Unable to add interview round. The sequence order number may already be in use.", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "danger")
                
    return redirect(url_for("tpo.view_drive", drive_id=drive_id))


@tpo_bp.route("/drives/<uuid:drive_id>/rounds/<uuid:round_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def edit_round(drive_id, round_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive)
    rnd = InterviewRound.query.filter_by(id=round_id, drive_id=drive_id).first_or_404()
    
    form = InterviewRoundForm(obj=rnd)
    
    if request.method == "GET":
        form.round_type.data = rnd.round_type.value

    if form.validate_on_submit():
        try:
            round_data = {
                "round_name": form.round_name.data,
                "round_type": form.round_type.data,
                "description": form.description.data,
                "passing_score": form.passing_score.data,
                "sequence_order": form.sequence_order.data,
                "is_eliminatory": form.is_eliminatory.data
            }
            TpoService.update_interview_round(round_id, round_data)
            flash("Interview round updated successfully.", "success")
            return redirect(url_for("tpo.view_drive", drive_id=drive_id))
        except Exception:
            db.session.rollback()
            flash("Unable to update interview round. Please try again.", "danger")
            
    return render_template("tpo/rounds_form.html", form=form, drive=drive, round=rnd, title="Edit Interview Round")


@tpo_bp.route("/drives/<uuid:drive_id>/rounds/<uuid:round_id>/delete", methods=["POST"])
@role_required(UserRole.TPO)
def delete_round(drive_id, round_id):
    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)
    try:
        TpoService.delete_interview_round(round_id)
        flash("Interview round removed.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to remove interview round. Candidate results exist for this round.", "danger")
    return redirect(url_for("tpo.view_drive", drive_id=drive_id))


# ==========================================
# STUDENT VERIFICATION ROUTES
# ==========================================

@tpo_bp.route("/verification", methods=["GET"])
@role_required(UserRole.TPO)
def verification():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    college_id = tpo_admin.college_id
    
    stats = TpoService.get_verification_stats(college_id)
    branch_stats = TpoService.get_branch_verification_stats(college_id)
    pending_students = TpoService.get_pending_students(college_id)
    
    return render_template(
        "tpo/verification_dashboard.html",
        stats=stats,
        branch_stats=branch_stats,
        pending_students=pending_students
    )


@tpo_bp.route("/verification/history", methods=["GET"])
@role_required(UserRole.TPO)
def verification_history():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    history = TpoService.get_verification_history(tpo_admin.college_id)
    return render_template("tpo/verification_history.html", history=history)


@tpo_bp.route("/verification/<uuid:student_id>", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def review_student(student_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    student = Student.query.get_or_404(student_id)
    TpoService.validate_college_access(student)
    
    resumes = student.resumes.order_by(Student.resumes.property.mapper.class_.is_primary.desc()).all()
    primary_resume = next((r for r in resumes if r.is_primary), None)
    
    projects = student.projects.all()
    certifications = student.certifications.all()
    skills_list = [s_skill.skill.name for s_skill in student.skills.all() if s_skill.skill]

    return render_template(
        "tpo/verification_review.html",
        student=student,
        primary_resume=primary_resume,
        resumes=resumes,
        projects=projects,
        certifications=certifications,
        skills=skills_list
    )


@tpo_bp.route("/verification/<uuid:student_id>/approve", methods=["POST"])
@role_required(UserRole.TPO)
def approve_student(student_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
    student = Student.query.get_or_404(student_id)
    TpoService.validate_college_access(student)
    try:
        TpoService.verify_student(student_id, current_user.id)
        flash("Student profile has been verified and academic details locked.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to verify student profile. Please try again.", "danger")
    return redirect(url_for("tpo.verification"))


@tpo_bp.route("/verification/<uuid:student_id>/reject", methods=["POST"])
@role_required(UserRole.TPO)
def reject_student(student_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
    student = Student.query.get_or_404(student_id)
    TpoService.validate_college_access(student)
        
    remarks = request.form.get("remarks", "").strip()
    try:
        TpoService.reject_student(student_id, current_user.id, remarks)
        flash("Student profile verification rejected and feedback sent to student.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to process rejection. Please try again.", "danger")
    return redirect(url_for("tpo.verification"))


@tpo_bp.route("/verification/bulk", methods=["POST"])
@role_required(UserRole.TPO)
def bulk_verify():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    student_ids = request.form.getlist("student_ids")
    if not student_ids:
        flash("Please select at least one student profile for bulk verification.", "warning")
        return redirect(url_for("tpo.verification"))
        
    try:
        verified_count, skipped = TpoService.bulk_verify_students(student_ids, current_user.id)
        if verified_count:
            flash(f"Successfully verified {verified_count} student profile(s) in bulk.", "success")
        if skipped:
            flash(f"{skipped} student profile(s) were skipped because they were incomplete or not pending verification.", "warning")
        if not verified_count and not skipped:
            flash("No student profiles were verified.", "warning")
    except Exception:
        db.session.rollback()
        flash("Bulk verification failed. Please try again.", "danger")
        
    return redirect(url_for("tpo.verification"))


# ==========================================
# AUTOMATIC ELIGIBILITY ENGINE ROUTES
# ==========================================

@tpo_bp.route("/drives/<uuid:drive_id>/eligibility", methods=["GET"])
@role_required(UserRole.TPO)
def drive_eligibility(drive_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)
    report = TpoService.get_drive_eligibility_report(drive_id, tpo_admin.college_id)
    
    return render_template(
        "tpo/drive_eligibility.html",
        drive=report["drive"],
        eligible=report["eligible"],
        ineligible=report["ineligible"],
        stats=report["stats"]
    )


@tpo_bp.route("/drives/<uuid:drive_id>/eligibility/export", methods=["GET"])
@role_required(UserRole.TPO)
def export_eligible_students(drive_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    drive_obj = PlacementDrive.query.get_or_404(drive_id)
    TpoService.validate_college_access(drive_obj)
    report = TpoService.get_drive_eligibility_report(drive_id, tpo_admin.college_id)
    drive = report["drive"]
    eligible_list = report["eligible"]
    
    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Student Name", 
        "Email", 
        "Enrollment Number", 
        "Branch", 
        "CGPA", 
        "Backlogs", 
        "Graduation Year", 
        "Batch"
    ])
    
    # Data rows
    for item in eligible_list:
        student = item["student"]
        writer.writerow([
            student.full_name,
            student.user.email,
            student.enrollment_number or "",
            student.branch.code if student.branch else "",
            student.cgpa or "",
            student.backlogs_count if student.backlogs_count is not None else "",
            student.graduation_year or "",
            student.batch or ""
        ])
        
    response = make_response(output.getvalue())
    clean_title = "".join(c for c in drive.title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    response.headers["Content-Disposition"] = f"attachment; filename=eligible_students_{clean_title}.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


# ==========================================
# PLACEMENT ANALYTICS ROUTES
# ==========================================

@tpo_bp.route("/analytics", methods=["GET"])
@role_required(UserRole.TPO)
def analytics():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    college_id = tpo_admin.college_id
    
    summary = TpoService.get_dashboard_stats(college_id)
    branch_data = TpoService.get_branch_analytics(college_id)
    company_data = TpoService.get_company_analytics(college_id)
    package_dist = TpoService.get_package_distribution(college_id)
    offer_stats = TpoService.get_offer_acceptance_stats(college_id)
    monthly_trends = TpoService.get_monthly_placement_trends(college_id)
    yearly_trends = TpoService.get_yearly_placement_trends(college_id)

    return render_template(
        "tpo/analytics.html",
        summary=summary,
        branch_data=branch_data,
        company_data=company_data,
        package_dist=package_dist,
        offer_stats=offer_stats,
        monthly_trends=monthly_trends,
        yearly_trends=yearly_trends
    )


@tpo_bp.route("/analytics/unplaced", methods=["GET"])
@role_required(UserRole.TPO)
def analytics_unplaced():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    unplaced_students = TpoService.get_unplaced_students_list(tpo_admin.college_id)
    
    # Calculate branch-wise counts of unplaced
    branch_counts = {}
    for item in unplaced_students:
        branch_code = item.branch.code if item.branch else "Unknown"
        branch_counts[branch_code] = branch_counts.get(branch_code, 0) + 1

    return render_template(
        "tpo/analytics_unplaced.html",
        unplaced=unplaced_students,
        branch_counts=branch_counts
    )


@tpo_bp.route("/announcements", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def announcements():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    college_id = tpo_admin.college_id

    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        content  = request.form.get("content", "").strip()
        audience = request.form.get("audience", AnnouncementAudience.ALL.value)
        is_pinned = request.form.get("is_pinned") == "on"

        if not title or not content:
            flash("Title and content are required.", "danger")
        else:
            try:
                audience_enum = AnnouncementAudience(audience)
            except ValueError:
                audience_enum = AnnouncementAudience.ALL

            ann = Announcement(
                college_id=college_id,
                created_by=current_user.id,
                title=title,
                content=content,
                target_audience=audience_enum,
                is_pinned=is_pinned,
                published_at=datetime.now(timezone.utc),
            )
            db.session.add(ann)
            try:
                db.session.commit()
                flash(f"Announcement '{title}' published successfully.", "success")
            except Exception:
                db.session.rollback()
                flash("Unable to publish announcement. Please try again.", "danger")

        return redirect(url_for("tpo.announcements"))

    # GET — list all announcements for this college
    all_announcements = Announcement.query.filter_by(college_id=college_id)\
        .order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc())\
        .all()

    return render_template(
        "tpo/announcements.html",
        announcements=all_announcements,
        audience_choices=[(a.value, a.value.title()) for a in AnnouncementAudience],
    )


@tpo_bp.route("/announcements/<uuid:ann_id>/delete", methods=["POST"])
@role_required(UserRole.TPO)
def delete_announcement(ann_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
    ann = Announcement.query.filter_by(id=ann_id, college_id=tpo_admin.college_id).first_or_404()
    db.session.delete(ann)
    db.session.commit()
    flash("Announcement deleted.", "info")
    return redirect(url_for("tpo.announcements"))


@tpo_bp.route("/analytics/export/<report_type>", methods=["GET"])
@role_required(UserRole.TPO)
def export_analytics(report_type):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    college_id = tpo_admin.college_id
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "branch":
        writer.writerow(["Branch Code", "Branch Name", "Total Students", "Placed", "Unplaced", "Highest Package (LPA)", "Average Package (LPA)", "Placement Rate (%)"])
        data = TpoService.get_branch_analytics(college_id)
        for item in data:
            writer.writerow([item["code"], item["name"], item["total"], item["placed"], item["unplaced"], item["highest"], item["average"], item["rate"]])
        filename = "branch_placement_report.csv"
        
    elif report_type == "company":
        writer.writerow(["Company Name", "Total Drives", "Total Hires", "Highest Package (LPA)", "Average Package (LPA)"])
        data = TpoService.get_company_analytics(college_id)
        for item in data:
            writer.writerow([item["name"], item["drives"], item["hires"], item["highest"], item["average"]])
        filename = "company_placement_report.csv"
        
    elif report_type == "year":
        writer.writerow(["Academic Year", "Total Students", "Placed Students", "Highest Package (LPA)", "Average Package (LPA)", "Placement Rate (%)"])
        data = TpoService.get_yearly_placement_trends(college_id)
        for item in data:
            writer.writerow([item["year"], item["total"], item["placed"], item["highest_package"], item["average_package"], item["placement_rate"]])
        filename = "yearly_placement_trends.csv"
        
    elif report_type == "unplaced":
        writer.writerow(["Student Name", "Email", "Enrollment Number", "Branch Code", "CGPA", "Backlogs", "Batch", "Graduation Year"])
        data = TpoService.get_unplaced_students_list(college_id)
        for s in data:
            writer.writerow([s.full_name, s.user.email, s.enrollment_number or "", s.branch.code if s.branch else "", s.cgpa or "", s.backlogs_count if s.backlogs_count is not None else "", s.batch or "", s.graduation_year or ""])
        filename = "unplaced_students_report.csv"
        
    else:
        abort(400)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv"
    return response


# ==========================================
# PROFILE CHANGE REQUESTS WORKFLOW (TPO)
# ==========================================

FIELD_LABELS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "date_of_birth": "Date of Birth",
    "gender": "Gender",
    "enrollment_number": "Enrollment Number",
    "branch_id": "Branch",
    "batch": "Batch",
    "graduation_year": "Graduation Year",
    "email": "Official College Email"
}

def format_field_value(field_name, value):
    if not value:
        return "N/A"
    if field_name == "branch_id":
        from app.models.college import Branch
        try:
            import uuid
            branch = Branch.query.get(uuid.UUID(value))
            return branch.name if branch else value
        except Exception:
            return value
    return value

def apply_profile_change(student, field_name, new_value_str):
    if field_name == "email":
        student.user.email = new_value_str
    elif field_name == "branch_id":
        import uuid
        student.branch_id = uuid.UUID(new_value_str)
    elif field_name == "graduation_year":
        student.graduation_year = int(new_value_str)
    elif field_name == "date_of_birth":
        from datetime import datetime
        student.date_of_birth = datetime.strptime(new_value_str, "%Y-%m-%d").date()
    elif field_name == "gender":
        student.gender = new_value_str
    elif field_name == "first_name":
        student.first_name = new_value_str
    elif field_name == "last_name":
        student.last_name = new_value_str
    elif field_name == "enrollment_number":
        student.enrollment_number = new_value_str
    elif field_name == "batch":
        student.batch = new_value_str


@tpo_bp.route("/verification/change-requests", methods=["GET"])
@role_required(UserRole.TPO)
def list_change_requests():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    from app.models.student import ProfileChangeRequest, Student
    
    # Query parameters
    search_query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "pending").strip()
    sort_order = request.args.get("sort", "newest").strip()
    
    # Base query for requests from the same college
    from sqlalchemy.orm import joinedload
    query = ProfileChangeRequest.query.join(Student).options(joinedload(ProfileChangeRequest.student)).filter(Student.college_id == tpo_admin.college_id)
    
    if status_filter:
        query = query.filter(ProfileChangeRequest.status == status_filter)
        
    if search_query:
        # Search by student name or enrollment number
        search_pattern = f"%{search_query}%"
        query = query.filter(
            (Student.first_name.ilike(search_pattern)) | 
            (Student.last_name.ilike(search_pattern)) | 
            (Student.enrollment_number.ilike(search_pattern))
        )
        
    if sort_order == "oldest":
        query = query.order_by(ProfileChangeRequest.created_at.asc())
    else:
        query = query.order_by(ProfileChangeRequest.created_at.desc())
        
    requests_list = query.all()
    
    return render_template(
        "tpo/change_requests.html",
        requests=requests_list,
        search_query=search_query,
        status_filter=status_filter,
        sort_order=sort_order,
        format_val=format_field_value,
        labels=FIELD_LABELS
    )


@tpo_bp.route("/verification/change-requests/<uuid:request_id>/approve", methods=["POST"])
@role_required(UserRole.TPO)
def approve_change_request(request_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    from app.models.student import ProfileChangeRequest
    req = ProfileChangeRequest.query.get_or_404(request_id)
    
    TpoService.validate_college_access(req.student)
        
    if req.status != "pending":
        flash("This request has already been reviewed.", "warning")
        return redirect(url_for("tpo.list_change_requests"))
        
    try:
        old_val = req.old_value
        new_val = req.requested_value
        field = req.field_name
        
        apply_profile_change(req.student, field, new_val)
        
        req.status = "approved"
        req.reviewed_by = current_user.id
        req.reviewed_at = db.func.now()
        
        # Audit Log
        from app.models.audit import AuditLog, AuditAction
        log = AuditLog(
            user_id=current_user.id,
            action=AuditAction.UPDATE.value,
            entity_type="student",
            entity_id=req.student.id,
            old_values={field: old_val},
            new_values={field: new_val},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)
        
        # Notify student
        from app.models.notification import Notification, NotificationType
        notification = Notification(
            user_id=req.student.user_id,
            title="Profile Change Approved",
            message=f"Your request to change '{FIELD_LABELS.get(field, field)}' has been approved. The value has been updated to '{format_field_value(field, new_val)}'.",
            notification_type=NotificationType.SUCCESS,
            entity_type="student",
            entity_id=req.student.id
        )
        db.session.add(notification)
        
        db.session.commit()
        flash("Profile change request approved successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error approving request: {str(exc)}", "danger")
        
    return redirect(url_for("tpo.list_change_requests"))


@tpo_bp.route("/verification/change-requests/<uuid:request_id>/reject", methods=["POST"])
@role_required(UserRole.TPO)
def reject_change_request(request_id):
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)
        
    from app.models.student import ProfileChangeRequest
    req = ProfileChangeRequest.query.get_or_404(request_id)
    
    TpoService.validate_college_access(req.student)
        
    if req.status != "pending":
        flash("This request has already been reviewed.", "warning")
        return redirect(url_for("tpo.list_change_requests"))
        
    rejection_reason = request.form.get("rejection_reason", "").strip()
    if not rejection_reason:
        flash("A rejection reason is required.", "danger")
        return redirect(url_for("tpo.list_change_requests"))
        
    try:
        req.status = "rejected"
        req.rejection_reason = rejection_reason
        req.reviewed_by = current_user.id
        req.reviewed_at = db.func.now()
        
        # Notify student
        from app.models.notification import Notification, NotificationType
        notification = Notification(
            user_id=req.student.user_id,
            title="Profile Change Rejected",
            message=f"Your request to change '{FIELD_LABELS.get(req.field_name, req.field_name)}' was rejected. Reason: {rejection_reason}",
            notification_type=NotificationType.WARNING,
            entity_type="student",
            entity_id=req.student.id
        )
        db.session.add(notification)
        
        db.session.commit()
        flash("Profile change request rejected.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error rejecting request: {str(exc)}", "danger")
        
    return redirect(url_for("tpo.list_change_requests"))


@tpo_bp.route("/profile", methods=["GET", "POST"])
@role_required(UserRole.TPO)
def profile():
    tpo_admin = current_user.tpo_profile
    if not tpo_admin:
        abort(404)

    college = tpo_admin.college
    from app.tpo.forms import TpoProfileForm
    form = TpoProfileForm(obj=tpo_admin)

    if form.validate_on_submit():
        try:
            tpo_admin.phone = form.phone.data.strip() if form.phone.data else None
            tpo_admin.designation = form.designation.data.strip() if form.designation.data else None
            tpo_admin.department = form.department.data.strip() if form.department.data else None
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("tpo.profile"))
        except Exception:
            db.session.rollback()
            flash("Unable to update profile. Please try again.", "danger")

    from app.models.student import Student
    from app.models.company import Recruiter, Company
    from app.models.drive import PlacementDrive
    from app.models.enums import ProfileStatus, DriveStatus

    students_managed = Student.query.filter_by(college_id=college.id).count()

    recruiters_connected = Recruiter.query.join(Company).join(PlacementDrive).filter(
        PlacementDrive.college_id == college.id
    ).distinct(Recruiter.id).count()

    active_drives = PlacementDrive.query.filter(
        PlacementDrive.college_id == college.id,
        PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])
    ).count()

    pending_verifications = Student.query.filter_by(
        college_id=college.id,
        profile_status=ProfileStatus.PENDING_VERIFICATION
    ).count()

    total_branches = college.branches.count()

    stats = {
        "students_managed": students_managed,
        "recruiters_connected": recruiters_connected,
        "active_drives": active_drives,
        "pending_verifications": pending_verifications,
        "total_branches": total_branches
    }

    return render_template(
        "tpo/profile.html",
        tpo_admin=tpo_admin,
        college=college,
        stats=stats,
        form=form
    )
