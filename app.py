import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Keyword Project Queue", layout="wide")
st.title("📊 Keyword Project Queue Tool")

# ----------------------
# Session State for Projects
# ----------------------
if "projects" not in st.session_state:
    st.session_state.projects = []

# ----------------------
# Tabs
# ----------------------
tabs = st.tabs(["Upload Project", "History"])

# ----------------------
# Tab 1: Upload Project
# ----------------------
with tabs[0]:
    st.header("📤 Upload Keyword Project")

    uploaded_file = st.file_uploader(
        "Upload a CSV or Excel file with a 'Keyword' column",
        type=["csv", "xlsx"]
    )
    project_name = st.text_input("Project Name")

    if st.button("Submit Project"):
        if not uploaded_file:
            st.error("Please upload a file before submitting.")
        elif not project_name:
            st.error("Please enter a project name.")
        else:
            # Load file just to count keywords
            try:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                if "Keyword" not in df.columns:
                    st.error("Uploaded file must have a 'Keyword' column.")
                else:
                    keyword_count = len(df)
                    
                    # Generate template file
                    template_file_name = f"{project_name.replace(' ', '_')}_template.csv"
                    template_df = pd.DataFrame({
                        "Keyword": df["Keyword"],
                        "Translation": [""] * keyword_count
                    })
                    template_df.to_csv(template_file_name, index=False)

                    # Add to projects queue
                    st.session_state.projects.append({
                        "Timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "Project Name": project_name,
                        "Keyword Count": keyword_count,
                        "Status": "Completed",
                        "File": template_file_name
                    })

                    st.success(f"Project '{project_name}' submitted and template generated!")
                    st.download_button(
                        "📥 Download Template",
                        data=open(template_file_name, "rb"),
                        file_name=template_file_name
                    )

            except Exception as e:
                st.error(f"Error processing file: {e}")

# ----------------------
# Tab 2: History
# ----------------------
with tabs[1]:
    st.header("📜 Historical Projects")

    if not st.session_state.projects:
        st.info("No projects submitted yet.")
    else:
        history_df = pd.DataFrame(st.session_state.projects)
        # Add download links
        history_df_display = history_df.copy()
        history_df_display["Download"] = [
            f"[Download](./{row['File']})" for _, row in history_df.iterrows()
        ]
        st.dataframe(history_df_display[["Timestamp", "Project Name", "Keyword Count", "Status", "Download"]], use_container_width=True)
