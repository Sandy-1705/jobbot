# matcher.py
import yaml
from urllib.parse import urlparse

# Load configuration
cfg = yaml.safe_load(open("jobbot/config.yaml"))

def is_product_company(job):
    # Simple heuristic: check domain or company name for known product company keywords
    domain = urlparse(job.get("link", "")).netloc.lower()
    company = job.get("company", "").lower()
    product_signals = [
        "product", "saas", "startup", "platform", "stripe", "airbnb",
        "google", "microsoft", "amazon", "chargebee", "razorpay",
        "browserstack", "freshworks", "postman", "flipkart", "zoho"
    ]
    for s in product_signals:
        if s in domain or s in company:
            return True
    return False

def location_score(job):
    title = job.get("title", "").lower()
    link = job.get("link", "").lower()
    score = 0
    for i, loc in enumerate(cfg.get("location_priority", [])):
        if loc.lower() in title or loc.lower() in link:
            # earlier locations in the list get higher weight
            score += (len(cfg["location_priority"]) - i) * 12
    return score

def visa_score(job):
    snippet = job.get("snippet", "").lower()
    if not cfg.get("global_allow_visa_sponsor", True):
        return 0
    # boost if job mentions visa/relocation/sponsorship
    for kw in ["visa", "sponsor", "sponsorship", "relocation", "work permit"]:
        if kw in snippet:
            return 20
    return 0

def keyword_score(job):
    text = (job.get("title", "") + " " + job.get("snippet", "")).lower()
    score = 0
    for kw in cfg.get("required_keywords", []):
        if kw.lower() in text:
            score += 6
    return score

def low_applicant_score(job):
    # If applicant count present and low, reward it.
    applicants = job.get("applicants")
    if applicants is None:
        return 0
    try:
        if int(applicants) <= int(cfg.get("max_applicants_for_low", 30)):
            return 10
    except:
        return 0
    return 0

def score_job(job):
    score = 0
    score += location_score(job)
    score += keyword_score(job)
    score += visa_score(job)
    score += low_applicant_score(job)

    # Product company boost (only if config allows preference)
    if cfg.get("product_company_only", True) and is_product_company(job):
        score += 20
    # Otherwise a small neutral boost for product signals even if not strict
    elif is_product_company(job):
        score += 10

    job["score"] = score
    return job
