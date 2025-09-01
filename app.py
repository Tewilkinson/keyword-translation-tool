# app.py
import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Upload Tab
# -----------------------------
st.title("Keyword Translation Tool")
tab1, tab2 = st.tabs(["Upload & Create Project", "Historical Projects"])

with tab1:
    st.header("Upload Your Keyword File")

    template_df = pd.DataFrame({
        "keyword": [],
        "category": [],
        "subcategory": [],
        "product_category": []
    })
    st.download_button("Download Template", template_df.to_csv(index=False), file_name="keyword_template.csv")

    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["csv", "xlsx"])
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.dataframe(df.head())

        language = st.selectbox("Select Target Language", ["French", "German", "Spanish", "Chinese", "Japanese"])
        project_name = st.text_input("Project Name", "My Translation Project")

        if st.button("Create Project"):
            # 1️⃣ Create project
            project_resp = supabase.table("translation_projects").insert({
                "project_name": project_name,
                "language": language,
                "status": "pending"
            }).execute()
            project_id = project_resp.data[0]["id"]
            st.success(f"Project created! ID: {project_id}")

            # 2️⃣ Insert rows with null translations
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "project_id": project_id,
                    "keyword": row.get("keyword"),
                    "category": row.get("category"),
                    "subcategory": row.get("subcategory"),
                    "product_category": row.get("product_category"),
                    "translated_keyword": None,
                    "translated_variable_2": None
                })
            supabase.table("translations").insert(rows).execute()
            st.success(f"{len(rows)} keywords inserted. Run worker.py manually with this project ID to translate.")

# -----------------------------
# Historical Tab
# -----------------------------
with tab2:
    st.header("Historical Projects")
    projects_resp = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute()
    projects = projects_resp.data

    if projects:
        for project in projects:
            st.subheader(f"{project['project_name']} ({project['language']}) - Status: {project['status']}")
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button(f"Download {project['project_name']}", key=f"download_{project['id']}"):
                    translations_resp = supabase.table("translations").select("*").eq("project_id", project['id']).execute()
                    translations_df = pd.DataFrame(translations_resp.data)
                    st.download_button(
                        "Download CSV",
                        translations_df.to_csv(index=False),
                        file_name=f"{project['project_name']}_translations.csv"
                    )
            with col2:
                if st.button(f"Delete {project['project_name']}", key=f"delete_{project['id']}"):
                    supabase.table("translation_projects").delete().eq("id", project['id']).execute()
                    st.success(f"Project {project['project_name']} deleted!")
                    st.experimental_rerun()
    else:
        st.info("No projects found.")
