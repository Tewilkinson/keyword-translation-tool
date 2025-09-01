import os
import uuid
import streamlit as st
import pandas as pd

# --- Constants ---
JOBS_LOG = "jobs.csv"
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Ensure jobs.csv exists and has correct headers ---
if not os.path.exists(JOBS_LOG) or os.stat(JOBS_LOG).st_size == 0:
    pd.DataFrame(columns=["job_id", "language", "status", "output_file"]).to_csv(JOBS_LOG, index=False)

st.title("🌍 Keyword Translation Tool")

# --- Step 1: Keyword Input ---
st.subheader("Step 1: Upload or Paste Keywords")

uploaded_file = st.file_uploader("Upload CSV with a 'keyword' column", type=["csv"])
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

# --- Step 2: Select Target Language ---
st.subheader("Step 2: Select Target Language")
language = st.selectbox("Choose a language to translate into:", [
    "Spanish", "French", "German", "Japanese", "Chinese", "Arabic", "Italian"
])

# --- Step 3: Submit Job ---
if st.button("Submit Translation Job") and keywords:
    job_id = str(uuid.uuid4())

    # Save input keywords
    input_df = pd.DataFrame({"keyword": keywords})
    input_file = os.path.join(OUTPUT_DIR, f"{job_id}_input.csv")
    input_df.to_csv(input_file, index=False)

    # Add job to log
    job_log_df = pd.read_csv(JOBS_LOG)
    job_log_df.loc[len(job_log_df)] = [job_id, language, "in_progress", ""]
    job_log_df.to_csv(JOBS_LOG, index=False)

    st.success(f"✅ Job submitted! Job ID: `{job_id}`. Refresh to check status.")

# --- Job History Viewer ---
st.subheader("📄 Translation Jobs")

try:
    job_log_df = pd.read_csv(JOBS_LOG)

    required_cols = {"job_id", "language", "status", "output_file"}
    if required_cols.issubset(job_log_df.columns):
        for _, row in job_log_df.iterrows():
            st.write(f"**Job ID:** {row['job_id']} | Language: {row['language']} | Status: {row['status']}")
            if row["status"] == "complete" and os.path.exists(row["output_file"]):
                with open(row["output_file"], "rb") as f:
                    st.download_button(
                        label="⬇️ Download Translated File",
                        data=f,
                        file_name=os.path.basename(row["output_file"]),
                        mime="text/csv",
                        key=row["job_id"]
                    )
    else:
        st.warning("⚠️ `jobs.csv` is missing required columns. Try resetting the file.")
except Exception as e:
    st.error(f"Error reading jobs log: {e}")

# --- Optional: Reset jobs.csv ---
with st.expander("⚠️ Reset Jobs Log"):
    if st.button("Delete jobs.csv (and start fresh)"):
        if os.path.exists(JOBS_LOG):
            os.remove(JOBS_LOG)
            pd.DataFrame(columns=["job_id", "language", "status", "output_file"]).to_csv(JOBS_LOG, index=False)
            st.success("Jobs log reset.")
