# app.py

import streamlit as st
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
import openai
import math

# --------------------------
# Load environment variables
# --------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client (v1 API)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --------------------------
# Streamlit App Setup
# --------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("Keyword Translation Tool 🌐")
st.write("Upload your keyword file, select a language, and translate while keeping category alignment intact.")

# --------------------------
# Step 1: Download Template
# --------------------------
template_df = pd.DataFrame(columns=["Keyword", "Category", "Subcategory", "Product Category"])
output_template = BytesIO()
with pd.ExcelWriter(output_template, engine="openpyxl") as writer:
    template_df.to_excel(writer, index=False, sheet_name="Keywords")
output_template.seek(0)

st.download_button(
    label="📥 Download Excel Template",
    data=output_template,
    file_name="keyword_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --------------------------
# Step 2: Upload File
# --------------------------
uploaded_file = st.file_uploader("Upload your filled Excel file", type=["xlsx"])

# --------------------------
# Step 3: Select Target Language
# --------------------------
target_language = st.selectbox(
    "Choose a language to translate keywords into",
    ["Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese", "Korean", "Russian"]
)

# --------------------------
# Step 4: Load uploaded file
# --------------------------
df = None
keywords_loaded = 0
translated_count = 0
est_cost = 0.0

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        keywords_loaded = len(df)
    except Exception as e:
        st.error(f"Error reading file: {e}")

# --------------------------
# Step 5: Dashboard cards at top
# --------------------------
col1, col2, col3 = st.columns(3)
keywords_card = col1.metric("Keywords Loaded", keywords_loaded)
translated_card = col2.metric("Translated Keywords", translated_count)
cost_card = col3.metric("Estimated Cost (USD)", f"${est_cost:.4f}")

# --------------------------
# Step 6: Translate Keywords
# --------------------------
st.subheader("Translate Keywords")

if df is not None and st.button("Translate Keywords"):
    translated_keywords = []
    translated_count = 0

    progress_bar = st.progress(0)
    total_keywords = len(df)

    with st.spinner("Translating keywords..."):
        for idx, row in df.iterrows():
            keyword = row["Keyword"]
            category = row.get("Category", "")
            subcategory = row.get("Subcategory", "")
            product_category = row.get("Product Category", "")

            # Prompt for translation - limit to 2 variants
            prompt = (
                f"Translate the following keyword into {target_language}. Provide:\n"
                f"1. Direct translation\n"
                f"2. One other known variation (synonym or commonly used phrase)\n"
                f"Keep it aligned with the original category structure.\n"
                f"Keyword: \"{keyword}\"\n"
                f"Category: \"{category}\"\n"
                f"Subcategory: \"{subcategory}\"\n"
                f"Product Category: \"{product_category}\"\n"
                f"Return as a comma-separated string: direct_translation, variant"
            )

            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                translation_text = response.choices[0].message.content.strip()
                translations = [t.strip() for t in translation_text.split(",")][:2]  # Only 2 variants
                translated_keywords.append([keyword, category, subcategory, product_category] + translations)
                translated_count += 1

                # Estimate tokens roughly: 1 keyword ~ 20 tokens in prompt, 2 translations ~ 10 tokens
                est_cost += ((20 + 10) / 1000) * 0.06  # $0.06 per 1k tokens GPT-4

            except Exception as e:
                translated_keywords.append([keyword, category, subcategory, product_category, f"Error: {e}"])
            
            progress_bar.progress((idx + 1) / total_keywords)

        # --------------------------
        # Pad rows to same length
        # --------------------------
        max_cols = 6  # 4 original + 2 translations
        for i in range(len(translated_keywords)):
            while len(translated_keywords[i]) < max_cols:
                translated_keywords[i].append("")

        columns = ["Keyword", "Category", "Subcategory", "Product Category", "Translation_1", "Translation_2"]
        translated_df = pd.DataFrame(translated_keywords, columns=columns)

        # Update dashboard cards
        translated_card.metric("Translated Keywords", translated_count)
        cost_card.metric("Estimated Cost (USD)", f"${est_cost:.4f}")

        st.success("✅ Translation complete!")

        # --------------------------
        # Step 7: Download Translated Excel
        # --------------------------
        output_translated = BytesIO()
        with pd.ExcelWriter(output_translated, engine="openpyxl") as writer:
            translated_df.to_excel(writer, index=False, sheet_name="Translated Keywords")
        output_translated.seek(0)

        st.download_button(
            label="📥 Download Translated Excel",
            data=output_translated,
            file_name=f"translated_keywords_{target_language}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.dataframe(translated_df)

