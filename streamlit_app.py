import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    cam_df = pd.read_csv("data/Factbook_CAM.csv")
    peru_df = pd.read_csv("data/Factbook_Peru.csv")
    factbook_df = pd.concat([cam_df, peru_df], ignore_index=True)
    
    pipeline_df = pd.read_csv("data/Pipeline.csv")
    
    factbook_df['MARCA_CLEAN'] = factbook_df['MARCA'].astype(str).str.strip().str.upper()
    pipeline_df['Name_CLEAN'] = pipeline_df['Name'].astype(str).str.strip().str.upper()
    pipeline_df['Notes'] = pipeline_df['Notes'].astype(str)
    pipeline_df['Tags'] = pipeline_df['Tags'].astype(str)
    
    return factbook_df, pipeline_df

def main():
    st.title("M&A Buy-side Search Tool")

    factbook_df, pipeline_df = load_data()

    search_options = sorted(
        set(factbook_df['MARCA_CLEAN'].dropna()) | set(pipeline_df['Name_CLEAN'].dropna())
    )

    search_term = st.selectbox("Search for a brand or company", search_options)

    if search_term:
        factbook_results = factbook_df[factbook_df['MARCA_CLEAN'] == search_term]

        pipeline_exact = pipeline_df[pipeline_df['Name_CLEAN'] == search_term]
        pipeline_notes_tags = pipeline_df[
            pipeline_df['Notes'].str.upper().str.contains(search_term, na=False) |
            pipeline_df['Tags'].str.upper().str.contains(search_term, na=False)
        ]
        pipeline_results = pd.concat([pipeline_exact, pipeline_notes_tags]).drop_duplicates()

        st.subheader("Factbook Results")
        if not factbook_results.empty:
            st.dataframe(factbook_results)
        else:
            st.info("No Factbook data found for this brand.")

        st.subheader("Pipeline Key Info Summary")
        if not pipeline_results.empty:
            # Get first matching row (or aggregate logic if needed)
            row = pipeline_results.iloc[0]

            # Display filled values
            if pd.notna(row.get('Section/Column')):
                st.write(f"**Section/Column:** {row['Section/Column']}")
            if pd.notna(row.get('Categoría')):
                st.write(f"**Categoría:** {row['Categoría']}")
            if pd.notna(row.get('País')):
                st.write(f"**País:** {row['País']}")
            if pd.notna(row.get('Love brand')):
                st.write(f"**Love brand:** {row['Love brand']}")
            if pd.notna(row.get('Score según matriz')):
                st.write(f"**Score según matriz:** {row['Score según matriz']}")

            st.subheader("Pipeline Full Data")
            st.dataframe(pipeline_results)
        else:
            st.info("No Pipeline data found for this company or related notes/tags.")

        st.subheader("Add a Tag")
        new_tag = st.text_input("Enter a new tag for this search term")
        if st.button("Add Tag"):
            if new_tag.strip():
                if 'tag_log' not in st.session_state:
                    st.session_state['tag_log'] = []
                st.session_state['tag_log'].append({'Search Term': search_term, 'New Tag': new_tag})
                st.success(f"Tag '{new_tag}' added for {search_term}")
            else:
                st.warning("Please enter a valid tag.")

        if 'tag_log' in st.session_state and st.session_state['tag_log']:
            st.write("Added tags this session:")
            st.dataframe(pd.DataFrame(st.session_state['tag_log']))

        combined_csv = pd.concat([factbook_results, pipeline_results], axis=0).to_csv(index=False).encode('utf-8')
        st.download_button("Download Results as CSV", data=combined_csv, file_name="search_results.csv", mime="text/csv")

        if 'tag_log' in st.session_state and st.session_state['tag_log']:
            tag_csv = pd.DataFrame(st.session_state['tag_log']).to_csv(index=False).encode('utf-8')
            st.download_button("Download Added Tags", data=tag_csv, file_name="added_tags.csv", mime="text/csv")

if __name__ == "__main__":
    main()