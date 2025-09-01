import pandas as pd
import os
import openai
from time import sleep

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs_log.csv"

openai.api_key = os.getenv("OPENAI_API_KEY")

def clean_translation(text):
    return text.replace('"', '').replace("'", "").strip()

def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run_translation_job(input_file, target_language):
    df = pd.read_excel(input_file)
    keywords = df["keyword"].tolist()
    translated_keywords = []

    # Progress callback generator
    def progress_callback():
        total = len(keywords)
        for i, chunk in enumerate(chunk_list(keywords, 100), 1):
            prompt = f"""
Translate these keywords into {target_language}:
{', '.join(chunk)}
Return only the translated keywords in the same order, separated by commas.
"""
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            translated_chunk = response.choices[0].message.content.split(",")
            translated_keywords.extend([clean_translation(k) for k in translated_chunk])
            yield min(int(i * 100 / (len(keywords)/100)), 100)
            sleep(0.5)  # prevent rate limits

    # Run translation
    progress_gen = progress_callback()
    for _ in progress_gen:
        pass  # just iterate to run the job

    df["translated_keyword"] = translated_keywords[:len(df)]
    output_file = os.path.join(OUTPUT_DIR, f"translated_{os.path.basename(input_file)}")
    df.to_excel(output_file, index=False)

    # Log job
    if os.path.exists(JOBS_LOG):
        log_df = pd.read_csv(JOBS_LOG)
    else:
        log_df = pd.DataFrame(columns=["input_file", "output_file", "status", "total_keywords"])
    log_df = log_df.append({
        "input_file": os.path.basename(input_file),
        "output_file": os.path.basename(output_file),
        "status": "Completed",
        "total_keywords": len(keywords)
    }, ignore_index=True)
    log_df.to_csv(JOBS_LOG, index=False)

    return output_file, lambda: progress_callback()

def list_outputs(output_dir):
    return [f for f in os.listdir(output_dir) if f.endswith(".xlsx")]
