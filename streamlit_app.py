import streamlit as st
import pandas as pd
import re
import openai

@st.cache_data
def load_data():
    cam_df = pd.read_csv("data/Factbook_CAM.csv")
    peru_df = pd.read_csv("data/Factbook_Peru.csv")
    factbook_df = pd.concat([cam_df, peru_df], ignore_index=True)

    mapping_df = pd.read_csv("data/Brand_Company_Mapping.csv")
    factbook_df = factbook_df.merge(mapping_df, on="MARCA", how="left")

    pipeline_df = pd.read_csv("data/Pipeline.csv")

    factbook_df['MARCA_CLEAN'] = factbook_df['MARCA'].astype(str).str.strip().str.upper()
    factbook_df['COMPANY_CLEAN'] = factbook_df['Company'].astype(str).str.strip().str.upper()

    pipeline_df['Name_CLEAN'] = pipeline_df['Name'].astype(str).str.strip().str.upper()
    pipeline_df['Notes'] = pipeline_df['Notes'].astype(str)
    pipeline_df['Tags'] = pipeline_df['Tags'].astype(str)

    def standardize_name(name):
        if pd.isna(name):
            return ''
        return re.sub(r'\s*\(.*?\)\s*', '', str(name)).strip().upper()

    factbook_df['STANDARD_NAME'] = factbook_df['MARCA'].apply(standardize_name)
    pipeline_df['STANDARD_NAME'] = pipeline_df['Name'].apply(standardize_name)

    return factbook_df, pipeline_df

def main():
    st.title("M&A PDC Buy-side Search Tool")

    api_key = st.text_input("Enter your OpenAI API key for AI summary", type="password")

    factbook_df, pipeline_df = load_data()

    # Safe build of search strings
    def safe_str(val):
        return str(val).strip().upper() if pd.notna(val) else ""

    def build_search_string(row):
        marca = str(row['MARCA']).strip() if pd.notna(row['MARCA']) else ""
        std_name = str(row['STANDARD_NAME']).strip() if pd.notna(row['STANDARD_NAME']) else ""
        if safe_str(row['MARCA']) == safe_str(row['STANDARD_NAME']):
            return marca
        else:
            return f"{marca} - {std_name}"

    search_strings = factbook_df.apply(build_search_string, axis=1).dropna().unique()
    search_options = sorted(search_strings)

    search_display = st.selectbox("Search for a brand or company", search_options)

    if search_display:
        if " - " in search_display:
            search_term = search_display.split(" - ")[-1].strip().upper()
        else:
            search_term = search_display.strip().upper()

        factbook_results = factbook_df[
            (factbook_df['STANDARD_NAME'] == search_term) |
            (factbook_df['COMPANY_CLEAN'] == search_term)
        ]

        pipeline_results = pipeline_df[
            (pipeline_df['STANDARD_NAME'] == search_term) |
            (pipeline_df['Notes'].str.upper().str.contains(search_term, na=False)) |
            (pipeline_df['Tags'].str.upper().str.contains(search_term, na=False))
        ]

        merged_results = factbook_results.merge(
            pipeline_df,
            on="STANDARD_NAME",
            how="left",
            suffixes=('_Factbook', '_Pipeline')
        )

        if 'tag_log' in st.session_state and st.session_state['tag_log']:
            tag_df = pd.DataFrame(st.session_state['tag_log'])
            if not merged_results.empty:
                merged_results['Added Tags'] = merged_results['STANDARD_NAME'].map(
                    lambda name: ", ".join(tag_df.loc[tag_df['Search Term'] == name, 'New Tag'].tolist())
                )
            elif not pipeline_results.empty:
                pipeline_results['Added Tags'] = pipeline_results['STANDARD_NAME'].map(
                    lambda name: ", ".join(tag_df.loc[tag_df['Search Term'] == name, 'New Tag'].tolist())
                )

        cols_to_hide = [
            'Task ID', 'Created At', 'Completed At', 'Last Modified', 'Name',
            'Assignee', 'Assignee Email', 'Start Date', 'Due Date', 'Notes',
            'Parent task', 'Blocking (Dependencies)', 'Blocked By (Dependencies)',
            'Link ficha de candidato', 'Activo / inactivo', 'Fecha último contacto',
            'Name_CLEAN', 'BU', 'STANDARD_NAME'
        ]

        clean_cols = [col for col in merged_results.columns if col not in cols_to_hide]

        st.subheader("Pipeline Key Info Summary")
        display_row = None
        if not merged_results.empty:
            display_row = merged_results.iloc[0]
        elif not pipeline_results.empty:
            display_row = pipeline_results.iloc[0]

        if display_row is not None:
            if pd.notna(display_row.get('Section/Column')):
                st.write(f"**Section/Column:** {display_row['Section/Column']}")
            if pd.notna(display_row.get('Categoría')):
                st.write(f"**Categoría:** {display_row['Categoría']}")
            if pd.notna(display_row.get('País')):
                st.write(f"**País:** {display_row['País']}")
            if pd.notna(display_row.get('Love brand')):
                st.write(f"**Love brand:** {display_row['Love brand']}")
            if pd.notna(display_row.get('Score según matriz')):
                st.write(f"**Score según matriz:** {display_row['Score según matriz']}")
        else:
            st.info("No Pipeline data found for this search term.")

        st.subheader("Table Results")
        if not merged_results.empty:
            final_cols = clean_cols
            if 'Added Tags' in merged_results.columns and 'Added Tags' not in clean_cols:
                final_cols = clean_cols + ['Added Tags']
            st.dataframe(merged_results[final_cols])
        elif not pipeline_results.empty:
            cols_to_show = [col for col in pipeline_results.columns if col not in cols_to_hide]
            if 'Added Tags' in pipeline_results.columns and 'Added Tags' not in cols_to_show:
                cols_to_show += ['Added Tags']
            st.dataframe(pipeline_results[cols_to_show])
        else:
            st.info("No merged or Pipeline data found for this search term.")

        st.subheader("AI Summary (Ownership & Brand Info)")
        
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            if st.button("Generate AI Summary"):
                with st.spinner("Generating summary..."):
                    try:
                        prompt = (
                            f"You are a factual assistant for M&A research. "
                            f"Summarize publicly known facts about the latin american brand {search_term}. "
                            f"Give a very brief overview of the brand. Then,  if possible mention brand ownership, parent company, and corporate structure. "
                            f"Do not speculate or fabricate information. If no public information is known, say so. Make the entire answer very direct and concise. "
                        )
                        response = client.chat.completions.create(
                            model="gpt-4",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=300
                        )
                        summary = response.choices[0].message.content.strip()
                        st.success("AI Summary generated:")
                        st.write(summary)
                    except Exception as e:
                        st.error(f"Error generating summary: {str(e)}")

        st.subheader("Add a Tag")
        new_tag = st.text_input("Enter a new tag for this search term", key="new_tag_input")
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

if __name__ == "__main__":
    main()