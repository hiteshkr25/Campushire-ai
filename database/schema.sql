-- =============================================================================
-- CampusHire AI — PostgreSQL Schema (3NF)
-- Intelligent Campus Recruitment and Placement Management System
-- =============================================================================
-- Run order: extensions → enums → reference tables → core tables → junction tables
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "citext";     -- case-insensitive email

-- ---------------------------------------------------------------------------
-- Enumerated Types
-- ---------------------------------------------------------------------------
CREATE TYPE user_role AS ENUM (
    'student',
    'tpo',
    'recruiter',
    'admin'
);

CREATE TYPE profile_status AS ENUM (
    'incomplete',
    'pending_verification',
    'verified',
    'rejected',
    'suspended'
);

CREATE TYPE verification_status AS ENUM (
    'pending',
    'approved',
    'rejected'
);

CREATE TYPE drive_status AS ENUM (
    'draft',
    'published',
    'registration_closed',
    'ongoing',
    'completed',
    'cancelled'
);

CREATE TYPE location_type AS ENUM (
    'on_campus',
    'off_campus',
    'virtual',
    'hybrid'
);

CREATE TYPE eligibility_rule_type AS ENUM (
    'min_cgpa',
    'max_cgpa',
    'max_backlogs',
    'min_graduation_year',
    'max_graduation_year',
    'allowed_batch',
    'required_skill',
    'gender',
    'custom'
);

CREATE TYPE eligibility_operator AS ENUM (
    'eq',
    'neq',
    'gt',
    'gte',
    'lt',
    'lte',
    'in',
    'not_in',
    'contains'
);

CREATE TYPE application_status AS ENUM (
    'draft',
    'submitted',
    'under_review',
    'shortlisted',
    'rejected',
    'withdrawn',
    'interview_in_progress',
    'selected',
    'offered',
    'placed',
    'not_selected'
);

CREATE TYPE round_type AS ENUM (
    'aptitude',
    'technical',
    'coding',
    'group_discussion',
    'hr',
    'managerial',
    'other'
);

CREATE TYPE round_result_status AS ENUM (
    'scheduled',
    'passed',
    'failed',
    'on_hold',
    'absent',
    'disqualified'
);

CREATE TYPE schedule_status AS ENUM (
    'scheduled',
    'confirmed',
    'in_progress',
    'completed',
    'cancelled',
    'rescheduled',
    'no_show'
);

CREATE TYPE offer_status AS ENUM (
    'draft',
    'extended',
    'accepted',
    'declined',
    'revoked',
    'expired'
);

CREATE TYPE notification_type AS ENUM (
    'info',
    'success',
    'warning',
    'error',
    'reminder',
    'announcement'
);

CREATE TYPE announcement_audience AS ENUM (
    'all',
    'students',
    'tpo',
    'recruiters',
    'admins'
);

CREATE TYPE parse_status AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed'
);

CREATE TYPE audit_action AS ENUM (
    'create',
    'update',
    'delete',
    'login',
    'logout',
    'login_failed',
    'status_change',
    'export',
    'upload',
    'download'
);

-- ---------------------------------------------------------------------------
-- Reference Tables (required for 3NF — college / branch hierarchy)
-- ---------------------------------------------------------------------------
CREATE TABLE colleges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(20)  NOT NULL,
    name            VARCHAR(255) NOT NULL,
    university      VARCHAR(255),
    city            VARCHAR(100),
    state           VARCHAR(100),
    country         VARCHAR(100) NOT NULL DEFAULT 'India',
    contact_email   CITEXT,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_colleges_code UNIQUE (code),
    CONSTRAINT chk_colleges_code_format CHECK (code ~ '^[A-Z0-9_-]+$')
);

CREATE TABLE branches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    college_id      UUID         NOT NULL REFERENCES colleges (id) ON DELETE RESTRICT,
    code            VARCHAR(20)  NOT NULL,
    name            VARCHAR(255) NOT NULL,
    degree          VARCHAR(100),
    duration_years  SMALLINT,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_branches_college_code UNIQUE (college_id, code),
    CONSTRAINT chk_branches_duration CHECK (duration_years IS NULL OR duration_years BETWEEN 1 AND 6)
);

