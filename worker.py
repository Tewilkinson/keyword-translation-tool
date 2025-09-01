import os
import pandas as pd
import openai
from time import sleep

OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

def chunk_list(lst, n):
    """Yield successive n-sized chunks from list."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def clean_translation(text):
    """Remove extra quotes or whitespace."""
    return text.replace('"', '').replace("'", "").strip()

def run_translation_job(input_file, target_language):
    df = pd.read_excel(input_file)
    if "keyword" not in df.columns:
        raise ValueError("Excel must have a 'keyword' column")

    keywords = df["keyword"].tolist()
    translated_keywords = []

    # Progress generator
    def progress_callback():
        total_chunks = len(list(chunk_list(keywords, 100)))
        for i, chunk in enumerate(chunk_list(keywords, 100), 1):
            prompt = f"""
Translate these keywords into {target_language}, providing **up to 2 variations per keyword** if possible:
{', '.join(chunk)}
Return only the translated keywords in the same order, separated by commas.
"""
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            translated_chunk = response.choices[0].message.content.split(",")
            translated_keywords.extend([clean_translation(k) for k in translated_chunk])
            yield min(int(i * 100 / total_chunks), 100)
            sleep(0.5)  # prevent rate limits

    # Run the generator
    progress_gen = progress_callback()
    for _ in progress_gen:
        pass

    # Add translations to DataFrame
    df["translated_keyword"] = translated_keywords[:len(df)]

    output_file = os.path.join(OUTPUT_DIR, f"translated_{os.path.basename(input_file)}")
    df.to_excel(output_file, index=False)

    # Log job
    if os.path.exists(JOBS_LOG):
        log_df = pd.read_csv(JOBS_LOG)
    else:
        log_df = pd.DataFrame(columns=["input_file", "output_file", "translated_to", "total_keywords", "status"])

    new_row = pd.DataFrame([{
        "input_file": os.path.basename(input_file),
        "output_file": os.path.basename(output_file),
        "translated_to": target_language,
        "total_keywords": len(keywords),
        "status": "Completed"
    }])

    log_df = pd.concat([log_df, new_row], ignore_index=True)
    log_df.to_csv(JOBS_LOG, index=False)

    return output_file, lambda: progress_callback()
