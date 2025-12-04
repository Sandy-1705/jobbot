# fetchers.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -------------------------
# Session with retries
# -------------------------
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
    # inside requests_session_with_retries()
    s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
})


    return s

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote

def fetch_linkedin_jobs(query="Azure Data Engineer", location="Hyderabad"):
    """
    Indirect LinkedIn scraping using Google results.
    LinkedIn blocks direct scraping on GitHub Actions.
    So we scrape Google for 'site:linkedin.com/jobs' results.
    """
    session = requests_session_with_retries()
    google_query = f"site:linkedin.com/jobs {query} {location}"
    url = "https://www.google.com/search"
    params = {"q": google_query}

    jobs = []

    try:
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print("LinkedIn Google search failed:", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Google search results = <a href="/url?q=..." >
    for a in soup.select("a"):
        href = a.get("href", "")
        if not href.startswith("/url?q="):
            continue

        # extract actual URL
        real_url = href.replace("/url?q=", "").split("&")[0]
        real_url = unquote(real_url)

        # keep only LinkedIn job URLs
        if "linkedin.com/jobs" not in real_url:
            continue

        title = a.get_text(" ", strip=True)
        if not title:
            title = "LinkedIn Job"

        jobs.append({
            "source": "linkedin",
            "title": title,
            "company": "LinkedIn",
            "link": real_url,
            "snippet": "Found via Google",
            "posted_at": datetime.now(timezone.utc).isoformat()
        })

    return jobs


# -------------------------
# Indeed fetcher (India)
# -------------------------
def fetch_indeed(query="Azure Data Engineer", location="Hyderabad"):
    """
    Fetch job cards from in.indeed.com search results (basic scraping).
    Returns list of job dicts: {source, title, company, link, snippet, posted_at}
    """
    base = "https://in.indeed.com/jobs"
    params = {"q": query, "l": location}
    session = requests_session_with_retries()

    try:
        resp = session.get(base, params=params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print("Error fetching Indeed jobs:", e)
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print("Error parsing Indeed HTML:", e)
        return []

    jobs = []
    # different Indeed versions use different classes; try a few selectors
    card_selectors = [
        ".jobsearch-SerpJobCard",  # older
        ".result",                 # common generic
        "a.tapItem"                # newer mobile/search
    ]

    cards = []
    for sel in card_selectors:
        found = soup.select(sel)
        if found:
            cards = found
            break

    for card in cards:
        # title
        title_tag = card.select_one("h2.jobTitle") or card.select_one(".jobTitle") or card.select_one(".title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # company
        company_tag = card.select_one(".companyName") or card.select_one(".company")
        company = company_tag.get_text(strip=True) if company_tag else ""

        # snippet/summary
        snippet_tag = card.select_one(".job-snippet") or card.select_one(".summary")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # link
        link_tag = card.select_one("a") or card.select_one("a.jobtitle")
        link = ""
        if link_tag and link_tag.get("href"):
            href = link_tag.get("href").strip()
            # many Indeed links are relative
            if href.startswith("http"):
                link = href
            else:
                link = urljoin("https://in.indeed.com", href)

        jobs.append({
            "source": "indeed",
            "title": title,
            "company": company,
            "link": link,
            "snippet": snippet,
            "posted_at": datetime.now(timezone.utc).isoformat()
        })

    return jobs

# ------------------------------------------------------------
# Fetch Azure Data Engineer jobs from company career pages (robust)
# ------------------------------------------------------------
def fetch_company_jobs(url, session=None):
    """
    Fetch job links heuristically from a company careers page.
    Only returns links that look like job postings (path contains job/careers/openings/apply/etc).
    """
    if not url:
        return []

    parsed = urlparse(url)
    if not parsed.scheme:
        print("Skipping invalid company URL (no scheme):", url)
        return []

    if session is None:
        session = requests_session_with_retries()

    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
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
        text = a.get_text(" ", strip=True).strip()
        if not href:
            continue

        # normalize relative links
        if not href.startswith("http"):
            try:
                href = urljoin(url, href)
            except Exception:
                continue

        # quickly filter out non-job links by path segment
        job_path_indicators = ("job", "jobs", "careers", "career", "openings", "positions", "role", "apply", "vacancy")
        parsed_href = urlparse(href)
        if not any(ind in parsed_href.path.lower() for ind in job_path_indicators):
            # skip links that don't look like job pages
            continue

        # Candidate title: anchor text or last path segment
        cand_title = text or parsed_href.path.split("/")[-1].replace("-", " ").replace("_", " ")

        # only consider if title contains job-like keywords
        lowered = cand_title.lower()
        if not any(k in lowered for k in ("data", "engineer", "analytics", "analyst", "scientist", "databricks", "azure", "etl", "spark")):
            continue

        company_domain = parsed.netloc
        jobs.append({
            "source": "company",
            "title": cand_title,
            "company": company_domain,
            "link": href,
            "snippet": text
        })

    return jobs


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
            try:
                href = urljoin(url, href)
            except Exception:
                continue

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
