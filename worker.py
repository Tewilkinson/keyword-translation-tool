# worker.py

import os
import sys
import time
import json
import openai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

def get_language(project_id):
    res = supabase.table("translation_projects").select("language").eq("id", project_id).execute()
    return res.data[0]["language"] if res.data else "English"

def generate_prompt(keyword, language, category=None, subcategory=None, product_category=None):
    context = f"You are an SEO expert. Translate the keyword '{keyword}' into {language} as a user would search it online in that language. Provide two natural, SEO-friendly versions."

    if category:
        context += f" The category is '{category}'."
    if subcategory:
        context += f" The subcategory is '{subcategory}'."
    if product_category:
        context += f" The product category is '{product_category}'."

    context += "\nRespond in JSON:\n{\"translated_keyword\": \"...\", \"translated_variable_2\": \"...\"}"
    return context

def translate_keyword(prompt, fallback):
    for _ in range(3):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)
            return parsed.get("translated_keyword", fallback), parsed.get("translated_variable_2", fallback)
        except Exception as e:
            print("Retrying after error:", e)
            time.sleep(2)
    return fallback, fallback

def run_worker(project_id):
    print(f"Running translation for project {project_id}")
    lang = get_language(project_id)

    # Set status
    supabase.table("translation_projects").update({"status": "Running"}).eq("id", project_id).execute()

    # Get keywords
    rows = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute().data
    total = len(rows)
    print(f"{total} keywords found")

    for i, row in enumerate(rows, 1):
        kw = row['keyword']
        prompt = generate_prompt(
            keyword=kw,
            language=lang,
            category=row.get("category"),
            subcategory=row.get("subcategory"),
            product_category=row.get("product_category")
        )
        var1, var2 = translate_keyword(prompt, fallback=kw)
        supabase.table("translation_keywords").update({
            "translated_var1": var1,
            "translated_var2": var2
        }).eq("id", row["id"]).execute()
        print(f"[{i}/{total}] Translated: {kw} → {var1}, {var2}")
        time.sleep(1)  # prevent hitting rate limits

    supabase.table("translation_projects").update({"status": "Completed"}).eq("id", project_id).execute()
    print("✅ Translations complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker.py <project_id>")
        sys.exit(1)
    run_worker(int(sys.argv[1]))
