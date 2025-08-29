# keyword_translator_dashboard.py

import streamlit as st
import pandas as pd
import openai
from io import BytesIO
from dotenv import load_dotenv
import os

# --------------------------
# Load environment variables
# --------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --------------------------
# Streamlit App
# --------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("Keyword Translation Tool 🌐")
st.write("Upload your keyword file, select a language, and translate while keeping category alignment intact.")

# --------------------------
# Step 1: Download template
# --------------------------
st.subheader("Download Template")
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
# Step 2: Upload file
# --------------------------
st.subheader("Upload Your Keyword File")
uploaded_file = st.file_uploader("Upload your filled Excel file", type=["xlsx"])

# --------------------------
# Step 3: Select target language
# --------------------------
target_language = st.selectbox(
    "Choose a language to translate keywords into",
    ["Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese", "Korean", "Russian"]
)

# --------------------------
# Initialize dashboard variables
# --------------------------
keywords_loaded = 0
translated_count = 0
est_cost = 0.0

# --------------------------
# Step 4: Show estimated cost
# --------------------------
def estimate_cost(n_keywords):
    # Example: $0.0004 per word
    return round(n_keywords * 0.0004, 4)

df = None
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        keywords_loaded = len(df)
        est_cost = estimate_cost(keywords_loaded)
    except Exception as e:
        st.error(f"Error reading file: {e}")

# --------------------------
# Dashboard at the top
# --------------------------
st.subheader("Translation Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Keywords Loaded", keywords_loaded)
col2.metric("Translated Keywords", translated_count)
col3.metric("Estimated Cost (USD)", f"${est_cost}")

# --------------------------
# Step 5: Translate
# --------------------------
st.subheader("Translate Keywords")

if df is not None and st.button("Translate Keywords"):
    translated_keywords = []
    translated_count = 0
    with st.spinner("Translating keywords..."):
        for _, row in df.iterrows():
            keyword = row["Keyword"]
            category = row.get("Category", "")
            subcategory = row.get("Subcategory", "")
            product_category = row.get("Product Category", "")

            prompt = f"""
Translate the following keyword into {target_language}. Provide:
1. Direct translation
2. Other known variations (synonyms, commonly used phrases)
Keep it aligned with the original category structure.
Keyword: "{keyword}"
Category: "{category}"
Subcategory: "{subcategory}"
Product Category: "{product_category}"
Return as a comma-separated string: direct_translation, variant1, variant2,...
"""

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                translation_text = response["choices"][0]["message"]["content"].strip()
                translations = [t.strip() for t in translation_text.split(",")]
                translated_keywords.append([keyword, category, subcategory, product_category] + translations)
                translated_count += 1
            except Exception as e:
                translated_keywords.append([keyword, category, subcategory, product_category, f"Error: {e}"])

        # Create translated DataFrame
        max_cols = max(len(t) for t in translated_keywords)
        columns = ["Keyword", "Category", "Subcategory", "Product Category"] + [f"Translation_{i}" for i in range(1, max_cols - 3 + 1)]
        translated_df = pd.DataFrame(translated_keywords, columns=columns)

        # Update dashboard metrics
        col2.metric("Translated Keywords", translated_count)

        st.success("✅ Translation complete!")

        # --------------------------
        # Step 6: Download translated file
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

st.info("💡 Note: Make sure your OpenAI API key is set in your .env file as OPENAI_API_KEY.")
