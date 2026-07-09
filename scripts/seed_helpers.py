"""Idempotent seed/upsert helpers shared by init_db.py and reset_demo_data.py.

Every function here is safe to call repeatedly: it creates a record if
missing, or updates it in place to match `scripts/demo_data.py` if it already
exists. Nothing here ever creates a duplicate row.
"""

from decimal import Decimal

from app.auth.services import AuthService
from app.extensions import db
from app.models.college import Branch, College, Skill
from app.models.company import Company, Recruiter
from app.models.drive import DriveBranch, PlacementDrive
from app.models.enums import (
    DriveStatus,
    LocationType,
    ProfileStatus,
    UserRole,
    VerificationStatus,
)
from app.models.student import Student
from app.models.tpo import TpoAdmin
from app.models.user import User
from scripts.demo_data import (
    DEMO_ACCOUNTS,
    DEMO_BRANCHES,
    DEMO_COLLEGES,
    DEMO_COMPANIES,
    DEMO_DRIVE,
    DEMO_SKILLS,
)


def seed_reference_data():
    """Colleges, branches, skills, companies — create-if-missing, update-if-present."""
    log = []

    for c_data in DEMO_COLLEGES:
        college = College.query.filter_by(code=c_data["code"]).first()
        if college is None:
            college = College(name=c_data["name"], code=c_data["code"], is_active=True)
            db.session.add(college)
            log.append(f"Created College: {c_data['code']}")
        elif college.name != c_data["name"] or not college.is_active:
            college.name = c_data["name"]
            college.is_active = True
            log.append(f"Updated College: {c_data['code']}")

    db.session.flush()

    college_by_code = {c.code: c for c in College.query.filter(
        College.code.in_([c["code"] for c in DEMO_COLLEGES])
    ).all()}

    for b_data in DEMO_BRANCHES:
        college = college_by_code.get(b_data["college_code"])
        if college is None:
            continue
        branch = Branch.query.filter_by(code=b_data["code"], college_id=college.id).first()
        if branch is None:
            branch = Branch(
                name=b_data["name"],
                code=b_data["code"],
                college_id=college.id,
                is_active=True,
            )
            db.session.add(branch)
            log.append(f"Created Branch: {b_data['code']} for {college.code}")
        elif branch.name != b_data["name"] or not branch.is_active:
            branch.name = b_data["name"]
            branch.is_active = True
            log.append(f"Updated Branch: {b_data['code']} for {college.code}")

    for sk_name in DEMO_SKILLS:
        skill = Skill.query.filter_by(name=sk_name).first()
        if skill is None:
            db.session.add(Skill(name=sk_name))
            log.append(f"Created Skill: {sk_name}")

    for comp_data in DEMO_COMPANIES:
        company = Company.query.filter(db.func.lower(Company.name) == comp_data["name"].lower()).first()
        if company is None:
            company = Company(
                name=comp_data["name"],
                website=comp_data["website"],
                contact_email=comp_data["email"],
                verification_status=VerificationStatus.APPROVED,
                is_active=True,
            )
            db.session.add(company)
            log.append(f"Created Company: {comp_data['name']}")
        else:
            changed = False
            if company.verification_status != VerificationStatus.APPROVED:
                company.verification_status = VerificationStatus.APPROVED
                changed = True
            if not company.is_active:
                company.is_active = True
                changed = True
            if changed:
                log.append(f"Updated Company: {comp_data['name']}")

    db.session.commit()
    return log


def _upsert_user(email, role, password, *, is_active=True, is_verified=True):
    user = User.query.filter_by(email=email).first()
    password_hash = AuthService.hash_password(password)
    if user is None:
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
        )
        db.session.add(user)
        db.session.flush()
        return user, True
    user.password_hash = password_hash
    user.role = role
    user.is_active = is_active
    user.is_verified = is_verified
    return user, False


def seed_demo_admin():
    data = DEMO_ACCOUNTS["admin"]
    user, created = _upsert_user(data["email"], UserRole.ADMIN, data["password"])
    db.session.commit()
    return f"{'Created' if created else 'Updated'} demo Admin: {data['email']}"


def seed_demo_tpo():
    data = DEMO_ACCOUNTS["tpo"]
    college = College.query.filter_by(code=data["college_code"]).first()
    if college is None:
        return f"Skipped demo TPO: college {data['college_code']} not seeded yet"

    user, created = _upsert_user(data["email"], UserRole.TPO, data["password"])

    tpo = TpoAdmin.query.filter_by(user_id=user.id).first()
    if tpo is None:
        tpo = TpoAdmin(user_id=user.id, college_id=college.id)
        db.session.add(tpo)
    tpo.college_id = college.id
    tpo.first_name = data["first_name"]
    tpo.last_name = data["last_name"]
    tpo.designation = data["designation"]
    tpo.department = data["department"]
    tpo.is_primary_tpo = data["is_primary_tpo"]
    tpo.is_active = True

    db.session.commit()
    return f"{'Created' if created else 'Updated'} demo TPO: {data['email']}"