CREATE TABLE skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    category        VARCHAR(50),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_skills_name UNIQUE (name)
);

-- ---------------------------------------------------------------------------
-- Core Identity
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT       NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role    NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_password_hash CHECK (char_length(password_hash) >= 60)
);

-- ---------------------------------------------------------------------------
-- Module: Student
-- ---------------------------------------------------------------------------
CREATE TABLE students (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    college_id          UUID            NOT NULL REFERENCES colleges (id) ON DELETE RESTRICT,
    branch_id           UUID            NOT NULL REFERENCES branches (id) ON DELETE RESTRICT,
    enrollment_number   VARCHAR(50)     NOT NULL,
    first_name          VARCHAR(100)    NOT NULL,
    last_name           VARCHAR(100)    NOT NULL,
    phone               VARCHAR(20),
    date_of_birth       DATE,
    gender              VARCHAR(20),
    cgpa                NUMERIC(4, 2),
    graduation_year     SMALLINT        NOT NULL,
    batch               VARCHAR(20)     NOT NULL,
    semester            SMALLINT,
    backlogs_count      SMALLINT        NOT NULL DEFAULT 0,
    profile_status      profile_status  NOT NULL DEFAULT 'incomplete',
    bio                 TEXT,
    linkedin_url        VARCHAR(500),
    github_url          VARCHAR(500),
    verified_at         TIMESTAMPTZ,
    verified_by         UUID            REFERENCES users (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_students_user_id UNIQUE (user_id),
    CONSTRAINT uq_students_enrollment UNIQUE (college_id, enrollment_number),
    CONSTRAINT chk_students_cgpa CHECK (cgpa IS NULL OR (cgpa >= 0 AND cgpa <= 10)),
    CONSTRAINT chk_students_backlogs CHECK (backlogs_count >= 0),
    CONSTRAINT chk_students_semester CHECK (semester IS NULL OR semester BETWEEN 1 AND 12),
    CONSTRAINT chk_students_graduation_year CHECK (graduation_year BETWEEN 2000 AND 2100),
    CONSTRAINT chk_students_phone CHECK (phone IS NULL OR phone ~ '^[+]?[0-9]{10,15}$')
);

CREATE TABLE student_skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID         NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    skill_id        UUID         NOT NULL REFERENCES skills (id) ON DELETE RESTRICT,
    proficiency     SMALLINT     NOT NULL DEFAULT 3,
    years_experience NUMERIC(3, 1),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_student_skills UNIQUE (student_id, skill_id),
    CONSTRAINT chk_student_skills_proficiency CHECK (proficiency BETWEEN 1 AND 5),
    CONSTRAINT chk_student_skills_experience CHECK (years_experience IS NULL OR years_experience >= 0)
);

CREATE TABLE student_projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID         NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    tech_stack      TEXT,
    project_url     VARCHAR(500),
    repository_url  VARCHAR(500),
    start_date      DATE,
    end_date        DATE,
    is_ongoing      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_student_projects_dates CHECK (
        start_date IS NULL OR end_date IS NULL OR end_date >= start_date
    )
);

CREATE TABLE student_certifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID         NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    issuer          VARCHAR(255) NOT NULL,
    credential_id   VARCHAR(100),
    credential_url  VARCHAR(500),
    issue_date      DATE         NOT NULL,
    expiry_date     DATE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_student_certifications_dates CHECK (
        expiry_date IS NULL OR expiry_date >= issue_date
    )
);

CREATE TABLE resumes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID         NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(1000) NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT       NOT NULL,
    is_primary      BOOLEAN      NOT NULL DEFAULT FALSE,
    parsed_text     TEXT,
    parse_status    parse_status NOT NULL DEFAULT 'pending',
    parsed_at       TIMESTAMPTZ,
    uploaded_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_resumes_file_size CHECK (file_size_bytes > 0 AND file_size_bytes <= 10485760),
    CONSTRAINT chk_resumes_mime_type CHECK (mime_type IN (
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ))
);

