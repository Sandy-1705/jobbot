# run_cycle.py
import os
import re
import yaml
import time
from fetchers import fetch_indeed, fetch_company_jobs
from matcher import score_job
from tailor_resume import generate_tailored_copy
from emailer import send_email

# Load config
CFG_PATH = "jobbot/config.yaml"
cfg = yaml.safe_load(open(CFG_PATH, "r", encoding="utf-8"))

def load_company_pages():
    try:
        with open("jobbot/company_list.txt", "r", encoding="utf-8") as f:
            pages = []
            for line in f:
                s = line.strip()
                if not s:
                    continue
                # skip comment lines that start with '#'
                if s.startswith("#"):
                    continue
                pages.append(s)
            return pages
    except FileNotFoundError:
        return []


def safe_jobs_deduplicate(jobs):
    seen = set()
    out = []
    for j in jobs:
        key = (j.get("title","").lower(), j.get("company","").lower(), j.get("link",""))
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out

def looks_like_azure_data(text):
    """
    Mandatory relevance: must be Azure + data/engineer OR the phrase 'data engineer'
    """
    text = (text or "").lower()
    if "data engineer" in text:
        return True
    if "azure" in text and ("data" in text or "engineer" in text):
        return True
    return False

def contains_junior_marker(text):
    return any(w in text for w in ("intern", "junior", "jr.", "trainee", "fresher", "entry"))

def parse_years(text):
    """
    Attempt to parse an integer number of years from text like '5+ years', '3 years', '6 yrs'
    Returns integer or None.
    """
    if not text:
        return None
    m = re.search(r'(\d{1,2})\+?\s*(?:years|yrs|year)', text.lower())
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None

def main_once():
    all_jobs = []

    # 1) Indeed (Hyderabad focus)
    try:
        all_jobs += fetch_indeed(query="Azure Data Engineer", location="Hyderabad")
    except Exception as e:
        print("Indeed fetch failed:", e)

    # 2) company career pages
    for url in load_company_pages():
        try:
            all_jobs += fetch_company_jobs(url)
            time.sleep(1)  # polite pause
        except Exception as e:
            print("Company fetch failed for", url, e)

    # deduplicate
    all_jobs = safe_jobs_deduplicate(all_jobs)

    # score jobs
    scored = [score_job(j) for j in all_jobs]

    # final configured threshold
    threshold = cfg.get("score_threshold", 30)

    # env SMTP from GitHub Secrets or local env
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        print("SMTP_USER and SMTP_PASS environment variables not found. Exiting without sending emails.")
        return

    sent_count = 0
    for job in scored:
        try:
            # normalize combined text for quick checks
            combined_text = " ".join([
                job.get("title","") or "",
                job.get("snippet","") or "",
                job.get("company","") or "",
                job.get("location","") or ""
            ]).lower()

            # 1) Mandatory Azure + data relevance
            if not looks_like_azure_data(combined_text):
                print("Skipping (not azure+data):", job.get("title"), job.get("company"))
                continue

            # 2) Reject obvious junior roles
            if contains_junior_marker(combined_text):
                print("Skipping junior role:", job.get("title"), job.get("company"))
                continue

            # 3) If job states explicit years and < 5, skip
            years = parse_years(combined_text)
            if years is not None and years < 5:
                print("Skipping due to experience < 5 years:", years, job.get("title"), job.get("company"))
                continue

            # 4) Final score gate (use configured threshold)
            if job.get("score", 0) < threshold:
                print("Skipping low score:", job.get("score"), job.get("title"))
                continue

            # Passed all gates -> create tailored resume + email
            text_resume, pdf_path = generate_tailored_copy(job)

            subject = f"[JobBot] {job.get('title','')} @ {job.get('company','')}  Score:{job.get('score',0)}"
            body = (
                f"Role: {job.get('title','')}\n"
                f"Company: {job.get('company','')}\n"
                f"Link: {job.get('link','')}\n\n"
                f"Match Score: {job.get('score',0)}\n\n"
                f"Tailored Resume (text summary):\n\n{text_resume}\n"
            )
            send_email(smtp_user, smtp_pass, cfg.get("email"), subject, body, attachments=[pdf_path])
            sent_count += 1
            print("Emailed job:", job.get("title"), job.get("company"), " score:", job.get("score",0))
            # small pause so SMTP and file IO behave nicely
            time.sleep(2)

        except Exception as e:
            print("Failed to process job:", job.get("title"), job.get("company"), e)


        # DEBUG: if nothing sent, create a test tailored PDF for verification.
    if sent_count == 0:
        print("No emails sent — creating a sample tailored PDF for verification.")
        test_job = {
            "title": "Senior Azure Data Engineer (Test)",
            "company": "TestCompany",
            "link": "https://example.com/test-job",
            "snippet": "Azure Databricks Data Factory PySpark ETL SQL",
            "score": 99,
            "location": "Hyderabad"
        }
        try:
            text_resume, pdf_path = generate_tailored_copy(test_job)
            print("Created test PDF at:", pdf_path)
        except Exception as e:
            print("Failed to create test PDF:", e)


    print(f"Run complete. Emails sent: {sent_count}")

if __name__ == "__main__":
    main_once()
