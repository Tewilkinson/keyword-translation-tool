import streamlit as st
import pandas as pd
import uuid
import datetime
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🌍 Bulk Keyword Translation Tool")

st.markdown("""
Upload a CSV file or paste a list of keywords.  
The system will generate and translate **two variants** for each keyword using OpenAI.
""")

# Language selection
target_language = st.selectbox("Select Target Language", ["Spanish", "French", "German", "Italian", "Japanese"])

# File upload
uploaded_file = st.file_uploader("Upload CSV with one column: keyword", type=["csv"])

# Paste input
st.markdown("Or paste keywords (one per line) below:")
pasted_data = st.text_area("Paste keywords")

# Handle input
df = None
if uploaded_file:
    df = pd.read_csv(uploaded_file)
elif pasted_data:
    df = pd.DataFrame({"keyword": [line.strip() for line in pasted_data.splitlines() if line.strip()]})

if df is not None:
    if "keyword" not in df.columns:
        st.error("CSV must contain a 'keyword' column.")
    else:
        st.dataframe(df)
        if st.button("Submit Translation Job"):
            job_id = str(uuid.uuid4())
            submitted_at = datetime.datetime.utcnow().isoformat()

            # Create translation job
            supabase.table("translation_jobs").insert({
                "id": job_id,
                "status": "queued",
                "submitted_at": submitted_at,
                "target_language": target_language
            }).execute()

            # Add keyword rows to translation_items
            for _, row in df.iterrows():
                supabase.table("translation_items").insert({
                    "job_id": job_id,
                    "keyword": row["keyword"]
                }).execute()

            st.success(f"✅ Translation job submitted! Job ID: `{job_id}`")

# Job status viewer
st.markdown("---")
st.subheader("📥 View Recent Jobs")
jobs = supabase.table("translation_jobs").select("*").order("submitted_at", desc=True).limit(10).execute().data

for job in jobs:
    st.write(f"🗂️ Job ID: `{job['id']}` | Status: `{job['status']}` | Language: {job['target_language']} | Submitted: {job['submitted_at']}")
    if job["status"] == "completed" and job.get("download_url"):
        st.markdown(f"[📄 Download Translated File]({job['download_url']})")
