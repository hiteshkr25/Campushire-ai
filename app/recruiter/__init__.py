import io
import csv
import uuid
from pathlib import Path
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, make_response, send_file
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models.enums import UserRole, ApplicationStatus, ScheduleStatus, RoundType, OfferStatus, DriveStatus
from app.models import Branch, PlacementDrive, Application, InterviewSchedule, InterviewRound, RoundResult, Offer
from app.recruiter.services import RecruiterService
from app.recruiter.forms import InterviewScheduleForm, InterviewEvaluationForm, OfferForm, OfferResponseForm

recruiter_bp = Blueprint("recruiter", __name__)


@recruiter_bp.app_context_processor
def inject_workflow_helpers():
    return dict(ScheduleStatus=ScheduleStatus, RoundType=RoundType, OfferStatus=OfferStatus)


@recruiter_bp.route("/dashboard")
@role_required(UserRole.RECRUITER)
def dashboard():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
    if not recruiter.is_active:
        abort(403)

    company_id = recruiter.company_id

    # Fetch stats, funnel data, interview schedules, offers, activities, notifications, and new analytics
    stats = RecruiterService.get_dashboard_stats(company_id)
    offers = RecruiterService.get_offer_stats(company_id)
    interviews = RecruiterService.get_upcoming_interviews(company_id, limit=5)
    activities = RecruiterService.get_recent_activities(company_id, limit=5)
    notifications = RecruiterService.get_notifications(current_user.id, limit=5)
    branch_pipeline = RecruiterService.get_branch_pipeline(company_id)
    package_dist = RecruiterService.get_package_distribution(company_id)

    return render_template(
        "portals/recruiter_dashboard.html",
        recruiter=recruiter,
        company=recruiter.company,
        stats=stats,
        offers=offers,
        interviews=interviews,
        activities=activities,
        notifications=notifications,
        branch_pipeline=branch_pipeline,
        package_dist=package_dist
    )


# ==========================================
# CANDIDATE REVIEW MODULE ROUTES
# ==========================================

@recruiter_bp.route("/candidates", methods=["GET"])
@role_required(UserRole.RECRUITER)
def candidates():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
        
    company_id = recruiter.company_id

    # Filters
    q = request.args.get("q", "").strip()
    branch_id = request.args.get("branch_id", "").strip()
    min_cgpa = request.args.get("min_cgpa", "").strip()
    max_backlogs = request.args.get("max_backlogs", "").strip()
    status = request.args.get("status", "").strip()
    drive_id = request.args.get("drive_id", "").strip()

    # Query lists
    candidates_list = RecruiterService.get_candidates_list(
        company_id=company_id,
        q=q,
        branch_id=branch_id,
        min_cgpa=min_cgpa,
        max_backlogs=max_backlogs,
        status=status,
        drive_id=drive_id
    )

    # General statistics for dashboard cards
    stats = RecruiterService.get_dashboard_stats(company_id)
    
    # Filter collections for dropdowns
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.name.asc()).all()
    drives = PlacementDrive.query.filter_by(company_id=company_id).order_by(PlacementDrive.title.asc()).all()

    return render_template(
        "recruiter/candidates.html",
        candidates=candidates_list,
        stats=stats,
        branches=branches,
        drives=drives,
        filters={
            "q": q,
            "branch_id": branch_id,
            "min_cgpa": min_cgpa,
            "max_backlogs": max_backlogs,
            "status": status,
            "drive_id": drive_id
        }
    )


