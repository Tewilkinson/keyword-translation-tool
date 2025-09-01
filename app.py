import os
import uuid
import json
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
import io

# --- Load secrets ---
load_dotenv()

def get_secret(name: str, default: str | None = None) -> str | None:
    """Prefer Streamlit secrets on Cloud; fallback to environment variables locally."""
    try:
        if "secrets" in dir(st) and name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials missing. Add SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ---------- Helpers ----------
def ensure_storage_link(job_id: str) -> str | None:
    """(Re)build CSV for a job and upload to Storage; return public (or signed) URL."""
    items = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data or []
    if not items:
        return None
    df = pd.DataFrame(items)
    fname = f"translated_{job_id}.csv"
    tmp = f"/tmp/{fname}"
    df.to_csv(tmp, index=False)

    try:
        with open(tmp, "rb") as f:
            supabase.storage.from_("translated_files").upload(
                f"results/{fname}",
                f,
                {"contentType": "text/csv", "cacheControl": "3600", "upsert": "true"}
            )
        # If bucket is PUBLIC:
        url = supabase.storage.from_("translated_files").get_public_url(f"results/{fname}")
        # If bucket is PRIVATE, switch to signed URL:
        # url = supabase.storage.from_("translated_files").create_signed_url(f"results/{fname}", 60*60)["signedURL"]
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

    supabase.table("translation_jobs").update({"download_url": url}).eq("id", job_id).execute()
    return url

def build_csv_bytes_for_job(job_id: str) -> bytes | None:
    """Build a CSV in memory for instant download."""
    rows = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data or []
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=[
        "keyword", "category", "subcategory", "product_category",
        "translated_keyword_1", "translated_keyword_2"
    ])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def translate_keyword_variants(keyword: str, target_lang: str) -> tuple[str,str]:
    if not openai_client:
        return "",""
    system_msg = (
        "You generate two alternative search keyword phrases based on an input keyword, "
        "then translate them into the target language. Return ONLY strict JSON with keys "
        "`t1` and `t2` (strings)."
    )
    user_msg = json.dumps({"keyword": keyword, "target_language": target_lang}, ensure_ascii=False)
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            response_format={"type":"json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return (data.get("t1") or "").strip(), (data.get("t2") or "").strip()
    except Exception as e:
        st.error(f"OpenAI error for '{keyword}': {e}")
        return "",""

def run_worker_once():
    jobs = supabase.table("translation_jobs").select("*").eq("status","queued").execute().data or []
    if not jobs:
        st.info("No queued jobs.")
        return

    for job in jobs:
        job_id = job["id"]
        lang = job.get("target_language","Spanish")
        st.write(f"Processing job `{job_id}` (lang={lang}) ...")
        supabase.table("translation_jobs").update({"status":"in_progress"}).eq("id", job_id).execute()

        rows = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data or []
        translated = 0
        for r in rows:
            t1, t2 = translate_keyword_variants(r.get("keyword",""), lang)
            supabase.table("translation_items").update({
                "translated_keyword_1": t1,
                "translated_keyword_2": t2,
            }).eq("id", r["id"]).execute()
            if t1 or t2:
                translated += 1

        # Build CSV & upload
        _ = ensure_storage_link(job_id)

        supabase.table("translation_jobs").update({
            "status":"completed",
        }).eq("id", job_id).execute()
        st.success(f"Job `{job_id}` completed. {translated}/{len(rows)} translated.")

# ---------- UI ----------
st.title("🌍 Keyword Translation Tool")
st.caption(
    "Upload a CSV with **keyword, category, subcategory, product_category**. "
    "Only **keyword** is translated into **two variants**; other fields are preserved."
)

# --- Submission form (with Project) ---
with st.expander("➕ Submit a new translation job", expanded=True):
    c1, c2 = st.columns([2,1])
    with c1:
        project_name = st.text_input("Project name (used for download later)", placeholder="e.g., September Batch FR")
    with c2:
        target_language = st.selectbox(
            "Target Language",
            ["Spanish","French","German","Italian","Japanese","Portuguese","Polish","Dutch","Turkish"]
        )

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    st.markdown("Or paste CSV data below:")
    pasted_data = st.text_area("Paste CSV-formatted data matching the required columns")

    def load_df_from_inputs():
        if uploaded_file is not None:
            return pd.read_csv(uploaded_file)
        if pasted_data.strip():
            try:
                return pd.read_csv(StringIO(pasted_data))
            except Exception:
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
        required = {"keyword","category","subcategory","product_category"}
        missing = required - set(df.columns)
        if missing:
            st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        else:
            st.write("Preview:")
            st.dataframe(df.head(200), width='stretch')

            disabled = not project_name.strip()
            if st.button("Submit Translation Job", disabled=disabled):
                job_id = str(uuid.uuid4())
                submitted_at = datetime.now(timezone.utc).isoformat()

                supabase.table("translation_jobs").insert({
                    "id": job_id,
                    "project_name": project_name.strip(),
                    "status": "queued",
                    "submitted_at": submitted_at,
                    "target_language": target_language,
                }).execute()

                rows = [{
                    "job_id": job_id,
                    "keyword": str(r["keyword"]) if pd.notna(r["keyword"]) else "",
                    "category": str(r["category"]) if pd.notna(r["category"]) else "",
                    "subcategory": str(r["subcategory"]) if pd.notna(r["subcategory"]) else "",
                    "product_category": str(r["product_category"]) if pd.notna(r["product_category"]) else "",
                } for _, r in df.iterrows()]

                for i in range(0, len(rows), 500):
                    supabase.table("translation_items").insert(rows[i:i+500]).execute()

                st.success(f"✅ Job submitted for project **{project_name}**! Job ID: `{job_id}`")

st.divider()

# --- Project-based download ---
st.subheader("⬇️ Download by Project")

# Pull recent jobs and derive distinct projects (most-recent first)
jobs_for_projects = (
    supabase.table("translation_jobs")
    .select("id,project_name,submitted_at,status,target_language")
    .order("submitted_at", desc=True)
    .limit(500)
    .execute()
    .data or []
)

# Build project list preserving recency order
project_names = [j["project_name"] for j in jobs_for_projects if j.get("project_name")]
project_names = list(dict.fromkeys(project_names))  # dedupe, keep order

if not project_names:
    st.info("No projects found yet. Submit a job above.")
else:
    selected_project = st.selectbox("Select project", project_names)

    # Jobs for this project, newest first
    proj_jobs = [j for j in jobs_for_projects if j.get("project_name") == selected_project]

    # Prefer latest COMPLETED job; fallback to the newest regardless of status
    latest_completed = next((j for j in proj_jobs if j.get("status") == "completed"), None)
    latest_job = latest_completed or (proj_jobs[0] if proj_jobs else None)

    if latest_job:
        st.write(
            f"Latest job for **{selected_project}** → "
            f"`{latest_job['id']}` | Status: `{latest_job['status']}` | "
            f"Lang: `{latest_job.get('target_language')}`"
        )

        # Only show the direct download button
        csv_bytes = build_csv_bytes_for_job(latest_job["id"])
        if csv_bytes:
            st.download_button(
                label="📥 Download CSV",
                data=csv_bytes,
                file_name=f"translated_{latest_job['id']}.csv",
                mime="text/csv",
                key=f"dl_{latest_job['id']}"
            )
        else:
            st.info("No items found for this job.")


st.divider()
st.subheader("🧪 Debug / Run Worker Inline")

if st.button("▶️ Process queued jobs now"):
    run_worker_once()
