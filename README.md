<div align="center">

# 🎓 CampusHire AI

### AI-Powered Campus Placement Management System

A production-ready AI-powered campus recruitment platform that streamlines the complete placement lifecycle for Students, Recruiters, Training & Placement Officers (TPOs), and Administrators.

Built using Flask, PostgreSQL, SQLAlchemy, Bootstrap, and AI-based Resume Parsing & ATS Matching.

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue?logo=postgresql)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple?logo=bootstrap)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

# 📌 Overview

CampusHire AI is an intelligent campus placement management platform that digitizes and automates the complete recruitment workflow.

The system connects **Students**, **Recruiters**, **Training & Placement Officers (TPOs)**, and **Administrators** through a secure role-based platform featuring AI-powered resume parsing, ATS scoring, placement drive management, interview workflows, analytics dashboards, notifications, and audit logging.

Unlike traditional placement portals, CampusHire AI incorporates resume intelligence and automated candidate ranking to help recruiters identify the most suitable candidates efficiently.

---

# ✨ Key Features

## 👨‍🎓 Student Portal

- Student Registration & Authentication
- Profile Completion Workflow
- Resume Repository
- AI Resume Parsing
- ATS Score Generation
- Placement Drive Discovery
- Job Applications
- Application Tracking
- Interview Schedule
- Offer Acceptance/Rejection
- Notification Center
- Profile Change Requests
- Dark & Light Theme

---

## 🏢 Recruiter Portal

- Recruiter Registration
- Admin Approval Workflow
- Company Dashboard
- Placement Drive Management
- Candidate Search
- ATS Candidate Ranking
- Resume Viewer
- Candidate Comparison
- Interview Scheduling
- Offer Generation
- Offer Management

---

## 🏫 TPO Portal

- Student Verification
- Recruiter Verification
- Placement Drive Creation
- Eligibility Engine
- Student Reports
- Placement Analytics
- Change Request Management
- CSV Export
- Dashboard Insights

---

## 🛡 Admin Portal

- User Management
- Role Management
- System Monitoring
- Audit Logs
- Recruiter Approval
- Database Health
- Reports
- Security Logs

---

## 🤖 AI Features

- Resume Parsing
- Skills Extraction
- Education Detection
- Work Experience Extraction
- Project Extraction
- GitHub Detection
- LinkedIn Detection
- Resume Summary
- ATS Scoring
- Candidate Ranking

---

# 🖼 Screenshots


## Main Page

![Main](docs/pictures/main-page.png)

---

## Login Page

![Login](docs/pictures/login-page.png)

---


## Student Dashboard

![Student Dashboard](docs/screenshots/student-dashboard.png)

---

## Recruiter Dashboard

![Recruiter Dashboard](docs/screenshots/recruiter-dashboard.png)

---

## TPO Dashboard

![TPO Dashboard](docs/screenshots/tpo-dashboard.png)

---

## Admin Dashboard

![Admin Dashboard](docs/screenshots/admin-dashboard.png)

---

## Analytics Dashboard

![Analytics](docs/screenshots/analytics.png)

---

## Resume ATS Analysis

![ATS](docs/screenshots/resume-ats.png)

---

# 🏗 System Architecture

```text
                    Browser
                        │
                        ▼
               Flask Application
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
 Authentication     Business Logic    AI Services
                        │
                SQLAlchemy ORM
                        │
                  PostgreSQL
```

---

# 🗄 Database ER Diagram

```text
Users
 │
 ├──────────────┐
 ▼              ▼
Students     Recruiters
 │              │
 ▼              ▼
Applications  Companies
 │              │
 ▼              ▼
Placement Drives
 │
 ▼
Offers
 │
 ▼
Notifications

Audit Logs

Resume Repository

Resume Parser

ATS Engine
```

---

# ⚙ Tech Stack

| Category | Technologies |
|----------|--------------|
| Backend | Flask, Python |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Authentication | Flask-Login |
| Forms | WTForms |
| Frontend | Bootstrap 5 |
| Styling | CSS3 |
| Charts | Chart.js |
| AI | Resume Parsing, ATS Engine |
| Templates | Jinja2 |
| Version Control | Git & GitHub |

---

# 📂 Folder Structure

```
CampusHire-AI/

│
├── app/
│   ├── admin/
│   ├── auth/
│   ├── recruiter/
│   ├── student/
│   ├── tpo/
│   ├── models/
│   ├── services/
│   └── utils/
│
├── config/
│
├── docs/
│
├── scripts/
│
├── static/
│
├── templates/
│
├── uploads/
│
├── tests/
│
├── requirements.txt
│
├── run.py
│
└── README.md
```

---

# 🚀 Installation

Clone the repository

```bash
git clone https://github.com/<username>/CampusHire-AI.git
```

Move inside the project

```bash
cd CampusHire-AI
```

Create virtual environment

```bash
python -m venv venv
```

Activate environment

Windows

```bash
venv\Scripts\activate
```

Linux/Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙ Configuration

Create a PostgreSQL database.

Update:

```
config.py
```

Configure

- Database URL
- Secret Key
- Mail Settings
- Upload Directory

Initialize database

```bash
python scripts/init_db.py
```

Run application

```bash
python run.py
```

---

# 🔑 Demo Accounts

| Role | Email | Password |
|------|--------|----------|
| Admin | admin.demo@campushire.ai | Demo@1234 |
| TPO | tpo.demo@campushire.ai | Demo@1234 |
| Recruiter | recruiter.demo@campushire.ai | Demo@1234 |
| Student | student.demo@campushire.ai | Demo@1234 |

---

# 📈 Placement Workflow

```
Student Registration
        │
        ▼
Profile Completion
        │
        ▼
TPO Verification
        │
        ▼
Resume Upload
        │
        ▼
AI Resume Parsing
        │
        ▼
ATS Score Generation
        │
        ▼
Placement Drive Access
        │
        ▼
Application Submission
        │
        ▼
Recruiter Review
        │
        ▼
Interview Process
        │
        ▼
Offer Generation
        │
        ▼
Offer Acceptance
        │
        ▼
Placed
```

---

# 🔒 Security Features

- Password Hashing
- Role-Based Access Control
- Session Authentication
- CSRF Protection
- Audit Logging
- Resume Validation
- File Type Validation
- Recruiter Approval Workflow

---

# 📊 Future Enhancements

- AI Interview Preparation
- Resume Improvement Suggestions
- AI Chat Assistant
- Email Notifications
- SMS Notifications
- Multi-College Support
- OCR-based Resume Parsing
- Machine Learning ATS Ranking
- Video Interview Integration
- Real-time Chat
- Placement Prediction

---

# 🤝 Contributing

Contributions, feature requests, and improvements are welcome.

Please fork the repository, create a feature branch, and submit a Pull Request.

---

# 📝 Changelog

## v1.0

- Authentication System
- Student Portal
- Recruiter Portal
- TPO Portal
- Admin Portal
- AI Resume Parser
- ATS Engine
- Placement Workflow
- Notifications
- Analytics Dashboard
- Audit Logs

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Developer

**Hitesh Kumar**

AI-Powered Campus Placement Management System

Built as a production-grade DBMS & Full Stack project using Flask, PostgreSQL, SQLAlchemy, and AI-powered resume analysis.

⭐ If you found this project helpful, please consider giving it a star.
