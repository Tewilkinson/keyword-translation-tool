# app.py
import streamlit as st
import pandas as pd
from supabase import create_client
import os

# -------------------------------
# Streamlit page config
# -------------------------------
st.set_page_config(page_title="SEO Keyword Translator", layout="wide")

# -------------------------------
# Supabase connection
# -------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# Tabs
# -------------------------------
tab1, tab2 = st.tabs(["Upload Keywords", "Dashboard"])

# -------------------------------
# Tab 1: Upload Keywords
# -------------------------------
with tab1:
    st.header("Upload Your Keyword File")
    st.markdown(
        """
        Upload an Excel file with the following columns:
        - keyword
        - category
        - subcategory
        - product_category
        
        After uploading, select your target language and create a project.
        """
    )

    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])
    language = st.selectbox(
        "Select Target Language",
        ["French", "German", "Spanish", "Italian", "Portuguese", "Dutch"]
    )

    project_name = st.text_input("Project Name", value="New Project")

    if uploaded_file and st.button("Create Project"):
        try:
            df = pd.read_excel(uploaded_file, engine="openpyxl")
            required_columns = ["keyword", "category", "subcategory", "product_category"]
            if not all(col in df.columns for col in required_columns):
                st.error(f"Uploaded file must contain columns: {required_columns}")
            else:
                # Insert project into Supabase
                project_resp = supabase.table("translation_projects").insert({
                    "project_name": project_name,
                    "language": language,
                    "status": "pending"
                }).execute()

                project_id = project_resp.data[0]["id"]

                # Insert all keywords into translations table (empty translations)
                for _, row in df.iterrows():
                    supabase.table("translations").insert({
                        "project_id": project_id,
                        "keyword": row["keyword"],
                        "category": row["category"],
                        "subcategory": row["subcategory"],
                        "product_category": row["product_category"],
                        "translated_keyword": None,
                        "translated_variable_2": None
                    }).execute()

                st.success(f"Project '{project_name}' created! Project ID: {project_id}")
                st.info("Run worker.py with this Project ID to perform translations in the background.")
        except Exception as e:
            st.error(f"Error reading file: {e}")

# -------------------------------
# Tab 2: Dashboard
# -------------------------------
with tab2:
    st.header("Projects Dashboard")

    try:
        # Total projects
        projects_resp = supabase.table("translation_projects").select("*").execute()
        projects = projects_resp.data
        total_projects = len(projects)

        # Total translations done
        translations_resp = supabase.table("translations").select("*").execute()
        translations = translations_resp.data
        total_translations = sum(1 for t in translations if t.get("translated_keyword"))

        col1, col2 = st.columns(2)
        col1.metric("Total Projects", total_projects)
        col2.metric("Total Translations Completed", total_translations)

        st.markdown("---")
        st.subheader("Recent Projects")
        recent_projects = sorted(projects, key=lambda x: x["created_at"], reverse=True)[:10]
        for p in recent_projects:
            st.write(f"Project: **{p['project_name']}**, Language: {p['language']}, Status: {p['status']}, Created: {p['created_at']}")
    except Exception as e:
        st.error(f"Error fetching dashboard data: {e}")
