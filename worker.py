import pandas as pd
import os
import uuid
import time
from datetime import datetime
import openai

# -----------------------------
# Directories
# -----------------------------
UPLOADS_DIR = "uploads"
OUTPUTS_DIR = "outputs"

# -----------------------------
# Translation Logic
# -----------------------------
def run_translation_job(file_path, target_language):
    # Load Excel
    df = pd.read_excel(file_path)

    # Check required column
    if "keyword" not in df.columns:
        raise ValueError("Excel must have a 'keyword' column")

    # Prepare translations
    translated_keywords = []
    for _, row in df.iterrows():
        keyword = str(row["keyword"])
        category = row.get("category", "")
        subcategory = row.get("subcategory", "")
        product_category = row.get("product_category", "")

        # Call OpenAI for translations (two variations)
        translation1 = call_openai_translate(keyword, target_language)
        translation2 = call_openai_translate(keyword, target_language, alternative=True)

        # Clean quotes
        translation1 = translation1.replace('"', '').replace("'", "")
        translation2 = translation2.replace('"', '').replace("'", "")

        translated_keywords.append({
            "keyword": keyword,
            "category": category,
            "subcategory": subcategory,
            "product_category": product_category,
            "translation_1": translation1,
            "translation_2": translation2
        })

    # Save output Excel
    output_name = f"{os.path.basename(file_path).split('.')[0]}_translated_{uuid.uuid4().hex[:8]}.xlsx"
    output_path = os.path.join(OUTPUTS_DIR, output_name)
    pd.DataFrame(translated_keywords).to_excel(output_path, index=False)

    # Return path
    return output_path, None

# -----------------------------
# OpenAI translation call
# -----------------------------
def call_openai_translate(keyword, target_language, alternative=False):
    prompt = f"Translate the following keyword into {target_language}. Provide a {'second alternative translation' if alternative else 'primary translation'}: {keyword}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content.strip()
    return text

# -----------------------------
# Historical jobs
# -----------------------------
def get_historical_jobs(outputs_dir):
    jobs = []
    for file in os.listdir(outputs_dir):
        if file.endswith(".xlsx"):
            try:
                df = pd.read_excel(os.path.join(outputs_dir, file))
                jobs.append({
                    "report_name": file.split("_translated_")[0] + ".xlsx",
                    "status": "Completed",
                    "total_keywords": len(df),
                    "language": "Unknown",  # Optionally extract from filename or store in metadata
                    "output_file": os.path.join(outputs_dir, file)
                })
            except:
                continue
    return jobs
