import os
import time
import openai
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

JOBS_LOG = "jobs.csv"
OUTPUT_DIR = "outputs"

def translate_keywords(keywords, target_lang):
    chunks = [keywords[i:i+30] for i in range(0, len(keywords), 30)]
    results = []

    for chunk in chunks:
        prompt = f"Translate the following keywords to {target_lang}. Return only the translated keywords in a list:\n" + "\n".join(chunk)
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            translations = response.choices[0].message.content.strip().split("\n")
            results.extend([t.strip() for t in translations])
        except Exception as e:
            print("Error:", e)
            results.extend([""] * len(chunk))

        time.sleep(1)

    return results

def process_jobs():
    if not os.path.exists(JOBS_LOG):
        return

    jobs_df = pd.read_csv(JOBS_LOG)

    for idx, row in jobs_df.iterrows():
        if row["status"] != "in_progress":
            continue

        job_id = row["job_id"]
        target_lang = row["language"]
        input_file = os.path.join(OUTPUT_DIR, f"{job_id}_input.csv")
        output_file = os.path.join(OUTPUT_DIR, f"{job_id}.csv")

        if not os.path.exists(input_file):
            continue

        input_df = pd.read_csv(input_file)
        keywords = input_df["keyword"].dropna().tolist()

        translations = translate_keywords(keywords, target_lang)

        output_df = pd.DataFrame({
            "original": keywords,
            "translated": translations
        })

        output_df.to_csv(output_file, index=False)

        jobs_df.at[idx, "status"] = "complete"
        jobs_df.at[idx, "output_file"] = output_file
        jobs_df.to_csv(JOBS_LOG, index=False)

if __name__ == "__main__":
    while True:
        print("Checking for translation jobs...")
        process_jobs()
        time.sleep(10)  # Run every 10 seconds
