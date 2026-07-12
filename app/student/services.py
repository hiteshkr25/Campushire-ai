from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.exceptions import ApplicationError, ApplicationNotFoundError, DriveNotFoundError, EligibilityError
from app.extensions import db
from app.models.application import Application
from app.models.company import Company
from app.models.drive import DriveBranch, EligibilityRule, PlacementDrive
from app.models.enums import (
    ApplicationStatus,
    DriveStatus,
    EligibilityOperator,
    EligibilityRuleType,
    LocationType,
    ProfileStatus,
)
from app.models.student import Resume, Student, StudentSkill


VISIBLE_DRIVE_STATUSES = (
    DriveStatus.PUBLISHED,
    DriveStatus.REGISTRATION_CLOSED,
    DriveStatus.ONGOING,
)

ACTIVE_APPLICATION_STATUSES = {
    ApplicationStatus.DRAFT,
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.INTERVIEW_IN_PROGRESS,
    ApplicationStatus.SELECTED,
    ApplicationStatus.OFFERED,
}

WITHDRAWABLE_STATUSES = {
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.SHORTLISTED,
}

REAPPLY_STATUSES = {
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.REJECTED,
    ApplicationStatus.NOT_SELECTED,
}


@dataclass
class EligibilityCheck:
    rule_id: str
    label: str
    passed: bool
    message: str
    is_mandatory: bool = True


@dataclass
class EligibilityResult:
    eligible: bool
    checks: list = field(default_factory=list)

    def failed_mandatory(self):
        return [check for check in self.checks if check.is_mandatory and not check.passed]


@dataclass
class DriveListItem:
    drive: PlacementDrive
    eligibility: EligibilityResult
    application: Application | None
    registration_open: bool


