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
st.title("Keyword Translation Tool")

# Scorecards
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
else:
    log_df = pd.DataFrame(columns=["input_file", "output_file", "status", "total_keywords"])

completed_jobs = len(log_df[log_df["status"] == "Completed"]) if not log_df.empty else 0
total_keywords = log_df["total_keywords"].sum() if not log_df.empty else 0

col1, col2 = st.columns(2)
col1.metric("Completed Jobs", completed_jobs)
col2.metric("Total Keywords Translated", total_keywords)

st.subheader("Upload Keywords for Translation")
uploaded_file = st.file_uploader("Upload Excel file with columns: keyword, category, subcategory, product_category", type=["xlsx"])

target_language = st.selectbox("Select target language", ["French", "Spanish", "German", "Italian", "Chinese"])

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

st.subheader("Historical Translation Jobs")
if not log_df.empty:
    st.dataframe(log_df)
    for idx, row in log_df.iterrows():
        out_file = os.path.join(OUTPUT_DIR, row["output_file"])
        if os.path.exists(out_file):
            st.download_button(
                label=f"Download {row['output_file']}",
                data=open(out_file, "rb").read(),
                file_name=row["output_file"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("No translation jobs found yet.")
