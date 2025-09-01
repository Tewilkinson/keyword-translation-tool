import os
import uuid
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def get_secret(name: str, default: str | None = None) -> str | None:
    # Prefer Streamlit secrets on Streamlit Cloud; fallback to env for local runs.
    try:
        if "secrets" in dir(st) and name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials are missing. Set SUPABASE_URL and SUPABASE_KEY in Streamlit secrets or environment.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🌍 Keyword Translation Tool")
st.markdown(
    "Upload a CSV with columns: **keyword, category, subcategory, product_category**.\n\n"
    "Only **keyword** will be translated into **two variants**. "
    "All other columns are preserved for alignment in Supabase and in the export."
)

# Language selection
target_language = st.selectbox(
    "Select Target Language",
    ["Spanish", "French", "German", "Italian", "Japanese", "Portuguese", "Polish", "Dutch", "Turkish"]
)

# --- INPUT AREA ---
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
st.markdown("Or paste CSV data below:")
pasted_data = st.text_area("Paste CSV-formatted data matching the required columns")

def load_df_from_inputs():
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    if pasted_data.strip():
        # Try CSV first
        try:
            return pd.read_csv(StringIO(pasted_data))
        except Exception:
            # If users paste just keywords (one per line), convert to required schema with blanks
            lines = [ln.strip() for ln in pasted_data.splitlines() if ln.strip()]
            return pd.DataFrame({
                "keyword": lines,
                "category": ["" for _ in lines],
                "subcategory": ["" for _ in lines],
                "product_category": ["" for _ in lines],
            })
    return None

df = load_df_from_inputs()

if df is not None:
    required = {"keyword", "category", "subcategory", "product_category"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Missing required columns: {', '.join(sorted(missing))}")
    else:
        st.write("Preview:")
        st.dataframe(df.head(200), use_container_width=True)

        if st.button("Submit Translation Job"):
            job_id = str(uuid.uuid4())
            submitted_at = datetime.now(timezone.utc).isoformat()

            # Create job
            supabase.table("translation_jobs").insert({
                "id": job_id,
                "status": "queued",
                "submitted_at": submitted_at,
                "target_language": target_language,
            }).execute()

            # Insert items
            rows = []
            for _, r in df.iterrows():
                rows.append({
                    "job_id": job_id,
                    "keyword": str(r["keyword"]) if pd.notna(r["keyword"]) else "",
                    "category": str(r["category"]) if pd.notna(r["category"]) else "",
                    "subcategory": str(r["subcategory"]) if pd.notna(r["subcategory"]) else "",
                    "product_category": str(r["product_category"]) if pd.notna(r["product_category"]) else "",
                })

            # Batch insert in chunks (Supabase can be picky about huge payloads)
            chunk = 500
            for i in range(0, len(rows), chunk):
                supabase.table("translation_items").insert(rows[i:i+chunk]).execute()

            st.success(f"✅ Job submitted! Job ID: `{job_id}`")

st.markdown("---")
st.subheader("📄 Recent Translation Jobs")

try:
    jobs = (
        supabase.table("translation_jobs")
        .select("*")
        .order("submitted_at", desc=True)
        .limit(25)
        .execute()
        .data
    )
except Exception as e:
    st.error(f"Failed to load jobs from Supabase: {e}")
    jobs = []

for job in jobs:
    st.write(
        f"**Job ID:** `{job.get('id')}`  |  "
        f"**Status:** `{job.get('status')}`  |  "
        f"**Language:** {job.get('target_language')}  |  "
        f"**Submitted:** {job.get('submitted_at')}"
    )
    if job.get("status") == "completed" and job.get("download_url"):
        st.markdown(f"[📥 Download CSV]({job['download_url']})")
