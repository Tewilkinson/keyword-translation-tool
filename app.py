# app.py
import os
import pandas as pd
import streamlit as st
from supabase import create_client

# -------------------------------
# Supabase setup
# -------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials are missing in Streamlit secrets!")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(page_title="SEO Keyword Translator", layout="wide")
st.title("SEO Keyword Translation Tool")

tabs = st.tabs(["Upload Keywords", "Projects Dashboard"])

# -------------------------------
# TAB 1: Upload Keywords
# -------------------------------
with tabs[0]:
    st.header("Upload Keywords")
    st.markdown("Download template and upload your keywords Excel file.")

    # Download template
    if st.button("Download Template"):
        template_df = pd.DataFrame(columns=["keyword", "category", "subcategory", "product_category"])
        template_df.to_excel("keyword_template.xlsx", index=False)
        st.download_button("Download Excel Template", data=open("keyword_template.xlsx", "rb"), file_name="keyword_template.xlsx")

    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    language = st.selectbox("Select Target Language", ["Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese"])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df = df.fillna(value=None)  # avoid NaN issues
            st.success(f"{len(df)} keywords detected in uploaded file.")
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
            st.stop()

        project_name = st.text_input("Project Name")
        if st.button("Create Project"):
            if not project_name:
                st.warning("Please enter a project name.")
            else:
                # Insert project
                project_resp = supabase.table("translation_projects").insert({
                    "project_name": project_name,
                    "language": language,
                    "status": "pending"
                }).execute()

                if project_resp.error:
                    st.error(f"Error creating project: {project_resp.error}")
                else:
                    project_id = project_resp.data[0]["id"]

                    # Insert keywords
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

                    st.success(f"Project '{project_name}' created with {len(df)} keywords. Run the worker to start translations.")

# -------------------------------
# TAB 2: Projects Dashboard
# -------------------------------
with tabs[1]:
    st.header("Projects Dashboard")
    projects_resp = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute()

    if projects_resp.error:
        st.error(f"Error fetching projects: {projects_resp.error}")
    elif not projects_resp.data:
        st.info("No projects found.")
    else:
        projects = projects_resp.data
        project_df = pd.DataFrame(projects)

        # Compute translations count
        def get_translation_counts(pid):
            resp = supabase.table("translations").select("*").eq("project_id", pid).execute()
            if resp.error or not resp.data:
                return 0, 0
            total = len(resp.data)
            translated = sum(1 for k in resp.data if k.get("translated_keyword"))
            return total, translated

        counts = [get_translation_counts(p["id"]) for p in projects]
        project_df["keywords_uploaded"] = [c[0] for c in counts]
        project_df["keywords_translated"] = [c[1] for c in counts]

        st.dataframe(project_df[["id", "project_name", "language", "status", "keywords_uploaded", "keywords_translated", "created_at"]])

        # Download and delete buttons
        col1, col2 = st.columns(2)
        with col1:
            selected_id = st.number_input("Enter Project ID to Download CSV", min_value=0, step=1)
            if st.button("Download Project CSV"):
                if selected_id > 0:
                    resp = supabase.table("translations").select("*").eq("project_id", selected_id).execute()
                    if resp.error or not resp.data:
                        st.warning("No data to download")
                    else:
                        df_download = pd.DataFrame(resp.data)
                        st.download_button("Download CSV", df_download.to_csv(index=False), file_name=f"project_{selected_id}.csv")

        with col2:
            delete_id = st.number_input("Enter Project ID to Delete", min_value=0, step=1)
            if st.button("Delete Project"):
                if delete_id > 0:
                    # Delete translations first
                    supabase.table("translations").delete().eq("project_id", delete_id).execute()
                    # Delete project
                    supabase.table("translation_projects").delete().eq("id", delete_id).execute()
                    st.success(f"Project {delete_id} and its keywords deleted.")
