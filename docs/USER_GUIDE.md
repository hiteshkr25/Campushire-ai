# Platform Workflows User Guide

This user guide describes workflows for the different user roles on the CampusHire AI platform.

---

## 1. Student Workflows

### Upload and Verify Resumes
1. Log in to the Student Portal.
2. Select **Resumes** from the left navigation sidebar.
3. Drag-and-drop or select your PDF resume file in the upload zone. Check the "Set as primary active resume" box and click **Upload & Parse Resume**.
4. Once the upload finishes, the resume appears in the version history table with a green **Parsed** status.
5. Click **Parsed Data** to review the extracted technical skills, education history, and experience fields.
6. The panel highlights a **Confidence Score** and lists **Missing Information Alerts** (e.g. "Missing LinkedIn Link").
7. Adjust your resume file based on the feedback and upload a new version to optimize your matching score.

### Evaluate ATS Match
1. Go to the **ATS Rank Match** section in the sidebar.
2. The dashboard displays all active hiring drives alongside your matching percentages.
3. Click **Breakdown details** next to any drive.
4. Review the breakdown card showing the scoring weights (Skills 40%, Projects 20%, CGPA 20%, Certifications 10%, Experience 10%) and the TF-IDF Vector cosine match explanation.
5. Make adjustments suggested in the **Actionable Improvement Suggestions** (e.g., adding specific skills keywords) to increase your matching score.

---

## 2. Recruiter Workflows

### Search, Filter, and Compare Candidates
1. Log in to the Recruiter Portal.
2. Navigate to **Candidates** in the sidebar.
3. Use the filter controls to search by branch, CGPA standings, backlog counts, or drive.
4. Check the select boxes next to any 2 or 3 candidates in the table.
5. Click the **Compare Selected** button in the actions header.
6. Review the comparison grid, which highlights match confidence, ATS recommendations, skill gaps, and keyword similarity overlap side-by-side.

### Schedule and Grade Interviews
1. Navigate to **Drive Pipeline** in the sidebar.
2. Click **Schedule Evaluation** at the top.
3. Select the candidate, placement drive, target round, scheduled date, and provide a meeting link or venue details.
4. Once the interview is complete, click **Evaluate** next to the entry.
5. Input the evaluation score, select the outcome status (`Passed`, `Failed`, or `On Hold`), add notes, and click **Save Evaluation**.

---

## 3. Training & Placement Officer (TPO) Workflows

### Verify Student Profiles
1. Log in to the TPO Portal.
2. Select **Verification** in the sidebar.
3. Review the pending student registrations list. Click **Review** next to any candidate.
4. Verify the student's CGPA, active backlogs, enrollment number, and graduation year against the official database registry.
5. Click **Approve Profile** (which locks academic editing fields for the student) or **Reject Profile** (with remarks to prompt fixes).

### Manage Drives & Verify Eligibility
1. Select **Placement Drives** from the sidebar.
2. Click **Create New Drive**. Configure details, add target branches, and specify eligibility rules.
3. Once created, click **Eligibility Report** on the drive details page.
4. The system validates all students against the rules and resume presence.
5. Click **Export Eligibility (CSV)** to download the spreadsheet of eligible candidates.

---

## 4. System Administrator Workflows

### User Administration
1. Log in to the Admin Portal using `admin@campushire.ai`.
2. Go to **Users** in the sidebar.
3. Use the search input to filter users by email or name.
4. Click the lock/unlock icons to toggle account access status.
5. Select **Preview** to review credentials details and specific activity history.

### Bulk Imports
1. Click **Bulk Import** on the users list.
2. Download or copy the CSV template guidelines.
3. Upload a roster CSV to create multiple student, recruiter, or TPO accounts at once.
