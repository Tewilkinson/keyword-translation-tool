# worker.py
import os
from supabase import create_client
import openai
import time

# -------------------------------
# Supabase & OpenAI setup
# -------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL") or input("Enter your SUPABASE_URL: ")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or input("Enter your SUPABASE_KEY: ")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or input("Enter your OpenAI API Key: ")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

# -------------------------------
# Helper function for SEO-friendly translation
# -------------------------------
def translate_keyword(keyword: str, language: str):
    """
    Returns two SEO-friendly translations for the keyword in the target language.
    """
    prompt = f"""
You are an expert SEO specialist. Translate the following keyword into {language} not literally, 
but as how people would likely search for it online in {language}. 
Provide **two different natural search-friendly variations**.
Respond in JSON format: {{"translated_keyword": "...", "translated_variable_2": "..."}}
Keyword: "{keyword}"
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        message = response.choices[0].message.content.strip()

        # Extract JSON safely
        import json
        try:
            result = json.loads(message)
            return result.get("translated_keyword"), result.get("translated_variable_2")
        except json.JSONDecodeError:
            # fallback if LLM output is not proper JSON
            lines = message.splitlines()
            return lines[0], lines[1] if len(lines) > 1 else lines[0]

    except Exception as e:
        print(f"Error translating keyword '{keyword}': {e}")
        return None, None

# -------------------------------
# Main worker logic
# -------------------------------
def run_worker(project_id: int):
    # Fetch project info
    project_resp = supabase.table("translation_projects").select("*").eq("id", project_id).execute()
    if not project_resp.data:
        print(f"No project found with ID {project_id}")
        return

    project = project_resp.data[0]
    language = project["language"]
    print(f"Running translations for project '{project['project_name']}' in {language}...")

    # Fetch all keywords for this project that are not yet translated
    keywords_resp = supabase.table("translations").select("*").eq("project_id", project_id).is_("translated_keyword", None).execute()
    keywords = keywords_resp.data
    total = len(keywords)
    print(f"{total} keywords to translate.")

    if total == 0:
        print("All keywords already translated.")
        return

    # Update project status to "in_progress"
    supabase.table("translation_projects").update({"status": "in_progress"}).eq("id", project_id).execute()

    # Translate keywords one by one
    for idx, kw in enumerate(keywords, 1):
        print(f"[{idx}/{total}] Translating '{kw['keyword']}'...")
        translated1, translated2 = translate_keyword(kw["keyword"], language)

        # Update Supabase with translations
        supabase.table("translations").update({
            "translated_keyword": translated1,
            "translated_variable_2": translated2
        }).eq("id", kw["id"]).execute()

        # Optional: short sleep to avoid rate limiting
        time.sleep(0.5)

    # Update project status to "completed"
    supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
    print(f"Project '{project['project_name']}' translations completed!")


# -------------------------------
# CLI entry point
# -------------------------------
if __name__ == "__main__":
    project_id_input = input("Enter Project ID to translate: ")
    try:
        project_id = int(project_id_input)
        run_worker(project_id)
    except ValueError:
        print("Invalid Project ID")
