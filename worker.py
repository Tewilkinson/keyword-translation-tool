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

def run_translation_job(input_file, target_language, project_name):
    df = pd.read_excel(input_file)
    if "keyword" not in df.columns:
        raise ValueError("Excel must have a 'keyword' column")

    keywords = df["keyword"].tolist()
    translation_1 = []
    translation_2 = []

    # Progress generator
    def progress_callback():
        total_chunks = len(list(chunk_list(keywords, 50)))
        for i, chunk in enumerate(chunk_list(keywords, 50), 1):
            prompt = f"""
Translate the following keywords into {target_language}. For each keyword, provide two distinct, natural-sounding translations.

Respond in table format with three columns: Keyword | Translation 1 | Translation 2

Keywords:
{', '.join(chunk)}
"""
            try:
                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                content = response.choices[0].message.content

                # Parse table from markdown format
                table = pd.read_csv(pd.compat.StringIO(content), sep="|", engine="python")
                table.columns = [col.strip() for col in table.columns]
                table = table.dropna(how="all")

                translation_1.extend(table["Translation 1"].map(clean_translation).tolist())
                translation_2.extend(table["Translation 2"].map(clean_translation).tolist())

            except Exception as e:
                print(f"Error during chunk {i}: {e}")
                # Fallback: duplicate keywords if failed
                translation_1.extend([""] * len(chunk))
                translation_2.extend([""] * len(chunk))

            yield min(int(i * 100 / total_chunks), 100)
            sleep(0.5)  # avoid rate limits

    # Run generator to collect translations
    progress_gen = progress_callback()
    for _ in progress_gen:
        pass

    df["Translation 1"] = translation_1[:len(df)]
    df["Translation 2"] = translation_2[:len(df)]

    output_file = os.path.join(OUTPUT_DIR, f"translated_{os.path.basename(input_file)}")
    df.to_excel(output_file, index=False)

    # Log job
    if os.path.exists(JOBS_LOG):
        log_df = pd.read_csv(JOBS_LOG)
    else:
        log_df = pd.DataFrame(columns=["input_file", "output_file", "status", "total_keywords", "project"])

    new_row = pd.DataFrame([{
        "input_file": os.path.basename(input_file),
        "output_file": os.path.basename(output_file),
        "status": "Completed",
        "total_keywords": len(keywords),
        "project": project_name
    }])

    log_df = pd.concat([log_df, new_row], ignore_index=True)
    log_df.to_csv(JOBS_LOG, index=False)

    return output_file, lambda: progress_callback()
