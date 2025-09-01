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

        # Prepare display DataFrame
        display_df_display = display_df.rename(columns={
            "input_file": "File Name",
            "translated_to": "Translated To",
            "total_keywords": "Keywords Translated",
            "status": "Status"
        })[["File Name", "Translated To", "Keywords Translated", "Status"]]

        st.dataframe(display_df_display, use_container_width=True)

        # Dropdown to select report
        st.markdown("### Download or Delete Historical Report")
        selected_file = st.selectbox(
            "Select a report",
            options=display_df["output_file"].tolist(),
            format_func=lambda x: x
        )

        # One download button
        file_path = os.path.join(OUTPUT_DIR, selected_file)
        if os.path.exists(file_path):
            st.download_button(
                label=f"Download {selected_file}",
                data=open(file_path, "rb").read(),
                file_name=selected_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("File not found. It may have been deleted.")

        # Delete button with confirmation modal
        if st.button("Delete Selected Report"):
            # Modal for confirmation
            with st.modal("Confirm Deletion"):
                st.warning(f"Are you sure you want to delete '{selected_file}' and all its historical data?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Yes, Delete"):
                        # Delete file
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        # Remove from log
                        log_df = log_df[log_df["output_file"] != selected_file]
                        log_df.to_csv(JOBS_LOG, index=False)
                        st.success(f"'{selected_file}' deleted successfully.")
                        st.experimental_rerun()  # Refresh app
                with col_no:
                    if st.button("Cancel"):
                        st.info("Deletion cancelled.")
    else:
        st.info("No translation jobs found yet.")
