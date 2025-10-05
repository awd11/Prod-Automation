import streamlit as st
import pandas as pd
from sharepoint_client import SharePointClient
from datetime import datetime

st.set_page_config(page_title="Internal Tickets Tracker", layout="wide")
st.title("SharePoint — Internal Tickets Dashboard")

# Sidebar: credentials & list selection
st.sidebar.header("🔐 SharePoint Login & Settings")
site_url = st.sidebar.text_input("SharePoint Site URL", value="https://share.amazon.com/sites/Testing_failure_tracker")
username = st.sidebar.text_input("Username (DOMAIN\\user)", value="")
password = st.sidebar.text_input("Password", type="password")
list_name = st.sidebar.text_input("List Title", value="Internal Tickets Tracker")

btn_fetch = st.sidebar.button("Fetch Data")

if btn_fetch:
    if not (site_url and username and password and list_name):
        st.error("Please fill in all fields")
    else:
        with st.spinner("Fetching data..."):
            try:
                sp = SharePointClient(site_url, username, password)
                df = sp.fetch_list(list_name)
                if df.empty:
                    st.warning("No data returned (empty or no permissions)")
                else:
                    # Show raw data
                    st.subheader("Raw Data")
                    st.dataframe(df)

                    # Basic metrics & transformations
                    # Clean column names if needed (normalize encoding)
                    # e.g. df.columns gives something like "User_x0020_Name", "Process", etc.

                    st.subheader("Summary by Process")
                    # Count per process
                    if 'Process' in df.columns:
                        proc_counts = df['Process'].value_counts().reset_index()
                        proc_counts.columns = ['Process', 'Count']
                        st.dataframe(proc_counts)
                    else:
                        st.write("No Process column found.")

                    st.subheader("Summary by User")
                    # The "User Name" column may appear as "User_x0020_Name" or similar
                    user_col = None
                    for col in df.columns:
                        if 'User' in col:
                            user_col = col
                            break
                    if user_col:
                        user_counts = df[user_col].value_counts().reset_index()
                        user_counts.columns = ['User', 'Count']
                        st.dataframe(user_counts)
                    else:
                        st.write("User column not found in data.")

                    # Maybe compute resolution times if appropriate columns exist
                    st.subheader("Resolution Time (if dates present)")
                    if 'Resolved_x0020_Date' in df.columns and 'Worked_x0020_on_x0020_date' in df.columns:
                        # parse dates
                        df['ResolvedDate_dt'] = pd.to_datetime(df['Resolved_x0020_Date'])
                        df['WorkedDate_dt'] = pd.to_datetime(df['Worked_x0020_on_x0020_date'])
                        df['ResolutionDays'] = (df['ResolvedDate_dt'] - df['WorkedDate_dt']).dt.days
                        st.dataframe(df[['ResolvedDate_dt', 'WorkedDate_dt', 'ResolutionDays']].head(20))
                        st.write("Average resolution days:", df['ResolutionDays'].mean())
                    else:
                        st.write("Could not find both Resolved and Worked date columns.")

            except Exception as e:
                st.error(f"Error: {e}")
