# Database Schema Reference

This document maps all the primary entities, columns, relationships, and tables of the CampusHire AI PostgreSQL database.

## Entities Relationship Diagram (Summary)
- `users` (Central Identity Model)
  - `students` (1-to-1)
  - `recruiters` (1-to-1)
  - `tpo_admins` (1-to-1)
- `companies`
  - `recruiters` (1-to-many)
  - `placement_drives` (1-to-many)
- `colleges`
  - `branches` (1-to-many)
  - `students` (1-to-many)
  - `tpo_admins` (1-to-many)
  - `placement_drives` (1-to-many)
- `placement_drives`
  - `eligibility_rules` (1-to-many)
  - `interview_rounds` (1-to-many)
  - `applications` (1-to-many)
- `applications`
  - `interview_schedules` (1-to-many)
  - `round_results` (1-to-many)
  - `offers` (1-to-1)

---

## Tables Directory

### 1. `users`
Represents the credentials and authentication profile.
- `id` (UUID, Primary Key)
- `email` (String(255), Unique, Indexed)
- `password_hash` (String(255))
- `role` (Enum: student, recruiter, tpo, admin)
- `is_active` (Boolean, Default True)
- `is_verified` (Boolean, Default False)
- `last_login_at` (DateTime)
- `created_at` (DateTime, Default Now)

### 2. `students`
Profile metadata for student users.
- `id` (UUID, Primary Key)
- `user_id` (UUID, ForeignKey to `users.id`)
- `college_id` (UUID, ForeignKey to `colleges.id`)
- `branch_id` (UUID, ForeignKey to `branches.id`)
- `enrollment_number` (String(100), Unique)
- `first_name` (String(100))
- `last_name` (String(100))
- `cgpa` (Numeric(4,2))
- `backlogs_count` (Integer)
- `batch` (String(50))
- `graduation_year` (Integer)
- `phone` (String(20))
- `profile_status` (Enum: incomplete, pending_verification, verified, rejected)

### 3. `recruiters`
Profile details for company recruiters.
- `id` (UUID, Primary Key)
- `user_id` (UUID, ForeignKey to `users.id`)
- `company_id` (UUID, ForeignKey to `companies.id`)
- `first_name` (String(100))
- `last_name` (String(100))
- `designation` (String(100))
- `phone` (String(20))
- `is_active` (Boolean, Default True)

### 4. `tpo_admins`
Profile details for Training & Placement Officers.
- `id` (UUID, Primary Key)
- `user_id` (UUID, ForeignKey to `users.id`)
- `college_id` (UUID, ForeignKey to `colleges.id`)
- `first_name` (String(100))
- `last_name` (String(100))
- `designation` (String(100))
- `department` (String(100))
- `phone` (String(20))
- `is_active` (Boolean, Default True)
- `is_primary_tpo` (Boolean, Default False)

### 5. `companies`
Registered company partners.
- `id` (UUID, Primary Key)
- `name` (String(255), Unique)
- `website_url` (String(255))
- `contact_email` (String(255))
- `verification_status` (Enum: pending, verified, rejected)
- `logo_path` (String(1000))
- `is_active` (Boolean, Default True)

### 6. `colleges`
Affiliated educational campuses.
- `id` (UUID, Primary Key)
- `name` (String(255), Unique)
- `code` (String(50), Unique)
- `is_active` (Boolean, Default True)

### 7. `branches`
Academic courses/departments inside colleges.
- `id` (UUID, Primary Key)
- `college_id` (UUID, ForeignKey to `colleges.id`)
- `name` (String(255))
- `code` (String(50))
- `is_active` (Boolean, Default True)

### 8. `placement_drives`
Campaign entries for corporate recruitment.
- `id` (UUID, Primary Key)
- `company_id` (UUID, ForeignKey to `companies.id`)
- `college_id` (UUID, ForeignKey to `colleges.id`)
- `title` (String(255))
- `job_role` (String(255))
- `job_description` (Text)
- `package_lpa` (Numeric(10,2))
- `location` (String(255))
- `location_type` (Enum: on_site, remote, hybrid)
- `status` (Enum: draft, published, registration_closed, ongoing, completed, cancelled)
- `created_at` (DateTime, Default Now)

