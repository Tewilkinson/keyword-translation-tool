# app.py

import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode
import openai
import os
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# -----------------------------
# Streamlit page setup
# -----------------------------
st.set_page_config(
    page_title="Keyword Translation Tool",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 Keyword Translation Tool")
st.markdown(
    """
    Translate your keywords into multiple languages using OpenAI.
    Upload an Excel file or enter keywords manually.
    """
)

# -----------------------------
# User input: upload Excel or manual input
# -----------------------------
uploaded_file = st.file_uploader("Upload Excel with a column 'Keyword'", type=["xlsx", "csv"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    if 'Keyword' not in df.columns:
        st.error("Uploaded file must contain a 'Keyword' column.")
        st.stop()
else:
    raw_keywords = st.text_area("Enter keywords (one per line):")
    df = pd.DataFrame({'Keyword': [k.strip() for k in raw_keywords.splitlines() if k.strip()]})

if df.empty:
    st.warning("No keywords provided yet.")
    st.stop()

# -----------------------------
# Language selection
# -----------------------------
languages = st.multiselect(
    "Select target languages",
    options=["French", "German", "Spanish", "Italian", "Portuguese", "Japanese", "Chinese"],
    default=["French", "German"]
)

if not languages:
    st.warning("Please select at least one target language.")
    st.stop()

# -----------------------------
# Translate function
# -----------------------------
def translate_keyword(keyword, target_language):
    try:
        prompt = f"Translate the following keyword into {target_language}: '{keyword}'"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        translation = response.choices[0].message.content.strip()
        return translation
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return ""

# -----------------------------
# Perform translation
# -----------------------------
st.info(f"Translating {len(df)} keywords into {len(languages)} languages...")
for lang in languages:
    df[lang] = df['Keyword'].apply(lambda k: translate_keyword(k, lang))

# -----------------------------
# Display results with AgGrid
# -----------------------------
st.subheader("Translated Keywords")
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(editable=True, groupable=True)
gridOptions = gb.build()

AgGrid(
    df,
    gridOptions=gridOptions,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    update_mode=GridUpdateMode.VALUE_CHANGED,
    fit_columns_on_grid_load=True,
    enable_enterprise_modules=False
)

# -----------------------------
# Download translated Excel
# -----------------------------
def convert_df_to_excel(df):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    processed_data = output.getvalue()
    return processed_data

excel_data = convert_df_to_excel(df)
st.download_button(
    label="📥 Download Translated Keywords as Excel",
    data=excel_data,
    file_name="translated_keywords.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
