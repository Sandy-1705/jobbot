# fetchers.py
"""
Robust job fetchers for JobBot.

Provides:
- requests_session_with_retries(...) : HTTP session with sensible headers + retries
- fetch_linkedin_jobs(query, location) : indirect LinkedIn discovery via Google search (no direct scraping of LinkedIn)
- fetch_indeed(query, location)      : basic Indeed scraping (may 403 from Actions IPs)
- fetch_company_jobs(url)            : heuristic scraping of company career pages (follows job-like links)

Each fetcher returns a list of job dicts:
{
  "source": "company"|"indeed"|"linkedin",
  "title": "...",
  "company": "...",
  "link": "...",
  "snippet": "...",
  "posted_at": "...",   # iso timestamp (if available)
  "location": "..."     # optional
}
"""

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, unquote
import time
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -------------------------
# Session with retries & friendly headers
# -------------------------
def requests_session_with_retries(
    total_retries: int = 5,
    backoff: float = 1.0,
    status_forcelist=(429, 500, 502, 503, 504)
):
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

    # Browser-like headers (helps some sites avoid trivial bot blocks)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    })
    return s

# -------------------------
# LinkedIn discovery via Google search (indirect)
# -------------------------
def fetch_linkedin_jobs(query: str = "Azure Data Engineer", location: str = "Hyderabad"):
    """
    Discover LinkedIn job links by scraping Google search results for 'site:linkedin.com/jobs ...'
    This avoids direct LinkedIn scraping (which is blocked aggressively).
    Returns list of job dicts.
    """
    session = requests_session_with_retries()
    google_query = f"site:linkedin.com/jobs {query} {location}"
    url = "https://www.google.com/search"
    params = {"q": google_query, "num": 10}

    jobs = []
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print("LinkedIn (via Google) fetch failed:", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Google search result anchors typically use /url?q=...
    anchors = soup.select("a")
    seen = set()
    for a in anchors:
        href = a.get("href", "")
        if not href.startswith("/url?q="):
            continue
        real_url = href.replace("/url?q=", "").split("&")[0]
        real_url = unquote(real_url)

        # only accept linkedin job links
        if "linkedin.com/jobs" not in real_url:
            continue

        # prefer view links; filter noisy redirectors
        if not any(x in real_url for x in ("/jobs/view", "/jobs/search", "/jobs/")):
            # still may be useful, but skip noisy pages
            continue

        title = a.get_text(" ", strip=True) or "LinkedIn Job"
        if real_url in seen:
            continue
        seen.add(real_url)

        jobs.append({
            "source": "linkedin",
            "title": title,
            "company": "LinkedIn",
            "link": real_url,
            "snippet": "Found via Google search",
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "location": location
        })

    return jobs

# -------------------------
# Indeed fetcher (simple)
# -------------------------
def fetch_indeed(query: str = "Azure Data Engineer", location: str = "Hyderabad"):
    """
    Basic scraping of in.indeed.com search results.
    Note: Indeed often blocks automated requests from cloud runners; expect 403 sometimes.
    """
    base = "https://in.indeed.com/jobs"
    params = {"q": query, "l": location}
    session = requests_session_with_retries()

    try:
        resp = session.get(base, params=params, timeout=30)
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
    card_selectors = [
        ".jobsearch-SerpJobCard",  # older Indeed
        ".result",                 # generic
        "a.tapItem",               # newer mobile layout
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
        snippet_tag = card.select_one(".job-snippet") or card.select_one(".summary") or card.select_one(".jobCardShelfContainer")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # link
        link_tag = card.select_one("a") or card.select_one("a.jobtitle")
        link = ""
        if link_tag and link_tag.get("href"):
            href = link_tag.get("href").strip()
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
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "location": location
        })

    return jobs

# ------------------------------------------------------------
# Fetch jobs from a company careers page (heuristic)
# ------------------------------------------------------------
def fetch_company_jobs(url: str, session=None):
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
        r = session.get(url, timeout=30)
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
    seen_links = set()

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

        # filter out obviously non-job links by path segment
        job_path_indicators = (
            "job", "jobs", "careers", "career", "openings", "positions",
            "role", "apply", "vacancy", "opportunity", "posting"
        )
        parsed_href = urlparse(href)
        if not any(ind in parsed_href.path.lower() for ind in job_path_indicators):
            # sometimes job lists are on different domains or require JS; skip these noisy links
            continue

        # Candidate title: anchor text or last path segment
        cand_title = text or parsed_href.path.split("/")[-1].replace("-", " ").replace("_", " ")

        # Basic keyword filter for data/engineering-related roles
        lowered = cand_title.lower()
        if not any(k in lowered for k in ("data", "engineer", "analytics", "analyst", "scientist", "databricks", "azure", "etl", "spark")):
            # still allow some cases where snippet contains keywords
            snippet_lower = (a.get("aria-label","") + " " + a.get("title","")).lower()
            if not any(k in snippet_lower for k in ("data", "engineer", "azure")):
                continue

        company_domain = parsed.netloc or urlparse(url).netloc
        link_key = href.split("?")[0]
        if link_key in seen_links:
            continue
        seen_links.add(link_key)

        jobs.append({
            "source": "company",
            "title": cand_title,
            "company": company_domain,
            "link": href,
            "snippet": text,
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "location": ""
        })

    return jobs

# -------------------------
# Convenience: aggregate multiple sources (optional utility)
# -------------------------
def fetch_multiple_sources(query="Azure Data Engineer", location="Hyderabad", company_pages=None):
    """
    Helper that fetches from LinkedIn (via Google), Indeed, and a list of company pages.
    Returns a combined list of job dicts.
    """
    out = []
    try:
        out += fetch_linkedin_jobs(query=query, location=location)
    except Exception as e:
        print("LinkedIn fetch failed (aggregate):", e)

    try:
        out += fetch_indeed(query=query, location=location)
    except Exception as e:
        print("Indeed fetch failed (aggregate):", e)

    if company_pages:
        session = requests_session_with_retries()
        for u in company_pages:
            try:
                out += fetch_company_jobs(u, session=session)
                time.sleep(1.5)  # polite pause between company pages
            except Exception as e:
                print("Company fetch failed for", u, e)

    return out
