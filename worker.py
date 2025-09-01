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

# --- UI ---
st.title("🌍 Keyword Translation Tool")
st.caption(
    "Upload a CSV with **keyword, category, subcategory, product_category**. "
    "Only the **keyword** is translated into **two variants**; other fields are preserved."
)

target_language = st.selectbox(
    "Select Target Language",
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

        if st.button("Submit Translation Job"):
            job_id = str(uuid.uuid4())
            submitted_at = datetime.now(timezone.utc).isoformat()

            supabase.table("translation_jobs").insert({
                "id": job_id,
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

            st.success(f"✅ Job submitted! Job ID: `{job_id}`")

# --- Recent Jobs ---
st.divider()
st.subheader("📄 Recent Translation Jobs")

jobs = (
    supabase.table("translation_jobs")
    .select("*")
    .order("submitted_at", desc=True)
    .limit(25)
    .execute()
    .data or []
)

for job in jobs:
    st.write(
        f"**Job ID:** `{job.get('id')}` | **Status:** `{job.get('status')}` | "
        f"**Language:** {job.get('target_language')} | **Submitted:** {job.get('submitted_at')}"
    )
    items = supabase.table("translation_items").select("id,translated_keyword_1,translated_keyword_2").eq("job_id", job["id"]).execute().data or []
    total = len(items)
    done = sum(1 for r in items if (r.get("translated_keyword_1") or r.get("translated_keyword_2")))
    st.caption(f"Items translated: {done}/{total}")
    if job.get("status") == "completed" and job.get("download_url"):
        st.markdown(f"[📥 Download CSV]({job['download_url']})")

# --- Inline Worker ---
st.divider()
st.subheader("🧪 Debug / Run Worker Inline")

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

        df = pd.DataFrame(
            supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data
        )
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
            public_url = supabase.storage.from_("translated_files").get_public_url(f"results/{fname}")
        except Exception as e:
            public_url = None
            st.error(f"Storage upload failed: {e}")

        supabase.table("translation_jobs").update({
            "status":"completed",
            "download_url": public_url
        }).eq("id", job_id).execute()
        st.success(f"Job `{job_id}` completed. {translated}/{len(rows)} translated. {public_url or ''}")

if st.button("▶️ Process queued jobs now"):
    run_worker_once()
