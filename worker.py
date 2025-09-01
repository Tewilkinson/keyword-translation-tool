# worker.py
import os
import time
import json
from supabase import create_client
import openai

# -------------------------------
# Supabase & OpenAI setup
# -------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
    raise ValueError("Please set SUPABASE_URL, SUPABASE_KEY, and OPENAI_API_KEY as environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

# -------------------------------
# Helper: SEO-friendly translation
# -------------------------------
def translate_keyword(keyword: str, language: str):
    prompt = f (
You are an SEO expert. Translate the keyword into {language}, but do not translate literally.
Provide how people would search for this keyword online in {language}.
Return two variations in JSON: {{"translated_keyword": "...", "translated_variable_2": "..."}}
Keyword: "{keyword}"
)
    for attempt in range(2):
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
        except Exception:
            time.sleep(1)
            continue
    return keyword, keyword

# -------------------------------
# Main Worker
# -------------------------------
def run_worker(project_id: int):
    project_resp = supabase.table("translation_projects").select("*").eq("id", project_id).execute()
    if project_resp.error or not project_resp.data:
        print(f"No project found or error: {project_resp.error}")
        return

    project = project_resp.data[0]
    language = project.get("language", "English")
    print(f"Running translations for project '{project['project_name']}' in {language}...")

    keywords_resp = supabase.table("translations").select("*").eq("project_id", project_id).is_("translated_keyword", None).execute()
    if keywords_resp.error or not keywords_resp.data:
        print("No keywords to translate or error.")
        supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
        return

    keywords = keywords_resp.data
    total = len(keywords)
    print(f"{total} keywords to translate.")

    supabase.table("translation_projects").update({"status": "