class EligibilityService:
    RULE_LABELS = {
        EligibilityRuleType.MIN_CGPA: "Minimum CGPA",
        EligibilityRuleType.MAX_CGPA: "Maximum CGPA",
        EligibilityRuleType.MAX_BACKLOGS: "Maximum backlogs",
        EligibilityRuleType.MIN_GRADUATION_YEAR: "Minimum graduation year",
        EligibilityRuleType.MAX_GRADUATION_YEAR: "Maximum graduation year",
        EligibilityRuleType.ALLOWED_BATCH: "Allowed batch",
        EligibilityRuleType.REQUIRED_SKILL: "Required skill",
        EligibilityRuleType.GENDER: "Gender",
        EligibilityRuleType.CUSTOM: "Custom requirement",
    }

    @classmethod
    def evaluate(cls, student, drive, student_skills=None, rules=None, branch_links=None):
        checks = []
        branch_check = cls._check_branch(student, drive, branch_links=branch_links)
        checks.append(branch_check)

        if rules is None:
            rules = (
                drive.eligibility_rules.order_by(
                    EligibilityRule.display_order.asc(),
                    EligibilityRule.created_at.asc(),
                ).all()
            )
        for rule in rules:
            checks.append(cls._evaluate_rule(student, rule, student_skills=student_skills))

        eligible = all(check.passed for check in checks if check.is_mandatory)
        return EligibilityResult(eligible=eligible, checks=checks)

    @classmethod
    def _check_branch(cls, student, drive, branch_links=None):
        if branch_links is None:
            branch_links = drive.drive_branches.all()
        if not branch_links:
            return EligibilityCheck(
                rule_id="branch",
                label="Branch eligibility",
                passed=True,
                message="Open to all branches in your college.",
                is_mandatory=True,
            )

        allowed = {link.branch_id for link in branch_links}
        passed = student.branch_id in allowed
        return EligibilityCheck(
            rule_id="branch",
            label="Branch eligibility",
            passed=passed,
            message=(
                "Your branch is eligible for this drive."
                if passed
                else "This drive is not open to your branch."
            ),
            is_mandatory=True,
        )

    @classmethod
    def _evaluate_rule(cls, student, rule, student_skills=None):
        label = cls.RULE_LABELS.get(rule.rule_type, rule.rule_type.value)
        passed, message = cls._apply_rule(student, rule, student_skills=student_skills)
        return EligibilityCheck(
            rule_id=str(rule.id),
            label=label,
            passed=passed,
            message=message,
            is_mandatory=rule.is_mandatory,
        )

    @classmethod
    def _apply_rule(cls, student, rule, student_skills=None):
        value = rule.rule_value
        operator = rule.operator
        rule_type = rule.rule_type

        if rule_type == EligibilityRuleType.MIN_CGPA:
            return cls._compare_numeric(student.cgpa, operator or EligibilityOperator.GTE, value, "CGPA")
        if rule_type == EligibilityRuleType.MAX_CGPA:
            return cls._compare_numeric(student.cgpa, operator or EligibilityOperator.LTE, value, "CGPA")
        if rule_type == EligibilityRuleType.MAX_BACKLOGS:
            return cls._compare_numeric(student.backlogs_count, operator or EligibilityOperator.LTE, value, "backlogs")
        if rule_type == EligibilityRuleType.MIN_GRADUATION_YEAR:
            return cls._compare_numeric(student.graduation_year, operator or EligibilityOperator.GTE, value, "graduation year")
        if rule_type == EligibilityRuleType.MAX_GRADUATION_YEAR:
            return cls._compare_numeric(student.graduation_year, operator or EligibilityOperator.LTE, value, "graduation year")
        if rule_type == EligibilityRuleType.ALLOWED_BATCH:
            return cls._compare_batch(student.batch, operator or EligibilityOperator.IN, value)
        if rule_type == EligibilityRuleType.REQUIRED_SKILL:
            return cls._compare_skill(student, operator or EligibilityOperator.CONTAINS, value, student_skills=student_skills)
        if rule_type == EligibilityRuleType.GENDER:
            return cls._compare_text(student.gender, operator or EligibilityOperator.EQ, value, "gender")
        if rule_type == EligibilityRuleType.CUSTOM:
            return True, "Custom rule recorded by TPO."

        return False, "Unsupported eligibility rule."

    @staticmethod
    def _normalize_json_value(value):
        if isinstance(value, dict):
            return value.get("value", value.get("values", value))
        return value

    @classmethod
    def _compare_numeric(cls, actual, operator, expected_raw, label):
        expected = cls._normalize_json_value(expected_raw)
        if actual is None:
            return False, f"Your {label} is not set on your profile."
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False, f"Invalid {label} requirement configured for this drive."

        passed = cls._compare(actual_num, operator, expected_num)
        op_label = operator.value.replace("_", " ")
        if passed:
            return True, f"Your {label} ({actual_num:g}) meets the requirement ({op_label} {expected_num:g})."
        return False, f"Your {label} ({actual_num:g}) does not meet the requirement ({op_label} {expected_num:g})."

    @classmethod
    def _compare_batch(cls, batch, operator, expected_raw):
        expected = cls._normalize_json_value(expected_raw)
        if not batch:
            return False, "Your batch is not set on your profile."
        values = expected if isinstance(expected, list) else [expected]
        values = [str(item).strip().lower() for item in values if item is not None]
        passed = cls._compare(batch.strip().lower(), operator, values)
        if passed:
            return True, f"Your batch ({batch}) is eligible."
        return False, f"Your batch ({batch}) is not in the allowed list."

    @classmethod
    def _compare_skill(cls, student, operator, expected_raw, student_skills=None):
        expected = cls._normalize_json_value(expected_raw)
        if student_skills is None:
            student_skills = {
                link.skill.name.strip().lower()
                for link in student.skills.all()
                if link.skill and link.skill.name
            }
        skill_names = student_skills
        required = expected if isinstance(expected, list) else [expected]
        required = [str(item).strip().lower() for item in required if item]

        if operator in (EligibilityOperator.IN, EligibilityOperator.CONTAINS, EligibilityOperator.EQ):
            passed = any(item in skill_names for item in required)
        elif operator == EligibilityOperator.NOT_IN:
            passed = all(item not in skill_names for item in required)
        else:
            passed = any(item in skill_names for item in required)

        if passed:
            return True, "Required skills satisfied."
        missing = ", ".join(required)
        return False, f"Missing required skill(s): {missing}."

    @classmethod
    def _compare_text(cls, actual, operator, expected_raw, label):
        expected = cls._normalize_json_value(expected_raw)
        if not actual:
            return False, f"Your {label} is not set on your profile."
        passed = cls._compare(str(actual).strip().lower(), operator, str(expected).strip().lower())
        if passed:
            return True, f"Your {label} matches the drive requirement."
        return False, f"Your {label} does not match the drive requirement."

    @staticmethod
    def _compare(actual, operator, expected):
        if operator == EligibilityOperator.EQ:
            return actual == expected
        if operator == EligibilityOperator.NEQ:
            return actual != expected
        if operator == EligibilityOperator.GT:
            return actual > expected
        if operator == EligibilityOperator.GTE:
            return actual >= expected
        if operator == EligibilityOperator.LT:
            return actual < expected
        if operator == EligibilityOperator.LTE:
            return actual <= expected
        if operator == EligibilityOperator.IN:
            if isinstance(expected, list):
                return actual in expected
            return actual == expected
        if operator == EligibilityOperator.NOT_IN:
            if isinstance(expected, list):
                return actual not in expected
            return actual != expected
        if operator == EligibilityOperator.CONTAINS:
            if isinstance(expected, list):
                return actual in expected
            return str(expected).lower() in str(actual).lower()
        return False


