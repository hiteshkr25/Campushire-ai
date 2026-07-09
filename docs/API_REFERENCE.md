# Endpoints Route & API Reference

This document catalogs the web routes mapped in the platform blueprints.

---

## 1. Authentication Blueprint (`/auth`)
- `GET /auth/login`: Render login portal.
- `POST /auth/login`: Validate credentials and establish session.
- `GET /auth/register`: Render student self-registration layout.
- `POST /auth/register`: Create student user credentials.
- `GET /auth/logout`: Terminate user session.
- `POST /auth/change-password`: Update password credentials.

---

## 2. Student Blueprint (`/student`)
- `GET /student/dashboard`: Student statistics, verifications, and drive listings.
- `GET /student/profile`: Review details.
- `POST /student/profile`: Modify student credentials (verified values are locked).
- `GET /student/resumes`: Review resume repository dashboard.
- `POST /student/resumes`: Upload new resume version (triggers parser).
- `GET /student/resumes/<id>/parsed`: Preview parsed AI credentials.
- `POST /student/resumes/<id>/reparse`: Force manual re-parsing.
- `POST /student/resumes/<id>/activate`: Select active resume.
- `POST /student/resumes/<id>/delete`: Remove resume.
- `GET /student/ats`: ATS matching drives roster dashboard.
- `GET /student/ats/drive/<id>`: ATS detailed match score analysis.

---

## 3. Recruiter Blueprint (`/recruiter`)
- `GET /recruiter/dashboard`: Progress funnel charts, timelines, and schedules.
- `GET /recruiter/candidates`: Candidate directory search and filtering.
- `GET /recruiter/candidates/compare`: Compare up to 3 profiles side-by-side.
- `GET /recruiter/candidates/<id>`: Detailed applicant profile review.
- `POST /recruiter/candidates/<id>/evaluate`: Submit candidate evaluation notes.
- `GET /recruiter/interviews`: Upcoming schedule calendar.
- `POST /recruiter/interviews/new`: Schedule candidate round.
- `POST /recruiter/interviews/<id>/reschedule`: Update interview logistics.
- `POST /recruiter/interviews/<id>/cancel`: Cancel interview schedule.
- `POST /recruiter/interviews/<id>/evaluate`: Grade round score.
- `GET /recruiter/drives/<id>/ats-rankings`: Candidate rankings sorted by ATS score.
- `GET /recruiter/offers`: Release dashboard.
- `POST /recruiter/offers/new`: Extend offer to selected candidate.

---

## 4. TPO Blueprint (`/tpo`)
- `GET /tpo/dashboard`: Central analytics dashboard.
- `GET /tpo/verification`: Pending student verification list.
- `GET /tpo/verification/<id>`: Review student profile and verify.
- `POST /tpo/verification/bulk`: Approve multiple selected students.
- `GET /tpo/companies`: Manage recruiters and partner profiles.
- `GET /tpo/drives`: Add and manage campaigns.
- `GET /tpo/drives/<id>/eligibility`: Candidate eligibility report.
- `GET /tpo/analytics`: Global statistics and Chart.js dashboards.
- `GET /tpo/analytics/unplaced`: List unplaced candidates.

---

## 5. System Administrator Blueprint (`/admin`)
- `GET /admin/dashboard`: Platform health logs, storage, registrations, and login charts.
- `GET /admin/users`: User roster.
- `POST /admin/users/new`: Create user accounts.
- `GET /admin/users/<id>`: Preview user profile and audit events log.
- `POST /admin/users/<id>/status/<action>`: Lock or unlock user accounts.
- `POST /admin/users/<id>/reset-password`: Override password.
- `POST /admin/users/<id>/delete`: Soft delete user account.
- `POST /admin/users/import`: CSV bulk upload.
- `GET /admin/users/export`: Export user roster.
- `GET /admin/audit-logs`: Review system events and logs.
- `GET /admin/audit-logs/export`: Export audit logs as CSV.
