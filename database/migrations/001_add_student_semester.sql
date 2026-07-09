-- Add semester support for student profile management.
-- Safe to run after the base schema has already been applied.

ALTER TABLE students
    ADD COLUMN IF NOT EXISTS semester SMALLINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_students_semester'
    ) THEN
        ALTER TABLE students
            ADD CONSTRAINT chk_students_semester
            CHECK (semester IS NULL OR semester BETWEEN 1 AND 12);
    END IF;
END $$;
