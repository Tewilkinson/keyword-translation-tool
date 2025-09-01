import streamlit as st
import pandas as pd
from worker import run_translation_job
import os

st.set_page_config(page_title="Keyword Translation Tool", layout="wide")

st.title("Keyword Translation Tool")

# ------------------------------
# Dashboard score cards
# ------------------------------
if os.path.exists("jobs_log.csv"):
    jobs_df = pd.read_csv("jobs_log.csv")
    total_jobs = len(jobs_df)
    total_keywords = 0
    for file in jobs_df["output_file"]:
        df = pd.read_excel(os.path.join("outputs", file))
        total_keywords += len(df)
else:
    total_jobs = 0
    total_keywords = 0

col1, col2 = st.columns(2)
col1.metric("Total Jobs Completed", total_jobs)
col2.metric("Total Keywords Translated", total_keywords)

st.markdown("---")

# ------------------------------
# Upload section
# ------------------------------
st.subheader("Upload Keywords Excel File")
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

target_language = st.selectbox("Select Target Language", ["French", "Spanish", "German", "Italian", "Chinese"])

if uploaded_file:
    file_path = os.path.join("uploads", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"File {uploaded_file.name} uploaded successfully!")

    if st.button("Translate Keywords"):
        with st.spinner("Translating..."):
            output_file = run_translation_job(file_path, target_language)
        st.success(f"Translation completed! File saved to outputs/")
        st.download_button(
            "Download Translated File",
            data=open(output_file, "rb"),
            file_name=os.path.basename(output_file)
        )

# ------------------------------
# Past jobs table with downloads
# ------------------------------
st.subheader("Past Translation Jobs")
if os.path.exists("jobs_log.csv"):
    jobs_df = pd.read_csv("jobs_log.csv")
    jobs_df_sorted = jobs_df.sort_values("timestamp", ascending=False).reset_index(drop=True)

    for i, row in jobs_df_sorted.iterrows():
        col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
        col1.write(row["timestamp"])
        col2.write(row["input_file"])
        col3.write(row["target_language"])
        output_path = os.path.join("outputs", row["output_file"])
        if os.path.exists(output_path):
            col4.download_button(
                "Download Translated Output",
                data=open(output_path, "rb"),
                file_name=row["output_file"]
            )
        else:
            col4.write("File missing")
else:
    st.info("No past translation jobs found.")