def seed_demo_recruiter():
    data = DEMO_ACCOUNTS["recruiter"]
    company = Company.query.filter(db.func.lower(Company.name) == data["company_name"].lower()).first()
    if company is None:
        return f"Skipped demo Recruiter: company {data['company_name']} not seeded yet"

    user, created = _upsert_user(data["email"], UserRole.RECRUITER, data["password"])

    recruiter = Recruiter.query.filter_by(user_id=user.id).first()
    if recruiter is None:
        recruiter = Recruiter(user_id=user.id, company_id=company.id)
        db.session.add(recruiter)
    recruiter.company_id = company.id
    recruiter.first_name = data["first_name"]
    recruiter.last_name = data["last_name"]
    recruiter.designation = data["designation"]
    recruiter.is_primary_contact = data["is_primary_contact"]
    recruiter.is_active = True

    db.session.commit()
    return f"{'Created' if created else 'Updated'} demo Recruiter: {data['email']}"


def seed_demo_student():
    data = DEMO_ACCOUNTS["student"]
    college = College.query.filter_by(code=data["college_code"]).first()
    if college is None:
        return f"Skipped demo Student: college {data['college_code']} not seeded yet"
    branch = Branch.query.filter_by(code=data["branch_code"], college_id=college.id).first()
    if branch is None:
        return f"Skipped demo Student: branch {data['branch_code']} not seeded yet"

    user, created = _upsert_user(data["email"], UserRole.STUDENT, data["password"])

    student = Student.query.filter_by(user_id=user.id).first()
    if student is None:
        student = Student(
            user_id=user.id,
            college_id=college.id,
            branch_id=branch.id,
            enrollment_number=data["enrollment_number"],
        )
        db.session.add(student)
    student.college_id = college.id
    student.branch_id = branch.id
    student.enrollment_number = data["enrollment_number"]
    student.first_name = data["first_name"]
    student.last_name = data["last_name"]
    student.phone = data["phone"]
    student.batch = data["batch"]
    student.graduation_year = data["graduation_year"]
    student.semester = data["semester"]
    student.cgpa = Decimal(data["cgpa"])
    student.profile_status = ProfileStatus.VERIFIED

    db.session.commit()
    return f"{'Created' if created else 'Updated'} demo Student: {data['email']}"


def seed_demo_accounts():
    return [
        seed_demo_admin(),
        seed_demo_tpo(),
        seed_demo_recruiter(),
        seed_demo_student(),
    ]


def seed_demo_drive():
    data = DEMO_DRIVE
    company = Company.query.filter(db.func.lower(Company.name) == data["company_name"].lower()).first()
    college = College.query.filter_by(code=data["college_code"]).first()
    tpo = TpoAdmin.query.join(User).filter(User.email == DEMO_ACCOUNTS["tpo"]["email"]).first()

    if not (company and college and tpo):
        return "Skipped demo Placement Drive: dependent demo records not seeded yet"

    drive = PlacementDrive.query.filter_by(title=data["title"], college_id=college.id).first()
    if drive is None:
        drive = PlacementDrive(
            company_id=company.id,
            college_id=college.id,
            created_by_tpo_id=tpo.id,
            title=data["title"],
            job_role=data["job_role"],
            job_description=data["job_description"],
            package_min_lpa=Decimal(data["package_min_lpa"]),
            package_max_lpa=Decimal(data["package_max_lpa"]),
            vacancies=data["vacancies"],
            status=DriveStatus.PUBLISHED,
            location_type=LocationType.ON_CAMPUS,
            published_at=db.func.now(),
        )
        db.session.add(drive)
        db.session.flush()
        created = True
    else:
        drive.job_role = data["job_role"]
        drive.job_description = data["job_description"]
        drive.package_min_lpa = Decimal(data["package_min_lpa"])
        drive.package_max_lpa = Decimal(data["package_max_lpa"])
        drive.vacancies = data["vacancies"]
        created = False

    branches = Branch.query.filter(
        Branch.college_id == college.id,
        Branch.code.in_(data["branch_codes"]),
    ).all()
    existing_branch_ids = {db_link.branch_id for db_link in drive.drive_branches}
    for branch in branches:
        if branch.id not in existing_branch_ids:
            db.session.add(DriveBranch(drive_id=drive.id, branch_id=branch.id))

    db.session.commit()
    return f"{'Created' if created else 'Updated'} demo Placement Drive: {data['title']}"