@recruiter_bp.route("/candidates/<uuid:application_id>", methods=["GET"])
@role_required(UserRole.RECRUITER)
def view_candidate(application_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    # Load complete profile
    details = RecruiterService.get_candidate_profile_details(application_id)
    
    # Security: Verify this application belongs to the recruiter's company
    if details["drive"].company_id != recruiter.company_id:
        abort(403)

    return render_template(
        "recruiter/candidate_profile.html",
        application=details["application"],
        student=details["student"],
        drive=details["drive"],
        ats_score=details["ats_score"],
        match_score=details["match_score"],
        resumes=details["resumes"],
        primary_resume=details["primary_resume"],
        projects=details["projects"],
        certifications=details["certifications"],
        skills=details["skills"],
        statuses=[s.value for s in ApplicationStatus]
    )


@recruiter_bp.route("/candidates/<uuid:application_id>/evaluate", methods=["POST"])
@role_required(UserRole.RECRUITER)
def evaluate_candidate(application_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
        
    status = request.form.get("status", "").strip()
    remarks = request.form.get("remarks", "").strip()

    if not status:
        flash("Please select a valid evaluation status.", "warning")
        return redirect(url_for("recruiter.view_candidate", application_id=application_id))

    try:
        RecruiterService.evaluate_candidate(application_id, status, remarks, current_user.id)
        flash("Candidate status updated and notification dispatched.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to update candidate evaluation. Please try again.", "danger")

    return redirect(url_for("recruiter.view_candidate", application_id=application_id))


@recruiter_bp.route("/candidates/compare", methods=["GET"])
@role_required(UserRole.RECRUITER)
def compare_candidates():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    # Get application IDs from query params
    app_ids = request.args.getlist("ids")
    if not app_ids or len(app_ids) < 2:
        flash("Please select at least 2 candidates to compare.", "warning")
        return redirect(url_for("recruiter.candidates"))
    if len(app_ids) > 3:
        flash("You can compare a maximum of 3 candidates side-by-side.", "warning")
        app_ids = app_ids[:3]

    comparison_data = []
    for app_id in app_ids:
        try:
            details = RecruiterService.get_candidate_profile_details(uuid.UUID(app_id))
            if details["drive"].company_id == recruiter.company_id:
                comparison_data.append(details)
        except Exception:
            pass

    if len(comparison_data) < 2:
        flash("Comparison query failed. Invalid parameters.", "danger")
        return redirect(url_for("recruiter.candidates"))

    return render_template(
        "recruiter/candidate_compare.html",
        candidates=comparison_data
    )


@recruiter_bp.route("/candidates/export", methods=["GET"])
@role_required(UserRole.RECRUITER)
def export_candidates():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
        
    company_id = recruiter.company_id

    # Retrieve filters
    q = request.args.get("q", "").strip()
    branch_id = request.args.get("branch_id", "").strip()
    min_cgpa = request.args.get("min_cgpa", "").strip()
    max_backlogs = request.args.get("max_backlogs", "").strip()
    status = request.args.get("status", "").strip()
    drive_id = request.args.get("drive_id", "").strip()

    candidates_list = RecruiterService.get_candidates_list(
        company_id=company_id,
        q=q,
        branch_id=branch_id,
        min_cgpa=min_cgpa,
        max_backlogs=max_backlogs,
        status=status,
        drive_id=drive_id
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Candidate Name", 
        "Email", 
        "Enrollment Number", 
        "Branch", 
        "CGPA", 
        "Backlogs", 
        "Drive Title", 
        "ATS Score", 
        "Resume Match Score", 
        "Status"
    ])

    for item in candidates_list:
        student = item["student"]
        app = item["application"]
        writer.writerow([
            student.full_name,
            student.user.email,
            student.enrollment_number or "",
            student.branch.code if student.branch else "",
            student.cgpa or "",
            student.backlogs_count if student.backlogs_count is not None else "",
            app.drive.title,
            item["ats_score"],
            item["match_score"],
            app.status.value.replace("_", " ").title()
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=candidate_review_roster.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@recruiter_bp.route("/candidates/resumes/<uuid:resume_id>/preview")
@role_required(UserRole.RECRUITER)
def preview_candidate_resume(resume_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
        
    from app.models.student import Resume
    resume = Resume.query.get_or_404(resume_id)
    application = Application.query.join(PlacementDrive).filter(
        Application.student_id == resume.student_id,
        PlacementDrive.company_id == recruiter.company_id
    ).first()
    if not application:
        abort(403)
        
    file_path = Path(resume.file_path)
    if not file_path.exists():
        abort(404)
        
    if resume.mime_type == "application/pdf":
        return send_file(file_path, mimetype=resume.mime_type, as_attachment=False, download_name=resume.file_name)
    return render_template("student/resume_preview.html", resume=resume)


@recruiter_bp.route("/candidates/resumes/<uuid:resume_id>/download")
@role_required(UserRole.RECRUITER)
def download_candidate_resume(resume_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
        
    from app.models.student import Resume
    resume = Resume.query.get_or_404(resume_id)
    application = Application.query.join(PlacementDrive).filter(
        Application.student_id == resume.student_id,
        PlacementDrive.company_id == recruiter.company_id
    ).first()
    if not application:
        abort(403)
        
    file_path = Path(resume.file_path)
    if not file_path.exists():
        abort(404)
        
    return send_file(file_path, mimetype=resume.mime_type, as_attachment=True, download_name=resume.file_name)


# ==========================================
# INTERVIEW WORKFLOW MODULE ROUTES
# ==========================================

@recruiter_bp.route("/interviews", methods=["GET"])
@role_required(UserRole.RECRUITER)
def interviews():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company_id = recruiter.company_id

    # Filters
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    round_type = request.args.get("round_type", "").strip()
    drive_id = request.args.get("drive_id", "").strip()

    # Query schedules
    schedules = RecruiterService.get_interviews_list(
        company_id=company_id,
        q=q,
        status=status,
        round_type=round_type,
        drive_id=drive_id
    )

    # Statistics & Ratios
    stats = RecruiterService.get_interviews_dashboard_stats(company_id)
    
    # Dropdowns helper collections
    drives = PlacementDrive.query.filter_by(company_id=company_id).order_by(PlacementDrive.title.asc()).all()

    return render_template(
        "recruiter/interviews.html",
        interviews=schedules,
        stats=stats,
        drives=drives,
        filters={
            "q": q,
            "status": status,
            "round_type": round_type,
            "drive_id": drive_id
        }
    )


@recruiter_bp.route("/interviews/new", methods=["GET", "POST"])
@role_required(UserRole.RECRUITER)
def schedule_interview():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company_id = recruiter.company_id
    form = InterviewScheduleForm()

    drives = PlacementDrive.query.filter_by(company_id=company_id).all()
    form.drive_id.choices = [("", "Select Drive")] + [(str(d.id), d.title) for d in drives]
    
    drive_ids = [d.id for d in drives]
    rounds = InterviewRound.query.filter(InterviewRound.drive_id.in_(drive_ids)).all()
    form.round_id.choices = [("", "Select Round")] + [(str(r.id), f"{r.drive.title} - {r.round_name}") for r in rounds]
    
    apps = Application.query.join(PlacementDrive).filter(PlacementDrive.company_id == company_id).all()
    form.application_id.choices = [("", "Select Candidate")] + [(str(a.id), f"{a.student.full_name} ({a.drive.title})") for a in apps]

    if form.validate_on_submit():
        try:
            form_data = {
                "drive_id": form.drive_id.data,
                "round_id": form.round_id.data,
                "application_id": form.application_id.data,
                "scheduled_start": form.scheduled_start.data,
                "scheduled_end": form.scheduled_end.data,
                "venue": form.venue.data.strip() if form.venue.data else None,
                "meeting_link": form.meeting_link.data.strip() if form.meeting_link.data else None
            }
            RecruiterService.schedule_interview(form_data)
            flash("Interview round scheduled and student user alerted.", "success")
            return redirect(url_for("recruiter.interviews"))
        except Exception:
            db.session.rollback()
            flash("Unable to schedule interview evaluation. Please try again.", "danger")

    return render_template("recruiter/interview_form.html", form=form, title="Schedule Interview")


@recruiter_bp.route("/interviews/<uuid:schedule_id>/reschedule", methods=["GET", "POST"])
@role_required(UserRole.RECRUITER)
def reschedule_interview(schedule_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    schedule = InterviewSchedule.query.get_or_404(schedule_id)
    if schedule.round.drive.company_id != recruiter.company_id:
        abort(403)

    form = InterviewScheduleForm(obj=schedule)
    form.drive_id.choices = [(str(schedule.round.drive_id), schedule.round.drive.title)]
    form.round_id.choices = [(str(schedule.round_id), schedule.round.round_name)]
    form.application_id.choices = [(str(schedule.application_id), schedule.application.student.full_name)]

    if form.validate_on_submit():
        try:
            RecruiterService.reschedule_interview(
                schedule_id=schedule.id,
                start_time=form.scheduled_start.data,
                end_time=form.scheduled_end.data,
                venue=form.venue.data.strip() if form.venue.data else None,
                meeting_link=form.meeting_link.data.strip() if form.meeting_link.data else None
            )
            flash("Interview round rescheduled successfully.", "success")
            return redirect(url_for("recruiter.interviews"))
        except Exception:
            db.session.rollback()
            flash("Reschedule failed. Please verify data and try again.", "danger")

    return render_template("recruiter/interview_form.html", form=form, title="Reschedule Interview", schedule=schedule)


@recruiter_bp.route("/interviews/<uuid:schedule_id>/cancel", methods=["POST"])
@role_required(UserRole.RECRUITER)
def cancel_interview(schedule_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    schedule = InterviewSchedule.query.get_or_404(schedule_id)
    if schedule.round.drive.company_id != recruiter.company_id:
        abort(403)

    try:
        RecruiterService.cancel_interview(schedule.id)
        flash("Interview schedule cancelled successfully.", "info")
    except Exception:
        db.session.rollback()
        flash("Unable to cancel interview. Please try again.", "danger")

    return redirect(url_for("recruiter.interviews"))


@recruiter_bp.route("/interviews/<uuid:schedule_id>/evaluate", methods=["GET", "POST"])
@role_required(UserRole.RECRUITER)
def evaluate_interview(schedule_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    schedule = InterviewSchedule.query.get_or_404(schedule_id)
    if schedule.round.drive.company_id != recruiter.company_id:
        abort(403)

    result = RoundResult.query.filter_by(application_id=schedule.application_id, round_id=schedule.round_id).first()
    form = InterviewEvaluationForm(obj=result)
    
    if request.method == "GET" and result:
        form.status.data = result.result_status.value if result.result_status else ""

    if form.validate_on_submit():
        try:
            RecruiterService.evaluate_interview(
                schedule_id=schedule.id,
                score=form.score.data,
                status=form.status.data,
                remarks=form.remarks.data.strip() if form.remarks.data else "",
                evaluator_user_id=current_user.id
            )
            flash("Interview round evaluated and student score recorded.", "success")
            return redirect(url_for("recruiter.interviews"))
        except Exception:
            db.session.rollback()
            flash("Evaluation submission failed. Please try again.", "danger")

    return render_template("recruiter/interview_evaluate.html", form=form, schedule=schedule, result=result)


@recruiter_bp.route("/interviews/candidate/<uuid:application_id>/timeline", methods=["GET"])
@role_required(UserRole.RECRUITER)
def candidate_timeline(application_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    app = Application.query.get_or_404(application_id)
    if app.drive.company_id != recruiter.company_id:
        abort(403)

    timeline_data = RecruiterService.get_candidate_interview_timeline(application_id)

    return render_template(
        "recruiter/candidate_timeline.html",
        application=app,
        student=app.student,
        timeline=timeline_data
    )


# ==========================================
# OFFER MANAGEMENT MODULE ROUTES
# ==========================================

@recruiter_bp.route("/offers", methods=["GET"])
@role_required(UserRole.RECRUITER)
def offers_dashboard():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company_id = recruiter.company_id

    # Stats
    stats = RecruiterService.get_offer_stats(company_id)
    
    # Selections ready list
    selections = RecruiterService.get_offers_selection_list(company_id)
    
    # Extended offers list
    offers = RecruiterService.get_company_offers_list(company_id)
    
    # Form for recording offline responses
    response_form = OfferResponseForm()

    return render_template(
        "recruiter/offers.html",
        stats=stats,
        selections=selections,
        offers=offers,
        response_form=response_form
    )


@recruiter_bp.route("/offers/new", methods=["GET", "POST"])
@role_required(UserRole.RECRUITER)
def create_offer():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company_id = recruiter.company_id
    form = OfferForm()

    # Prepopulate candidates
    selections = RecruiterService.get_offers_selection_list(company_id)
    form.application_id.choices = [("", "Select Selected Candidate")] + [(str(s.id), f"{s.student.full_name} ({s.drive.title})") for s in selections]

    # Pre-select candidate if ID passed in args
    arg_app_id = request.args.get("application_id", "").strip()
    if request.method == "GET" and arg_app_id:
        form.application_id.data = arg_app_id

    if form.validate_on_submit():
        file = form.offer_letter.data
        try:
            form_data = {
                "application_id": form.application_id.data,
                "package_offered_lpa": form.package_offered_lpa.data,
                "job_location": form.job_location.data.strip(),
                "joining_date": form.joining_date.data,
                "expires_at": form.expires_at.data
            }
            RecruiterService.create_and_release_offer(form_data, file, recruiter.id)
            flash("Offer successfully released and student user notified.", "success")
            return redirect(url_for("recruiter.offers_dashboard"))
        except Exception:
            db.session.rollback()
            flash("Offer release failed. Please try again.", "danger")

    return render_template("recruiter/offer_form.html", form=form, title="Release Placement Offer")


@recruiter_bp.route("/offers/<uuid:offer_id>/response", methods=["POST"])
@role_required(UserRole.RECRUITER)
def record_response(offer_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    form = OfferResponseForm()
    if form.validate_on_submit():
        try:
            status = form.status.data
            note = form.response_note.data.strip() if form.response_note.data else ""
            RecruiterService.record_offer_response(offer_id, status, note)
            flash("Candidate response recorded successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Response entry failed. Please try again.", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "danger")
                
    return redirect(url_for("recruiter.offers_dashboard"))


@recruiter_bp.route("/offers/<uuid:offer_id>/revoke", methods=["POST"])
@role_required(UserRole.RECRUITER)
def revoke_offer(offer_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    try:
        RecruiterService.revoke_offer(offer_id)
        flash("Offer successfully revoked.", "info")
    except Exception:
        db.session.rollback()
        flash("Revocation failed. Please try again.", "danger")

    return redirect(url_for("recruiter.offers_dashboard"))


@recruiter_bp.route("/offers/export", methods=["GET"])
@role_required(UserRole.RECRUITER)
def export_offers():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company_id = recruiter.company_id
    offers = RecruiterService.get_company_offers_list(company_id)

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Candidate Name", 
        "Email", 
        "Drive Title", 
        "CTC Offered (LPA)", 
        "Job Location", 
        "Joining Date", 
        "Offer Status", 
        "Released Date"
    ])

    for o in offers:
        app = o.application
        writer.writerow([
            app.student.full_name,
            app.student.user.email,
            app.drive.title,
            o.package_offered_lpa,
            o.job_location,
            o.joining_date.strftime('%Y-%m-%d') if o.joining_date else "",
            o.status.value.replace("_", " ").title(),
            o.extended_at.strftime('%Y-%m-%d %H:%M') if o.extended_at else ""
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=placement_offers_tracker.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@recruiter_bp.route("/offers/download-letter/<uuid:offer_id>")
@role_required(UserRole.RECRUITER)
def download_offer_letter(offer_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    offer = Offer.query.get_or_404(offer_id)
    if offer.application.drive.company_id != recruiter.company_id:
        abort(403)

    if not offer.offer_letter_path:
        abort(404)

    file_path = Path(offer.offer_letter_path)
    if not file_path.exists():
        abort(404)

    return send_file(file_path, mimetype="application/pdf", as_attachment=True, download_name=f"offer_letter_{offer.id}.pdf")


@recruiter_bp.route("/company", methods=["GET"])
@role_required(UserRole.RECRUITER)
def company_profile():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    company = recruiter.company
    stats   = RecruiterService.get_company_profile_stats(company.id)
    history = RecruiterService.get_company_recruitment_history(company.id)
    team    = company.recruiters.filter_by(is_active=True).all()

    return render_template(
        "recruiter/company.html",
        company=company,
        recruiter=recruiter,
        stats=stats,
        history=history,
        team=team,
    )


@recruiter_bp.route("/drives", methods=["GET"])
@role_required(UserRole.RECRUITER)
def drives():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    status_filter = request.args.get("status", "").strip()
    drives_data = RecruiterService.get_company_drives(recruiter.company_id, status=status_filter or None)

    return render_template(
        "recruiter/drives.html",
        drives_data=drives_data,
        company=recruiter.company,
        DriveStatus=DriveStatus,
        current_status=status_filter,
    )


@recruiter_bp.route("/drives/<uuid:drive_id>/ats-rankings", methods=["GET"])
@role_required(UserRole.RECRUITER)
def drive_ats_rankings(drive_id):
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)

    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_id != recruiter.company_id:
        abort(403)

    applications = Application.query.filter_by(drive_id=drive.id).all()
    
    import json
    from app.student.ats_service import AtsService
    rankings = []
    for app in applications:
        student = app.student
        if app.ats_score is None or app.ats_data is None:
            RecruiterService._persist_ats_scores(app)
        try:
            ats_data = json.loads(app.ats_data)
        except Exception:
            ats_data = AtsService.calculate_ats_score(student, drive)
            
        rankings.append({
            "application": app,
            "student": student,
            "ats_score": float(app.ats_score),
            "breakdown": ats_data.get("breakdown", {}),
            "missing_skills": ats_data.get("missing_skills", [])
        })

    rankings.sort(key=lambda x: x["ats_score"], reverse=True)

    return render_template(
        "recruiter/ats_rankings.html",
        drive=drive,
        rankings=rankings
    )


@recruiter_bp.route("/profile", methods=["GET", "POST"])
@role_required(UserRole.RECRUITER)
def profile():
    recruiter = current_user.recruiter_profile
    if not recruiter:
        abort(404)
    if not recruiter.is_active:
        abort(403)

    company = recruiter.company

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        designation = request.form.get("designation", "").strip()
        try:
            recruiter.phone = phone if phone else None
            recruiter.designation = designation if designation else None
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("recruiter.profile"))
        except Exception:
            db.session.rollback()
            flash("Unable to update profile. Please try again.", "danger")

    # Dynamic Stats
    from app.models.drive import PlacementDrive
    from app.models.application import Application
    from app.models.enums import DriveStatus, ApplicationStatus
    
    total_drives = PlacementDrive.query.filter_by(company_id=company.id).count()
    active_drives = PlacementDrive.query.filter(
        PlacementDrive.company_id == company.id,
        PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])
    ).count()

    total_applications = Application.query.join(PlacementDrive).filter(
        PlacementDrive.company_id == company.id
    ).count()

    placed_count = Application.query.join(PlacementDrive).filter(
        PlacementDrive.company_id == company.id,
        Application.status == ApplicationStatus.PLACED
    ).count()

    stats = {
        "total_drives": total_drives,
        "active_drives": active_drives,
        "total_applications": total_applications,
        "placed_count": placed_count
    }

    return render_template(
        "recruiter/profile.html",
        recruiter=recruiter,
        company=company,
        stats=stats
    )