-- ---------------------------------------------------------------------------
-- Module: Recruiter / HR
-- ---------------------------------------------------------------------------
CREATE TABLE companies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    legal_name          VARCHAR(255),
    website             VARCHAR(500),
    industry            VARCHAR(100),
    company_size        VARCHAR(50),
    description         TEXT,
    hq_city             VARCHAR(100),
    hq_country          VARCHAR(100) DEFAULT 'India',
    contact_email       CITEXT,
    verification_status verification_status NOT NULL DEFAULT 'pending',
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    verified_at         TIMESTAMPTZ,
    verified_by         UUID         REFERENCES users (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_companies_name UNIQUE (name)
);

CREATE TABLE recruiters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    company_id      UUID         NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    designation     VARCHAR(100),
    phone           VARCHAR(20),
    is_primary_contact BOOLEAN   NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_recruiters_user_id UNIQUE (user_id),
    CONSTRAINT chk_recruiters_phone CHECK (phone IS NULL OR phone ~ '^[+]?[0-9]{10,15}$')
);

-- ---------------------------------------------------------------------------
-- Module: PC Admin / TPO
-- ---------------------------------------------------------------------------
CREATE TABLE tpo_admins (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    college_id      UUID         NOT NULL REFERENCES colleges (id) ON DELETE RESTRICT,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    designation     VARCHAR(100),
    department      VARCHAR(100),
    phone           VARCHAR(20),
    is_primary_tpo  BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tpo_admins_user_id UNIQUE (user_id),
    CONSTRAINT chk_tpo_admins_phone CHECK (phone IS NULL OR phone ~ '^[+]?[0-9]{10,15}$')
);

-- ---------------------------------------------------------------------------
-- Placement Drives & Eligibility
-- ---------------------------------------------------------------------------
CREATE TABLE placement_drives (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id              UUID         NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    college_id              UUID         NOT NULL REFERENCES colleges (id) ON DELETE RESTRICT,
    created_by_tpo_id       UUID         NOT NULL REFERENCES tpo_admins (id) ON DELETE RESTRICT,
    title                   VARCHAR(255) NOT NULL,
    job_role                VARCHAR(255) NOT NULL,
    job_description         TEXT         NOT NULL,
    package_min_lpa         NUMERIC(8, 2),
    package_max_lpa         NUMERIC(8, 2),
    currency                CHAR(3)      NOT NULL DEFAULT 'INR',
    vacancies               INTEGER      NOT NULL DEFAULT 1,
    drive_date              DATE,
    registration_deadline   TIMESTAMPTZ,
    status                  drive_status NOT NULL DEFAULT 'draft',
    location_type           location_type NOT NULL DEFAULT 'on_campus',
    venue                   VARCHAR(255),
    meeting_link            VARCHAR(500),
    published_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_placement_drives_vacancies CHECK (vacancies > 0),
    CONSTRAINT chk_placement_drives_package CHECK (
        package_min_lpa IS NULL
        OR package_max_lpa IS NULL
        OR package_max_lpa >= package_min_lpa
    ),
    CONSTRAINT chk_placement_drives_deadline CHECK (
        registration_deadline IS NULL
        OR drive_date IS NULL
        OR registration_deadline::DATE <= drive_date
    )
);

-- Junction: placement_drives ↔ branches (eligible departments per drive)
CREATE TABLE drive_branches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drive_id        UUID         NOT NULL REFERENCES placement_drives (id) ON DELETE CASCADE,
    branch_id       UUID         NOT NULL REFERENCES branches (id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_drive_branches UNIQUE (drive_id, branch_id)
);

CREATE TABLE eligibility_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drive_id        UUID                  NOT NULL REFERENCES placement_drives (id) ON DELETE CASCADE,
    rule_type       eligibility_rule_type NOT NULL,
    operator        eligibility_operator  NOT NULL,
    rule_value      JSONB                 NOT NULL,
    is_mandatory    BOOLEAN               NOT NULL DEFAULT TRUE,
    display_order   SMALLINT              NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_eligibility_rules_value CHECK (jsonb_typeof(rule_value) IN ('string', 'number', 'array', 'boolean'))
);

