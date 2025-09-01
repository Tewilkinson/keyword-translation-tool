# worker.py
import os
import pandas as pd
import openai
import time
from datetime import datetime

openai.api_key = os.getenv("OPENAI_API_KEY")

UPLOADS_DIR = "uploads"
OUTPUTS_DIR = "outputs"
JOBS_LOG = "jobs_log.csv"

BATCH_SIZE = 50
VARIANTS = 2

def clean_translation(text):
    if not isinstance(text, str):
        return text
    return text.strip().strip('"').strip("'")

def run_translation_job(input_file_path, target_language):
    df = pd.read_excel(input_file_path)
    if "keyword" not in df.columns:
        raise ValueError("Excel must have a 'keyword' column")

    keywords = df["keyword"].tolist()
    total_keywords = len(keywords)
    translated_rows = []

    output_file_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(input_file_path)}"
    output_file_path = os.path.join(OUTPUTS_DIR, output_file_name)

    # Initialize job log
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "input_file": os.path.basename(input_file_path),
        "output_file": output_file_name,
        "target_language": target_language,
        "total_keywords": total_keywords,
        "progress_percent": 0,
        "status": "Running"
    }
    if os.path.exists(JOBS_LOG):
        log_df = pd.read_csv(JOBS_LOG)
        log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        log_df = pd.DataFrame([log_entry])
    log_df.to_csv(JOBS_LOG, index=False)

    for i in range(0, total_keywords, BATCH_SIZE):
        batch_keywords = keywords[i:i+BATCH_SIZE]

        prompt = f"""
Translate the following keywords into {target_language}.
Provide {VARIANTS} distinct translations for each keyword.
Return the result in the format: keyword | translation1 | translation2
Here are the keywords:
"""
        for kw in batch_keywords:
            prompt += f"{kw}\n"

        success = False
        while not success:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                )
                output_text = response.choices[0].message.content
                success = True
            except openai.error.RateLimitError:
                print("Rate limit hit, waiting 10 seconds...")
                time.sleep(10)
            except Exception as e:
                print("OpenAI API error:", e)
                time.sleep(5)

        for line in output_text.splitlines():
            parts = [clean_translation(p.strip()) for p in line.split("|")]
            if len(parts) == 1:
                parts = [parts[0], "", ""]
            elif len(parts) == 2:
                parts.append("")
            translated_rows.append(parts)

        # Update progress in log
        progress = min(100, int(((i + BATCH_SIZE) / total_keywords) * 100))
        log_df.loc[log_df['output_file'] == output_file_name, 'progress_percent'] = progress
        log_df.to_csv(JOBS_LOG, index=False)

    # Build final DataFrame
    translated_df = pd.DataFrame(translated_rows, columns=["keyword", "translation1", "translation2"])
    for col in df.columns:
        if col != "keyword":
            translated_df[col] = df[col]

    # Save output Excel
    translated_df.to_excel(output_file_path, index=False)

    # Mark job complete
    log_df.loc[log_df['output_file'] == output_file_name, 'progress_percent'] = 100
    log_df.loc[log_df['output_file'] == output_file_name, 'status'] = "Completed"
    log_df.to_csv(JOBS_LOG, index=False)

    return output_file_path
