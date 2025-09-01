import pandas as pd
import os
import re
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
import csv
from datetime import datetime

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def clean_text(text):
    """Remove extra quotes from translations"""
    return re.sub(r'^"|"$', '', str(text))

def run_translation_job(file_path, target_language):
    # Load Excel
    df = pd.read_excel(file_path)

    # Normalize column names: lowercase and strip spaces
    df.columns = [col.strip().lower() for col in df.columns]

    # Ensure required column exists
    if "keyword" not in df.columns:
        raise ValueError(
            f"Excel must have a 'keyword' column. Found columns: {df.columns.tolist()}"
        )

    translated_keywords = []
    for kw in tqdm(df["keyword"], desc="Translating"):
        prompt = (
            f"Translate this keyword into {target_language}. "
            "Provide 2 translated variants. Respond as comma-separated values."
            f"\nKeyword: {kw}"
        )

        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.choices[0].message.content
        variants = [clean_text(x.strip()) for x in text.split(",")][:2]
        translated_keywords.append(variants)

    # Create DataFrame
    translated_df = pd.DataFrame(translated_keywords, columns=["Translation 1", "Translation 2"])

    # Keep original columns aligned
    output_df = pd.concat([df.reset_index(drop=True), translated_df], axis=1)

    # Save output Excel
    if not os.path.exists("outputs"):
        os.makedirs("outputs")
    output_file = os.path.join("outputs", f"translated_{os.path.basename(file_path)}")
    output_df.to_excel(output_file, index=False)

    # Log job to CSV
    log_file = "jobs_log.csv"
    file_exists = os.path.exists(log_file)
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "input_file", "output_file", "target_language"])
        writer.writerow([datetime.now(), os.path.basename(file_path), os.path.basename(output_file), target_language])

    return output_file
