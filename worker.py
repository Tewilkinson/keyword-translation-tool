# worker.py
import os
import pandas as pd
from supabase import create_client, Client
import openai
from datetime import datetime
import argparse
import time

# -----------------------------
# Load credentials from environment
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Helper Functions
# -----------------------------
def translate_text(text: str, target_language: str) -> str:
    """Translate a single text string using OpenAI GPT."""
    prompt = f"Translate the following text to {target_language}: '{text}'"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"

def insert_translation(project_id, row, translated_1, translated_2=None):
    """Insert a single translation into Supabase."""
    data = {
        "id": row.get("id") or None,
        "project_id": project_id,
        "keyword": row.get("keyword"),
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "product_category": row.get("product_category"),
        "translated_keyword": translated_1,
        "translated_variable_2": translated_2,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("translations").insert(data).execute()

def run_project_translation(project_id: str):
    """Run translation for a single project by ID."""
    # Fetch the project
    project_resp = supabase.table("translation_projects").select("*").eq("id", project_id).execute()
    if not project_resp.data:
        print(f"Project {project_id} not found!")
        return
    project = project_resp.data[0]
    language = project["language"]

    # Update project status to running
    supabase.table("translation_projects").update({"status": "running"}).eq("id", project_id).execute()

    # Fetch rows with null translations
    rows_resp = supabase.table("translations").select("*").eq("project_id", project_id).execute()
    rows = rows_resp.data

    if not rows:
        print(f"No rows found for project '{project['project_name']}'")
        supabase.table("translation_projects").update({"status": "failed"}).eq("id", project_id).execute()
        return

    print(f"Starting translation for project: {project['project_name']} ({len(rows)} rows)")

    for row in rows:
        # Skip already translated rows
        if row.get("translated_keyword"):
            continue

        translated_1 = translate_text(row["keyword"], language)
        translated_2 = None
        if row.get("subcategory"):
            translated_2 = translate_text(row["subcategory"], language)

        insert_translation(project_id, row, translated_1, translated_2)
        time.sleep(1)  # safety sleep to avoid rate limit

    # Mark project as completed
    supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()
    print(f"Project '{project['project_name']}' completed!")

# -----------------------------
# Command-line Interface
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run keyword translation for a specific project.")
    parser.add_argument("--project_id", required=True, help="The ID of the project to translate")
    args = parser.parse_args()

    run_project_translation(args.project_id)
