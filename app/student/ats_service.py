import json
import re

from app.models import Resume, PlacementDrive, Student
from app.models.enums import EligibilityRuleType, ParseStatus
# Single source of truth for skills — defined in resume_parser
from app.student.resume_parser import SKILLS_POOL


class AtsService:
    SKILLS_POOL = SKILLS_POOL  # kept for any external callers

    EDU_KEYWORDS = [
        "b.tech", "btech", "b.e.", "m.tech", "mtech", "b.sc", "m.sc", "bca", "mca", "mba", "ph.d", "phd",
        "bachelor", "master", "university", "college", "institute", "school"
    ]

    @classmethod
    def _primary_or_latest_resume(cls, student, resumes=None):
        if resumes is not None:
            # Filter in Python memory to avoid SQL query
            prim = next((r for r in resumes if r.is_primary), None)
            if prim:
                return prim
            # Sort by uploaded_at desc or created_at desc
            sorted_resumes = sorted(
                resumes,
                key=lambda r: (r.uploaded_at or r.created_at or datetime.min, r.created_at or datetime.min),
                reverse=True
            )
            return sorted_resumes[0] if sorted_resumes else None

        resume = Resume.query.filter_by(student_id=student.id, is_primary=True).first()
        if not resume:
            resume = student.resumes.order_by(Resume.uploaded_at.desc(), Resume.created_at.desc()).first()
        return resume

    @classmethod
    def calculate_dashboard_score(cls, student, resume=None):
        if not resume:
            resume = cls._primary_or_latest_resume(student)

        if not resume:
            return {
                "score": 0,
                "status": "Not Available",
                "message": "Upload a resume to generate ATS insights.",
            }

        if not resume.parsed_text or resume.parse_status != ParseStatus.COMPLETED:
            return {
                "score": 0,
                "status": "Processing",
                "message": "Resume parsing in progress.",
            }

        try:
            parsed_envelope = json.loads(resume.parsed_text)
            structured_data = parsed_envelope.get("structured_data", {})
        except Exception:
            structured_data = {}

        resume_skills = structured_data.get("skills", [])
        projects_count = len(structured_data.get("projects", []))
        certs_count = len(structured_data.get("certifications", []))
        exp_count = len(structured_data.get("experience", []))

        skills_score = min(40.0, (len(resume_skills) / 5.0) * 40.0)
        projects_score = min(20.0, projects_count * 10.0)

        student_cgpa = float(student.cgpa) if student.cgpa is not None else 0.0
        if student_cgpa >= 9.0:
            cgpa_score = 20.0
        elif student_cgpa >= 8.0:
            cgpa_score = 18.0
        elif student_cgpa >= 7.0:
            cgpa_score = 15.0
        elif student_cgpa >= 6.0:
            cgpa_score = 10.0
        else:
            cgpa_score = 5.0

        cert_score = min(10.0, certs_count * 5.0)
        exp_score = min(10.0, exp_count * 5.0)

        final_score = max(0, min(100, round(skills_score + projects_score + cgpa_score + cert_score + exp_score)))

        if final_score >= 75:
            status = "Excellent"
            message = "Strong ATS readiness — your resume aligns well with software roles."
        elif final_score >= 50:
            status = "Good"
            message = "Solid profile. Add more projects or certifications to improve your score."
        elif final_score > 0:
            status = "Needs Work"
            message = "Strengthen your resume by adding skills, projects, and certifications."
        else:
            status = "Low"
            message = "Complete your profile and add resume content to improve your score."

        return {
            "score": final_score,
            "status": status,
            "message": message,
        }

    @classmethod
    def build_dashboard_checklist(cls, student, profile_completion, resume=None, checklist_data=None):
        if not resume:
            resume = cls._primary_or_latest_resume(student)
        has_resume = resume is not None
        has_parsed = (
            has_resume and
            bool(resume.parsed_text) and
            resume.parse_status == ParseStatus.COMPLETED
        )

        education_found = False
        if has_parsed:
            try:
                data = json.loads(resume.parsed_text)
                education_found = len(data.get("structured_data", {}).get("education", [])) > 0
            except Exception:
                pass
        if not education_found:
            education_found = bool(student.cgpa is not None and student.graduation_year)

        if checklist_data:
            has_skills = checklist_data.get("skills", False)
            has_projects = checklist_data.get("projects", False)
        else:
            has_skills = student.skills.count() > 0
            has_projects = student.projects.count() > 0

        return [
            {"label": "Resume Uploaded", "done": has_resume},
            {"label": "Resume Parsed", "done": has_parsed},
            {"label": "Skills Added", "done": has_skills},
            {"label": "Projects Added", "done": has_projects},
            {"label": "Education Added", "done": education_found},
            {"label": "Profile Completed", "done": profile_completion >= 40},
        ]

    @classmethod
    def calculate_ats_score(cls, student, drive, resume=None, drive_rules=None, student_skills=None, **kwargs):
        if not resume:
            resume = cls._primary_or_latest_resume(student)
        if not resume or not resume.parsed_text:
            return {
                "score": 0,
                "breakdown": {
                    "skills": 0,
                    "projects": 0,
                    "cgpa": 0,
                    "certifications": 0,
                    "experience": 0,
                    "similarity": 0
                },
                "missing_skills": [],
                "skill_gap": [],
                "strengths": [],
                "weaknesses": ["No primary resume found."],
                "suggestions": ["Upload a primary resume."],
                "similarity_explanation": "Could not calculate text similarity due to missing resume.",
                "candidate_recommendation": "No recommendation: missing active resume credentials.",
                "match_confidence": "Low"
            }

        parsed_envelope = kwargs.get("parsed_envelope")
        if parsed_envelope is not None:
            structured_data = parsed_envelope.get("structured_data", {})
            raw_resume_text = parsed_envelope.get("raw_text", "")
        else:
            try:
                parsed_envelope = json.loads(resume.parsed_text)
                structured_data = parsed_envelope.get("structured_data", {})
                raw_resume_text = parsed_envelope.get("raw_text", "")
            except Exception:
                structured_data = {}
                raw_resume_text = ""

        resume_skills = [s.lower().strip() for s in structured_data.get("skills", [])]
        projects_count = len(structured_data.get("projects", []))
        certs_count = len(structured_data.get("certifications", []))
        exp_count = len(structured_data.get("experience", []))

        if drive_rules is None:
            drive_rules = drive.eligibility_rules.all()
        required_skills = []
        min_cgpa_val = 0.0

        for rule in drive_rules:
            if rule.rule_type == EligibilityRuleType.REQUIRED_SKILL and rule.rule_value:
                vals = rule.rule_value if isinstance(rule.rule_value, list) else rule.rule_value.get("value", [])
                required_skills = [s.lower().strip() for s in vals]
            elif rule.rule_type == EligibilityRuleType.MIN_CGPA and rule.rule_value:
                try:
                    min_cgpa_val = float(rule.rule_value)
                except (ValueError, TypeError):
                    pass

        strengths = []
        weaknesses = []
        suggestions = []

        skills_score = 0.0
        missing_skills = []
        if required_skills:
            matched_skills = [s for s in required_skills if s in resume_skills]
            missing_skills = [s.title() for s in required_skills if s not in resume_skills]
            match_ratio = len(matched_skills) / len(required_skills)
            skills_score = match_ratio * 40.0

            if match_ratio >= 0.75:
                strengths.append("High alignment with drive's core technical skills.")
            else:
                weaknesses.append("Missing critical skills requested by the recruiter.")
                suggestions.append(f"Add missing keywords to your resume: {', '.join(missing_skills[:3])}")
        else:
            count = len(resume_skills)
            skills_score = min(40.0, (count / 5.0) * 40.0)
            if count >= 6:
                strengths.append("Broad technical skills repository listed.")
            else:
                suggestions.append("Expand your skills list to cover a wider tool stack.")

        projects_score = min(20.0, projects_count * 10.0)
        if projects_count >= 2:
            strengths.append("Good project portfolio showcasing hands-on experience.")
        else:
            weaknesses.append("Thin project representation.")
            suggestions.append("Add at least 2 detailed projects showing coding implementation.")

        cgpa_score = 0.0
        student_cgpa = float(student.cgpa) if student.cgpa is not None else 0.0
        if min_cgpa_val > 0.0:
            if student_cgpa >= min_cgpa_val:
                cgpa_score = 20.0
                strengths.append("Exceeds the minimum CGPA eligibility cut-off.")
            else:
                shortfall = min_cgpa_val - student_cgpa
                cgpa_score = max(0.0, 20.0 - (shortfall * 10.0))
                weaknesses.append(f"CGPA is below preferred target of {min_cgpa_val}.")
        else:
            if student_cgpa >= 9.0:
                cgpa_score = 20.0
                strengths.append("Excellent academic standing (CGPA > 9.0).")
            elif student_cgpa >= 8.0:
                cgpa_score = 18.0
            elif student_cgpa >= 7.0:
                cgpa_score = 15.0
            elif student_cgpa >= 6.0:
                cgpa_score = 10.0
            else:
                cgpa_score = 5.0
                suggestions.append("Academic record requires attention. Focus on projects to offset low CGPA.")

        cert_score = min(10.0, certs_count * 5.0)
        if certs_count >= 2:
            strengths.append("Professional credentials and external certifications present.")
        else:
            suggestions.append("Acquire domain-specific certifications to boost credentials.")

        exp_score = min(10.0, exp_count * 5.0)
        if exp_count >= 1:
            strengths.append("Prior professional work experience or internship listed.")
        else:
            weaknesses.append("Lack of professional corporate exposure.")
            suggestions.append("Look for virtual internships or freelance work to record active experience.")

        similarity_score = 0.0
        job_description = f"{drive.title} {drive.job_role} {drive.job_description or ''}"
        overlapping_terms = []

        # Construct structured resume text from parsed JSON data for TF-IDF similarity
        structured_resume_parts = []
        if structured_data.get("name"):
            structured_resume_parts.append(structured_data["name"])
        if structured_data.get("skills"):
            structured_resume_parts.append("Skills: " + ", ".join(structured_data["skills"]))
        for edu in structured_data.get("education", []):
            if edu.get("raw"):
                structured_resume_parts.append("Education: " + edu["raw"])
        for exp in structured_data.get("experience", []):
            exp_text = f"Experience: {exp.get('role', '')} at {exp.get('company', '')}."
            if exp.get("description"):
                exp_text += " " + " ".join(exp["description"])
            structured_resume_parts.append(exp_text)
        for proj in structured_data.get("projects", []):
            proj_text = f"Project: {proj.get('title', '')}."
            if proj.get("technologies"):
                proj_text += " Tech: " + ", ".join(proj["technologies"])
            if proj.get("description"):
                proj_text += " " + proj["description"]
            structured_resume_parts.append(proj_text)
        for cert in structured_data.get("certifications", []):
            structured_resume_parts.append("Certification: " + cert)
        for ach in structured_data.get("achievements", []):
            structured_resume_parts.append("Achievement: " + ach)
        for lang in structured_data.get("languages", []):
            structured_resume_parts.append("Language: " + lang)
            
        clean_resume_text = " ".join(structured_resume_parts)

        if job_description.strip() and clean_resume_text.strip():
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                
                vectorizer = TfidfVectorizer(stop_words='english')
                tfidf = vectorizer.fit_transform([job_description, clean_resume_text])
                sim = cosine_similarity(tfidf[0:1], tfidf[1:2])
                similarity_score = float(sim[0][0]) * 100.0

                words = vectorizer.get_feature_names_out()
                row0 = tfidf[0].toarray()[0]
                row1 = tfidf[1].toarray()[0]
                common = []
                for idx, w in enumerate(words):
                    if row0[idx] > 0 and row1[idx] > 0 and len(w) > 3:
                        common.append(w)
                overlapping_terms = common[:6]
            except Exception:
                similarity_score = 50.0
        else:
            similarity_score = 50.0

        if similarity_score >= 45.0:
            strengths.append("Strong textual context similarity with the job description.")
        else:
            suggestions.append("Align your resume vocabulary with the job description keywords.")

        rule_score = skills_score + projects_score + cgpa_score + cert_score + exp_score
        final_score = round((rule_score * 0.75) + (similarity_score * 0.25))
        final_score = max(0, min(100, final_score))

        skill_gap = missing_skills

        if overlapping_terms:
            similarity_explanation = f"Matched vocab overlap on keyword terms: {', '.join(overlapping_terms)}"
        else:
            similarity_explanation = "Low direct term overlaps. Make sure core tool vocab is present."

        if final_score >= 75:
            match_confidence = "High"
            candidate_recommendation = "Highly Recommended: Candidate matches core skills and has strong credentials."
        elif final_score >= 50:
            match_confidence = "Medium"
            candidate_recommendation = "Potential Fit: Good core background, but has minor skill gaps. Review project portfolio."
        else:
            match_confidence = "Low"
            candidate_recommendation = "Not Recommended: Significant skill gaps or academic/experience misalignment."

        return {
            "score": final_score,
            "breakdown": {
                "skills": round(skills_score, 1),
                "projects": round(projects_score, 1),
                "cgpa": round(cgpa_score, 1),
                "certifications": round(cert_score, 1),
                "experience": round(exp_score, 1),
                "similarity": round(similarity_score, 1)
            },
            "missing_skills": missing_skills,
            "skill_gap": skill_gap,
            "strengths": list(set(strengths))[:3],
            "weaknesses": list(set(weaknesses))[:3],
            "suggestions": list(set(suggestions))[:4],
            "similarity_explanation": similarity_explanation,
            "candidate_recommendation": candidate_recommendation,
            "match_confidence": match_confidence
        }
