# fetchers.py  (replace fetch_company_jobs with this version)
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# create a session with retries
def requests_session_with_retries(total_retries=3, backoff=1, status_forcelist=(429, 500, 502, 503, 504)):
    s = requests.Session()
    retries = Retry(
        total=total_retries,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET", "POST"])
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0; +https://github.com/)"})
    return s

# ------------------------------------------------------------
# Fetch Azure Data Engineer jobs from company career pages (robust)
# ------------------------------------------------------------
def fetch_company_jobs(url, session=None):
    """
    Fetch job links heuristically from a company careers page.
    Returns a list of job dicts.
    """
    if not url:
        return []

    # basic sanity check
    parsed = urlparse(url)
    if not parsed.scheme:
        # not a proper URL, skip
        print("Skipping invalid company URL (no scheme):", url)
        return []

    if session is None:
        session = requests_session_with_retries()

    try:
        r = session.get(url, timeout=20)
        # raise_for_status() can throw HTTPError for 4xx/5xx, we catch below
        r.raise_for_status()
    except Exception as e:
        # log a concise message and return empty list
        print(f"Error fetching company careers from {url}: {e}")
        return []

    try:
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Error parsing HTML from", url, e)
        return []

    jobs = []
    for a in soup.select("a"):
        href = a.get("href", "").strip()
        text = a.get_text(strip=True)
        if not href or not text:
            continue

        # normalize relative links
        if not href.startswith("http"):
            href = urljoin(url, href)

        lowered = (text + " " + href).lower()
        if any(keyword in lowered for keyword in [
                "data", "engineer", "analytics", "data engineer", "azure", "cloud", "big data", "databricks"
            ]):
            company_domain = urlparse(url).netloc
            jobs.append({
                "source": "company",
                "title": text,
                "company": company_domain,
                "link": href,
                "snippet": ""
            })

    return jobs
