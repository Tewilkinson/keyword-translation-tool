# worker.py

import os
import sys
import time
import json
import openai
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

# ---------------------
# Load environment variables
# ---------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

# ---------------------
# Helpers
# ---------------------
def get_project_language(project_id):
    res = supabase.table("translation_projects").select("language").eq("id", project_id).execute()
    return res.data[0]["language"] if res.data else "English"

def update_status(project_id, status):
    supabase.table("translation_projects").update({"status": status}).eq("id", project_id).execute()

def clean(text):
    return text.replace('"', '').replace("'", '').strip()

# ---------------------
# Translation logic
# ---------------------
def run_translation(project_id):
    print(f"\n🚀 Running translation for project {project_id}")
    update_status(project_id, "Running")

    language = get_project_language(project_id)
    print(f"🌍 Target language: {language}")

    # Fetch all keywords
    rows = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute().data

    if not rows:
        print("❌ No keywords found.")
        update_status(project_id, "Error")
        return

    for i, row in enumerate(rows, 1):
        keyword = row.get("keyword", "")
        if not keyword:
            continue

        prompt = f"""
You are an SEO expert. Translate the following keyword into {language} as a native speaker would search it on Google.

Keyword: {keyword}

Respond only with valid JSON:
{{
  "translated_keyword": "...",
  "translated_variable_2": "..."
}}
        """

        try:
            print(f"\n[{i}] 🔄 Translating: {keyword}")
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Only respond in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )

            raw = response.choices[0].message.content.strip()
            print(f"[{i}] 📥 GPT response:\n{raw}")

            try:
                data = json.loads(raw)
                var1 = clean(data.get("translated_keyword", keyword))
                var2 = clean(data.get("translated_variable_2", keyword + " alt"))
            except json.JSONDecodeError:
                print(f"[{i}] ⚠️ Failed to parse JSON, using fallback.")
                var1 = keyword
                var2 = keyword + " alt"

            # Update in Supabase
            update_resp = supabase.table("translation_keywords").update({
                "translated_var1": var1,
                "translated_var2": var2
            }).eq("id", row["id"]).execute()

            print(f"[{i}] ✅ Updated row ID {row['id']} → {var1} | {var2}")
            time.sleep(1)

        except Exception as e:
            print(f"[{i}] ❌ Error from OpenAI or Supabase: {e}")
            continue

    update_status(project_id, "Completed")
    print("\n🎉 Translations completed and status set to Completed.\n")

# ---------------------
# Entrypoint
# ---------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker.py <project_id>")
        sys.exit(1)

    try:
        run_translation(int(sys.argv[1]))
    except Exception as e:
        print(f"❌ Fatal error: {e}")
