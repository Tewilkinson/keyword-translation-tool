# worker.py

import os
import sys
import time
import json
import openai
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Connect to Supabase and OpenAI
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

# ------------------------------
# Generate structured prompt
# ------------------------------
def generate_prompt(keyword, language, category=None, subcategory=None, product_category=None):
    parts = [
        f"Translate the keyword: '{keyword}' into {language}.",
        "Return two natural-sounding SEO-friendly keyword variations in that language.",
        "These should reflect what people would actually search locally.",
        "Format your response as valid JSON only:",
        '{"translated_keyword": "...", "translated_variable_2": "..."}'
    ]

    if category:
        parts.append(f"Category: {category}")
    if subcategory:
        parts.append(f"Subcategory: {subcategory}")
    if product_category:
        parts.append(f"Product Category: {product_category}")

    return "\n".join(parts)

# ------------------------------
# Call OpenAI and parse JSON
# ------------------------------
def translate_keyword(prompt, fallback):
    for attempt in range(3):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a multilingual SEO expert. Only return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(content)
                t1 = parsed.get("translated_keyword", fallback)
                t2 = parsed.get("translated_variable_2", fallback)
                return t1.strip(), t2.strip()
            except json.JSONDecodeError:
                print(f"❌ JSON parsing failed:\n{content}")
                return fallback, fallback

        except Exception as e:
            print(f"[Retry {attempt+1}] OpenAI error: {e}")
            time.sleep(2)

    return fallback, fallback

# ------------------------------
# Get language from project
# ------------------------------
def get_language(project_id):
    res = supabase.table("translation_projects").select("language").eq("id", project_id).execute()
    return res.data[0]["language"] if res.data else "English"

# ------------------------------
# Run translations for project
# ------------------------------
def run_worker(project_id):
    print(f"🚀 Running translation for project ID: {project_id}")

    # Update status to Running
    supabase.table("translation_projects").update({"status": "Running"}).eq("id", project_id).execute()

    # Fetch keywords
    rows = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute().data
    lang = get_language(project_id)
    total = len(rows)

    print(f"📦 {total} keywords found.")

    for i, row in enumerate(rows, start=1):
        keyword = row.get("keyword", "")
        category = row.get("category") or ""
        subcategory = row.get("subcategory") or ""
        product_category = row.get("product_category") or ""

        prompt = generate_prompt(keyword, lang, category, subcategory, product_category)
        var1, var2 = translate_keyword(prompt, fallback=keyword)

        supabase.table("translation_keywords").update({
            "translated_var1": var1,
            "translated_var2": var2
        }).eq("id", row["id"]).execute()

        print(f"[{i}/{total}] ✅ {keyword} → {var1}, {var2}")
        time.sleep(1)  # To avoid hitting rate limits

    # Update status to Completed
    supabase.table("translation_projects").update({"status": "Completed"}).eq("id", project_id).execute()
    print(f"🎉 Project {project_id} completed.")

# ------------------------------
# Entry point
# ------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python worker.py <project_id>")
        sys.exit(1)

    try:
        run_worker(int(sys.argv[1]))
    except Exception as e:
        print(f"❌ Failed to run worker: {e}")
