"""Single source of truth for CampusHire AI demo/seed data.

Both `scripts/init_db.py` (idempotent bootstrap) and `scripts/reset_demo_data.py`
(wipe-and-recreate) import their record definitions from here so there is only
one place to update demo credentials, seed colleges, skills, etc.

Do not import this module from application request-handling code — it is a
setup-time only fixture module.
"""

DEMO_COLLEGES = [
    {"name": "Indian Institute of Technology Bombay", "code": "IITB"},
    {"name": "Birla Institute of Technology and Science, Pilani", "code": "BITS"},
    {"name": "Graphic Era University", "code": "GEU"},
    {"name": "National Institute of Technology Kurukshetra", "code": "NITK"},
]

DEMO_BRANCHES = [
    {"name": "Computer Science & Engineering", "code": "CSE", "college_code": "IITB"},
    {"name": "Electronics & Communication Engg.", "code": "ECE", "college_code": "IITB"},
    {"name": "Computer Science", "code": "CS", "college_code": "BITS"},
    {"name": "Computer Science & Engineering", "code": "CSE", "college_code": "GEU"},
    {"name": "Electronics & Communication Engg.", "code": "ECE", "college_code": "GEU"},
    {"name": "Mechanical Engineering", "code": "ME", "college_code": "GEU"},
    {"name": "Civil Engineering", "code": "CE", "college_code": "GEU"},
    {"name": "Information Technology", "code": "IT", "college_code": "GEU"},
    {"name": "Master of Business Administration", "code": "MBA", "college_code": "GEU"},
    {"name": "Master of Computer Applications", "code": "MCA", "college_code": "GEU"},
    {"name": "Computer Science & Engineering", "code": "CSE", "college_code": "NITK"},
]

DEMO_SKILLS = [
    "Python", "Java", "C++", "JavaScript", "SQL",
    "Flask", "React", "Docker", "Kubernetes", "Machine Learning",
]

DEMO_COMPANIES = [
    {"name": "Google", "website": "https://google.com", "email": "careers@google.com"},
    {"name": "Microsoft", "website": "https://microsoft.com", "email": "careers@microsoft.com"},
]

# ---------------------------------------------------------------------------
# Demo login accounts — the single place credentials are defined.
# `scripts/init_db.py` and `scripts/reset_demo_data.py` both read from here,
# and `docs/DEMO_CREDENTIALS.md` documents these same values for humans.
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "Demo@1234"

DEMO_ACCOUNTS = {
    "admin": {
        "email": "admin@campushire.ai",
        "password": DEMO_PASSWORD,
    },
    "tpo": {
        "email": "tpo@geu.edu.in",
        "password": DEMO_PASSWORD,
        "college_code": "GEU",
        "first_name": "Priya",
        "last_name": "Sharma",
        "designation": "Training & Placement Officer",
        "department": "Placement Cell",
        "is_primary_tpo": True,
    },
    "tpo_iitb": {
        "email": "tpo@iitb.ac.in",
        "password": DEMO_PASSWORD,
        "college_code": "IITB",
        "first_name": "Rahul",
        "last_name": "Mehta",
        "designation": "Training & Placement Officer",
        "department": "Placement Cell",
        "is_primary_tpo": True,
    },
    "tpo_nitk": {
        "email": "tpo@nitk.edu",
        "password": DEMO_PASSWORD,
        "college_code": "NITK",
        "first_name": "Neha",
        "last_name": "Verma",
        "designation": "Training & Placement Officer",
        "department": "Placement Cell",
        "is_primary_tpo": True,
    },
    "recruiter": {
        "email": "recruiter.demo@campushire.ai",
        "password": DEMO_PASSWORD,
        "company_name": "Google",
        "first_name": "Alex",
        "last_name": "Carter",
        "designation": "University Recruiter",
        "is_primary_contact": True,
    },
    "student": {
        "email": "student.demo@campushire.ai",
        "password": DEMO_PASSWORD,
        "college_code": "GEU",
        "branch_code": "CSE",
        "enrollment_number": "GEU-CSE-2022-0001",
        "first_name": "Rahul",
        "last_name": "Verma",
        "batch": "2022-2026",
        "graduation_year": 2026,
        "semester": 6,
        "cgpa": "8.40",
        "phone": "9876543210",
    },
}

DEMO_DRIVE = {
    "title": "Software Engineer Campus Drive (Demo)",
    "company_name": "Google",
    "college_code": "GEU",
    "job_role": "Software Engineer I",
    "job_description": (
        "Sample placement drive seeded for demo purposes. Work on backend "
        "services, participate in code reviews, and collaborate with "
        "cross-functional teams on production systems."
    ),
    "package_min_lpa": "12.00",
    "package_max_lpa": "18.00",
    "vacancies": 5,
    "branch_codes": ["CSE", "ECE", "IT"],
}
