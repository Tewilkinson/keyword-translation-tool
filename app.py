with tabs[1]:
    st.subheader("Historical Translation Jobs")

    if not log_df.empty:
        # Prepare table with inline download links
        display_df = log_df.copy()
        display_df["Download Link"] = display_df["output_file"].apply(
            lambda f: f"[Download](./outputs/{f})" if os.path.exists(os.path.join(OUTPUT_DIR, f)) else "Missing"
        )
        display_df.rename(columns={
            "input_file": "File Name",
            "translated_to": "Translated To",
            "total_keywords": "Keywords Translated",
            "status": "Status"
        }, inplace=True)

        # Display markdown table for inline links
        st.markdown(
            display_df.to_markdown(index=False),
            unsafe_allow_html=True
        )

        # Full historical CSV download
        st.download_button(
            label="Download Full Historical Report (CSV)",
            data=open(JOBS_LOG, "rb").read(),
            file_name="translation_jobs_history.csv",
            mime="text/csv"
        )
    else:
        st.info("No translation jobs found yet.")
