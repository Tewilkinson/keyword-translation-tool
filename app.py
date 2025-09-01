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

st.title("🌍 Keyword Translation Tool")

st.markdown("""
Upload a CSV with **columns**: `keyword`, `category`, `subcategory`, `product_category`.  
Only the `keyword` will be translated into **2 variants**, but the other fields will be preserved.
""")

# Language selection
target_language = st.selectbox("Select Target Language", ["Spanish", "French", "German", "Italian", "Japanese"])

# File upload
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

# Paste input
st.markdown("Or paste CSV data:")
pasted_data = st.text_area("Paste CSV-formatted data")

# Handle input
df = None
if uploaded_file:
    df = pd.read_csv(uploaded_file)
elif pasted_data:
    from io import StringIO
    df = pd.read_csv(StringIO(pasted_data))

if df is not None:
    expected_cols = {"keyword", "category", "subcategory", "product_category"}
    if not expected_cols.issubset(df.columns):
        st.error("Missing required columns. Must include: keyword, category, subcategory, product_category.")
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

            # Insert each keyword
            for _, row in df.iterrows():
                supabase.table("translation_items").insert({
                    "job_id": job_id,
                    "keyword": row["keyword"],
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "product_category": row["product_category"]
                }).execute()

            st.success(f"✅ Translation job submitted! Job ID: `{job_id}`")

# View jobs
st.markdown("---")
st.subheader("📥 Recent Jobs")
jobs = supabase.table("translation_jobs").select("*").order("submitted_at", desc=True).limit(10).execute().data

for job in jobs:
    st.write(f"🗂️ Job `{job['id']}` | Status: `{job['status']}` | Language: {job['target_language']} | Submitted: {job['submitted_at']}")
    if job["status"] == "completed" and job.get("download_url"):
        st.markdown(f"[📄 Download Translated CSV]({job['download_url']})")
