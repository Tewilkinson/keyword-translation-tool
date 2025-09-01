import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import os
import json
import subprocess

# -------------------------------
# Supabase client
# -------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(page_title="SEO Keyword Translator", layout="wide")
st.title("SEO Keyword Translation Tool")

tab1, tab2 = st.tabs(["Upload & Create Project", "Project Dashboard"])

# -------------------------------
# TAB 1: Upload & Create Project
# -------------------------------
with tab1:
    st.header("Upload your keyword file")

    col1, col2 = st.columns([2,1])
    with col1:
        uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])
    with col2:
        st.download_button(
            "Download Template",
            data=pd.DataFrame({
                "keyword": [],
                "category": [],
                "subcategory": [],
                "product_category": []
            }).to_excel(index=False, engine='openpyxl'),
            file_name="keyword_template.xlsx"
        )

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.success(f"{len(df)} keywords detected.")
            st.session_state["uploaded_df"] = df
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")

    language = st.selectbox("Select target language", ["French","German","Spanish","Italian","Japanese","Chinese","Korean","Portuguese","Russian"])

    project_name = st.text_input("Enter project name")

    if st.button("Create Project"):
        if not uploaded_file or not project_name:
            st.warning("Please upload a file and enter a project name.")
        else:
            # Insert project
            project_resp = supabase.table("translation_projects").insert({
                "name": project_name,
                "language": language,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            if project_resp.status_code != 201:
                st.error(f"Error creating project: {project_resp.data}")
            else:
                project_id = project_resp.data[0]["id"]
                # Insert keywords
                df_insert = []
                for _, row in df.iterrows():
                    df_insert.append({
                        "project_id": project_id,
                        "keyword": row["keyword"],
                        "category": row.get("category"),
                        "subcategory": row.get("subcategory"),
                        "product_category": row.get("product_category"),
                        "translated_keyword": None,
                        "translated_variable_2": None,
                        "created_at": datetime.utcnow().isoformat()
                    })
                kw_resp = supabase.table("translations").insert(df_insert).execute()
                if kw_resp.status_code != 201:
                    st.error(f"Error inserting keywords: {kw_resp.data}")
                else:
                    st.success(f"Project '{project_name}' created with {len(df_insert)} keywords.")
                    st.info(f"To translate keywords, run `worker.py` with Project ID: {project_id}")

# -------------------------------
# TAB 2: Project Dashboard
# -------------------------------
with tab2:
    st.header("Project Dashboard")

    projects_resp = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute()
    if projects_resp.status_code != 200:
        st.error(f"Error fetching projects: {projects_resp.data}")
    else:
        projects = projects_resp.data
        if not projects:
            st.info("No projects yet.")
        else:
            proj_options = {f"{p['name']} ({p['status']})": p["id"] for p in projects}
            selected_proj_name = st.selectbox("Select a project", list(proj_options.keys()))
            selected_proj_id = proj_options[selected_proj_name]

            # Fetch translations
            translations_resp = supabase.table("translations").select("*").eq("project_id", selected_proj_id).execute()
            if translations_resp.status_code != 200:
                st.error(f"Error fetching translations: {translations_resp.data}")
            else:
                translations = translations_resp.data
                total_keywords = len(translations)
                translated_count = sum(1 for t in translations if t["translated_keyword"] and t["translated_variable_2"])

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Keywords", total_keywords)
                col2.metric("Translated Keywords", translated_count)
                col3.metric("Status", next((p["status"] for p in projects if p["id"]==selected_proj_id), "N/A"))

                # Download button
                if st.button("Download Translations"):
                    df_download = pd.DataFrame(translations)
                    df_download = df_download[["keyword","translated_keyword","translated_variable_2","category","subcategory","product_category"]]
                    st.download_button(
                        "Download CSV",
                        df_download.to_csv(index=False),
                        file_name=f"{selected_proj_name}_translations.csv"
                    )

                # Delete project
                if st.button("Delete Project"):
                    supabase.table("translations").delete().eq("project_id", selected_proj_id).execute()
                    supabase.table("translation_projects").delete().eq("id", selected_proj_id).execute()
                    st.success(f"Project '{selected_proj_name}' deleted.")
