# fetchers.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# ------------------------------------------------------------
# Fetch Azure Data Engineer jobs from Indeed (Hyderabad focus)
# ------------------------------------------------------------
def fetch_indeed(query="Azure Data Engineer", location="Hyderabad"):
    url = "https://in.indeed.com/jobs"
    params = {"q": query, "l": location}

    try:
        r = requests.get(
            url,
            params=params,
            timeout=20,
            headers={"User-Agent":"Mozilla/5.0"}
        )
        soup = BeautifulSoup(r.text, "html.parser")

        jobs = []
        cards = soup.select(".result")

        for card in cards:
            title_tag = card.select_one(".jobTitle")
            company_tag = card.select_one(".companyName")
            snippet_tag = card.select_one(".job-snippet")
            link_tag = card.select_one("a")

            title = title_tag.get_text(strip=True) if title_tag else ""
            company = company_tag.get_text(strip=True) if company_tag else ""
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

            link = ""
            if link_tag and link_tag.get("href"):
                link = "https://in.indeed.com" + link_tag["href"]

            jobs.append({
                "source": "indeed",
                "title": title,
                "company": company,
                "link": link,
                "snippet": snippet,
                "posted_at": datetime.now(timezone.utc).isoformat()
            })

        return jobs

    except Exception as e:
        print("Error fetching Indeed jobs:", e)
        return []


# ------------------------------------------------------------
# Fetch Azure Data Engineer jobs from company career pages
# ------------------------------------------------------------
def fetch_company_jobs(url):
    try:
        r = requests.get(
            url,
            timeout=20,
            headers={"User-Agent":"Mozilla/5.0"}
        )
        soup = BeautifulSoup(r.text, "html.parser")

        jobs = []

        # Look for <a> tags that mention "engineer", "data", etc.
        for a in soup.select("a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)

            if not text or not href:
                continue

            lowered = text.lower() + " " + href.lower()

            # Heuristics for data engineering roles
            if any(keyword in lowered for keyword in [
                "data",
                "engineer",
                "analytics",
                "data engineer",
                "azure",
                "cloud",
                "big data"
            ]):
                link = (
                    href if href.startswith("http")
                    else url.rstrip("/") + "/" + href.lstrip("/")
                )

                jobs.append({
                    "source": "company",
                    "title": text,
                    "company": url.split("//")[-1].split("/")[0],
                    "link": link,
                    "snippet": ""
                })

        return jobs

    except Exception as e:
        print("Error fetching company careers:", e)
        return []