class DriveService:
    @staticmethod
    def is_registration_open(drive):
        if drive.status != DriveStatus.PUBLISHED:
            return False
        if drive.registration_deadline:
            now = datetime.now(timezone.utc)
            deadline = drive.registration_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline < now:
                return False
        return True

    @classmethod
    def list_for_student(cls, student, *, q=None, location_type=None, min_package=None, eligibility_filter=None, sort="deadline", student_skills=None):
        if student.profile_status != ProfileStatus.VERIFIED:
            return []

        query = (
            PlacementDrive.query.options(joinedload(PlacementDrive.company))
            .filter(
                PlacementDrive.college_id == student.college_id,
                PlacementDrive.status.in_(VISIBLE_DRIVE_STATUSES),
            )
        )

        if q:
            term = f"%{q.strip()}%"
            query = query.join(Company).filter(
                or_(
                    PlacementDrive.title.ilike(term),
                    PlacementDrive.job_role.ilike(term),
                    Company.name.ilike(term),
                )
            )

        if location_type:
            try:
                query = query.filter(
                    PlacementDrive.location_type == LocationType(location_type)
                )
            except ValueError:
                pass

        if min_package is not None:
            query = query.filter(
                or_(
                    PlacementDrive.package_max_lpa >= min_package,
                    PlacementDrive.package_min_lpa >= min_package,
                )
            )

        if sort == "package":
            query = query.order_by(
                PlacementDrive.package_max_lpa.desc().nullslast(),
                PlacementDrive.package_min_lpa.desc().nullslast(),
            )
        elif sort == "newest":
            query = query.order_by(PlacementDrive.published_at.desc().nullslast(), PlacementDrive.created_at.desc())
        else:
            query = query.order_by(
                PlacementDrive.registration_deadline.asc().nullslast(),
                PlacementDrive.drive_date.asc().nullslast(),
            )

        drives = query.all()
        application_map = cls._application_map(student, [drive.id for drive in drives])

        # Pre-load student skills with names in a single query if not provided
        if student_skills is None:
            from app.models.student import StudentSkill
            student_skills_loaded = StudentSkill.query.options(joinedload(StudentSkill.skill))\
                .filter_by(student_id=student.id).all()
            student_skills = {
                link.skill.name.strip().lower()
                for link in student_skills_loaded
                if link.skill and link.skill.name
            }

        # Batch query all drive branches and eligibility rules for the fetched drives
        from app.models.drive import EligibilityRule, DriveBranch
        from collections import defaultdict
        
        drive_ids = [d.id for d in drives]
        
        rules_map = defaultdict(list)
        if drive_ids:
            rules_list = EligibilityRule.query.filter(EligibilityRule.drive_id.in_(drive_ids))\
                .order_by(EligibilityRule.display_order.asc(), EligibilityRule.created_at.asc()).all()
            for rule in rules_list:
                rules_map[rule.drive_id].append(rule)
            
        branches_map = defaultdict(list)
        if drive_ids:
            branches_list = DriveBranch.query.filter(DriveBranch.drive_id.in_(drive_ids)).all()
            for b_link in branches_list:
                branches_map[b_link.drive_id].append(b_link)

        items = []
        for drive in drives:
            eligibility = EligibilityService.evaluate(
                student,
                drive,
                student_skills=student_skills,
                rules=rules_map.get(drive.id),
                branch_links=branches_map.get(drive.id)
            )
            if eligibility_filter == "eligible" and not eligibility.eligible:
                continue
            if eligibility_filter == "not_eligible" and eligibility.eligible:
                continue
            items.append(
                DriveListItem(
                    drive=drive,
                    eligibility=eligibility,
                    application=application_map.get(drive.id),
                    registration_open=cls.is_registration_open(drive),
                )
            )
        return items

    @classmethod
    def get_for_student(cls, student, drive_id):
        if student.profile_status != ProfileStatus.VERIFIED:
            raise DriveNotFoundError()

        drive = (
            PlacementDrive.query.options(joinedload(PlacementDrive.company))
            .filter_by(id=drive_id, college_id=student.college_id)
            .first()
        )
        if not drive:
            raise DriveNotFoundError()

        application = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
        if not application and drive.status not in VISIBLE_DRIVE_STATUSES:
            raise DriveNotFoundError()

        eligibility = EligibilityService.evaluate(student, drive)
        return DriveListItem(
            drive=drive,
            eligibility=eligibility,
            application=application,
            registration_open=cls.is_registration_open(drive),
        )

    @staticmethod
    def _application_map(student, drive_ids):
        if not drive_ids:
            return {}
        applications = Application.query.filter(
            Application.student_id == student.id,
            Application.drive_id.in_(drive_ids),
        ).all()
        return {application.drive_id: application for application in applications}


