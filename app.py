import os
import streamlit as st
import pandas as pd
from worker import run_translation_job
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# -----------------------------
# Directories and logs
# -----------------------------
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
JOBS_LOG = "jobs.csv"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(layout="wide")
st.title("Keyword Translation Tool")

# Load job logs
if os.path.exists(JOBS_LOG):
    log_df = pd.read_csv(JOBS_LOG)
else:
    log_df = pd.DataFrame(columns=["input_file", "output_file", "translated_to", "status", "total_keywords"])

# Scorecards
completed_jobs = len(log_df[log_df["status"] == "Completed"]) if not log_df.empty else 0
total_keywords = log_df["total_keywords"].sum() if not log_df.empty else 0

col1, col2 = st.columns(2)
col1.metric("Completed Jobs", completed_jobs)
col2.metric("Total Keywords Translated", total_keywords)

# Tabs
tabs = st.tabs(["New Translation", "Historical Reports"])

# -----------------------------
# Tab 1: New Translation
# -----------------------------
with tabs[0]:
    st.subheader("Upload Keywords for Translation")
    uploaded_file = st.file_uploader(
        "Upload Excel file with columns: keyword, category, subcategory, product_category",
        type=["xlsx"]
    )

    target_language = st.selectbox(
        "Select target language",
        ["French", "Spanish", "German", "Italian", "Chinese"]
    )

    if uploaded_file:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"File {uploaded_file.name} uploaded successfully.")

        if st.button("Translate"):
            progress_bar = st.progress(0)
            output_file, progress_callback = run_translation_job(file_path, target_language)

            # Iterate progress generator
            for pct in progress_callback():
                progress_bar.progress(pct)

            st.success(f"Translation complete: {output_file}")
            st.download_button(
                "Download Translated Keywords",
                data=open(output_file, "rb").read(),
                file_name=os.path.basename(output_file),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# -----------------------------
# Tab 2: Historical Reports
# -----------------------------
with tabs[1]:
    st.subheader("Historical Translation Jobs")
    if not log_df.empty:
        display_df = log_df.copy()
        display_df["Download"] = "Download"
        display_df["Delete"] = "Delete"

        # AgGrid options
        gb = GridOptionsBuilder.from_dataframe(display_df[["input_file", "translated_to", "total_keywords", "status", "Download", "Delete"]])
        gb.configure_columns(["input_file", "translated_to", "total_keywords", "status"], editable=False)
        # Make action columns buttons
        cell_renderer_js = JsCode("""
        class BtnRenderer {
            init(params) {this.params = params;}
            refresh(params){return true;}
            getGui() {
                const button = document.createElement('button');
                button.innerText = this.params.value;
                button.addEventListener('click', () => {
                    const e = new CustomEvent('buttonClicked', {detail: {rowIndex: this.params.rowIndex, colId: this.params.colDef.field}});
                    window.dispatchEvent(e);
                });
                return button;
            }
        }
        """)
        gb.configure_column("Download", cellRenderer=cell_renderer_js, width=120)
        gb.configure_column("Delete", cellRenderer=cell_renderer_js, width=120)
        grid_options = gb.build()

        grid_response = AgGrid(
            display_df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.NO_UPDATE,
            allow_unsafe_jscode=True,
            fit_columns_on_grid_load=True
        )

        # Handle button events
        st.write("### Actions")
        selected_row_index = st.session_state.get("selected_row_index", None)

        # Custom JS events can't pass directly to Streamlit, so we'll simulate selection
        selected_file_idx = st.number_input("Select row index for action (simulate button click)", min_value=0, max_value=len(display_df)-1, step=1)
        col_action = st.selectbox("Select Action", ["Download", "Delete"])

        if st.button("Run Action"):
            selected_file = display_df.iloc[selected_file_idx]["output_file"]
            file_path = os.path.join(OUTPUT_DIR, selected_file)
            if col_action == "Download":
                if os.path.exists(file_path):
                    st.download_button(
                        label=f"Download {selected_file}",
                        data=open(file_path, "rb").read(),
                        file_name=selected_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("File not found.")
            elif col_action == "Delete":
                confirm = st.radio(f"Are you sure you want to delete '{selected_file}'?", ["No", "Yes"])
                if confirm == "Yes":
                    # Delete file
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    # Remove from log
                    log_df = log_df[log_df["output_file"] != selected_file]
                    log_df.to_csv(JOBS_LOG, index=False)
                    st.success(f"'{selected_file}' deleted successfully.")
                    st.experimental_rerun()

    else:
        st.info("No translation jobs found yet.")
