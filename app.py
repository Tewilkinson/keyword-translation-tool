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
# Load historical jobs
# -----------------------------
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
else:
    log_df = pd.DataFrame(columns=["input_file", "output_file", "status", "total_keywords", "project"])

# -----------------------------
# Streamlit UI Tabs
# -----------------------------
st.title("Keyword Translation Tool")
tabs = st.tabs(["Translate Keywords", "Historical Reports"])

# -----------------------------
# Tab 1: Translate Keywords
# -----------------------------
with tabs[0]:
    # Scorecards
    completed_jobs = len(log_df[log_df["status"] == "Completed"]) if not log_df.empty else 0
    total_keywords = log_df["total_keywords"].sum() if not log_df.empty else 0

    col1, col2 = st.columns(2)
    col1.metric("Completed Jobs", completed_jobs)
    col2.metric("Total Keywords Translated", total_keywords)

    st.subheader("Upload Keywords for Translation")
    uploaded_file = st.file_uploader(
        "Upload Excel file with columns: keyword, category, subcategory, product_category", 
        type=["xlsx"]
    )

    project_name = st.text_input("Enter Project Name")
    target_language = st.selectbox(
        "Select target language", 
        ["French", "Spanish", "German", "Italian", "Chinese"]
    )

    if uploaded_file and project_name:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"File {uploaded_file.name} uploaded successfully.")

        if st.button("Translate"):
            progress_bar = st.progress(0)
            output_file, progress_callback = run_translation_job(file_path, target_language, project_name)

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
        projects = sorted(log_df["project"].dropna().unique())
        selected_project = st.selectbox("Select Project", options=["All Projects"] + projects)

        # Filter by project
        if selected_project == "All Projects":
            display_df = log_df.copy()
        else:
            display_df = log_df[log_df["project"] == selected_project]

        st.dataframe(display_df)

        # Download filtered logs
        csv_data = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Report (CSV)",
            data=csv_data,
            file_name=f"{selected_project}_jobs.csv",
            mime="text/csv"
        )

        # Download all log data
        st.download_button(
            label="📥 Download Full Report (CSV)",
            data=open(JOBS_LOG, "rb").read(),
            file_name="translation_jobs_history.csv",
            mime="text/csv"
        )

        # Deletion
        if selected_project != "All Projects":
            if st.button("🗑️ Delete This Project and Its Files"):
                confirm = st.warning("Are you sure you want to delete this project and all its associated files?")
                if st.button("Yes, delete project", key="delete_confirm"):
                    # Delete from log
                    log_df = log_df[log_df["project"] != selected_project]
                    log_df.to_csv(JOBS_LOG, index=False)

                    # Delete associated output files
                    for fname in display_df["output_file"]:
                        fpath = os.path.join(OUTPUT_DIR, fname)
                        if os.path.exists(fpath):
                            os.remove(fpath)

                    st.success("Project and files deleted. Please refresh.")
    else:
        st.info("No translation jobs found yet.")
