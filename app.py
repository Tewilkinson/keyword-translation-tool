import streamlit as st
import pandas as pd
import io
from supabase import create_client, Client
import os
import subprocess

# -----------------------------
# Supabase setup
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="SEO Keyword Translator", layout="wide")

st.title("SEO Keyword Translation Tool")

tab1, tab2 = st.tabs(["Upload & Create Project", "Project Dashboard"])

# -----------------------------
# Tab 1: Upload & Create Project
# -----------------------------
with tab1:
    st.header("Upload Keywords")
    st.write("Upload your Excel file with columns: keyword, category, subcategory, product_category")
    
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    
    # Template download
    output = io.BytesIO()
    template_df = pd.DataFrame({
        "keyword": [],
        "category": [],
        "subcategory": [],
        "product_category": []
    })
    template_df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    st.download_button(
        "Download Template",
        data=output,
        file_name="keyword_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        st.success(f"Uploaded {len(df)} keywords!")
        st.session_state['uploaded_df'] = df  # store in session

        project_name = st.text_input("Project Name")
        target_language = st.selectbox("Select Target Language", [
            "French", "German", "Spanish", "Italian", "Portuguese", "Dutch", "Japanese", "Chinese", "Korean"
        ])

        if st.button("Create Project"):
            if 'uploaded_df' not in st.session_state:
                st.error("Please upload a file first")
            elif not project_name:
                st.error("Please enter a project name")
            else:
                # Insert project into Supabase
                try:
                    project_resp = supabase.table("translation_projects").insert({
                        "name": project_name,
                        "language": target_language,
                        "status": "Pending",
                        "total_keywords": len(df)
                    }).execute()

                    project_id = project_resp.data[0]['id']

                    # Insert keywords into translation_keywords table
                    keyword_records = []
                    for _, row in df.iterrows():
                        keyword_records.append({
                            "project_id": project_id,
                            "keyword": row['keyword'],
                            "category": row.get('category', ''),
                            "subcategory": row.get('subcategory', ''),
                            "product_category": row.get('product_category', ''),
                            "translated_var1": None,
                            "translated_var2": None
                        })
                    # Bulk insert
                    supabase.table("translation_keywords").insert(keyword_records).execute()

                    st.success(f"Project '{project_name}' created! Starting worker...")
                    # Trigger worker.py
                    subprocess.Popen(["python", "worker.py", str(project_id)])
                    st.info("Worker started in background. Go to Project Dashboard to see status.")

                except Exception as e:
                    st.error(f"Error creating project: {e}")

# -----------------------------
# Tab 2: Dashboard
# -----------------------------
with tab2:
    st.header("Project Dashboard")
    projects_resp = supabase.table("translation_projects").select("*").order("created_at", desc=True).execute()
    
    if projects_resp.data:
        projects_df = pd.DataFrame(projects_resp.data)
        projects_df['translated_count'] = 0
        for idx, row in projects_df.iterrows():
            keyword_count_resp = supabase.table("translation_keywords").select("*").eq("project_id", row['id']).execute()
            translated_count = sum(1 for k in keyword_count_resp.data if k.get('translated_var1') or k.get('translated_var2'))
            projects_df.at[idx, 'translated_count'] = translated_count

        st.dataframe(projects_df[['name', 'language', 'status', 'total_keywords', 'translated_count', 'created_at']], use_container_width=True)

        selected_project = st.selectbox("Select Project", projects_df['name'])
        if selected_project:
            project_id = projects_df.loc[projects_df['name'] == selected_project, 'id'].values[0]
            keywords_resp = supabase.table("translation_keywords").select("*").eq("project_id", project_id).execute()
            keywords_df = pd.DataFrame(keywords_resp.data)
            
            st.download_button(
                "Download Translations",
                data=keywords_df.to_csv(index=False).encode('utf-8'),
                file_name=f"{selected_project}_translations.csv",
                mime="text/csv"
            )

            if st.button("Delete Project"):
                supabase.table("translation_keywords").delete().eq("project_id", project_id).execute()
                supabase.table("translation_projects").delete().eq("id", project_id).execute()
                st.success("Project deleted. Please refresh the dashboard.")

    else:
        st.info("No projects yet. Upload keywords and create a project in the first tab.")
