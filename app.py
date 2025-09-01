# app.py

import streamlit as st
import pandas as pd
import io
import os
from supabase import create_client
from datetime import datetime
from dotenv import load_dotenv

# Load secrets or env vars
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# Tab 1 – Upload & Translate
# ----------------------------
def upload_tab():
    st.header("📤 Upload Keywords for Translation")

    # Downloadable template
    with st.expander("📄 Download Template"):
        output = io.BytesIO()
        df_template = pd.DataFrame({
            "keyword": [],
            "category": [],
            "subcategory": [],
            "product_category": []
        })
        df_template.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)
        st.download_button("Download Excel Template", data=output, file_name="keyword_template.xlsx")

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])
    language = st.selectbox("Select target translation language", ["French", "German", "Spanish", "Japanese", "Korean", "Arabic"])
    project_name = st.text_input("Enter a project name")
    
    if uploaded_file and project_name and language:
        df = pd.read_excel(uploaded_file)
        if "keyword" not in df.columns:
            st.error("❌ 'keyword' column is required.")
            return
        
        st.success(f"{len(df)} keywords ready. Click below to create project.")

        if st.button("✅ Create Project"):
            try:
                df = df.fillna("")
                total = len(df)
                project_resp = supabase.table("translation_projects").insert({
                    "name": project_name,
                    "language": language,
                    "total_keywords": total,
                    "status": "Pending"
                }).execute()

                project_id = project_resp.data[0]['id']

                rows = [{
                    "project_id": project_id,
                    "keyword": row["keyword"],
                    "category": row.get("category", ""),
                    "subcategory": row.get("subcategory", ""),
                    "product_category": row.get("product_category", "")
                } for _, row in df.iterrows()]

                supabase.table("translation_keywords").insert(rows).execute()
                st.success(f"✅ Project '{project_name}' created with {total} keywords.")
            except Exception as e:
                st.error(f"Error creating project: {e}")

# ----------------------------
# Tab 2 – Dashboard
# ----------------------------
def dashboard_tab():
    st.header("📊 Project Dashboard")

    result = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute()
    projects = result.data or []

    if not projects:
        st.info("No projects found.")
        return

    for project in projects:
        st.subheader(f"📁 {project['name']}")
        st.markdown(f"**Language:** {project['language']}  |  **Status:** {project['status']}  |  **Total Keywords:** {project['total_keywords']}  |  Created: {project['created_at'][:10]}")

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button(f"⬇️ Download – {project['name']}", key=f"dl_{project['id']}"):
                rows = supabase.table("translation_keywords").select("*").eq("project_id", project['id']).execute().data
                df = pd.DataFrame(rows)
                if not df.empty:
                    output = io.BytesIO()
                    df.to_excel(output, index=False, engine="openpyxl")
                    output.seek(0)
                    st.download_button("Download Translations", data=output, file_name=f"{project['name']}_translations.xlsx", key=f"db_{project['id']}")
                else:
                    st.warning("No translations found.")

        with col2:
            if st.button(f"🗑 Delete – {project['name']}", key=f"del_{project['id']}"):
                supabase.table("translation_projects").delete().eq("id", project['id']).execute()
                st.warning(f"Deleted project: {project['name']}")
                st.experimental_rerun()

# ----------------------------
# Main UI
# ----------------------------
st.set_page_config(page_title="Keyword Translator", layout="wide")
tabs = st.tabs(["📤 Upload", "📊 Dashboard"])

with tabs[0]:
    upload_tab()
with tabs[1]:
    dashboard_tab()