### 9. `eligibility_rules`
Target restrictions mapped to placement drives.
- `id` (UUID, Primary Key)
- `drive_id` (UUID, ForeignKey to `placement_drives.id`)
- `rule_type` (Enum: min_cgpa, max_backlogs, required_skill, allowed_batch)
- `rule_value` (JSON)
- `is_mandatory` (Boolean, Default True)

### 10. `applications`
Placement requests submitted by students.
- `id` (UUID, Primary Key)
- `student_id` (UUID, ForeignKey to `students.id`)
- `drive_id` (UUID, ForeignKey to `placement_drives.id`)
- `resume_id` (UUID, ForeignKey to `resumes.id`)
- `status` (Enum: submitted, under_review, shortlisted, interview_in_progress, selected, offered, placed, rejected, withdrawn)
- `status_updated_at` (DateTime)
- `remarks` (Text)
- `created_at` (DateTime, Default Now)

### 11. `interview_rounds`
Workflow steps defined for campaigns.
- `id` (UUID, Primary Key)
- `drive_id` (UUID, ForeignKey to `placement_drives.id`)
- `round_name` (String(100))
- `round_type` (Enum: aptitude, coding, technical, hr, managerial)
- `sequence_order` (Integer)

### 12. `interview_schedules`
Timeline allocations for candidate rounds.
- `id` (UUID, Primary Key)
- `application_id` (UUID, ForeignKey to `applications.id`)
- `round_id` (UUID, ForeignKey to `interview_rounds.id`)
- `scheduled_start` (DateTime)
- `scheduled_end` (DateTime)
- `venue` (String(255))
- `meeting_link` (String(500))
- `status` (Enum: scheduled, completed, cancelled, rescheduled, no_show)
- `created_at` (DateTime, Default Now)

### 13. `round_results`
Evaluations outputs graded by recruiters.
- `id` (UUID, Primary Key)
- `application_id` (UUID, ForeignKey to `applications.id`)
- `round_id` (UUID, ForeignKey to `interview_rounds.id`)
- `score` (Numeric(5,2))
- `result_status` (Enum: passed, failed, on_hold, absent)
- `remarks` (Text)
- `evaluated_by` (UUID, ForeignKey to `users.id`)
- `evaluated_at` (DateTime)

### 14. `offers`
Extended package details.
- `id` (UUID, Primary Key)
- `application_id` (UUID, ForeignKey to `applications.id`)
- `extended_by` (UUID, ForeignKey to `recruiters.id`)
- `package_offered_lpa` (Numeric(10,2))
- `job_location` (String(255))
- `joining_date` (Date)
- `expires_at` (DateTime)
- `status` (Enum: extended, accepted, declined, expired, revoked)
- `offer_letter_path` (String(1000))
- `response_note` (Text)
- `extended_at` (DateTime, Default Now)
- `responded_at` (DateTime)

### 15. `audit_logs`
Track mutation events inside the platform.
- `id` (UUID, Primary Key)
- `user_id` (UUID, ForeignKey to `users.id`)
- `action` (Enum: create, update, delete, login, logout, login_failed, status_change, export, upload, download)
- `entity_type` (String(100))
- `entity_id` (UUID)
- `old_values` (JSON)
- `new_values` (JSON)
- `ip_address` (String(45))
- `user_agent` (String(255))
- `created_at` (DateTime, Default Now)

### 16. `notifications`
System alerts pushed to users.
- `id` (UUID, Primary Key)
- `user_id` (UUID, ForeignKey to `users.id`)
- `title` (String(255))
- `message` (Text)
- `notification_type` (Enum: info, success, warning, error)
- `is_read` (Boolean, Default False)
- `entity_type` (String(100))
- `entity_id` (UUID)
- `created_at` (DateTime, Default Now)
