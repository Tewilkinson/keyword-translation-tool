import os
import uuid
import streamlit as st
import pandas as pd

JOBS_LOG = "jobs.csv"
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.title("🌍 Keyword Translation Tool")

# Input keywords
st.subheader("Step 1: Upload or Paste Keywords")
uploaded_file = st.file_uploader("Upload CSV with 'keyword' column", type=["csv"])
keywords = []

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if "keyword" not in df.columns:
        st.error("CSV must contain a 'keyword' column.")
    else:
        keywords = df["keyword"].dropna().tolist()
else:
    text_input = st.text_area("Or paste keywords below (one per line)")
    if text_input:
        keywords = [k.strip() for k in text_input.split("\n") if k.strip()]

if keywords:
    st.success(f"{len(keywords)} keywords loaded.")

# Select language
st.subheader("Step 2: Select Target Language")
language = st.selectbox("Choose a language to translate into:", ["Spanish", "French", "German", "Japanese", "Chinese", "Arabic", "Italian"])

# Submit job
if st.button("Submit Translation Job") and keywords:
    job_id = str(uuid.uuid4())
    job_file = os.path.join(OUTPUT_DIR, f"{job_id}.csv")

    # Save job
    input_df = pd.DataFrame({"keyword": keywords})
    input_df.to_csv(f"{OUTPUT_DIR}/{job_id}_input.csv", index=False)

    # Log job
    job_log_df = pd.read_csv(JOBS_LOG) if os.path.exists(JOBS_LOG) else pd.DataFrame(columns=["job_id", "language", "status", "output_file"])
    job_log_df.loc[len(job_log_df)] = [job_id, language, "in_progress", ""]
    job_log_df.to_csv(JOBS_LOG, index=False)

    st.success(f"✅ Job submitted! Job ID: `{job_id}`. Refresh to check status.")

# Show all jobs
st.subheader("📄 Translation Jobs")
if os.path.exists(JOBS_LOG):
    job_log_df = pd.read_csv(JOBS_LOG)
    for _, row in job_log_df.iterrows():
        st.write(f"**Job ID:** {row['job_id']} | Language: {row['language']} | Status: {row['status']}")
        if row["status"] == "complete" and os.path.exists(row["output_file"]):
            with open(row["output_file"], "rb") as f:
                st.download_button("Download Translated File", f, file_name=os.path.basename(row["output_file"]))
