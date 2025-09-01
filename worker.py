import json
import os
import sys
from datetime import datetime, timezone
import unicodedata

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# Optional: if ever run inside Streamlit, allow secrets fallback
try:
    import streamlit as st
    HAS_STREAMLIT = True
except Exception:
    HAS_STREAMLIT = False

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
    print("❌ Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY.", file=sys.stderr)
    sys.exit(1)
if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY missing.", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s

def translate_keyword_variants(keyword: str, target_lang: str) -> tuple[str, str]:
    system_msg = (
        "You generate two alternative search keyword phrases based on an input keyword, "
        "then translate them into the target language. Return ONLY strict JSON with keys "
        "`t1` and `t2` (strings)."
    )
    user_msg = json.dumps({"keyword": keyword, "target_language": target_lang}, ensure_ascii=False)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        t1 = nfc((data.get("t1") or "").strip())
        t2 = nfc((data.get("t2") or "").strip())
        return t1, t2
    except Exception as e:
        print(f"❌ OpenAI error for keyword '{keyword}': {e}", file=sys.stderr)
        return "", ""

def main():
    # Connection sanity check
    try:
        supabase.table("translation_jobs").select("id").limit(1).execute()
        print("✅ Supabase connection OK")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    jobs = supabase.table("translation_jobs").select("*").eq("status", "queued").execute().data or []
    if not jobs:
        print("✅ No queued jobs.")
        return

    for job in jobs:
        job_id = job["id"]
        lang = job.get("target_language", "Spanish")
        print(f"🚀 Processing job: {job_id}  (lang={lang})")

        supabase.table("translation_jobs").update({"status": "in_progress"}).eq("id", job_id).execute()

        items = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data or []
        translated_rows = []

        for row in items:
            kw = row.get("keyword", "") or ""
            t1, t2 = translate_keyword_variants(kw, lang)

            supabase.table("translation_items").update({
                "translated_keyword_1": t1,
                "translated_keyword_2": t2,
            }).eq("id", row["id"]).execute()

            row["translated_keyword_1"] = t1
            row["translated_keyword_2"] = t2
            translated_rows.append(row)

        # Build CSV and upload (UTF-8 BOM for Excel)
        df = pd.DataFrame(translated_rows, columns=[
            "keyword", "category", "subcategory", "product_category",
            "translated_keyword_1", "translated_keyword_2"
        ])

        filename = f"translated_{job_id}.csv"
        tmp_path = f"/tmp/{filename}"
        df.to_csv(tmp_path, index=False, encoding="utf-8-sig")

        try:
            with open(tmp_path, "rb") as f:
                supabase.storage.from_("translated_files").upload(
                    f"results/{filename}",
                    f,
                    {"contentType": "text/csv; charset=utf-8", "cacheControl": "3600", "upsert": "true"}
                )
            public_url = supabase.storage.from_("translated_files").get_public_url(f"results/{filename}")
        except Exception as e:
            public_url = None
            print(f"❌ Storage upload failed: {e}", file=sys.stderr)

        supabase.table("translation_jobs").update({
            "status": "completed",
            "download_url": public_url,
        }).eq("id", job_id).execute()

        print(f"✅ Job {job_id} completed. Download: {public_url}")

if __name__ == "__main__":
    main()
