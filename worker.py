import sys
import os
import openai
from supabase import create_client, Client

import time

import os

# -----------------------------
# Supabase setup
# -----------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "your_url_here"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "your_key_here"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# OpenAI setup
# -----------------------------
openai.api_key = os.environ.get("OPENAI_API_KEY")

# -----------------------------
# Worker
# -----------------------------
if len(sys.argv) < 2:
    print("Usage: python worker.py <project_id>")
    sys.exit(1)

project_id = int(sys.argv[1])
print(f"Worker started for project {project_id}")

# Update project status to Running
supabase.table("translation_projects").update({"status": "Running"}).eq("id", project_id).execute()

# Fetch keywords to translate
keywords_resp = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute()
keywords = keywords_resp.data

for kw in keywords:
    keyword_text = kw['keyword']
    try:
        prompt = f"""
Translate the following SEO keyword for '{kw.get('product_category', '')}' into {kw.get('language', 'English')} in a way that a local would likely search for it. 
Provide 2 variations separated by a comma.
Keyword: {keyword_text}
"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        translation_text = response['choices'][0]['message']['content']
        # Split by comma
        var1, var2 = (translation_text.split(",") + [None, None])[:2]

        # Update keyword
        supabase.table("translation_keywords").update({
            "translated_var1": var1.strip() if var1 else None,
            "translated_var2": var2.strip() if var2 else None
        }).eq("id", kw['id']).execute()
        time.sleep(1)  # small delay to avoid rate limits

    except Exception as e:
        print(f"Error translating keyword {keyword_text}: {e}")

# Update project status to Completed
supabase.table("translation_projects").update({"status": "Completed"}).eq("id", project_id).execute()
print("Worker finished.")