-- ---------------------------------------------------------------------------
-- Applications & Interview Pipeline
-- ---------------------------------------------------------------------------
CREATE TABLE applications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID              NOT NULL REFERENCES students (id) ON DELETE RESTRICT,
    drive_id        UUID              NOT NULL REFERENCES placement_drives (id) ON DELETE RESTRICT,
    resume_id       UUID              REFERENCES resumes (id) ON DELETE SET NULL,
    status          application_status NOT NULL DEFAULT 'draft',
    cover_note      TEXT,
    applied_at      TIMESTAMPTZ,
    status_updated_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_applications_student_drive UNIQUE (student_id, drive_id)
);

CREATE TABLE interview_rounds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drive_id        UUID        NOT NULL REFERENCES placement_drives (id) ON DELETE CASCADE,
    round_number    SMALLINT    NOT NULL,
    round_name      VARCHAR(100) NOT NULL,
    round_type      round_type  NOT NULL DEFAULT 'other',
    description     TEXT,
    passing_score   NUMERIC(5, 2),
    sequence_order  SMALLINT    NOT NULL,
    is_eliminatory  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_interview_rounds_drive_number UNIQUE (drive_id, round_number),
    CONSTRAINT uq_interview_rounds_drive_sequence UNIQUE (drive_id, sequence_order),
    CONSTRAINT chk_interview_rounds_number CHECK (round_number > 0),
    CONSTRAINT chk_interview_rounds_passing_score CHECK (
        passing_score IS NULL OR (passing_score >= 0 AND passing_score <= 100)
    )
);

CREATE TABLE round_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID                NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    round_id        UUID                NOT NULL REFERENCES interview_rounds (id) ON DELETE RESTRICT,
    result_status   round_result_status NOT NULL DEFAULT 'scheduled',
    score           NUMERIC(5, 2),
    max_score       NUMERIC(5, 2)       DEFAULT 100,
    remarks         TEXT,
    evaluated_by    UUID                REFERENCES recruiters (id) ON DELETE SET NULL,
    evaluated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_round_results_application_round UNIQUE (application_id, round_id),
    CONSTRAINT chk_round_results_score CHECK (
        score IS NULL OR (score >= 0 AND (max_score IS NULL OR score <= max_score))
    )
);

CREATE TABLE interview_schedule (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID            NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    round_id        UUID            NOT NULL REFERENCES interview_rounds (id) ON DELETE RESTRICT,
    scheduled_start TIMESTAMPTZ     NOT NULL,
    scheduled_end   TIMESTAMPTZ     NOT NULL,
    venue           VARCHAR(255),
    meeting_link    VARCHAR(500),
    status          schedule_status NOT NULL DEFAULT 'scheduled',
    rescheduled_from UUID           REFERENCES interview_schedule (id) ON DELETE SET NULL,
    notified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_interview_schedule_times CHECK (scheduled_end > scheduled_start)
);

CREATE TABLE offers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID         NOT NULL REFERENCES applications (id) ON DELETE RESTRICT,
    extended_by     UUID         NOT NULL REFERENCES recruiters (id) ON DELETE RESTRICT,
    package_offered_lpa NUMERIC(8, 2) NOT NULL,
    currency        CHAR(3)      NOT NULL DEFAULT 'INR',
    job_location    VARCHAR(255),
    joining_date    DATE,
    offer_letter_path VARCHAR(1000),
    status          offer_status NOT NULL DEFAULT 'draft',
    extended_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    responded_at    TIMESTAMPTZ,
    response_note   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_offers_application_id UNIQUE (application_id),
    CONSTRAINT chk_offers_package CHECK (package_offered_lpa > 0),
    CONSTRAINT chk_offers_expiry CHECK (expires_at IS NULL OR extended_at IS NULL OR expires_at > extended_at)
);

