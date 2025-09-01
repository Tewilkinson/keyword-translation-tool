# worker.py

import os
import sys
import time
import json
import openai
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# ---------------------
# Setup
# ---------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------
# Helpers
# ---------------------
def chunk_list(lst, n):
    """Split list into n-sized chunks."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def clean_translation(text):
    return text.replace('"', '').replace("'", "").strip()

def get_project_language(project_id):
    resp = supabase.table("translation_projects").select("language").eq("id", project_id).execute()
    return resp.data[0]["language"] if resp.data else "English"

def update_status(project_id, status):
    supabase.table("translation_projects").update({"status": status}).eq("id", project_id).execute()

# ---------------------
# Main Translation Runner
# ---------------------
def run_translation(project_id):
    print(f"🚀 Starting project {project_id}")
    update_status(project_id, "Running")

    # Get project language
    language = get_project_language(project_id)

    # Fetch all keywords
    rows = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute().data
    df = pd.DataFrame(rows)

    if df.empty:
        print("❌ No keywords found.")
        update_status(project_id, "Error")
        return

    translated_var1 = []
    translated_var2 = []

    keywords = df["keyword"].tolist()
    chunk_size = 50
    total_chunks = len(list(chunk_list(keywords, chunk_size)))

    for i, chunk in enumerate(chunk_list(keywords, chunk_size), 1):
        prompt = f"""
You are a multilingual SEO expert. Translate the following keywords into {language} as a native speaker would search them on Google. 
Return only the translated keywords in the same order, no explanations, in JSON format as a list of strings.

Keywords: {chunk}

Format: ["translation1", "translation2", "..."]
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            content = response.choices[0].message.content.strip()
            print(f"[{i}/{total_chunks}] Raw output:", content)

            # Try to parse JSON
            translated_chunk = json.loads(content)
            translated_var1.extend([clean_translation(k) for k in translated_chunk])
            translated_var2.extend([clean_translation(k) + " alt" for k in translated_chunk])  # Fake alt variant

        except Exception as e:
            print(f"❌ Error in chunk {i}: {e}")
            translated_var1.extend([kw for kw in chunk])
            translated_var2.extend([kw for kw in chunk])
            time.sleep(2)

        time.sleep(1)

    # Apply translations
    df["translated_var1"] = translated_var1[:len(df)]
    df["translated_var2"] = translated_var2[:len(df)]

    # Update Supabase row-by-row
    for _, row in df.iterrows():
        supabase.table("translation_keywords").update({
            "translated_var1": row["translated_var1"],
            "translated_var2": row["translated_var2"]
        }).eq("id", row["id"]).execute()

    update_status(project_id, "Completed")
    print("✅ Translations complete.")

# ---------------------
# CLI Entry
# ---------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker.py <project_id>")
        sys.exit(1)

    try:
        run_translation(int(sys.argv[1]))
    except Exception as e:
        print(f"❌ Failed to run worker: {e}")
