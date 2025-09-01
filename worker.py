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
# Helper function for SEO-friendly translation
# -------------------------------
def translate_keyword(keyword: str, language: str):
    """
    Returns two SEO-friendly translations for the keyword in the target language.
    """
    prompt = (
You are an SEO expert. Translate the following keyword into {language}, but do NOT translate literally.
Provide how people would search for this keyword online in {language}.
Give **two different variations** as natural search queries.
Respond in JSON format: {{"translated_keyword": "...", "translated_variable_2": "..."}}
Keyword: "{keyword}"
)

    for attempt in range(2):  # retry once
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            message = response.choices[0].message.content.strip()
            # Attempt JSON parse
            data = json.loads(message)
            t1 = data.get("translated_keyword") or keyword
            t2 = data.get("translated_variable_2") or keyword
            return t1, t2
        except Exception:
            time.sleep(1)
            continue
    # fallback if OpenAI response is invalid
    return keyword, keyword

# -------------------------------
# Main worker logic
# -------------------------------
def run_worker(project_id: int):
    # Fetch project info
    project_resp = supabase.table("translation_projects").select("*").eq("id", project_id).execute()
    if project_resp.error:
        print(f"Error fetching project: {project_resp.error}")
        return
    if not project_resp.data:
        print(f"No project found with ID {project_id}")
        return

    project = project_resp.data[0]
    language = project.get("language", "English")
    print(f"Running translations for project '{project['project_name']}' in {language}...")

    # Fetch all keywords not yet translated
    keywords_resp = supabase.table("translations").select("*").eq("project_id", project_id).is_("translated_keyword", None).execute()
    if keywords_resp.error:
        print(f"Error fetching keywords: {keywords_resp.error}")
        return

    keywords = keywords_resp.data
    total = len(keywords)
    print(f"{total} keywords to translate.")

    if total == 0:
        print("All keywords already translated.")
        # Make sure project status is completed
        supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
        return

    # Update project status to "in_progress"
    supabase.table("translation_projects").update({"status": "in_progress"}).eq("id", project_id).execute()

    # Translate keywords
    for idx, kw in enumerate(keywords, 1):
        keyword_text = kw.get("keyword")
        if not keyword_text:
            continue

        print(f"[{idx}/{total}] Translating '{keyword_text}'...")
        t1, t2 = translate_keyword(keyword_text, language)

        # Update Supabase with translations
        update_resp = supabase.table("translations").update({
            "translated_keyword": t1,
            "translated_variable_2": t2
        }).eq("id", kw["id"]).execute()

        if update_resp.error:
            print(f"Error updating keyword '{keyword_text}': {update_resp.error}")

        time.sleep(0.5)  # avoid rate limiting

    # Update project status to "completed"
    supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
    print(f"Project '{project['project_name']}' translations completed!")

# -------------------------------
# CLI entry point
# -------------------------------
if __name__ == "__main__":
    project_id_input = input("Enter Project ID to translate: ")
    try:
        pid = int(project_id_input)
        run_worker(pid)
    except ValueError:
        print("Invalid Project ID")
