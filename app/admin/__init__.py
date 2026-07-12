import csv
import io
import uuid
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, make_response
from flask_login import current_user
from sqlalchemy.orm import joinedload

from app.decorators import role_required
from app.extensions import db
from app.models.enums import UserRole, AuditAction
from app.models import College, Branch, Company, User, AuditLog, Student, Recruiter, TpoAdmin
from app.admin.services import AdminService
from app.admin.forms import UserManagementForm, BulkImportForm, ResetPasswordForm

admin_bp = Blueprint("admin", __name__)


@admin_bp.app_context_processor
def inject_role_enums():
    return dict(UserRole=UserRole, AuditAction=AuditAction)


@admin_bp.route("/dashboard")
@role_required(UserRole.ADMIN)
def dashboard():
    stats = AdminService.get_dashboard_stats()
    system = AdminService.get_system_stats()
    security = AdminService.get_security_logs(limit=5)
    analytics = AdminService.get_growth_analytics()
    audit_events = AdminService.get_audit_events(limit=10)

    return render_template(
        "portals/admin_dashboard.html",
        stats=stats,
        system=system,
        security=security,
        analytics=analytics,
        audit_events=audit_events
    )


# ==========================================
# USER MANAGEMENT MODULE ROUTES
# ==========================================

@admin_bp.route("/users", methods=["GET"])
@role_required(UserRole.ADMIN)
def users_list():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    
    is_active = None
    status_filter = request.args.get("status", "").strip()
    if status_filter == "active":
        is_active = True
    elif status_filter == "locked":
        is_active = False

    users = AdminService.get_users_list(q=q, role=role, is_active=is_active)
    stats = AdminService.get_user_management_stats()

    return render_template(
        "admin/users.html",
        users=users,
        stats=stats,
        filters={
            "q": q,
            "role": role,
            "status": status_filter
        }
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def create_user():
    form = UserManagementForm()

    colleges = College.query.filter_by(is_active=True).all()
    form.student_college_id.choices = [("", "Select College")] + [(str(c.id), c.name) for c in colleges]
    form.tpo_college_id.choices = [("", "Select College")] + [(str(c.id), c.name) for c in colleges]
    
    branches = Branch.query.filter_by(is_active=True).all()
    form.student_branch_id.choices = [("", "Select Branch")] + [(str(b.id), f"{b.college.code} - {b.name}") for b in branches]
    
    companies = Company.query.filter_by(is_active=True).all()
    form.recruiter_company_id.choices = [("", "Select Company")] + [(str(c.id), c.name) for c in companies]

    if form.validate_on_submit():
        try:
            form_data = request.form.to_dict()
            form_data["is_active"] = form.is_active.data
            form_data["is_verified"] = form.is_verified.data
            AdminService.create_user_with_profile(form_data)
            flash("User account and profile successfully initialized.", "success")
            return redirect(url_for("admin.users_list"))
        except ValueError as e:
            flash(str(e), "warning")
        except Exception:
            db.session.rollback()
            flash("Failed to create user account. Please try again.", "danger")

    return render_template("admin/user_form.html", form=form, title="Create System User")


@admin_bp.route("/users/<uuid:user_id>", methods=["GET"])
@role_required(UserRole.ADMIN)
def view_user(user_id):
    user = User.query.options(
        joinedload(User.student_profile).joinedload(Student.branch),
        joinedload(User.recruiter_profile).joinedload(Recruiter.company),
        joinedload(User.tpo_profile).joinedload(TpoAdmin.college)
    ).get_or_404(user_id)

    activity = AdminService.get_user_activity_history(user.id)

    return render_template(
        "admin/user_profile.html",
        user_record=user,
        activity=activity
    )


@admin_bp.route("/users/<uuid:user_id>/edit", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserManagementForm()

    colleges = College.query.filter_by(is_active=True).all()
    form.student_college_id.choices = [("", "Select College")] + [(str(c.id), c.name) for c in colleges]
    form.tpo_college_id.choices = [("", "Select College")] + [(str(c.id), c.name) for c in colleges]
    
    branches = Branch.query.filter_by(is_active=True).all()
    form.student_branch_id.choices = [("", "Select Branch")] + [(str(b.id), f"{b.college.code} - {b.name}") for b in branches]
    
    companies = Company.query.filter_by(is_active=True).all()
    form.recruiter_company_id.choices = [("", "Select Company")] + [(str(c.id), c.name) for c in companies]

    if request.method == "GET":
        form.email.data = user.email
        form.role.data = user.role.value
        form.is_active.data = user.is_active
        form.is_verified.data = user.is_verified
        
        if user.role == UserRole.STUDENT and user.student_profile:
            student = user.student_profile
            form.student_college_id.data = str(student.college_id)
            form.student_branch_id.data = str(student.branch_id)
            form.student_enrollment_number.data = student.enrollment_number
            form.student_first_name.data = student.first_name
            form.student_last_name.data = student.last_name
            form.student_batch.data = student.batch
            form.student_graduation_year.data = student.graduation_year
            form.student_phone.data = student.phone
        elif user.role == UserRole.RECRUITER and user.recruiter_profile:
            rec = user.recruiter_profile
            form.recruiter_company_id.data = str(rec.company_id)
            form.recruiter_first_name.data = rec.first_name
            form.recruiter_last_name.data = rec.last_name
            form.recruiter_designation.data = rec.designation
            form.recruiter_phone.data = rec.phone
        elif user.role == UserRole.TPO and user.tpo_profile:
            tpo = user.tpo_profile
            form.tpo_college_id.data = str(tpo.college_id)
            form.tpo_first_name.data = tpo.first_name
            form.tpo_last_name.data = tpo.last_name
            form.tpo_designation.data = tpo.designation
            form.tpo_department.data = tpo.department
            form.tpo_phone.data = tpo.phone

    if form.validate_on_submit():
        try:
            form_data = request.form.to_dict()
            form_data["is_active"] = form.is_active.data
            form_data["is_verified"] = form.is_verified.data
            AdminService.update_user_with_profile(user.id, form_data)
            flash("User profile successfully modified.", "success")
            return redirect(url_for("admin.view_user", user_id=user.id))
        except ValueError as e:
            flash(str(e), "warning")
        except Exception:
            db.session.rollback()
            flash("Profile update failed. Please verify fields and try again.", "danger")

    return render_template("admin/user_form.html", form=form, title="Modify User Profile", edit_mode=True, user_role=user.role.value)


@admin_bp.route("/users/<uuid:user_id>/status/<string:action>", methods=["POST"])
@role_required(UserRole.ADMIN)
def toggle_user_status(user_id, action):
    try:
        if action == "lock" or action == "deactivate":
            AdminService.lock_user_account(user_id)
            flash("User account disabled/locked successfully.", "warning")
        elif action == "unlock" or action == "activate":
            AdminService.unlock_user_account(user_id)
            flash("User account active and unlocked.", "success")
    except Exception:
        db.session.rollback()
        flash("Status update failed.", "danger")
        
    return redirect(request.referrer or url_for("admin.users_list"))


@admin_bp.route("/users/<uuid:user_id>/reset-password", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    form = ResetPasswordForm()

    if form.validate_on_submit():
        try:
            AdminService.reset_user_password(user.id, form.new_password.data)
            flash("User credentials password reset completed.", "success")
            return redirect(url_for("admin.view_user", user_id=user.id))
        except Exception:
            db.session.rollback()
            flash("Password reset override failed. Try again.", "danger")

    return render_template("admin/user_reset_pwd.html", form=form, user_record=user)


@admin_bp.route("/users/<uuid:user_id>/delete", methods=["POST"])
@role_required(UserRole.ADMIN)
def delete_user(user_id):
    try:
        AdminService.soft_delete_user(user_id)
        flash("User soft deletion complete (account disabled, all histories preserved).", "info")
    except Exception:
        db.session.rollback()
        flash("Failed to soft delete user.", "danger")
        
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/import", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def import_users():
    form = BulkImportForm()
    if form.validate_on_submit():
        file = form.import_file.data
        try:
            count = AdminService.bulk_import_users_csv(file)
            flash(f"Bulk users roster import successful. Registered {count} users.", "success")
            return redirect(url_for("admin.users_list"))
        except Exception:
            db.session.rollback()
            flash("Import parser failed. Make sure columns match guidelines.", "danger")

    return render_template("admin/user_import.html", form=form)


@admin_bp.route("/users/export", methods=["GET"])
@role_required(UserRole.ADMIN)
def export_users():
    users = User.query.options(
        joinedload(User.student_profile),
        joinedload(User.recruiter_profile).joinedload(Recruiter.company),
        joinedload(User.tpo_profile)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Email", 
        "Role", 
        "Active Status", 
        "First Name", 
        "Last Name", 
        "Phone", 
        "Additional Metadata"
    ])

    for u in users:
        first = ""
        last = ""
        phone = ""
        meta = ""
        
        if u.role == UserRole.STUDENT and u.student_profile:
            first = u.student_profile.first_name
            last = u.student_profile.last_name
            phone = u.student_profile.phone or ""
            meta = f"Roll: {u.student_profile.enrollment_number}, Batch: {u.student_profile.batch}"
        elif u.role == UserRole.RECRUITER and u.recruiter_profile:
            first = u.recruiter_profile.first_name
            last = u.recruiter_profile.last_name
            phone = u.recruiter_profile.phone or ""
            meta = f"Company: {u.recruiter_profile.company.name}"
        elif u.role == UserRole.TPO and u.tpo_profile:
            first = u.tpo_profile.first_name
            last = u.tpo_profile.last_name
            phone = u.tpo_profile.phone or ""
            meta = f"Dept: {u.tpo_profile.department or ''}"

        writer.writerow([
            u.email,
            u.role.value.upper(),
            "ACTIVE" if u.is_active else "LOCKED",
            first,
            last,
            phone,
            meta
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=system_users_directory.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


# ==========================================
# ANALYTICS EXPORT ROUTE
# ==========================================

@admin_bp.route("/export-analytics", methods=["GET"])
@role_required(UserRole.ADMIN)
def export_analytics():
    """
    Generate a full-system analytics CSV report covering:
    - Platform summary stats
    - System metrics & DB row counts
    - User growth trend (last 12 months)
    - Placement trends (last 12 months)
    - Offer status breakdown
    - Top recruiting companies
    - Recent audit events (last 50)
    """
    from datetime import datetime as _dt

    def _safe(value: object) -> str:
        """
        Sanitize a cell value for CSV export.
        Prevents spreadsheet formula injection by prefixing with a single
        quote any string that starts with =, +, -, or @.
        """
        s = str(value) if value is not None else ""
        if s and s[0] in ("=", "+", "-", "@"):
            return "'" + s
        return s

    def _row(writer, cells):
        writer.writerow([_safe(c) for c in cells])

    try:
        stats        = AdminService.get_dashboard_stats() or {}
        system       = AdminService.get_system_stats() or {}
        analytics    = AdminService.get_growth_analytics() or {}
        audit_events = AdminService.get_audit_events(limit=50) or []

        output = io.StringIO()
        writer = csv.writer(output)

        # ── Header ───────────────────────────────────────────────────────────
        writer.writerow(["=== CAMPUSHIRE AI — SYSTEM ANALYTICS REPORT ==="])
        writer.writerow(["Generated On", _dt.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])

        # ── Section 1: Platform Summary ──────────────────────────────────────
        writer.writerow(["--- PLATFORM SUMMARY ---"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Users",         stats.get("total_users", 0)])
        writer.writerow(["Active Users",        stats.get("active_users", 0)])
        writer.writerow(["Students",            stats.get("students", 0)])
        writer.writerow(["Recruiters",          stats.get("recruiters", 0)])
        writer.writerow(["TPO Admins",          stats.get("tpos", 0)])
        writer.writerow(["System Admins",       stats.get("admins", 0)])
        writer.writerow(["Total Drives",        stats.get("total_drives", 0)])
        writer.writerow(["Active Drives",       stats.get("active_drives", 0)])
        writer.writerow(["Placement Rate (%)",  stats.get("placement_percentage", 0)])
        writer.writerow([])

        # ── Section 2: System Metrics ─────────────────────────────────────────
        writer.writerow(["--- SYSTEM METRICS ---"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Daily Active Users (DAU)",  system.get("dau", 0)])
        writer.writerow(["Total Logins (all-time)",   system.get("total_logins", 0)])
        writer.writerow(["Failed Login Attempts",     system.get("failed_logins", 0)])
        writer.writerow(["Resume Uploads",            system.get("resume_uploads", 0)])
        writer.writerow(["Resume Storage (MB)",
                         round(system.get("resume_storage_bytes", 0) / 1024 / 1024, 2)])
        writer.writerow(["Offer Letter Uploads",      system.get("offer_uploads", 0)])
        writer.writerow([])

        # ── Section 3: DB Row Counts ──────────────────────────────────────────
        writer.writerow(["--- DATABASE TABLE ROW COUNTS ---"])
        writer.writerow(["Table", "Row Count"])
        for table, count in (system.get("db_rows") or {}).items():
            writer.writerow([table.replace("_", " ").title(), count])
        writer.writerow([])

        # ── Section 4: User Growth ────────────────────────────────────────────
        writer.writerow(["--- USER REGISTRATION GROWTH (LAST 12 MONTHS) ---"])
        writer.writerow(["Month", "New Registrations"])
        for entry in (analytics.get("user_growth") or []):
            if isinstance(entry, dict):
                _row(writer, [entry.get("month", ""), entry.get("count", 0)])
        writer.writerow([])

        # ── Section 5: Placement Trends ───────────────────────────────────────
        writer.writerow(["--- PLACEMENT TRENDS (LAST 12 MONTHS) ---"])
        writer.writerow(["Month", "Placements Confirmed"])
        for entry in (analytics.get("placement_trends") or []):
            if isinstance(entry, dict):
                _row(writer, [entry.get("month", ""), entry.get("count", 0)])
        writer.writerow([])

        # ── Section 6: Offer Status ───────────────────────────────────────────
        writer.writerow(["--- OFFER LETTERS STATUS BREAKDOWN ---"])
        writer.writerow(["Status", "Count"])
        offers = analytics.get("offers_ratios") or {}
        writer.writerow(["Accepted", offers.get("accepted", 0)])
        writer.writerow(["Pending",  offers.get("pending",  0)])
        writer.writerow(["Declined", offers.get("declined", 0)])
        writer.writerow([])

        # ── Section 7: Top Companies ──────────────────────────────────────────
        writer.writerow(["--- TOP RECRUITING COMPANIES ---"])
        writer.writerow(["Company", "Drives Conducted"])
        for entry in (analytics.get("company_trends") or []):
            if isinstance(entry, dict):
                _row(writer, [entry.get("name", ""), entry.get("drives", 0)])
        writer.writerow([])

        # ── Section 8: Recent Audit Events ───────────────────────────────────
        writer.writerow(["--- RECENT AUDIT EVENTS (LAST 50) ---"])
        writer.writerow(["Timestamp", "Actor", "Action", "Entity Type", "Entity ID"])
        for log in audit_events:
            try:
                _row(writer, [
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
                    log.user.email if log.user else "System",
                    log.action.value.upper() if log.action else "",
                    log.entity_type or "",
                    str(log.entity_id) if log.entity_id else "",
                ])
            except Exception:
                continue  # skip malformed rows, never abort the export

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=campushire_analytics_report.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response

    except Exception:
        flash("Analytics export failed. Please try again.", "danger")
        return redirect(url_for("admin.dashboard"))


# ==========================================
# AUDIT LOGS MODULE ROUTES
# ==========================================

@admin_bp.route("/audit-logs", methods=["GET"])
@role_required(UserRole.ADMIN)
def audit_logs():
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "").strip()
    entity_type = request.args.get("entity_type", "").strip()

    logs = AdminService.get_audit_logs_list(q=q, action=action, entity_type=entity_type)
    stats = AdminService.get_audit_statistics()

    return render_template(
        "admin/audit_logs.html",
        logs=logs,
        stats=stats,
        filters={
            "q": q,
            "action": action,
            "entity_type": entity_type
        }
    )


@admin_bp.route("/audit-logs/export", methods=["GET"])
@role_required(UserRole.ADMIN)
def export_audit_logs():
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "").strip()
    entity_type = request.args.get("entity_type", "").strip()

    logs = AdminService.get_audit_logs_list(q=q, action=action, entity_type=entity_type)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Timestamp", 
        "Actor Email", 
        "Action Type", 
        "Entity Type", 
        "Entity ID", 
        "Old Parameters", 
        "New Parameters", 
        "IP Address", 
        "User Agent"
    ])

    for log in logs:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else "",
            log.user.email if log.user else "System Process",
            log.action.value.upper(),
            log.entity_type,
            str(log.entity_id) if log.entity_id else "",
            str(log.old_values) if log.old_values else "",
            str(log.new_values) if log.new_values else "",
            log.ip_address or "127.0.0.1",
            log.user_agent or "System Process"
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=system_audit_logs_archive.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@admin_bp.route("/profile", methods=["GET"])
@role_required(UserRole.ADMIN)
def profile():
    # Admin stats
    from app.models import User, Student, Recruiter, TpoAdmin, PlacementDrive
    
    total_users = User.query.count()
    total_students = Student.query.count()
    total_recruiters = Recruiter.query.count()
    total_tpos = TpoAdmin.query.count()
    total_drives = PlacementDrive.query.count()

    stats = {
        "total_users": total_users,
        "total_students": total_students,
        "total_recruiters": total_recruiters,
        "total_tpos": total_tpos,
        "total_drives": total_drives
    }

    return render_template(
        "admin/profile.html",
        admin_user=current_user,
        stats=stats
    )
