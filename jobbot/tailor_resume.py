# tailor_resume.py
import yaml
import textwrap
import time
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# Load config and master resume
CFG_PATH = "jobbot/config.yaml"
cfg = yaml.safe_load(open(CFG_PATH, "r", encoding="utf-8"))
MASTER = open("jobbot/master_resume.txt", "r", encoding="utf-8").read()

# Template path (the PDF you uploaded). Keep this filename as-is in the jobbot folder.
TEMPLATE_PATH = "jobbot/Sandeep_Resume_N.pdf"

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

# -----------------------
# Overlay creation
# -----------------------
def create_overlay_pdf(text_resume, overlay_path):
    """
    Create an overlay PDF (transparent page) containing the tailored text.
    Coordinates below are in points (origin at bottom-left).
    You will likely need small tweaks to x,y positions to align with your specific template.
    """
    w, h = A4  # page size in points
    c = canvas.Canvas(overlay_path, pagesize=A4)
    c.setFont("Helvetica", 10)

    # --- Tuning area: starting coordinates and spacing ---
    # These coordinates are conservative defaults — adjust after testing.
    left_x = 48           # left margin (points)
    y_start = h - 180     # start below top header (tune this value)
    line_height = 12

    # Write the tailored summary / highlights block
    y = y_start
    max_chars = 95  # rough wrap width for reportlab

    # We'll split the text_resume into paragraphs and wrap each paragraph
    for para in text_resume.split("\n\n"):
        lines = textwrap.wrap(para, width=95) or [""]
        for ln in lines:
            c.drawString(left_x, y, ln)
            y -= line_height
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = h - 50

    c.save()
    return overlay_path

# -----------------------
# Merge overlay with template
# -----------------------
def merge_with_template(overlay_path, template_path=TEMPLATE_PATH, output_path=None):
    """
    Merge overlay PDF on top of the template PDF.
    Returns the output_path (created file).
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found at {template_path}. Upload your resume PDF as that filename.")

    reader_template = PdfReader(template_path)
    reader_overlay = PdfReader(overlay_path)

    writer = PdfWriter()

    # For single-page templates: merge the first page
    base = reader_template.pages[0]
    over = reader_overlay.pages[0]

    # merge_page modifies base in place: overlay on top
    base.merge_page(over)
    writer.add_page(base)

    # If template has multiple pages, you can append remaining pages unchanged:
    # for p in reader_template.pages[1:]:
    #     writer.add_page(p)

    if output_path is None:
        ts = int(time.time())
        output_path = f"jobbot/tailored_resume_{ts}.pdf"

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path

# -----------------------
# Public generator
# -----------------------
def generate_for_job(job):
    """
    Given a job dict, return (text_resume, pdf_path).
    pdf_path is a final PDF file path stored under jobbot/.
    """
    keywords = extract_keywords(job)
    text_resume = build_text_resume(job, keywords)

    # overlay + merge
    ts = int(time.time())
    overlay_path = f"jobbot/overlay_{ts}.pdf"
    final_path = f"jobbot/tailored_resume_{ts}.pdf"

    create_overlay_pdf(text_resume, overlay_path)
    final_pdf = merge_with_template(overlay_path, template_path=TEMPLATE_PATH, output_path=final_path)

    # cleanup overlay if you want (optional)
    try:
        os.remove(overlay_path)
    except:
        pass

    return text_resume, final_pdf
