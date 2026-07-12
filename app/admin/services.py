from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from flask import current_app, request

from app.extensions import db, bcrypt
from app.models import (
    User,
    AuditLog,
    Student,
    Recruiter,
    TpoAdmin,
    PlacementDrive,
    Application,
    Offer,
    Resume,
    Company,
    College,
    Branch
)
from app.models.enums import (
    UserRole,
    DriveStatus,
    ApplicationStatus,
    OfferStatus,
    AuditAction,
    ProfileStatus,
    VerificationStatus
)

class AdminService:
    @staticmethod
    def get_dashboard_stats():
        from sqlalchemy import case, literal
        stats = db.session.query(
            db.session.query(User).statement.with_only_columns(func.count(User.id)).scalar_subquery(),
            db.session.query(User).filter_by(is_active=True).statement.with_only_columns(func.count(User.id)).scalar_subquery(),
            db.session.query(Student).statement.with_only_columns(func.count(Student.id)).scalar_subquery(),
            db.session.query(Recruiter).statement.with_only_columns(func.count(Recruiter.id)).scalar_subquery(),
            db.session.query(TpoAdmin).statement.with_only_columns(func.count(TpoAdmin.id)).scalar_subquery(),
            db.session.query(User).filter_by(role=UserRole.ADMIN).statement.with_only_columns(func.count(User.id)).scalar_subquery(),
            db.session.query(PlacementDrive).statement.with_only_columns(func.count(PlacementDrive.id)).scalar_subquery(),
            db.session.query(PlacementDrive).filter(PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])).statement.with_only_columns(func.count(PlacementDrive.id)).scalar_subquery(),
            db.session.query(Application).statement.with_only_columns(func.count(Application.id)).scalar_subquery(),
            db.session.query(Offer).statement.with_only_columns(func.count(Offer.id)).scalar_subquery(),
            db.session.query(Offer).filter_by(status=OfferStatus.ACCEPTED).statement.with_only_columns(func.count(Offer.id)).scalar_subquery()
        ).first()

        total_users = stats[0] or 0
        active_users = stats[1] or 0
        students = stats[2] or 0
        recruiters = stats[3] or 0
        tpos = stats[4] or 0
        admins = stats[5] or 0
        total_drives = stats[6] or 0
        active_drives = stats[7] or 0
        total_applications = stats[8] or 0
        total_offers = stats[9] or 0
        accepted_offers = stats[10] or 0

        # Placement Percentage
        placed_students = db.session.query(func.count(Student.id.distinct()))\
            .join(Application, Student.id == Application.student_id)\
            .filter(Application.status == ApplicationStatus.PLACED)\
            .scalar() or 0
        
        placement_percentage = round((placed_students / students * 100), 2) if students > 0 else 0.0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "students": students,
            "recruiters": recruiters,
            "tpos": tpos,
            "admins": admins,
            "total_drives": total_drives,
            "active_drives": active_drives,
            "total_applications": total_applications,
            "total_offers": total_offers,
            "accepted_offers": accepted_offers,
            "placement_percentage": placement_percentage
        }

    @staticmethod
    def get_system_stats():
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)

        stats = db.session.query(
            db.session.query(AuditLog).filter_by(action=AuditAction.LOGIN).statement.with_only_columns(func.count(AuditLog.id)).scalar_subquery(),
            db.session.query(AuditLog).filter_by(action=AuditAction.LOGIN_FAILED).statement.with_only_columns(func.count(AuditLog.id)).scalar_subquery(),
            db.session.query(User).statement.with_only_columns(func.count(User.id)).scalar_subquery(),
            db.session.query(User).filter(User.last_login_at >= one_day_ago).statement.with_only_columns(func.count(User.id)).scalar_subquery(),
            db.session.query(func.sum(Resume.file_size_bytes)).scalar_subquery(),
            db.session.query(Resume).statement.with_only_columns(func.count(Resume.id)).scalar_subquery(),
            db.session.query(Offer).filter(Offer.offer_letter_path.isnot(None)).statement.with_only_columns(func.count(Offer.id)).scalar_subquery(),
            
            db.session.query(Student).statement.with_only_columns(func.count(Student.id)).scalar_subquery(),
            db.session.query(Recruiter).statement.with_only_columns(func.count(Recruiter.id)).scalar_subquery(),
            db.session.query(Company).statement.with_only_columns(func.count(Company.id)).scalar_subquery(),
            db.session.query(PlacementDrive).statement.with_only_columns(func.count(PlacementDrive.id)).scalar_subquery(),
            db.session.query(Application).statement.with_only_columns(func.count(Application.id)).scalar_subquery(),
            db.session.query(Offer).statement.with_only_columns(func.count(Offer.id)).scalar_subquery(),
            db.session.query(AuditLog).statement.with_only_columns(func.count(AuditLog.id)).scalar_subquery()
        ).first()

        total_logins = stats[0] or 0
        failed_logins = stats[1] or 0
        user_registrations = stats[2] or 0
        dau = stats[3] or 0
        resume_storage = stats[4] or 0
        resume_uploads = stats[5] or 0
        offer_uploads = stats[6] or 0

        db_rows = {
            "users": stats[2] or 0,
            "students": stats[7] or 0,
            "recruiters": stats[8] or 0,
            "companies": stats[9] or 0,
            "drives": stats[10] or 0,
            "applications": stats[11] or 0,
            "offers": stats[12] or 0,
            "audit_logs": stats[13] or 0
        }

        return {
            "total_logins": total_logins,
            "failed_logins": failed_logins,
            "user_registrations": user_registrations,
            "dau": dau,
            "resume_storage_bytes": resume_storage,
            "resume_uploads": resume_uploads,
            "offer_uploads": offer_uploads,
            "db_rows": db_rows
        }

    @staticmethod
    def get_security_logs(limit=5):
        recent_logins = AuditLog.query.options(joinedload(AuditLog.user))\
            .filter_by(action=AuditAction.LOGIN)\
            .order_by(AuditLog.created_at.desc())\
            .limit(limit)\
            .all()

        recent_failed_attempts = AuditLog.query.options(joinedload(AuditLog.user))\
            .filter_by(action=AuditAction.LOGIN_FAILED)\
            .order_by(AuditLog.created_at.desc())\
            .limit(limit)\
            .all()

        return {
            "recent_logins": recent_logins,
            "failed_attempts": recent_failed_attempts
        }

    @staticmethod
    def get_growth_analytics():
        user_growth = [
            {"month": "Jan", "count": 80},
            {"month": "Feb", "count": 120},
            {"month": "Mar", "count": 210},
            {"month": "Apr", "count": 350},
            {"month": "May", "count": 480},
            {"month": "Jun", "count": 620}
        ]

        placement_trends = [
            {"month": "Jan", "count": 10},
            {"month": "Feb", "count": 25},
            {"month": "Mar", "count": 55},
            {"month": "Apr", "count": 90},
            {"month": "May", "count": 140},
            {"month": "Jun", "count": 185}
        ]

        offer_counts = db.session.query(Offer.status, func.count(Offer.id))\
            .group_by(Offer.status).all()
        counts_map = {status: count for status, count in offer_counts}
        accepted = counts_map.get(OfferStatus.ACCEPTED, 0)
        declined = counts_map.get(OfferStatus.DECLINED, 0)
        pending = counts_map.get(OfferStatus.EXTENDED, 0)
        ratios = {
            "accepted": accepted,
            "declined": declined,
            "pending": pending
        }

        company_drives = db.session.query(Company.name, func.count(PlacementDrive.id))\
            .outerjoin(PlacementDrive, Company.id == PlacementDrive.company_id)\
            .group_by(Company.id, Company.name)\
            .limit(5)\
            .all()
        company_trends = [{"name": name, "drives": count} for name, count in company_drives]

        return {
            "user_growth": user_growth,
            "placement_trends": placement_trends,
            "offers_ratios": ratios,
            "company_trends": company_trends
        }

    @staticmethod
    def get_audit_events(limit=10):
        return AuditLog.query.options(joinedload(AuditLog.user))\
            .filter(AuditLog.action.notin_([AuditAction.LOGIN, AuditAction.LOGOUT]))\
            .order_by(AuditLog.created_at.desc())\
            .limit(limit)\
            .all()


    # ==========================================
    # USER MANAGEMENT MODULE ADDITIONS
    # ==========================================

    @staticmethod
    def get_users_list(q=None, role=None, is_active=None):
        query = User.query.options(
            joinedload(User.student_profile).joinedload(Student.branch),
            joinedload(User.recruiter_profile).joinedload(Recruiter.company),
            joinedload(User.tpo_profile).joinedload(TpoAdmin.college)
        )

        if q:
            term = f"%{q.strip()}%"
            query = query.outerjoin(Student, User.id == Student.user_id)\
                         .outerjoin(Recruiter, User.id == Recruiter.user_id)\
                         .outerjoin(TpoAdmin, User.id == TpoAdmin.user_id)\
                         .filter(
                             or_(
                                 User.email.ilike(term),
                                 Student.first_name.ilike(term),
                                 Student.last_name.ilike(term),
                                 Student.enrollment_number.ilike(term),
                                 Recruiter.first_name.ilike(term),
                                 Recruiter.last_name.ilike(term),
                                 TpoAdmin.first_name.ilike(term),
                                 TpoAdmin.last_name.ilike(term)
                             )
                         )

        if role:
            try:
                query = query.filter(User.role == UserRole(role))
            except ValueError:
                pass

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.order_by(User.created_at.desc()).all()

    @staticmethod
    def get_user_management_stats():
        total_users = User.query.count()
        students = Student.query.count()
        recruiters = Recruiter.query.count()
        tpos = TpoAdmin.query.count()
        admins = User.query.filter_by(role=UserRole.ADMIN).count()
        locked = User.query.filter_by(is_active=False).count()

        return {
            "total_users": total_users,
            "students": students,
            "recruiters": recruiters,
            "tpos": tpos,
            "admins": admins,
            "locked": locked
        }

    @staticmethod
    def _hash_pwd(password):
        return bcrypt.generate_password_hash(
            password,
            rounds=current_app.config.get("BCRYPT_LOG_ROUNDS", 12)
        ).decode("utf-8")

    @classmethod
    def create_user_with_profile(cls, form_data):
        email = form_data.get("email").strip().lower()
        if User.query.filter_by(email=email).first():
            raise ValueError("A user account with this email address already exists.")

        role_str = form_data.get("role")
        role_enum = UserRole(role_str)

        password = form_data.get("password") or "Campus123"
        hashed = cls._hash_pwd(password)

        user = User(
            email=email,
            password_hash=hashed,
            role=role_enum,
            is_active=form_data.get("is_active", True),
            is_verified=form_data.get("is_verified", True)
        )
        db.session.add(user)
        db.session.flush()

        if role_enum == UserRole.STUDENT:
            student = Student(
                user_id=user.id,
                college_id=uuid.UUID(form_data.get("student_college_id")),
                branch_id=uuid.UUID(form_data.get("student_branch_id")),
                enrollment_number=form_data.get("student_enrollment_number").strip(),
                first_name=form_data.get("student_first_name").strip(),
                last_name=form_data.get("student_last_name").strip(),
                batch=form_data.get("student_batch").strip(),
                graduation_year=int(form_data.get("student_graduation_year")),
                phone=form_data.get("student_phone").strip() if form_data.get("student_phone") else None,
                profile_status=ProfileStatus.VERIFIED if user.is_verified else ProfileStatus.PENDING_VERIFICATION
            )
            db.session.add(student)
            user.college_id = student.college_id

        elif role_enum == UserRole.RECRUITER:
            recruiter = Recruiter(
                user_id=user.id,
                company_id=uuid.UUID(form_data.get("recruiter_company_id")),
                first_name=form_data.get("recruiter_first_name").strip(),
                last_name=form_data.get("recruiter_last_name").strip(),
                designation=form_data.get("recruiter_designation").strip() if form_data.get("recruiter_designation") else None,
                phone=form_data.get("recruiter_phone").strip() if form_data.get("recruiter_phone") else None,
                is_active=user.is_active
            )
            db.session.add(recruiter)

        elif role_enum == UserRole.TPO:
            tpo = TpoAdmin(
                user_id=user.id,
                college_id=uuid.UUID(form_data.get("tpo_college_id")),
                first_name=form_data.get("tpo_first_name").strip(),
                last_name=form_data.get("tpo_last_name").strip(),
                designation=form_data.get("tpo_designation").strip() if form_data.get("tpo_designation") else None,
                department=form_data.get("tpo_department").strip() if form_data.get("tpo_department") else None,
                phone=form_data.get("tpo_phone").strip() if form_data.get("tpo_phone") else None,
                is_active=user.is_active
            )
            db.session.add(tpo)
            user.college_id = tpo.college_id

        cls.log_audit(
            user_id=user.id,
            action=AuditAction.CREATE,
            entity_type="user",
            entity_id=user.id,
            new_values={"email": user.email, "role": user.role_value}
        )
        db.session.commit()
        return user

    @classmethod
    def update_user_with_profile(cls, user_id, form_data):
        user = User.query.get_or_404(user_id)
        email = form_data.get("email").strip().lower()
        
        if email != user.email:
            if User.query.filter_by(email=email).first():
                raise ValueError("A user account with this email address already exists.")
            user.email = email

        if form_data.get("password"):
            user.password_hash = cls._hash_pwd(form_data.get("password"))

        user.is_active = form_data.get("is_active", True)
        user.is_verified = form_data.get("is_verified", True)

        role_enum = user.role

        if role_enum == UserRole.STUDENT and user.student_profile:
            student = user.student_profile
            student.college_id = uuid.UUID(form_data.get("student_college_id"))
            student.branch_id = uuid.UUID(form_data.get("student_branch_id"))
            student.enrollment_number = form_data.get("student_enrollment_number").strip()
            student.first_name = form_data.get("student_first_name").strip()
            student.last_name = form_data.get("student_last_name").strip()
            student.batch = form_data.get("student_batch").strip()
            student.graduation_year = int(form_data.get("student_graduation_year"))
            student.phone = form_data.get("student_phone").strip() if form_data.get("student_phone") else None
            user.college_id = student.college_id

        elif role_enum == UserRole.RECRUITER and user.recruiter_profile:
            recruiter = user.recruiter_profile
            recruiter.company_id = uuid.UUID(form_data.get("recruiter_company_id"))
            recruiter.first_name = form_data.get("recruiter_first_name").strip()
            recruiter.last_name = form_data.get("recruiter_last_name").strip()
            recruiter.designation = form_data.get("recruiter_designation").strip() if form_data.get("recruiter_designation") else None
            recruiter.phone = form_data.get("recruiter_phone").strip() if form_data.get("recruiter_phone") else None
            recruiter.is_active = user.is_active

        elif role_enum == UserRole.TPO and user.tpo_profile:
            tpo = user.tpo_profile
            tpo.college_id = uuid.UUID(form_data.get("tpo_college_id"))
            tpo.first_name = form_data.get("tpo_first_name").strip()
            tpo.last_name = form_data.get("tpo_last_name").strip()
            tpo.designation = form_data.get("tpo_designation").strip() if form_data.get("tpo_designation") else None
            tpo.department = form_data.get("tpo_department").strip() if form_data.get("tpo_department") else None
            tpo.phone = form_data.get("tpo_phone").strip() if form_data.get("tpo_phone") else None
            tpo.is_active = user.is_active
            user.college_id = tpo.college_id

        cls.log_audit(
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity_type="user",
            entity_id=user.id,
            new_values={"email": user.email, "role": user.role_value}
        )
        db.session.commit()
        return user

    @classmethod
    def soft_delete_user(cls, user_id):
        user = User.query.get_or_404(user_id)
        user.is_active = False
        cls.log_audit(
            user_id=user.id,
            action=AuditAction.DELETE,
            entity_type="user",
            entity_id=user.id
        )
        db.session.commit()
        return user

    @classmethod
    def lock_user_account(cls, user_id):
        user = User.query.get_or_404(user_id)
        user.is_active = False
        cls.log_audit(
            user_id=user.id,
            action=AuditAction.STATUS_CHANGE,
            entity_type="user",
            entity_id=user.id,
            new_values={"status": "locked"}
        )
        db.session.commit()
        return user

    @classmethod
    def unlock_user_account(cls, user_id):
        user = User.query.get_or_404(user_id)
        user.is_active = True
        cls.log_audit(
            user_id=user.id,
            action=AuditAction.STATUS_CHANGE,
            entity_type="user",
            entity_id=user.id,
            new_values={"status": "unlocked"}
        )
        db.session.commit()
        return user

    @classmethod
    def reset_user_password(cls, user_id, new_password):
        user = User.query.get_or_404(user_id)
        user.password_hash = cls._hash_pwd(new_password)
        cls.log_audit(
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity_type="password",
            entity_id=user.id
        )
        db.session.commit()
        return user

    @staticmethod
    def get_user_activity_history(user_id):
        return AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.created_at.desc()).all()

    @classmethod
    def bulk_import_users_csv(cls, file_stream):
        stream = io.StringIO(file_stream.read().decode("utf-8"))
        reader = csv.DictReader(stream)

        count = 0
        for row in reader:
            email = row.get("email", "").strip().lower()
            if not email or User.query.filter_by(email=email).first():
                continue

            role_str = row.get("role", "").strip().lower()
            if role_str not in ("student", "recruiter", "tpo", "admin"):
                continue
            role_enum = UserRole(role_str)

            password = row.get("password", "").strip() or "Campus123"
            hashed = cls._hash_pwd(password)

            user = User(
                email=email,
                password_hash=hashed,
                role=role_enum,
                is_active=True,
                is_verified=True
            )
            db.session.add(user)
            db.session.flush()

            first_name = row.get("first_name", "First").strip()
            last_name = row.get("last_name", "Last").strip()
            phone = row.get("phone", "").strip() or None

            if role_enum == UserRole.STUDENT:
                college = College.query.filter_by(code=row.get("college_code", "").strip().upper()).first()
                branch = Branch.query.filter_by(code=row.get("branch_code", "").strip().upper()).first()
                if not college or not branch:
                    continue

                student = Student(
                    user_id=user.id,
                    college_id=college.id,
                    branch_id=branch.id,
                    enrollment_number=row.get("enrollment_number", f"EN_{user.id.hex[:6]}").strip(),
                    first_name=first_name,
                    last_name=last_name,
                    batch=row.get("batch", "2023-2027").strip(),
                    graduation_year=int(row.get("graduation_year", "2027")),
                    phone=phone,
                    profile_status=ProfileStatus.VERIFIED
                )
                db.session.add(student)
                user.college_id = college.id

            elif role_enum == UserRole.RECRUITER:
                company = Company.query.filter(
                    func.lower(Company.name) == row.get("company_name", "").strip().lower()
                ).first()
                if not company:
                    company = Company(
                        name=row.get("company_name", "Company A").strip(),
                        verification_status=VerificationStatus.VERIFIED,
                        is_active=True
                    )
                    db.session.add(company)
                    db.session.flush()

                recruiter = Recruiter(
                    user_id=user.id,
                    company_id=company.id,
                    first_name=first_name,
                    last_name=last_name,
                    designation=row.get("designation", "").strip() or None,
                    phone=phone,
                    is_active=True
                )
                db.session.add(recruiter)

            elif role_enum == UserRole.TPO:
                college = College.query.filter_by(code=row.get("college_code", "").strip().upper()).first()
                if not college:
                    continue

                tpo = TpoAdmin(
                    user_id=user.id,
                    college_id=college.id,
                    first_name=first_name,
                    last_name=last_name,
                    designation=row.get("designation", "").strip() or None,
                    department=row.get("department", "").strip() or None,
                    phone=phone,
                    is_active=True
                )
                db.session.add(tpo)
                user.college_id = college.id

            count += 1

        db.session.commit()
        return count


    # ==========================================
    # AUDIT LOGS MODULE ADDITIONS
    # ==========================================

    @staticmethod
    def log_audit(user_id, action, entity_type, entity_id, old_values=None, new_values=None):
        try:
            ip = request.remote_addr if request else "127.0.0.1"
            ua = request.user_agent.string if request else "System Process"
        except RuntimeError:
            ip = "127.0.0.1"
            ua = "System Process"

        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip,
            user_agent=ua
        )
        db.session.add(log)

    @staticmethod
    def get_audit_logs_list(q=None, action=None, entity_type=None):
        query = AuditLog.query.options(joinedload(AuditLog.user))

        if q:
            term = f"%{q.strip()}%"
            query = query.outerjoin(User, AuditLog.user_id == User.id)\
                         .filter(
                             or_(
                                 User.email.ilike(term),
                                 AuditLog.entity_type.ilike(term),
                                 func.cast(AuditLog.entity_id, func.text).ilike(term)
                             )
                         )

        if action:
            try:
                query = query.filter(AuditLog.action == AuditAction(action))
            except ValueError:
                pass

        if entity_type:
            query = query.filter(AuditLog.entity_type.ilike(entity_type.strip()))

        return query.order_by(AuditLog.created_at.desc()).all()

    @staticmethod
    def get_audit_statistics():
        total_logs = AuditLog.query.count()
        success_logins = AuditLog.query.filter_by(action=AuditAction.LOGIN).count()
        failed_logins = AuditLog.query.filter_by(action=AuditAction.LOGIN_FAILED).count()
        mutations = AuditLog.query.filter(
            AuditLog.action.in_([AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE, AuditAction.STATUS_CHANGE])
        ).count()

        # Distribution ratios
        distribution = {
            "login": success_logins,
            "failed_auth": failed_logins,
            "create": AuditLog.query.filter_by(action=AuditAction.CREATE).count(),
            "update": AuditLog.query.filter_by(action=AuditAction.UPDATE).count(),
            "delete": AuditLog.query.filter_by(action=AuditAction.DELETE).count(),
            "status_change": AuditLog.query.filter_by(action=AuditAction.STATUS_CHANGE).count()
        }

        # Daily trends counts (7-day line chart data)
        trends = []
        for i in range(6, -1, -1):
            day = datetime.now(timezone.utc) - timedelta(days=i)
            day_str = day.strftime('%d %b')
            
            # Start and End dates for this day in UTC
            start_dt = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc)
            end_dt = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
            
            logins_count = AuditLog.query.filter(
                AuditLog.action == AuditAction.LOGIN,
                AuditLog.created_at.between(start_dt, end_dt)
            ).count()
            
            mutations_count = AuditLog.query.filter(
                AuditLog.action.in_([AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE, AuditAction.STATUS_CHANGE]),
                AuditLog.created_at.between(start_dt, end_dt)
            ).count()
            
            trends.append({
                "day": day_str,
                "logins": logins_count,
                "mutations": mutations_count
            })

        return {
            "total_logs": total_logs,
            "success_logins": success_logins,
            "failed_logins": failed_logins,
            "mutations": mutations,
            "distribution": distribution,
            "trends": trends
        }
