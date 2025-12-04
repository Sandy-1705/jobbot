# tailor_resume.py
import yaml
import textwrap
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

# Load config and master resume
cfg = yaml.safe_load(open("jobbot/config.yaml", "r", encoding="utf-8"))
MASTER = open("jobbot/master_resume.txt", "r", encoding="utf-8").read()

# terms to detect in job descriptions
TERMS = [
    "azure", "databricks", "data factory", "synapse", "delta lake",
    "pyspark", "python", "sql", "ci/cd", "etl", "spark", "data lake",
    "data engineering", "lakehouse"
]

def extract_keywords(job):
    text = (job.get("title", "") + " " + job.get("snippet", "")).lower()
    keywords = []
    for t in TERMS:
        if t in text and t not in keywords:
            keywords.append(t)
    return keywords

def build_text_resume(job, keywords):
    # Start with master resume, then append tailoring info
    lines = []
    lines.append(MASTER.strip())
    lines.append("\n--- TAILORED FOR ---")
    lines.append(f"Role: {job.get('title','')}")
    lines.append(f"Company: {job.get('company','')}")
    lines.append(f"Job Link: {job.get('link','')}")
    lines.append(f"Match Score: {job.get('score',0)}")
    if keywords:
        lines.append("Matched Keywords: " + ", ".join(keywords))
    lines.append("\nTailored highlights:")
    # Add a few short tailored bullets based on detected keywords
    if "azure" in keywords or "data factory" in keywords:
        lines.append("- Built and maintained enterprise Azure Data Factory pipelines for ingestion and orchestration.")
    if "databricks" in keywords or "delta lake" in keywords:
        lines.append("- Designed Databricks notebooks and Delta Lake tables to support ACID transactions and efficient queries.")
    if "pyspark" in keywords or "spark" in keywords:
        lines.append("- Implemented PySpark transformations to process large datasets with performance tuning and partitioning.")
    if "ci/cd" in keywords:
        lines.append("- Implemented CI/CD for data pipelines using GitHub Actions for reliable deployments.")
    # Generic strong bullets
    lines.append("- Automated data validation, reconciliation and monitoring for reliable data quality.")
    lines.append("- Collaborated with analytics, data science, and architecture teams to deliver production-grade data platforms.")
    # Add timestamp
    lines.append(f"\nGenerated: {datetime.utcnow().isoformat()} UTC")
    return "\n".join(lines)

def create_pdf(text_resume, out_path):
    """
    Create a simple PDF from the text resume.
    Returns the path to the saved PDF.
    """
    w, h = A4
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setFont("Helvetica", 10)
    y = h - 50
    wrap_width = 95
    for para in text_resume.split("\n"):
        # wrap long lines
        lines = textwrap.wrap(para, width=wrap_width) or [""]
        for ln in lines:
            c.drawString(40, y, ln)
            y -= 12
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = h - 50
    c.save()
    return out_path

def safe_filename(s):
    # create a filesystem-safe short filename
    allowed = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return "".join(ch if ch in allowed else "_" for ch in s)[:60]

def generate_for_job(job):
    """
    Given a job dict, return (text_resume, pdf_path).
    pdf stored in repo working dir with a filename based on job title/company.
    """
    keywords = extract_keywords(job)
    text_resume = build_text_resume(job, keywords)
    # create safe filename
    title = job.get("title","").strip().replace(" ","_")[:40]
    company = job.get("company","").strip().replace(" ","_")[:30]
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe = f"resume_{title}_{company}_{timestamp}.pdf"
    # fallback for any odd characters
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in safe)
    pdf_path = create_pdf(text_resume, safe)
    return text_resume, pdf_path
