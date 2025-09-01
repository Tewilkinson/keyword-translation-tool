import streamlit as st
import pandas as pd
import os
from worker import run_translation_job

st.set_page_config(page_title="Keyword Translation Tool", layout="wide")

# Ensure folders exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

st.title("Keyword Translation Tool")

# -----------------------------
# Dashboard Score Cards
# -----------------------------
uploaded_files = os.listdir("uploads")
translated_files = os.listdir("outputs")

col1, col2 = st.columns(2)
col1.metric("Keywords Uploaded", len(uploaded_files))
col2.metric("Translations Completed", len(translated_files))

# -----------------------------
# File Upload
# -----------------------------
uploaded_file = st.file_uploader("Upload your keyword Excel file", type=["xlsx"])
target_language = st.selectbox(
    "Select target language",
    ["French", "German", "Spanish", "Italian", "Chinese", "Japanese"]
)

if uploaded_file:
    file_path = os.path.join("uploads", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"File {uploaded_file.name} uploaded successfully!")

    if st.button("Submit Translation Job"):
        with st.spinner("Running translation job..."):
            output_file = run_translation_job(file_path, target_language)
        st.success(f"Translation completed! Download file below:")
        st.download_button(
            label="Download Translated File",
            data=open(output_file, "rb"),
            file_name=os.path.basename(output_file)
        )
