import os
import pandas as pd
import openai
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def translate_keyword_variants(keyword, target_lang):
    prompt = f"""
You are a multilingual keyword assistant. For the keyword below, generate 2 alternative keyword phrases and translate both into {target_lang}.

Keyword: "{keyword}"

Respond ONLY with:
1. [Translation 1]
2. [Translation 2]
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        output = response.choices[0].message.content.strip()
        lines = output.split("\n")
        t1 = lines[0].split(". ", 1)[-1].strip() if len(lines) > 0 else ""
        t2 = lines[1].split(". ", 1)[-1].strip() if len(lines) > 1 else ""
        return t1, t2
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "", ""

def run_worker():
    print("🔄 Worker started...")

    jobs = supabase.table("translation_jobs").select("*").eq("status", "queued").execute().data
    if not jobs:
        print("✅ No queued jobs.")
        return

    for job in jobs:
        job_id = job["id"]
        lang = job["target_language"]
        print(f"🚀 Processing job {job_id} ({lang})")

        supabase.table("translation_jobs").update({"status": "in_progress"}).eq("id", job_id).execute()
        rows = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data
        translated_rows = []

        for row in rows:
            t1, t2 = translate_keyword_variants(row["keyword"], lang)
            supabase.table("translation_items").update({
                "translated_keyword_1": t1,
                "translated_keyword_2": t2
            }).eq("id", row["id"]).execute()
            row["translated_keyword_1"] = t1
            row["translated_keyword_2"] = t2
            translated_rows.append(row)

        df = pd.DataFrame(translated_rows)
        filename = f"translated_{job_id}.csv"
        df.to_csv(filename, index=False)

        with open(filename, "rb") as f:
            supabase.storage.from_("translated_files").upload(f"results/{filename}", f, {"cacheControl": "3600", "upsert": True})
        public_url = supabase.storage.from_("translated_files").get_public_url(f"results/{filename}")

        supabase.table("translation_jobs").update({
            "status": "completed",
            "download_url": public_url
        }).eq("id", job_id).execute()

        print(f"✅ Job {job_id} done!")

if __name__ == "__main__":
    run_worker()