class ApplicationService:
    @staticmethod
    def list_for_student(student, *, status=None, q=None):
        query = (
            Application.query.options(
                joinedload(Application.drive).joinedload(PlacementDrive.company)
            )
            .filter(Application.student_id == student.id)
            .order_by(Application.applied_at.desc().nullslast(), Application.created_at.desc())
        )

        if status:
            try:
                query = query.filter(Application.status == ApplicationStatus(status))
            except ValueError:
                pass

        if q:
            term = f"%{q.strip()}%"
            query = query.join(PlacementDrive).join(Company).filter(
                or_(
                    PlacementDrive.title.ilike(term),
                    PlacementDrive.job_role.ilike(term),
                    Company.name.ilike(term),
                )
            )

        return query.all()

    @staticmethod
    def get_for_student(student, application_id):
        application = (
            Application.query.options(
                joinedload(Application.drive).joinedload(PlacementDrive.company),
                joinedload(Application.resume),
            )
            .filter_by(id=application_id, student_id=student.id)
            .first()
        )
        if not application:
            raise ApplicationNotFoundError()
        return application

    @classmethod
    def apply(cls, student, drive_id, *, resume_id, cover_note=None):
        if student.profile_status != ProfileStatus.VERIFIED:
            raise ApplicationError("Your profile must be verified by the TPO before you can apply to drives.")

        resume = Resume.query.filter_by(id=resume_id, student_id=student.id).first()
        if not resume:
            raise ApplicationError("Select a valid resume to apply.")

        drive_item = DriveService.get_for_student(student, drive_id)
        drive = drive_item.drive

        if not drive_item.registration_open:
            raise ApplicationError("Registration is closed for this drive.")

        if not drive_item.eligibility.eligible:
            raise EligibilityError("You are not eligible for this drive.")

        existing = drive_item.application
        now = datetime.now(timezone.utc)

        if existing and existing.status in ACTIVE_APPLICATION_STATUSES:
            raise ApplicationError("You have already applied to this drive.")

        if existing and existing.status in REAPPLY_STATUSES:
            existing.status = ApplicationStatus.SUBMITTED
            existing.resume_id = resume.id
            existing.cover_note = (cover_note or "").strip() or None
            existing.applied_at = now
            existing.status_updated_at = now
            
            try:
                import json
                from app.student.ats_service import AtsService
                ats_data = AtsService.calculate_ats_score(student, drive, resume=resume)
                existing.ats_score = Decimal(str(ats_data["score"]))
                
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
                existing.match_score = Decimal(str(match_score))
                existing.ats_data = json.dumps(ats_data)
            except Exception:
                pass
                
            db.session.commit()
            return existing

        if existing:
            raise ApplicationError("You cannot apply again for this drive.")

        application = Application(
            student_id=student.id,
            drive_id=drive.id,
            resume_id=resume.id,
            cover_note=(cover_note or "").strip() or None,
            status=ApplicationStatus.SUBMITTED,
            applied_at=now,
            status_updated_at=now,
        )
        db.session.add(application)
        
        try:
            import json
            from app.student.ats_service import AtsService
            ats_data = AtsService.calculate_ats_score(student, drive, resume=resume)
            application.ats_score = Decimal(str(ats_data["score"]))
            
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
            application.match_score = Decimal(str(match_score))
            application.ats_data = json.dumps(ats_data)
        except Exception:
            pass
            
        db.session.commit()
        return application

    @classmethod
    def withdraw(cls, student, application_id):
        application = cls.get_for_student(student, application_id)
        if application.status not in WITHDRAWABLE_STATUSES:
            raise ApplicationError("This application can no longer be withdrawn.")

        application.status = ApplicationStatus.WITHDRAWN
        application.status_updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return application

    @staticmethod
    def summary(student, preloaded_applications=None):
        if preloaded_applications is None:
            preloaded_applications = Application.query.filter_by(student_id=student.id).all()
        active = sum(1 for app in preloaded_applications if app.status in ACTIVE_APPLICATION_STATUSES)
        withdrawn = sum(1 for app in preloaded_applications if app.status == ApplicationStatus.WITHDRAWN)
        placed = sum(1 for app in preloaded_applications if app.status == ApplicationStatus.PLACED)
        return {
            "total": len(preloaded_applications),
            "active": active,
            "withdrawn": withdrawn,
            "placed": placed,
        }

    @staticmethod
    def recent_active(student, limit=5, preloaded_applications=None):
        if preloaded_applications is not None:
            active_apps = [app for app in preloaded_applications if app.status in ACTIVE_APPLICATION_STATUSES]
            from datetime import datetime
            active_apps.sort(key=lambda a: (a.applied_at or datetime.min, a.created_at or datetime.min), reverse=True)
            return active_apps[:limit]

        return (
            Application.query.options(
                joinedload(Application.drive).joinedload(PlacementDrive.company)
            )
            .filter(
                Application.student_id == student.id,
                Application.status.in_(ACTIVE_APPLICATION_STATUSES),
            )
            .order_by(Application.applied_at.desc().nullslast(), Application.created_at.desc())
            .limit(limit)
            .all()
        )
