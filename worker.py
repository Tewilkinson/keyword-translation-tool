import os
import sys
import time
import openai
import json
from supabase import create_client, Client

# -----------------------------
# Supabase & OpenAI Setup
# -----------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY:
    raise EnvironmentError("❌ Please set SUPABASE_URL, SUPABASE_KEY, and OPENAI_API_KEY as environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

# -----------------------------
# Translation Logic
# -----------------------------
def generate_prompt(keyword, language, product_category=None, subcategory=None):
    base = f"You're an SEO expert. Translate the keyword '{keyword}' into {language} using natural language that a local user would search. Provide two SEO-friendly variations."

    if product_category:
        base += f" The product category is '{product_category}'."
    if subcategory:
        base += f" The subcategory is '{subcategory}'."

    base += "\nReturn the result in JSON:\n"
    base += '{"translated_keyword": "...", "translated_variable_2": "..."}'

    return base

def translate_keyword(keyword, language, product_category=None, subcategory=None):
    prompt = generate_prompt(keyword, language, product_category, subcategory)

    for attempt in range(3):  # retry up to 3 times
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()

            # Try to parse JSON response
            data = json.loads(content)
            t1 = data.get("translated_keyword", keyword)
            t2 = data.get("translated_variable_2", keyword)
            return t1.strip(), t2.strip()
        except Exception as e:
            print(f"[Retry {attempt+1}] OpenAI error: {e}")
            time.sleep(2)

    # Fallback if all attempts fail
    return keyword, keyword

# -----------------------------
# Run Translations
# -----------------------------
def run_worker(project_id):
    print(f"🚀 Starting translation for Project ID: {project_id}")

    # Mark project as in progress
    supabase.table("translation_projects").update({"status": "Running"}).eq("id", project_id).execute()

    # Fetch keywords for the project
    result = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute()
    rows = result.data or []

    total = len(rows)
    print(f"📦 {total} keywords found.")

    if total == 0:
        supabase.table("translation_projects").update({"status": "Completed"}).eq("id", project_id).execute()
        print("✅ No keywords to process. Project marked as completed.")
        return

    for idx, row in enumerate(rows, 1):
        keyword = row.get("keyword")
        category = row.get("category") or None
        subcategory = row.get("subcategory") or None
        product_category = row.get("product_category") or None
        language = get_project_language(project_id)

        print(f"[{idx}/{total}] Translating: {keyword}")

        var1, var2 = translate_keyword(keyword, language, product_category, subcategory)

        supabase.table("translation_keywords").update({
            "translated_var1": var1,
            "translated_var2": var2
        }).eq("id", row["id"]).execute()

        time.sleep(1)  # avoid rate limits

    # Mark project as completed
    supabase.table("translation_projects").update({"status": "Completed"}).eq("id", project_id).execute()
    print(f"🎉 All done! Project {project_id} marked as Completed.")

# -----------------------------
# Fetch Project Language
# -----------------------------
def get_project_language(project_id):
    res = supabase.table("translation_projects").select("language").eq("id", project_id).execute()
    if res.data and "language" in res.data[0]:
        return res.data[0]["language"]
    return "English"

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker.py <project_id>")
        sys.exit(1)

    try:
        project_id = int(sys.argv[1])
        run_worker(project_id)
    except ValueError:
        print("Invalid Project ID. Must be an integer.")
