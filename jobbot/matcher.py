# matcher.py
import re

SENIOR_KEYWORDS = ["senior", "sr.", "lead", "principal", "staff", "manager", "architect"]
JUNIOR_KEYWORDS = ["intern", "junior", "jr.", "trainee", "fresher", "entry"]

SKILL_KEYWORDS = {
    "azure": 20,
    "databricks": 18,
    "data factory": 16,
    "synapse": 14,
    "delta lake": 12,
    "pyspark": 14,
    "spark": 12,
    "python": 8,
    "sql": 8,
    "etl": 8,
    "ci/cd": 4,
    "lakehouse": 6
}

TITLE_BONUS = 40   # exact 'data engineer' in title
SENIOR_BONUS = 25  # senior-level titles get boost
LOCATION_BONUS = 20 # Hyderabad preferred
SPONSOR_BONUS = 20  # if job mentions sponsor/visa/relocation

def score_job(job, user_years=5):
    text = (job.get("title","") + " " + job.get("snippet","") + " " + job.get("company","")).lower()
    score = 0
    matched = []

    # Title exact match boost
    if re.search(r"\bdata engineer\b", job.get("title","").lower()):
        score += TITLE_BONUS
        matched.append("title:data engineer")

    # Seniority
    if any(k in text for k in SENIOR_KEYWORDS):
        score += SENIOR_BONUS
        matched.append("seniority:senior")
    if any(k in text for k in JUNIOR_KEYWORDS):
        score -= 30  # avoid juniors
        matched.append("seniority:junior")

    # Skills
    for k, w in SKILL_KEYWORDS.items():
        if k in text:
            score += w
            matched.append(k)

    # Location preference
    if "hyderabad" in text or "hyderabad" in (job.get("location","") or "").lower():
        score += LOCATION_BONUS
        matched.append("location:hyderabad")

    # Visa / sponsorship detectable
    if any(x in text for x in ("visa", "sponsor", "sponsorship", "relocation")):
        score += SPONSOR_BONUS
        matched.append("visa")

    # Prefer product company domains (optional): bump if company string contains product names
    # e.g., you can maintain a list of product domains and check here (left out for speed)

    # small base: presence of any word 'data' or 'engineer'
    if "data" in text or "engineer" in text:
        score += 2

    # Attach score and matched keywords to job object for later usage
    job["score"] = int(score)
    job["matched_keywords"] = matched
    return job
