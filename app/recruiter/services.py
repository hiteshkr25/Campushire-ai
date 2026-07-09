from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    PlacementDrive,
    Application,
    Offer,
    InterviewSchedule,
    InterviewRound,
    Student,
    Notification,
    Branch,
    User,
    EligibilityRule,
    StudentSkill,
    RoundResult
)
from app.models.enums import (
    ApplicationStatus,
    DriveStatus,
    OfferStatus,
    ScheduleStatus,
    EligibilityRuleType,
    NotificationType,
    RoundResultStatus,
    RoundType
)

class RecruiterService:
    @staticmethod
    def get_dashboard_stats(company_id):
        # 1. Active campaigns
        active_drives = PlacementDrive.query.filter(
            PlacementDrive.company_id == company_id,
            PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.REGISTRATION_CLOSED, DriveStatus.ONGOING])
        ).count()

        # 2. Total registered candidate applications
        total_candidates = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .scalar() or 0

        # 3. Shortlisted candidates (applications under review, shortlisted, or interviewing)
        shortlisted = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                Application.status.in_([
                    ApplicationStatus.SHORTLISTED,
                    ApplicationStatus.INTERVIEW_IN_PROGRESS,
                    ApplicationStatus.UNDER_REVIEW
                ])
            ).scalar() or 0

        # 4. Placed/Selected hires
        hires = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                Application.status == ApplicationStatus.PLACED
            ).scalar() or 0

        # 5. Pending Reviews (SUBMITTED or UNDER_REVIEW)
        pending_reviews = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW])
            ).scalar() or 0

        # 6. Interviews Scheduled
        interviews_scheduled = db.session.query(func.count(InterviewSchedule.id))\
            .join(InterviewRound, InterviewSchedule.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                InterviewSchedule.status == ScheduleStatus.SCHEDULED
            ).scalar() or 0

        # Funnel count metrics
        applied = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Application.status == ApplicationStatus.SUBMITTED)\
            .scalar() or 0

        under_review = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Application.status == ApplicationStatus.UNDER_REVIEW)\
            .scalar() or 0

        shortlisted_funnel = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Application.status == ApplicationStatus.SHORTLISTED)\
            .scalar() or 0

        interviewing = db.session.query(func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Application.status == ApplicationStatus.INTERVIEW_IN_PROGRESS)\
            .scalar() or 0

        return {
            "active_drives": active_drives,
            "total_candidates": total_candidates,
            "shortlisted": shortlisted,
            "hires": hires,
            "pending_reviews": pending_reviews,
            "interviews_scheduled": interviews_scheduled,
            "funnel": {
                "applied": applied,
                "under_review": under_review,
                "shortlisted": shortlisted_funnel,
                "interviewing": interviewing,
                "hired": hires
            }
        }

    @staticmethod
    def get_offer_stats(company_id):
        extended = db.session.query(func.count(Offer.id))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .scalar() or 0

        accepted = db.session.query(func.count(Offer.id))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Offer.status == OfferStatus.ACCEPTED)\
            .scalar() or 0

        rejected = db.session.query(func.count(Offer.id))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Offer.status == OfferStatus.DECLINED)\
            .scalar() or 0

        pending = db.session.query(func.count(Offer.id))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, Offer.status == OfferStatus.EXTENDED)\
            .scalar() or 0

        highest = db.session.query(func.max(Offer.package_offered_lpa))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .scalar()

        average = db.session.query(func.avg(Offer.package_offered_lpa))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .scalar()

        acceptance_rate = round((accepted / extended * 100), 2) if extended > 0 else 0.0

        return {
            "extended": extended,
            "accepted": accepted,
            "rejected": rejected,
            "pending": pending,
            "highest": float(highest) if highest is not None else 0.0,
            "average": float(average) if average is not None else 0.0,
            "acceptance_rate": acceptance_rate
        }

    @staticmethod
    def get_upcoming_interviews(company_id, limit=5):
        schedules = db.session.query(InterviewSchedule)\
            .join(InterviewRound, InterviewSchedule.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                InterviewSchedule.status == ScheduleStatus.SCHEDULED
            ).options(
                joinedload(InterviewSchedule.application).joinedload(Application.student),
                joinedload(InterviewSchedule.round)
            ).order_by(InterviewSchedule.scheduled_start.asc())\
            .limit(limit)\
            .all()

        interviews = []
        for s in schedules:
            student = s.application.student
            interviews.append({
                "student_name": student.full_name,
                "round_name": s.round.round_name,
                "drive_title": s.round.drive.title,
                "start_time": s.scheduled_start,
                "meeting_link": s.meeting_link,
                "venue": s.venue
            })
        return interviews

    @staticmethod
    def get_recent_activities(company_id, limit=5):
        apps = db.session.query(Application)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .options(joinedload(Application.student), joinedload(Application.drive))\
            .order_by(Application.created_at.desc())\
            .limit(limit)\
            .all()

        offers = db.session.query(Offer)\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .options(joinedload(Offer.application).joinedload(Application.student))\
            .order_by(Offer.created_at.desc())\
            .limit(limit)\
            .all()

        activities = []
        for a in apps:
            activities.append({
                "type": "application",
                "message": f"Student {a.student.full_name} registered for campaign '{a.drive.title}'",
                "timestamp": a.created_at
            })
        for o in offers:
            activities.append({
                "type": "offer",
                "message": f"Offer of {float(o.package_offered_lpa):g} LPA extended to student {o.application.student.full_name}",
                "timestamp": o.created_at
            })

        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]

    @staticmethod
    def get_notifications(user_id, limit=5):
        return Notification.query.filter_by(user_id=user_id)\
            .order_by(Notification.created_at.desc())\
            .limit(limit)\
            .all()

    @staticmethod
    def get_branch_pipeline(company_id):
        results = db.session.query(Branch.code, func.count(Application.id))\
            .join(Student, Application.student_id == Student.id)\
            .join(Branch, Student.branch_id == Branch.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .group_by(Branch.code)\
            .all()
        return [{"code": row[0], "count": row[1]} for row in results]

    @staticmethod
    def get_package_distribution(company_id):
        offers = db.session.query(Offer.package_offered_lpa)\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .all()
            
        brackets = {
            "under_5": 0,
            "5_to_10": 0,
            "10_to_15": 0,
            "over_15": 0
        }
        for pkg in offers:
            val = float(pkg[0]) if pkg[0] is not None else 0.0
            if val < 5.0:
                brackets["under_5"] += 1
            elif val <= 10.0:
                brackets["5_to_10"] += 1
            elif val <= 15.0:
                brackets["10_to_15"] += 1
            else:
                brackets["over_15"] += 1
        return brackets


    # ==========================================
    # CANDIDATE REVIEW MODULE ADDITIONS
    # ==========================================

    @classmethod
    def get_candidates_list(cls, company_id, q=None, branch_id=None, min_cgpa=None, max_backlogs=None, status=None, drive_id=None):
        query = Application.query.options(
            joinedload(Application.student).joinedload(Student.branch),
            joinedload(Application.student).joinedload(Student.user),
            joinedload(Application.drive)
        ).join(PlacementDrive).filter(PlacementDrive.company_id == company_id)

        if q:
            term = f"%{q.strip()}%"
            query = query.join(Student).join(User).filter(
                or_(
                    Student.first_name.ilike(term),
                    Student.last_name.ilike(term),
                    Student.enrollment_number.ilike(term),
                    User.email.ilike(term)
                )
            )

        if branch_id:
            try:
                query = query.filter(Student.branch_id == uuid.UUID(str(branch_id)))
            except ValueError:
                pass

        if min_cgpa:
            try:
                query = query.filter(Student.cgpa >= Decimal(str(min_cgpa)))
            except (ValueError, TypeError):
                pass

        if max_backlogs is not None:
            try:
                query = query.filter(Student.backlogs_count <= int(max_backlogs))
            except (ValueError, TypeError):
                pass

        if status:
            try:
                query = query.filter(Application.status == ApplicationStatus(status))
            except ValueError:
                pass

        if drive_id:
            try:
                query = query.filter(Application.drive_id == uuid.UUID(str(drive_id)))
            except ValueError:
                pass

        applications = query.all()
        candidates = []

        for app in applications:
            if app.ats_score is None or app.match_score is None:
                cls._persist_ats_scores(app)
            
            candidates.append({
                "application": app,
                "student": app.student,
                "drive": app.drive,
                "ats_score": float(app.ats_score),
                "match_score": float(app.match_score)
            })

        return candidates

    @classmethod
    def _persist_ats_scores(cls, app):
        import json
        from app.student.ats_service import AtsService
        student = app.student
        drive = app.drive
        
        ats_data = AtsService.calculate_ats_score(student, drive)
        
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
            
        app.ats_score = Decimal(str(ats_data["score"]))
        app.match_score = Decimal(str(match_score))
        app.ats_data = json.dumps(ats_data)
        db.session.commit()

    @classmethod
    def _calculate_dynamic_scores(cls, student, drive):
        app = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
        if app:
            if app.ats_score is None or app.match_score is None:
                cls._persist_ats_scores(app)
            return float(app.ats_score), float(app.match_score)

        from app.student.ats_service import AtsService
        ats_data = AtsService.calculate_ats_score(student, drive)

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

        return float(ats_data["score"]), match_score

    @classmethod
    def get_candidate_profile_details(cls, application_id):
        app = Application.query.options(
            joinedload(Application.student).joinedload(Student.branch),
            joinedload(Application.student).joinedload(Student.user),
            joinedload(Application.drive).joinedload(PlacementDrive.company)
        ).filter_by(id=application_id).first_or_404()

        student = app.student
        drive = app.drive

        if app.ats_score is None or app.match_score is None or app.ats_data is None:
            cls._persist_ats_scores(app)

        import json
        try:
            ats_data = json.loads(app.ats_data)
        except Exception:
            ats_data = {}

        resumes = student.resumes.order_by(Student.resumes.property.mapper.class_.is_primary.desc()).all()
        primary_resume = next((r for r in resumes if r.is_primary), None)

        projects = student.projects.all()
        certifications = student.certifications.all()
        skills = [s.skill.name for s in student.skills.all() if s.skill]

        return {
            "application": app,
            "student": student,
            "drive": drive,
            "ats_score": float(app.ats_score),
            "match_score": float(app.match_score),
            "resumes": resumes,
            "primary_resume": primary_resume,
            "projects": projects,
            "certifications": certifications,
            "skills": skills,
            "similarity_explanation": ats_data.get("similarity_explanation", ""),
            "match_confidence": ats_data.get("match_confidence", "Low"),
            "candidate_recommendation": ats_data.get("candidate_recommendation", ""),
            "skill_gap": ats_data.get("skill_gap", [])
        }

    @classmethod
    def evaluate_candidate(cls, application_id, status, remarks, evaluator_user_id):
        app = Application.query.filter_by(id=application_id).first_or_404()
        new_status = ApplicationStatus(status)
        app.status = new_status
        app.status_updated_at = db.func.now()

        latest_round = app.round_results.order_by(RoundResult.created_at.desc()).first()
        if latest_round and remarks:
            latest_round.remarks = remarks
            latest_round.evaluated_by = evaluator_user_id
            latest_round.evaluated_at = db.func.now()

        msg = f"Your application status for '{app.drive.title}' has been updated to '{new_status.value.replace('_', ' ').title()}'."
        if remarks:
            msg += f" Remarks: {remarks}"
            
        notification = Notification(
            user_id=app.student.user_id,
            title="Application Status Updated",
            message=msg,
            notification_type=NotificationType.INFO,
            entity_type="application",
            entity_id=app.id
        )
        db.session.add(notification)
        db.session.commit()
        return app


    # ==========================================
    # INTERVIEW WORKFLOW MODULE ADDITIONS
    # ==========================================

    @staticmethod
    def get_interviews_dashboard_stats(company_id):
        scheduled = db.session.query(func.count(InterviewSchedule.id))\
            .join(InterviewRound, InterviewSchedule.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, InterviewSchedule.status == ScheduleStatus.SCHEDULED)\
            .scalar() or 0

        completed = db.session.query(func.count(InterviewSchedule.id))\
            .join(InterviewRound, InterviewSchedule.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id, InterviewSchedule.status == ScheduleStatus.COMPLETED)\
            .scalar() or 0

        cancelled = db.session.query(func.count(InterviewSchedule.id))\
            .join(InterviewRound, InterviewSchedule.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                InterviewSchedule.status.in_([ScheduleStatus.CANCELLED, ScheduleStatus.RESCHEDULED])
            ).scalar() or 0

        results = db.session.query(RoundResult.result_status, func.count(RoundResult.id))\
            .join(InterviewRound, RoundResult.round_id == InterviewRound.id)\
            .join(PlacementDrive, InterviewRound.drive_id == PlacementDrive.id)\
            .filter(PlacementDrive.company_id == company_id)\
            .group_by(RoundResult.result_status)\
            .all()

        ratios = {
            "passed": 0,
            "failed": 0,
            "hold": 0,
            "absent": 0
        }
        for status_enum, count in results:
            if status_enum:
                val = status_enum.value.lower()
                if val == "passed":
                    ratios["passed"] = count
                elif val == "failed":
                    ratios["failed"] = count
                elif val == "on_hold":
                    ratios["hold"] = count
                elif val == "absent":
                    ratios["absent"] = count

        return {
            "scheduled": scheduled,
            "completed": completed,
            "cancelled": cancelled,
            "ratios": ratios
        }

    @staticmethod
    def get_interviews_list(company_id, q=None, status=None, round_type=None, drive_id=None):
        query = InterviewSchedule.query.options(
            joinedload(InterviewSchedule.application).joinedload(Application.student),
            joinedload(InterviewSchedule.round).joinedload(InterviewRound.drive)
        ).join(InterviewRound).join(PlacementDrive).filter(PlacementDrive.company_id == company_id)

        if q:
            term = f"%{q.strip()}%"
            query = query.join(Application).join(Student).filter(
                or_(
                    Student.first_name.ilike(term),
                    Student.last_name.ilike(term),
                    Student.enrollment_number.ilike(term)
                )
            )

        if status:
            try:
                query = query.filter(InterviewSchedule.status == ScheduleStatus(status))
            except ValueError:
                pass

        if round_type:
            try:
                query = query.filter(InterviewRound.round_type == RoundType(round_type))
            except ValueError:
                pass

        if drive_id:
            try:
                query = query.filter(InterviewRound.drive_id == uuid.UUID(str(drive_id)))
            except ValueError:
                pass

        return query.order_by(InterviewSchedule.scheduled_start.desc()).all()

    @classmethod
    def schedule_interview(cls, form_data):
        drive_id = uuid.UUID(form_data.get("drive_id"))
        round_id = uuid.UUID(form_data.get("round_id"))
        application_id = uuid.UUID(form_data.get("application_id"))

        schedule = InterviewSchedule(
            application_id=application_id,
            round_id=round_id,
            scheduled_start=form_data.get("scheduled_start"),
            scheduled_end=form_data.get("scheduled_end"),
            venue=form_data.get("venue"),
            meeting_link=form_data.get("meeting_link"),
            status=ScheduleStatus.SCHEDULED
        )
        db.session.add(schedule)

        result = RoundResult.query.filter_by(application_id=application_id, round_id=round_id).first()
        if not result:
            result = RoundResult(
                application_id=application_id,
                round_id=round_id,
                result_status=RoundResultStatus.SCHEDULED
            )
            db.session.add(result)
        else:
            result.result_status = RoundResultStatus.SCHEDULED

        app = Application.query.get(application_id)
        if app:
            app.status = ApplicationStatus.INTERVIEW_IN_PROGRESS
            app.status_updated_at = db.func.now()

        round_obj = InterviewRound.query.get(round_id)
        msg = f"An interview has been scheduled for round '{round_obj.round_name}' under drive '{round_obj.drive.title}'. Time: {schedule.scheduled_start.strftime('%d %b %Y, %I:%M %p')}."
        notification = Notification(
            user_id=app.student.user_id,
            title="Interview Scheduled",
            message=msg,
            notification_type=NotificationType.INFO,
            entity_type="interview",
            entity_id=schedule.id
        )
        db.session.add(notification)
        db.session.commit()
        return schedule

    @classmethod
    def reschedule_interview(cls, schedule_id, start_time, end_time, venue, meeting_link):
        schedule = InterviewSchedule.query.get_or_404(schedule_id)
        schedule.scheduled_start = start_time
        schedule.scheduled_end = end_time
        schedule.venue = venue
        schedule.meeting_link = meeting_link
        schedule.status = ScheduleStatus.RESCHEDULED

        app = schedule.application
        round_obj = schedule.round
        msg = f"Your interview for round '{round_obj.round_name}' under drive '{round_obj.drive.title}' has been rescheduled to {schedule.scheduled_start.strftime('%d %b %Y, %I:%M %p')}."
        notification = Notification(
            user_id=app.student.user_id,
            title="Interview Rescheduled",
            message=msg,
            notification_type=NotificationType.WARNING,
            entity_type="interview",
            entity_id=schedule.id
        )
        db.session.add(notification)
        db.session.commit()
        return schedule

    @classmethod
    def cancel_interview(cls, schedule_id):
        schedule = InterviewSchedule.query.get_or_404(schedule_id)
        schedule.status = ScheduleStatus.CANCELLED

        result = RoundResult.query.filter_by(application_id=schedule.application_id, round_id=schedule.round_id).first()
        if result:
            result.result_status = RoundResultStatus.DISQUALIFIED

        app = schedule.application
        round_obj = schedule.round
        msg = f"Your interview for round '{round_obj.round_name}' under drive '{round_obj.drive.title}' has been cancelled."
        notification = Notification(
            user_id=app.student.user_id,
            title="Interview Cancelled",
            message=msg,
            notification_type=NotificationType.ERROR,
            entity_type="interview",
            entity_id=schedule.id
        )
        db.session.add(notification)
        db.session.commit()
        return schedule

    @classmethod
    def evaluate_interview(cls, schedule_id, score, status, remarks, evaluator_user_id):
        schedule = InterviewSchedule.query.get_or_404(schedule_id)
        
        if status == "absent":
            schedule.status = ScheduleStatus.NO_SHOW
        else:
            schedule.status = ScheduleStatus.COMPLETED

        result = RoundResult.query.filter_by(application_id=schedule.application_id, round_id=schedule.round_id).first()
        if not result:
            result = RoundResult(application_id=schedule.application_id, round_id=schedule.round_id)
            db.session.add(result)

        result.result_status = RoundResultStatus(status)
        if score is not None:
            result.score = Decimal(str(score))
        result.remarks = remarks
        from app.models.company import Recruiter
        recruiter_profile = Recruiter.query.filter_by(user_id=evaluator_user_id).first()
        result.evaluated_by = recruiter_profile.id if recruiter_profile else None
        result.evaluated_at = db.func.now()

        app = schedule.application
        if status == "passed":
            next_round = InterviewRound.query.filter(
                InterviewRound.drive_id == schedule.round.drive_id,
                InterviewRound.sequence_order > schedule.round.sequence_order
            ).order_by(InterviewRound.sequence_order.asc()).first()
            
            if not next_round:
                app.status = ApplicationStatus.SELECTED
                app.status_updated_at = db.func.now()
        elif status in ("failed", "absent"):
            app.status = ApplicationStatus.REJECTED
            app.status_updated_at = db.func.now()

        round_obj = schedule.round
        msg = f"Evaluation complete for round '{round_obj.round_name}'. Outcome: {status.replace('_', ' ').title()}."
        if remarks:
            msg += f" Remarks: {remarks}"
            
        notification = Notification(
            user_id=app.student.user_id,
            title="Interview Round Evaluated",
            message=msg,
            notification_type=NotificationType.SUCCESS if status == "passed" else NotificationType.WARNING,
            entity_type="interview",
            entity_id=schedule.id
        )
        db.session.add(notification)
        db.session.commit()
        return schedule

    @staticmethod
    def get_candidate_interview_timeline(application_id):
        app = Application.query.get_or_404(application_id)
        rounds = InterviewRound.query.filter_by(drive_id=app.drive_id).order_by(InterviewRound.sequence_order.asc()).all()

        timeline = []
        for r in rounds:
            res = RoundResult.query.filter_by(application_id=application_id, round_id=r.id).first()
            sched = InterviewSchedule.query.filter_by(application_id=application_id, round_id=r.id).order_by(InterviewSchedule.created_at.desc()).first()
            
            timeline.append({
                "round": r,
                "result": res,
                "schedule": sched
            })
        return timeline


    # ==========================================
    # OFFER MANAGEMENT MODULE ADDITIONS
    # ==========================================

    @staticmethod
    def get_offers_selection_list(company_id):
        # Candidates in SELECTED status who do not have an Offer extended
        extended_sub = db.session.query(Offer.application_id).subquery()
        return Application.query.options(
            joinedload(Application.student).joinedload(Student.branch),
            joinedload(Application.drive)
        ).join(PlacementDrive)\
         .filter(
             PlacementDrive.company_id == company_id,
             Application.status == ApplicationStatus.SELECTED,
             Application.id.not_in(extended_sub)
         ).all()

    @staticmethod
    def get_company_offers_list(company_id):
        # All offers extended by recruiters of this company
        return Offer.query.options(
            joinedload(Offer.application).joinedload(Application.student),
            joinedload(Offer.application).joinedload(Application.drive),
            joinedload(Offer.extender)
        ).join(Application).join(PlacementDrive)\
         .filter(PlacementDrive.company_id == company_id)\
         .order_by(Offer.created_at.desc())\
         .all()

    @staticmethod
    def get_company_drives(company_id, status=None):
        """
        Return all placement drives for the given company, optionally filtered
        by status. Each drive is annotated with a live applicant count.
        """
        from sqlalchemy import func as _func
        q = PlacementDrive.query.filter(
            PlacementDrive.company_id == company_id
        )
        if status:
            try:
                q = q.filter(PlacementDrive.status == DriveStatus(status))
            except ValueError:
                pass
        drives = q.order_by(PlacementDrive.created_at.desc()).all()

        # Annotate each drive with applicant count (avoids N+1)
        drive_ids = [d.id for d in drives]
        counts = {}
        if drive_ids:
            rows = (
                db.session.query(Application.drive_id, _func.count(Application.id))
                .filter(Application.drive_id.in_(drive_ids))
                .group_by(Application.drive_id)
                .all()
            )
            counts = {str(drive_id): cnt for drive_id, cnt in rows}

        result = []
        for d in drives:
            result.append({
                "drive": d,
                "applicant_count": counts.get(str(d.id), 0),
            })
        return result

    @classmethod
    def create_and_release_offer(cls, form_data, file_storage, recruiter_profile_id):
        application_id = uuid.UUID(form_data.get("application_id"))
        
        offer = Offer(
            application_id=application_id,
            extended_by=recruiter_profile_id,
            package_offered_lpa=Decimal(str(form_data.get("package_offered_lpa"))),
            job_location=form_data.get("job_location"),
            joining_date=form_data.get("joining_date"),
            expires_at=form_data.get("expires_at"),
            status=OfferStatus.EXTENDED,
            extended_at=db.func.now()
        )
        db.session.add(offer)
        db.session.flush() # populate offer.id

        # Handle PDF upload
        if file_storage:
            upload_dir = Path("static/uploads/offers")
            upload_dir.mkdir(parents=True, exist_ok=True)
            stored_name = f"{offer.id}.pdf"
            file_path = upload_dir / stored_name
            file_storage.save(file_path)
            offer.offer_letter_path = str(file_path.as_posix())

        # Update application status
        app = Application.query.get(application_id)
        if app:
            app.status = ApplicationStatus.OFFERED
            app.status_updated_at = db.func.now()

            # Student Alert Notification
            msg = f"Congratulations! You have received a placement offer of {float(offer.package_offered_lpa):g} LPA from '{app.drive.company.name}' for the role of '{app.drive.job_role}'. Please accept/decline by {offer.expires_at.strftime('%d %b %Y, %I:%M %p')}."
            notification = Notification(
                user_id=app.student.user_id,
                title="Job Offer Received",
                message=msg,
                notification_type=NotificationType.SUCCESS,
                entity_type="offer",
                entity_id=offer.id
            )
            db.session.add(notification)

        db.session.commit()
        return offer

    @classmethod
    def record_offer_response(cls, offer_id, response_status, response_note):
        offer = Offer.query.get_or_404(offer_id)
        app = offer.application
        
        new_status = OfferStatus(response_status)
        offer.status = new_status
        offer.responded_at = db.func.now()
        offer.response_note = response_note

        if new_status == OfferStatus.ACCEPTED:
            app.status = ApplicationStatus.PLACED
            app.status_updated_at = db.func.now()
            
            # Send alert to student
            msg = f"Your acceptance of the placement offer from '{app.drive.company.name}' for {float(offer.package_offered_lpa):g} LPA has been recorded."
            notification = Notification(
                user_id=app.student.user_id,
                title="Offer Acceptance Recorded",
                message=msg,
                notification_type=NotificationType.SUCCESS,
                entity_type="offer",
                entity_id=offer.id
            )
            db.session.add(notification)
            
        elif new_status == OfferStatus.DECLINED:
            app.status = ApplicationStatus.REJECTED
            app.status_updated_at = db.func.now()
            
            msg = f"Your rejection of the placement offer from '{app.drive.company.name}' has been recorded."
            notification = Notification(
                user_id=app.student.user_id,
                title="Offer Rejection Recorded",
                message=msg,
                notification_type=NotificationType.WARNING,
                entity_type="offer",
                entity_id=offer.id
            )
            db.session.add(notification)

        db.session.commit()
        return offer

    @staticmethod
    def get_company_profile_stats(company_id):
        """
        Company-wide recruitment stats (across all colleges) for the
        recruiter's own company profile page.
        """
        from sqlalchemy import func as _func

        total_drives = PlacementDrive.query.filter_by(company_id=company_id).count()

        total_hires = db.session.query(_func.count(Application.id))\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                Application.status == ApplicationStatus.PLACED
            ).scalar() or 0

        avg_pkg = db.session.query(_func.avg(Offer.package_offered_lpa))\
            .join(Application, Offer.application_id == Application.id)\
            .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
            .filter(
                PlacementDrive.company_id == company_id,
                Application.status == ApplicationStatus.PLACED
            ).scalar()
        average_package = round(float(avg_pkg), 2) if avg_pkg is not None else 0.0

        last_drive = PlacementDrive.query\
            .filter_by(company_id=company_id)\
            .order_by(PlacementDrive.drive_date.desc().nullslast())\
            .first()
        last_recruitment_date = last_drive.drive_date if last_drive else None

        active_drives = PlacementDrive.query.filter(
            PlacementDrive.company_id == company_id,
            PlacementDrive.status.in_([DriveStatus.PUBLISHED, DriveStatus.ONGOING])
        ).count()

        return {
            "total_drives":        total_drives,
            "active_drives":       active_drives,
            "total_hires":         total_hires,
            "average_package":     average_package,
            "last_recruitment_date": last_recruitment_date,
        }

    @staticmethod
    def get_company_recruitment_history(company_id):
        """
        All drives + placed students for the recruiter's company (all colleges).
        """
        drives = PlacementDrive.query\
            .filter_by(company_id=company_id)\
            .order_by(PlacementDrive.drive_date.desc().nullslast(),
                      PlacementDrive.created_at.desc())\
            .all()

        hires_rows = db.session.query(
            Student.first_name,
            Student.last_name,
            Branch.code,
            Offer.package_offered_lpa,
            Offer.extended_at,
            Offer.created_at,
            PlacementDrive.job_role
        ).select_from(Student)\
         .join(Branch, Student.branch_id == Branch.id)\
         .join(Application, Student.id == Application.student_id)\
         .join(PlacementDrive, Application.drive_id == PlacementDrive.id)\
         .join(Offer, Offer.application_id == Application.id)\
         .filter(
             PlacementDrive.company_id == company_id,
             Application.status == ApplicationStatus.PLACED
         ).order_by(Offer.extended_at.desc().nullslast(),
                    Offer.created_at.desc())\
         .all()

        hires = [
            {
                "student_name": f"{r[0]} {r[1]}",
                "branch_code":  r[2],
                "package":      float(r[3]) if r[3] is not None else 0.0,
                "date":         r[4] or r[5],
                "job_role":     r[6],
            }
            for r in hires_rows
        ]

        return {"drives": drives, "hires": hires}

    @classmethod
    def revoke_offer(cls, offer_id):
        offer = Offer.query.get_or_404(offer_id)
        app = offer.application
        
        offer.status = OfferStatus.REVOKED
        app.status = ApplicationStatus.REJECTED
        app.status_updated_at = db.func.now()

        # Send alert
        msg = f"Your placement offer of {float(offer.package_offered_lpa):g} LPA from '{app.drive.company.name}' has been revoked by the corporate recruiter."
        notification = Notification(
            user_id=app.student.user_id,
            title="Offer Revoked",
            message=msg,
            notification_type=NotificationType.ERROR,
            entity_type="offer",
            entity_id=offer.id
        )
        db.session.add(notification)
        db.session.commit()
        return offer
