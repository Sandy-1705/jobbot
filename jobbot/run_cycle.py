# run_cycle.py
import os
import yaml
import time
from fetchers import fetch_indeed, fetch_company_jobs
from matcher import score_job
from tailor_resume import generate_for_job
from emailer import send_email

# Load config
CFG_PATH = "jobbot/config.yaml"
cfg = yaml.safe_load(open(CFG_PATH, "r", encoding="utf-8"))

def load_company_pages():
    try:
        with open("jobbot/company_list.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
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

    # filter by score threshold
    good = [j for j in scored if j.get("score", 0) >= cfg.get("score_threshold", 30)]

    # env SMTP from GitHub Secrets or local env
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        print("SMTP_USER and SMTP_PASS environment variables not found. Exiting without sending emails.")
        return

    for job in good:
        try:
            text_resume, pdf_path = generate_for_job(job)
            subject = f"[JobBot] {job.get('title','')} @ {job.get('company','')}  Score:{job.get('score',0)}"
            body = (
                f"Role: {job.get('title','')}\n"
                f"Company: {job.get('company','')}\n"
                f"Link: {job.get('link','')}\n\n"
                f"Match Score: {job.get('score',0)}\n\n"
                f"Tailored Resume (text below):\n\n{text_resume}\n"
            )
            send_email(smtp_user, smtp_pass, cfg.get("email"), subject, body, attachments=[pdf_path])
            print("Emailed job:", job.get("title"), job.get("company"))
            # small pause so SMTP and file IO behave nicely
            time.sleep(2)
        except Exception as e:
            print("Failed to process job:", job.get("title"), job.get("company"), e)

if __name__ == "__main__":
    main_once()
