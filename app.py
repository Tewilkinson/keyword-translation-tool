import streamlit as st
import pandas as pd
from datetime import datetime

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

    # Dropdown for target language
    target_language = st.selectbox(
        "Select Target Language",
        options=[
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Chinese", "Japanese", "Korean"
        ]
    )

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
                    template_file_name = f"{project_name.replace(' ', '_')}_{target_language}.csv"
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
                        "Target Language": target_language,
                        "Status": "Completed",
                        "File": template_file_name
                    })

                    st.success(f"Project '{project_name}' submitted for {target_language}!")
                    st.download_button(
                        "📥 Download Template",
                        data=open(template_file_name, "rb"),
                        file_name=template_file_name
                    )

            except Exception as e:
                st.error(f"Error reading uploaded file: {e}")

# ----------------------
# Tab 2: History
# ----------------------
with tabs[1]:
    st.header("📜 Historical Projects")

    if not st.session_state.projects:
        st.info("No projects submitted yet.")
    else:
        history_df = pd.DataFrame(st.session_state.projects)
        # Show table with download buttons
        st.write("Here is your historical project log:")
        for i, row in history_df.iterrows():
            st.write(
                f"**{row['Project Name']}** | Keywords: {row['Keyword Count']} | Language: {row['Target Language']} | Status: {row['Status']}"
            )
            st.download_button(
                "📥 Download File",
                data=open(row['File'], "rb"),
                file_name=row['File'],
                key=f"download_{i}"
            )
