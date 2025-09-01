import os
import pandas as pd
import openai
from time import sleep

OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)
openai.api_key = os.getenv("OPENAI_API_KEY")

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def clean_translation(text):
    return text.replace('"', '').replace("'", "").strip()

def run_translation_job(input_file, target_language):
    """
    target_language: string, e.g., 'French'
    Each keyword will have up to 2 variations
    """
    df = pd.read_excel(input_file)
    if "keyword" not in df.columns:
        raise ValueError("Excel must have a 'keyword' column")

    keywords = df["keyword"].tolist()
    translated_1 = []
    translated_2 = []

    # Progress generator
    def progress_callback():
        total_chunks = len(list(chunk_list(keywords, 100)))
        for i, chunk in enumerate(chunk_list(keywords, 100), 1):
            prompt = f"""
Translate each of these keywords into {target_language}, providing **up to 2 variations** for each keyword.
Return in the format: translation1 | translation2
If only one translation exists, leave the second blank.
Keep the order the same as the input keywords.
Keywords:
{', '.join(chunk)}
"""
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            # Parse translations
            translated_chunk = response.choices[0].message.content.split(",")
            for item in translated_chunk:
                parts = [clean_translation(x) for x in item.split("|")]
                if len(parts) == 1:
                    parts.append("")  # blank if only 1 variation
                translated_1.append(parts[0])
                translated_2.append(parts[1])
            yield min(int(i * 100 / total_chunks), 100)
            sleep(0.5)

    # Run generator to fill translations
    progress_gen = progress_callback()
    for _ in progress_gen:
        pass

    df["translated_keyword_1"] = translated_1[:len(df)]
    df["translated_keyword_2"] = translated_2[:len(df)]

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
