import streamlit as st
import pandas as pd
from io import BytesIO
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import subprocess

load_dotenv()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
DB_FILE = "jobs.db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize SQLite DB
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    target_language TEXT,
    status TEXT,
    created_at TEXT,
    output_file TEXT
)
""")
conn.commit()

st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("Keyword Translation Tool - Manual Job Execution 🌐")

# --------------------------
# Dashboard Scorecards
# --------------------------
c.execute("SELECT COUNT(*) FROM jobs")
total_jobs = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM jobs WHERE status='Completed'")
completed_jobs = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM jobs WHERE status='Pending'")
pending_jobs = c.fetchone()[0]

st.subheader("Job Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Total Jobs", total_jobs)
col2.metric("Completed Jobs", completed_jobs)
col3.metric("Pending Jobs", pending_jobs)

# --------------------------
# Download Template
# --------------------------
template_df = pd.DataFrame(columns=["Keyword", "Category", "Subcategory", "Product Category"])
output_template = BytesIO()
with pd.ExcelWriter(output_template, engine="openpyxl") as writer:
    template_df.to_excel(writer, index=False, sheet_name="Keywords")
output_template.seek(0)

st.download_button(
    label="📥 Download Excel Template",
    data=output_template,
    file_name="keyword_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --------------------------
# Upload File
# --------------------------
uploaded_file = st.file_uploader("Upload your filled Excel file", type=["xlsx"])

target_language = st.selectbox(
    "Choose a language to translate keywords into",
    ["Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese", "Korean", "Russian"]
)

if uploaded_file and st.button("Submit Translation Job"):
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    # Insert job into DB
    c.execute(
        "INSERT INTO jobs (filename, target_language, status, created_at) VALUES (?, ?, ?, ?)",
        (filename, target_language, "Pending", datetime.now().isoformat())
    )
    conn.commit()
    st.success(f"✅ Job submitted! It is now pending execution.")

# --------------------------
# Run Pending Job Manually
# --------------------------
st.subheader("Run Pending Translation Job")
c.execute("SELECT * FROM jobs WHERE status='Pending'")
pending_jobs_df = pd.DataFrame(c.fetchall(), columns=[desc[0] for desc in c.description])

if not pending_jobs_df.empty:
    selected_job_id = st.selectbox("Select Job ID to Run", pending_jobs_df['id'])
    if st.button("Run Selected Job"):
        subprocess.Popen(["python", "worker.py", str(selected_job_id)])
        st.info(f"🛠 Job {selected_job_id} started. It will run in background.")
else:
    st.info("No pending jobs to run.")

# --------------------------
# Completed Jobs
# --------------------------
st.subheader("Completed Translations")
c.execute("SELECT * FROM jobs WHERE status='Completed' ORDER BY created_at DESC")
completed_jobs_df = pd.DataFrame(c.fetchall(), columns=[desc[0] for desc in c.description])

if not completed_jobs_df.empty:
    st.dataframe(completed_jobs_df)
    for idx, row in completed_jobs_df.iterrows():
        if row['output_file']:
            download_path = os.path.join(OUTPUT_DIR, row['output_file'])
            if os.path.exists(download_path):
                st.download_button(
                    label=f"📥 Download {row['output_file']}",
                    data=open(download_path, "rb").read(),
                    file_name=row['output_file'],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
