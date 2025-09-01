# app.py
import streamlit as st
import os
import pandas as pd
from worker import run_translation_job

UPLOADS_DIR = "uploads"
OUTPUTS_DIR = "outputs"
JOBS_LOG = "jobs_log.csv"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

st.set_page_config(page_title="Keyword Translation Tool", layout="wide")

st.title("Keyword Translation Tool")

# Dashboard KPIs
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
    total_jobs = len(log_df)
    completed_jobs = len(log_df[log_df['status'] == "Completed"])
    total_keywords = log_df['total_keywords'].sum()
else:
    log_df = pd.DataFrame()
    total_jobs = completed_jobs = total_keywords = 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Jobs Submitted", total_jobs)
col2.metric("Jobs Completed", completed_jobs)
col3.metric("Total Keywords Processed", total_keywords)

st.header("Submit New Translation Job")
uploaded_file = st.file_uploader("Upload Excel with 'keyword' column", type=["xlsx"])

target_language = st.selectbox("Target Language", ["French", "Spanish", "German", "Italian"])

if uploaded_file and st.button("Translate"):
    file_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.info("Job submitted! Translation is running in the background...")
    run_translation_job(file_path, target_language)
    st.success("Job completed! Refresh the Past Jobs section below to see output.")

st.header("Past Translation Jobs")
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
    log_df = log_df.sort_values(by="timestamp", ascending=False)
    for idx, row in log_df.iterrows():
        st.write(f"**Job:** {row['input_file']} → {row['output_file']}")
        st.write(f"Language: {row['target_language']}, Keywords: {row['total_keywords']}, Status: {row['status']}, Progress: {row['progress_percent']}%")
        if row['status'] == "Completed":
            file_path = os.path.join(OUTPUTS_DIR, row['output_file'])
            st.download_button("Download Translated File", file_path, file_name=row['output_file'])