-- ---------------------------------------------------------------------------
-- Notifications, Announcements, Audit, Analytics
-- ---------------------------------------------------------------------------
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID              NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title           VARCHAR(255)      NOT NULL,
    message         TEXT              NOT NULL,
    notification_type notification_type NOT NULL DEFAULT 'info',
    entity_type     VARCHAR(50),
    entity_id       UUID,
    action_url      VARCHAR(500),
    is_read         BOOLEAN           NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE TABLE announcements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    college_id      UUID                  REFERENCES colleges (id) ON DELETE CASCADE,
    created_by      UUID                  NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    title           VARCHAR(255)          NOT NULL,
    content         TEXT                  NOT NULL,
    target_audience announcement_audience NOT NULL DEFAULT 'all',
    is_pinned       BOOLEAN               NOT NULL DEFAULT FALSE,
    published_at    TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_announcements_expiry CHECK (expires_at IS NULL OR expires_at > published_at)
);

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         REFERENCES users (id) ON DELETE SET NULL,
    action          audit_action NOT NULL,
    entity_type     VARCHAR(50)  NOT NULL,
    entity_id       UUID,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE placement_statistics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    college_id          UUID         NOT NULL REFERENCES colleges (id) ON DELETE CASCADE,
    branch_id           UUID         REFERENCES branches (id) ON DELETE CASCADE,
    academic_year       VARCHAR(9)   NOT NULL,
    total_students      INTEGER      NOT NULL DEFAULT 0,
    eligible_students   INTEGER      NOT NULL DEFAULT 0,
    placed_students     INTEGER      NOT NULL DEFAULT 0,
    companies_visited   INTEGER      NOT NULL DEFAULT 0,
    drives_conducted    INTEGER      NOT NULL DEFAULT 0,
    highest_package_lpa NUMERIC(8, 2),
    average_package_lpa NUMERIC(8, 2),
    median_package_lpa  NUMERIC(8, 2),
    computed_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_placement_statistics UNIQUE (college_id, academic_year, branch_id),
    CONSTRAINT chk_placement_statistics_counts CHECK (
        total_students >= 0
        AND eligible_students >= 0
        AND placed_students >= 0
        AND placed_students <= eligible_students
        AND eligible_students <= total_students
    ),
    CONSTRAINT chk_placement_statistics_academic_year CHECK (
        academic_year ~ '^\d{4}-\d{4}$'
    )
);

-- ---------------------------------------------------------------------------
-- Partial Unique: only one primary resume per student
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX uq_resumes_primary_per_student
    ON resumes (student_id)
    WHERE is_primary = TRUE;

