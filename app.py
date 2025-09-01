import os
import pandas as pd
import streamlit as st
from datetime import datetime
from worker import run_translation_job, get_historical_jobs
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------------
# Setup folders
# -----------------------------
UPLOADS_DIR = "uploads"
OUTPUTS_DIR = "outputs"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")

st.title("Keyword Translation Tool")

# -----------------------------
# Upload & Language Selection
# -----------------------------
with st.sidebar:
    st.header("Upload Keywords")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    target_language = st.selectbox("Select Target Language", ["French", "Spanish", "German", "Italian"])

# -----------------------------
# Dashboard Cards
# -----------------------------
st.subheader("Translation Dashboard")
historical_jobs = get_historical_jobs(OUTPUTS_DIR)

total_jobs = len(historical_jobs)
completed_jobs = sum(1 for job in historical_jobs if job["status"] == "Completed")
total_keywords_translated = sum(job["total_keywords"] for job in historical_jobs if job["status"] == "Completed")

col1, col2, col3 = st.columns(3)
col1.metric("Total Jobs Submitted", total_jobs)
col2.metric("Completed Jobs", completed_jobs)
col3.metric("Total Keywords Translated", total_keywords_translated)

# -----------------------------
# Run Translation
# -----------------------------
if uploaded_file is not None:
    st.info(f"File uploaded: {uploaded_file.name}")

    if st.button("Run Translation"):
        # Save uploaded file to uploads folder
        upload_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
        with open(upload_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Run the job
        with st.spinner("Translating keywords... this may take a while for large files"):
            output_file, progress_callback = run_translation_job(upload_path, target_language)

        st.success(f"Translation completed: {output_file}")
        st.download_button(
            "Download Translated File",
            data=open(output_file, "rb").read(),
            file_name=os.path.basename(output_file)
        )

# -----------------------------
# Historical Reports Table
# -----------------------------
st.subheader("Historical Reports")

if historical_jobs:
    df = pd.DataFrame(historical_jobs)

    # Add download links
    df["Download"] = df["output_file"].apply(lambda x: f"[Download]({x})" if os.path.exists(x) else "")

    # Select columns to show
    df_display = df[["report_name", "status", "total_keywords", "language", "Download"]]
    df_display.columns = ["Report Name", "Status", "Total Keywords Translated", "Language", "Download Link"]

    # AgGrid for interactive table
    gb = GridOptionsBuilder.from_dataframe(df_display)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_selection(selection_mode="single", use_checkbox=True)
    gb.configure_column("Download Link", cellRenderer='agGroupCellRenderer')
    gridOptions = gb.build()

    AgGrid(df_display, gridOptions=gridOptions, update_mode=GridUpdateMode.SELECTION_CHANGED, fit_columns_on_grid_load=True)

else:
    st.info("No historical reports found yet.")
