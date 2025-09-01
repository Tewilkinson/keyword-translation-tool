import os
import pandas as pd
import openai
from supabase import create_client, Client
from dotenv import load_dotenv
import time
import uuid

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def translate(keyword1, keyword2, target_lang):
    prompt = f"""
Translate the following keywords into {target_lang}. Return only the translations, no explanation.

Keyword 1: {keyword1}
Keyword 2: {keyword2}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        result = response.choices[0].message.content.strip().split("\n")
        translated_1 = result[0].replace("Keyword 1: ", "").strip() if len(result) > 0 else ""
        translated_2 = result[1].replace("Keyword 2: ", "").strip() if len(result) > 1 else ""
        return translated_1, translated_2
    except Exception as e:
        print(f"Error: {e}")
        return "", ""

def run_worker():
    print("🔄 Worker running...")

    jobs = supabase.table("translation_jobs").select("*").eq("status", "queued").execute().data
    if not jobs:
        print("✅ No queued jobs found.")
        return

    for job in jobs:
        job_id = job["id"]
        target_lang = job["target_language"]
        print(f"🚀 Processing job {job_id}...")

        # Mark job as in progress
        supabase.table("translation_jobs").update({"status": "in_progress"}).eq("id", job_id).execute()

        # Fetch items
        rows = supabase.table("translation_items").select("*").eq("job_id", job_id).execute().data
        translated_rows = []

        for row in rows:
            translated_1, translated_2 = translate(row["keyword"], row["subcategory"], target_lang)
            update = {
                "translated_keyword_1": translated_1,
                "translated_keyword_2": translated_2,
            }
            supabase.table("translation_items").update(update).eq("id", row["id"]).execute()
            row.update(update)
            translated_rows.append(row)

        # Save result CSV and upload
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

        print(f"✅ Job {job_id} completed!")

if __name__ == "__main__":
    run_worker()
