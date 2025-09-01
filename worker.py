import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

# Optional import: if worker ever runs inside Streamlit, we can read st.secrets.
try:
    import streamlit as st
    HAS_STREAMLIT = True
except Exception:
    HAS_STREAMLIT = False

from supabase import create_client, Client
from openai import OpenAI

load_dotenv()

def get_secret(name: str, default: str | None = None) -> str | None:
    if HAS_STREAMLIT:
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
    print("❌ Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY in secrets or env.", file=sys.stderr)
    sys.exit(1)

if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY missing. Set it in secrets or env.", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

def translate_keyword_variants(keyword: str, target_lang: str) -> tuple[str, str]:
    """
    Ask the model for two translated variants and force strict JSON so parsing is reliable.
    """
    system_msg = (
        "You generate two alternative search keyword phrases based on an input keyword, "
        "then translate them into the target language. Return ONLY strict JSON with keys "
        "`t1` and `t2` (strings). Do not include extra text."
    )
    user_msg = json.dumps({
        "keyword": keyword,
        "target_language": target_lang
    }, ensure_ascii=False)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # fast, cheap; switch to gpt-4o if you prefer
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        t1 = (data.get("t1") or "").strip()
        t2 = (data.get("t2") or "").strip()
        return t1, t2
    except Exception as e:
        print(f"❌ OpenAI error for keyword '{keyword}': {e}", file=sys.stderr)
        return "", ""

def main():
    # Quick connection test
    try:
        supabase.table("translation_jobs").select("id").limit(1).execute()
        print("✅ Supabase connection OK")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch queued jobs
    jobs_resp = supabase.table("translation_jobs").select("*").eq("status", "queued").execute()
    jobs = jobs_resp.data or []
    if not jobs:
        print("✅ No queued jobs.")
        return

    for job in jobs:
        job_id = job["id"]
        lang = job.get("target_language", "Spanish")

        print(f"🚀 Processing job: {job_id}  (lang={lang})")

        # Mark in progress
        supabase.table("translation_jobs").update({
            "status": "in_progress"
        }).eq("id", job_id).execute()

        # Fetch items for this job
        items_resp = supabase.table("translation_items").select("*").eq("job_id", job_id).execute()
        items = items_resp.data or []
        translated_rows = []

        for row in items:
            kw = row.get("keyword", "") or ""
            t1, t2 = translate_keyword_variants(kw, lang)

            # Update row in DB
            supabase.table("translation_items").update({
                "translated_keyword_1": t1,
                "translated_keyword_2": t2,
            }).eq("id", row["id"]).execute()

            row["translated_keyword_1"] = t1
            row["translated_keyword_2"] = t2
            translated_rows.append(row)

        # Build CSV with preserved alignment
        df = pd.DataFrame(translated_rows, columns=[
            "keyword", "category", "subcategory", "product_category",
            "translated_keyword_1", "translated_keyword_2"
        ])

        # Store in Supabase Storage
        filename = f"translated_{job_id}.csv"
        tmp_path = f"/tmp/{filename}"
        df.to_csv(tmp_path, index=False)

        try:
            with open(tmp_path, "rb") as f:
                supabase.storage.from_("translated_files").upload(
                    f"results/{filename}", f, {"cacheControl": "3600", "upsert": True}
                )
            public_url = supabase.storage.from_("translated_files").get_public_url(f"results/{filename}")
        except Exception as e:
            print(f"❌ Storage upload failed: {e}", file=sys.stderr)
            public_url = None

        # Mark completed
        supabase.table("translation_jobs").update({
            "status": "completed",
            "download_url": public_url,
        }).eq("id", job_id).execute()

        print(f"✅ Job {job_id} completed. Download: {public_url}")

if __name__ == "__main__":
    main()
