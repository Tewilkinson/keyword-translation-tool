import streamlit as st
import pandas as pd
import os
from worker import run_translation_job, list_outputs

# File paths
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs_log.csv"

st.set_page_config(page_title="Keyword Translation Tool", layout="wide")

st.title("Keyword Translation Tool")

# --- Dashboard ---
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
    for col in ["status", "total_keywords"]:
        if col not in log_df.columns:
            log_df[col] = "" if col == "status" else 0
    total_jobs = len(log_df)
    completed_jobs = len(log_df[log_df['status'] == "Completed"])
    total_keywords = log_df['total_keywords'].sum()
else:
    log_df = pd.DataFrame(columns=["status", "total_keywords"])
    total_jobs = completed_jobs = total_keywords = 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Jobs", total_jobs)
col2.metric("Completed Jobs", completed_jobs)
col3.metric("Total Keywords", total_keywords)

st.markdown("---")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload your keyword Excel file", type=["xlsx"])

target_language = st.selectbox("Select target language", ["French", "German", "Spanish", "Italian", "Japanese", "Chinese"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if "keyword" not in df.columns:
        st.error("Excel must have a 'keyword' column")
    else:
        st.success(f"{len(df)} keywords loaded")

        if st.button("Translate"):
            with st.spinner("Translation in progress..."):
                # Save uploaded file
                file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                df.to_excel(file_path, index=False)

                # Run worker
                output_file, progress_callback = run_translation_job(file_path, target_language)

                # Show progress bar
                progress_bar = st.progress(0)
                for p in progress_callback():
                    progress_bar.progress(p)

                st.success("Translation completed!")

                # Show download button
                st.download_button(
                    label="Download Translated Keywords",
                    data=open(output_file, "rb").read(),
                    file_name=os.path.basename(output_file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# --- Previous Outputs ---
st.markdown("## Previous Translations")
outputs = list_outputs(OUTPUT_DIR)
if outputs:
    for f in outputs:
        st.download_button(
            label=f"Download {f}",
            data=open(os.path.join(OUTPUT_DIR, f), "rb").read(),
            file_name=f,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("No previous translated outputs found.")