-- ---------------------------------------------------------------------------
-- Indexes — Users & Identity
-- ---------------------------------------------------------------------------
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_is_active ON users (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_users_created_at ON users (created_at DESC);

-- ---------------------------------------------------------------------------
-- Indexes — Students
-- ---------------------------------------------------------------------------
CREATE INDEX idx_students_college_id ON students (college_id);
CREATE INDEX idx_students_branch_id ON students (branch_id);
CREATE INDEX idx_students_graduation_year ON students (graduation_year);
CREATE INDEX idx_students_profile_status ON students (profile_status);
CREATE INDEX idx_students_college_batch ON students (college_id, batch);
CREATE INDEX idx_students_cgpa ON students (cgpa) WHERE cgpa IS NOT NULL;

CREATE INDEX idx_student_skills_student_id ON student_skills (student_id);
CREATE INDEX idx_student_skills_skill_id ON student_skills (skill_id);

CREATE INDEX idx_student_projects_student_id ON student_projects (student_id);
CREATE INDEX idx_student_certifications_student_id ON student_certifications (student_id);
CREATE INDEX idx_resumes_student_id ON resumes (student_id);
CREATE INDEX idx_resumes_parse_status ON resumes (parse_status) WHERE parse_status IN ('pending', 'processing');

-- ---------------------------------------------------------------------------
-- Indexes — Companies & Recruiters
-- ---------------------------------------------------------------------------
CREATE INDEX idx_companies_verification_status ON companies (verification_status);
CREATE INDEX idx_companies_is_active ON companies (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_recruiters_company_id ON recruiters (company_id);

-- ---------------------------------------------------------------------------
-- Indexes — TPO & Drives
-- ---------------------------------------------------------------------------
CREATE INDEX idx_tpo_admins_college_id ON tpo_admins (college_id);

CREATE INDEX idx_placement_drives_company_id ON placement_drives (company_id);
CREATE INDEX idx_placement_drives_college_id ON placement_drives (college_id);
CREATE INDEX idx_placement_drives_status ON placement_drives (status);
CREATE INDEX idx_placement_drives_college_status ON placement_drives (college_id, status);
CREATE INDEX idx_placement_drives_registration_deadline ON placement_drives (registration_deadline)
    WHERE status IN ('published', 'registration_closed');

CREATE INDEX idx_drive_branches_drive_id ON drive_branches (drive_id);
CREATE INDEX idx_drive_branches_branch_id ON drive_branches (branch_id);

CREATE INDEX idx_eligibility_rules_drive_id ON eligibility_rules (drive_id);

-- ---------------------------------------------------------------------------
-- Indexes — Applications & Interviews
-- ---------------------------------------------------------------------------
CREATE INDEX idx_applications_student_id ON applications (student_id);
CREATE INDEX idx_applications_drive_id ON applications (drive_id);
CREATE INDEX idx_applications_status ON applications (status);
CREATE INDEX idx_applications_drive_status ON applications (drive_id, status);
CREATE INDEX idx_applications_applied_at ON applications (applied_at DESC);

CREATE INDEX idx_interview_rounds_drive_id ON interview_rounds (drive_id);

CREATE INDEX idx_round_results_application_id ON round_results (application_id);
CREATE INDEX idx_round_results_round_id ON round_results (round_id);
CREATE INDEX idx_round_results_status ON round_results (result_status);

CREATE INDEX idx_interview_schedule_application_id ON interview_schedule (application_id);
CREATE INDEX idx_interview_schedule_round_id ON interview_schedule (round_id);
CREATE INDEX idx_interview_schedule_start ON interview_schedule (scheduled_start);
CREATE INDEX idx_interview_schedule_status ON interview_schedule (status);

CREATE INDEX idx_offers_status ON offers (status);
CREATE INDEX idx_offers_application_id ON offers (application_id);

-- ---------------------------------------------------------------------------
-- Indexes — Notifications, Announcements, Audit, Stats
-- ---------------------------------------------------------------------------
CREATE INDEX idx_notifications_user_id ON notifications (user_id);
CREATE INDEX idx_notifications_user_unread ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX idx_announcements_college_id ON announcements (college_id);
CREATE INDEX idx_announcements_published_at ON announcements (published_at DESC);
CREATE INDEX idx_announcements_audience ON announcements (target_audience);

CREATE INDEX idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);

CREATE INDEX idx_placement_statistics_college_year ON placement_statistics (college_id, academic_year);

-- ---------------------------------------------------------------------------
-- JSONB GIN index for eligibility rule queries
-- ---------------------------------------------------------------------------
CREATE INDEX idx_eligibility_rules_value_gin ON eligibility_rules USING GIN (rule_value);

-- ---------------------------------------------------------------------------
-- updated_at trigger function (reusable)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_colleges_updated_at
    BEFORE UPDATE ON colleges FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_branches_updated_at
    BEFORE UPDATE ON branches FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_students_updated_at
    BEFORE UPDATE ON students FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_student_skills_updated_at
    BEFORE UPDATE ON student_skills FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_student_projects_updated_at
    BEFORE UPDATE ON student_projects FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_student_certifications_updated_at
    BEFORE UPDATE ON student_certifications FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_resumes_updated_at
    BEFORE UPDATE ON resumes FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_companies_updated_at
    BEFORE UPDATE ON companies FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_recruiters_updated_at
    BEFORE UPDATE ON recruiters FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_tpo_admins_updated_at
    BEFORE UPDATE ON tpo_admins FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_placement_drives_updated_at
    BEFORE UPDATE ON placement_drives FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_eligibility_rules_updated_at
    BEFORE UPDATE ON eligibility_rules FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_interview_rounds_updated_at
    BEFORE UPDATE ON interview_rounds FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_round_results_updated_at
    BEFORE UPDATE ON round_results FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_interview_schedule_updated_at
    BEFORE UPDATE ON interview_schedule FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_offers_updated_at
    BEFORE UPDATE ON offers FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_announcements_updated_at
    BEFORE UPDATE ON announcements FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER trg_placement_statistics_updated_at
    BEFORE UPDATE ON placement_statistics FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

COMMIT;
