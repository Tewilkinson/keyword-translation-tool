import streamlit as st
import pandas as pd
from datetime import datetime
from bokeh.models import ColumnDataSource, HTMLTemplateFormatter, TableColumn
from bokeh.models.widgets import DataTable

# ---------------------------
# Session storage for history
# ---------------------------
if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=[
        "keyword1", "keyword2", "translation1", "translation2", "report_url", "created_at"
    ])

# ---------------------------
# Helper functions
# ---------------------------
def render_history_table():
    df = st.session_state.history
    if df.empty:
        st.info("No translation history yet.")
        return

    df_display = df.copy()
    df_display["Delete"] = df_display.index.astype(str)

    source = ColumnDataSource(df_display)

    report_template = """
    <% if (value) { %>
    <a href="<%= value %>" target="_blank">Download</a>
    <% } else { %>
    -
    <% } %>
    """

    delete_template = """
    <button type="button" onclick="window.dispatchEvent(new CustomEvent('delete_click', {detail: '<%= value %>'}))">Delete</button>
    """

    columns = [
        TableColumn(field="keyword1", title="Keyword 1"),
        TableColumn(field="keyword2", title="Keyword 2"),
        TableColumn(field="translation1", title="Translation 1"),
        TableColumn(field="translation2", title="Translation 2"),
        TableColumn(field="report_url", title="Report", formatter=HTMLTemplateFormatter(template=report_template)),
        TableColumn(field="Delete", title="Delete", formatter=HTMLTemplateFormatter(template=delete_template)),
        TableColumn(field="created_at", title="Submitted At")
    ]

    data_table = DataTable(source=source, columns=columns, width=1000, height=300, sizing_mode="stretch_width")
    st.bokeh_chart(data_table)

    # Delete buttons below table
    for idx, row in df.iterrows():
        if st.button(f"Delete '{row['keyword1']}, {row['keyword2']}'", key=f"del_{idx}"):
            st.session_state.history.drop(idx, inplace=True)
            st.session_state.history.reset_index(drop=True, inplace=True)
            st.experimental_rerun()

# ---------------------------
# Streamlit UI
# ---------------------------
st.title("Keyword Translation Tool")

tabs = st.tabs(["Run Translation", "History"])

with tabs[0]:
    st.header("Upload Keywords for Translation")
    uploaded_file = st.file_uploader("Upload CSV with columns: keyword1, keyword2", type=["csv"])
    if uploaded_file:
        input_df = pd.read_csv(uploaded_file)
        st.dataframe(input_df.head())

        if st.button("Run Translation"):
            # Replace this with your actual translation logic
            translated_df = input_df.copy()
            translated_df["translation1"] = translated_df["keyword1"] + "_translated"
            translated_df["translation2"] = translated_df["keyword2"] + "_translated"
            translated_df["report_url"] = ""  # Add links if you generate downloadable reports
            translated_df["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Append to session history
            st.session_state.history = pd.concat([translated_df, st.session_state.history], ignore_index=True)
            st.success("Translation completed and added to history!")

with tabs[1]:
    st.header("Translation History")
    render_history_table()
