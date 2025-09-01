# app.py
import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime
from supabase import create_client, Client
import openai
import time

# -----------------------------
# Load env variables
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Helper Functions
# -----------------------------
def create_project(project_name: str, language: str):
    project_id = str(uuid.uuid4())
    data = {
        "id": project_id,
        "project_name": project_name,
        "language": language,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending"
    }
    supabase.table("translation_projects").insert(data).execute()
    return project_id

def insert_translation(project_id, row, translated_1, translated_2=None):
    data = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "keyword": row.get("keyword"),
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "product_category": row.get("product_category"),
        "translated_keyword": translated_1,
        "translated_variable_2": translated_2,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("translations").insert(data).execute()

def translate_text(text: str, target_language: str) -> str:
    prompt = f"Translate the following text to {target_language}: '{text}'"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"

def run_translation(project_id, df: pd.DataFrame, language: str):
    supabase.table("translation_projects").update({"status": "running"}).eq("id", project_id).execute()
    for idx, row in df.iterrows():
        translated_1 = translate_text(row["keyword"], language)
        translated_2 = None
        if "subcategory" in df.columns:
            translated_2 = translate_text(row["subcategory"], language)
        insert_translation(project_id, row, translated_1, translated_2)
        time.sleep(1)  # rate limit safety
    supabase.table("translation_projects").update({"status": "completed"}).eq("id", project_id).execute()

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Keyword Translation Tool", layout="wide")
st.title("🌐 Keyword Translation Tool")

tabs = st.tabs(["Upload & Translate", "Historical Projects"])

# -----------------------------
# Tab 1: Upload & Translate
# -----------------------------
with tabs[0]:
    st.subheader("Upload Your Keyword File")
    with st.expander("Download Template"):
        template = pd.DataFrame({
            "keyword": ["example keyword"],
            "category": ["category"],
            "subcategory": ["subcategory"],
            "product_category": ["product category"]
        })
        st.download_button("Download Template", template.to_csv(index=False), "keyword_template.csv", "text/csv")

    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])
    language = st.selectbox("Select Target Language", ["Spanish", "French", "German", "Chinese", "Japanese"])

    project_name = st.text_input("Project Name", value=f"Project_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")

    if uploaded_file is not None and st.button("Run Translation"):
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        project_id = create_project(project_name, language)

        st.info("Translation started. You can close the app; it will continue in the background.")

        # Run translation in background thread
        import threading
        threading.Thread(target=run_translation, args=(project_id, df, language), daemon=True).start()

        st.success(f"Project '{project_name}' submitted! Check Historical Projects tab for progress.")

# -----------------------------
# Tab 2: Historical Projects
# -----------------------------
with tabs[1]:
    st.subheader("Historical Projects")
    projects = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute().data
    projects_df = pd.DataFrame(projects)
    if projects_df.empty:
        st.write("No projects found.")
    else:
        selected_project = st.selectbox("Select Project", projects_df["project_name"])
        project_id = projects_df[projects_df["project_name"] == selected_project]["id"].values[0]
        translations = supabase.table("translations").select("*").eq("project_id", project_id).execute().data
        if translations:
            translations_df = pd.DataFrame(translations)
            st.dataframe(translations_df)
            csv = translations_df.to_csv(index=False)
            st.download_button("Download CSV", csv, f"{selected_project}_translations.csv", "text/csv")
            if st.button("Delete Project"):
                supabase.table("translations").delete().eq("project_id", project_id).execute()
                supabase.table("translation_projects").delete().eq("id", project_id).execute()
                st.experimental_rerun()
        else:
            st.write("No translations found for this project yet.")
