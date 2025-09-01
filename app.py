import streamlit as st
import pandas as pd
import openai
import os
from dotenv import load_dotenv
from datetime import datetime

# ------------------------------
# Load environment variables
# ------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------
# App layout
# ------------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("🌐 Keyword Translation Tool")

# ------------------------------
# Load historical data
# ------------------------------
HISTORY_FILE = "translation_history.csv"

try:
    history_df = pd.read_csv(HISTORY_FILE)
except FileNotFoundError:
    history_df = pd.DataFrame(columns=["Timestamp", "Keyword", "Translation", "Target Language"])

# ------------------------------
# Tabs
# ------------------------------
tabs = st.tabs(["Live Translation", "History"])

# ------------------------------
# Tab 1: Live Translation
# ------------------------------
with tabs[0]:
    st.header("📝 Live Translation")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file with a 'Keyword' column",
        type=["csv", "xlsx"]
    )

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            if "Keyword" not in df.columns:
                st.error("The uploaded file must contain a 'Keyword' column.")
            else:
                st.success(f"Loaded {len(df)} keywords!")

                # Editable table
                st.subheader("Editable Keyword Table")
                df_editor = st.data_editor(
                    df,
                    num_rows="dynamic",
                    use_container_width=True
                )

                # Translation options
                st.subheader("Translation Settings")
                target_language = st.text_input("Target Language", "French")
                translate_button = st.button("Translate Keywords")

                if translate_button:
                    if df_editor.empty:
                        st.warning("No keywords to translate.")
                    else:
                        st.info("Translating keywords... this may take a few seconds.")

                        translations = []
                        for keyword in df_editor["Keyword"]:
                            try:
                                response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=[
                                        {"role": "user", "content": f"Translate '{keyword}' to {target_language} in a concise manner."}
                                    ],
                                    temperature=0
                                )
                                translated = response.choices[0].message.content.strip()
                                translations.append(translated)
                            except Exception as e:
                                translations.append(f"Error: {str(e)}")

                        df_editor["Translation"] = translations
                        df_editor["Target Language"] = target_language
                        df_editor["Timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        
                        st.success("Translation complete!")

                        # Append to history and save
                        history_df = pd.concat([history_df, df_editor[["Timestamp", "Keyword", "Translation", "Target Language"]]], ignore_index=True)
                        history_df.to_csv(HISTORY_FILE, index=False)

                # Show final table
                st.subheader("Final Table")
                st.dataframe(df_editor, use_container_width=True)

                # Download button
                csv_data = df_editor.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Table as CSV",
                    data=csv_data,
                    file_name="translated_keywords.csv",
                    mime="text/csv"
                )

        except Exception as e:
            st.error(f"Error loading file: {e}")
    else:
        st.info("Upload a CSV or Excel file to get started.")

# ------------------------------
# Tab 2: History
# ------------------------------
with tabs[1]:
    st.header("📜 Translation History")
    
    if history_df.empty:
        st.info("No historical data yet.")
    else:
        st.dataframe(history_df.sort_values("Timestamp", ascending=False), use_container_width=True)
        
        # Optional download
        history_csv = history_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full History",
            data=history_csv,
            file_name="translation_history.csv",
            mime="text/csv"
        )
