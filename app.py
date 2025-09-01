import os
import streamlit as st
import pandas as pd
from worker import run_translation_job

# -----------------------------
# Directories and logs
# -----------------------------
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs.csv"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(layout="wide")
st.title("Keyword Translation Tool")

# Load job logs
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
else:
    log_df = pd.DataFrame(columns=["input_file", "output_file", "translated_to", "status", "total_keywords"])

# Scorecards
completed_jobs = len(log_df[log_df["status"] == "Completed"]) if not log_df.empty else 0
total_keywords = log_df["total_keywords"].sum() if not log_df.empty else 0

col1, col2 = st.columns(2)
col1.metric("Completed Jobs", completed_jobs)
col2.metric("Total Keywords Translated", total_keywords)

# Tabs
tabs = st.tabs(["New Translation", "Historical Reports"])

# -----------------------------
# Tab 1: New Translation
# -----------------------------
with tabs[0]:
    st.subheader("Upload Keywords for Translation")
    uploaded_file = st.file_uploader(
        "Upload Excel file with columns: keyword, category, subcategory, product_category",
        type=["xlsx"]
    )

    target_language = st.selectbox(
        "Select target language",
        ["French", "Spanish", "German", "Italian", "Chinese"]
    )

    if uploaded_file:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"File {uploaded_file.name} uploaded successfully.")

        if st.button("Translate"):
            progress_bar = st.progress(0)
            output_file, progress_callback = run_translation_job(file_path, target_language)

            # Iterate progress generator
            for pct in progress_callback():
                progress_bar.progress(pct)

            st.success(f"Translation complete: {output_file}")
            st.download_button(
                "Download Translated Keywords",
                data=open(output_file, "rb").read(),
                file_name=os.path.basename(output_file),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# -----------------------------
# Tab 2: Historical Reports
# -----------------------------
with tabs[1]:
    st.subheader("Historical Translation Jobs")
    if not log_df.empty:
        display_df = log_df.copy()

        # Ensure 'translated_to' column exists
        if "translated_to" not in display_df.columns:
            display_df["translated_to"] = "N/A"

        # Prepare display DataFrame without the download column
        display_df_display = display_df.rename(columns={
            "input_file": "File Name",
            "translated_to": "Translated To",
            "total_keywords": "Keywords Translated",
            "status": "Status"
        })[["File Name", "Translated To", "Keywords Translated", "Status"]]

        st.dataframe(display_df_display, use_container_width=True)

        st.markdown("### Downloads")
        for idx, row in display_df.iterrows():
            file_path = os.path.join(OUTPUT_DIR, row["output_file"])
            if os.path.exists(file_path):
                st.download_button(
                    label=f"{row['input_file']}",
                    data=open(file_path, "rb").read(),
                    file_name=row["output_file"],
                    key=f"download_{idx}"
                )

        # Download full CSV
        st.download_button(
            label="Download Full Historical Report (CSV)",
            data=open(JOBS_LOG, "rb").read(),
            file_name="translation_jobs_history.csv",
            mime="text/csv"
        )
    else:
        st.info("No translation jobs found yet.")
