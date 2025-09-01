import sqlite3
import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import openai

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
DB_FILE = "jobs.db"

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

job_id = int(sys.argv[1])
c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
job = c.fetchone()

if not job:
    print(f"Job ID {job_id} not found.")
    sys.exit()

job_id, filename, target_language, status, created_at, output_file = job
input_path = os.path.join(UPLOAD_DIR, filename)

def translate_keyword(keyword, category, subcategory, product_category, target_language):
    prompt = (
        f"Translate the following keyword into {target_language}. Provide:\n"
        f"1. Direct translation\n"
        f"2. One known variation (synonym or commonly used phrase)\n"
        f"Keep category alignment.\n"
        f"Keyword: \"{keyword}\"\n"
        f"Category: \"{category}\"\n"
        f"Subcategory: \"{subcategory}\"\n"
        f"Product Category: \"{product_category}\"\n"
        f"Return as comma-separated string: direct_translation, variant"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        translation_text = response.choices[0].message.content.strip()
        translations = [t.strip().replace('"', '').replace("'", "") for t in translation_text.split(",")][:2]
        return translations
    except Exception as e:
        return [f"Error: {e}", ""]

# Update job status to Running
c.execute("UPDATE jobs SET status=? WHERE id=?", ("Running", job_id))
conn.commit()

try:
    df = pd.read_excel(input_path)
    translated_keywords = []

    for idx, row in df.iterrows():
        keyword = row["Keyword"]
        category = row.get("Category", "")
        subcategory = row.get("Subcategory", "")
        product_category = row.get("Product Category", "")
        translations = translate_keyword(keyword, category, subcategory, product_category, target_language)
        translated_keywords.append([keyword, category, subcategory, product_category] + translations)

    # Pad to 6 columns
    for i in range(len(translated_keywords)):
        while len(translated_keywords[i]) < 6:
            translated_keywords[i].append("")

    columns = ["Keyword", "Category", "Subcategory", "Product Category", "Translation_1", "Translation_2"]
    translated_df = pd.DataFrame(translated_keywords, columns=columns)

    output_filename = f"translated_{target_language}_{filename}"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    translated_df.to_excel(output_path, index=False)

    # Update job in DB
    c.execute("UPDATE jobs SET status=?, output_file=? WHERE id=?", ("Completed", output_filename, job_id))
    conn.commit()
    print(f"Job {job_id} completed successfully!")

except Exception as e:
    c.execute("UPDATE jobs SET status=? WHERE id=?", (f"Failed: {e}", job_id))
    conn.commit()
    print(f"Job {job_id} failed: {e}")
