import os
import json
import time
import openai
from supabase import create_client
from datetime import datetime

# -------------------------------
# Supabase & OpenAI
# -------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_KEY

# -------------------------------
# Translate a single keyword
# -------------------------------
def translate_keyword(keyword: str, language: str):
    prompt = (
        f"You are an SEO expert. Translate the keyword into {language}, but do not translate literally.\n"
        f"Provide how people would search for this keyword online in {language}.\n"
        f"Return two variations in JSON format:\n"
        f'{{"translated_keyword": "...", "translated_variable_2": "..."}}\n'
        f'Keyword: "{keyword}"'
    )

    for attempt in range(3):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            message = response.choices[0].message.content.strip()
            data = json.loads(message)
            t1 = data.get("translated_keyword") or keyword
            t2 = data.get("translated_variable_2") or keyword
            return t1, t2
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)
            continue
    return keyword, keyword

# -------------------------------
# Run translations for a project
# -------------------------------
def run_worker(project_id: int):
    print(f"Starting worker for project {project_id}...")
    # Mark project in progress
    supabase.table("translation_projects").update({"status": "in_progress"}).eq("id", project_id).execute()

    # Fetch keywords
    keywords_resp = supabase.table("translations").select("*").eq("project_id", project_id).execute()
    keywords = keywords_resp.data
    total = len(keywords)
    if total == 0:
        print("No keywords to translate.")
        return

    for i, row in enumerate(keywords, 1):
        kw = row.get("keyword")
        if not kw:
            continue
        t1, t2 = translate_keyword(kw, row.get("language", "English"))
        supabase.table("translations").update({
            "translated_keyword": t1,
            "translated_variable_2": t2
        }).eq("id", row["id"]).execute()
        print(f"[{i}/{total}] {kw} → {t1}, {t2}")

    # Mark project complete
    supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
    print("All keywords translated.")

# -------------------------------
# Manual run
# -------------------------------
if __name__ == "__main__":
    project_id = int(input("Enter Project ID to process: "))
    run_worker(project_id)
