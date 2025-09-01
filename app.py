import streamlit as st
import pandas as pd
import os
from datetime import datetime
from worker import run_translation_job  # your server-side worker handling translation

# -------------------------------
# Setup directories
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
LOG_FILE = os.path.join(BASE_DIR, "jobs.db")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# -------------------------------
# Load historical jobs
# -------------------------------
if os.path.exists(LOG_FILE):
    log_df = pd.read_csv(LOG_FILE)
else:
    log_df = pd.DataFrame(columns=["report_name", "status", "total_keywords", "language", "output_file", "timestamp"])

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("Keyword Translation Tool")

# -------------------------------
# Dashboard KPIs
# -------------------------------
st.subheader("Dashboard")
completed_jobs = len(log_df[log_df['status'] == "Completed"])
total_keywords_translated = log_df['total_keywords'].sum() if not log_df.empty else 0
st.metric("Completed Jobs", completed_jobs)
st.metric("Total Keywords Translated", total_keywords_translated)

st.markdown("---")

# -------------------------------
# File upload and translation
# -------------------------------
st.subheader("Submit Translation Job")
uploaded_file = st.file_uploader("Upload Excel with 'keyword' column", type=["xlsx"])

target_language = st.selectbox("Select Target Language", ["French", "Spanish", "German", "Italian"])

if uploaded_file:
    file_path = os.path.join(UPLOADS_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    if st.button("Run Translation"):
        with st.spinner("Running translation job..."):
            try:
                output_file, progress_callback = run_translation_job(file_path, target_language)
                
                # Add to logs
                new_log = {
                    "report_name": uploaded_file.name,
                    "status": "Completed",
                    "total_keywords": progress_callback['total'],
                    "language": target_language,
                    "output_file": output_file,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                log_df = pd.concat([log_df, pd.DataFrame([new_log])], ignore_index=True)
                log_df.to_csv(LOG_FILE, index=False)
                
                st.success(f"Translation completed! Output: {output_file}")
            except Exception as e:
                st.error(f"Error running translation: {e}")

st.markdown("---")

# -------------------------------
# Historical Reports Table
# -------------------------------
st.subheader("Historical Reports")

if not log_df.empty:
    table_df = log_df.copy()
    table_df["Download"] = table_df["output_file"].apply(lambda f: f"[Download]({f})" if os.path.exists(f) else "File missing")
    
    # Select relevant columns
    table_df = table_df[["report_name", "status", "total_keywords", "language", "Download"]]
    
    # Display table
    st.data_editor(
        table_df,
        column_config={
            "report_name": st.column_config.TextColumn("Report Name"),
            "status": st.column_config.TextColumn("Status"),
            "total_keywords": st.column_config.NumberColumn("Total Keywords"),
            "language": st.column_config.TextColumn("Language"),
            "Download": st.column_config.LinkColumn("Download Link")
        },
        hide_index=True
    )
else:
    st.info("No historical reports yet.")

