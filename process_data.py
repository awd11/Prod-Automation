import os
import json
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests_ntlm import HttpNtlmAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# Updated to use your Testing Failure Tracker site and list.
SHAREPOINT_SITE_URL = 'https://share.amazon.com/sites/Testing_failure_tracker'
SHAREPOINT_LIST_NAME = 'Internal Tickets Tracker'

class SharePointManager:
    """
    This class connects to SharePoint and fetches all data for processing.
    """
    def __init__(self, username: str, password: str):
        if not username or not password:
            raise ValueError("Service account credentials are not set in GitHub Secrets.")
        self.auth = HttpNtlmAuth(username, password)
        self.headers = {'Accept': 'application/json;odata=verbose'}

    def fetch_all_from_list(self):
        """Fetches all items from the configured SharePoint list with pagination."""
        all_items = []
        # Fetches data from the last 90 days. Adjust if needed.
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # OData query to select relevant fields. This makes the query faster.
        # Using generic fields. You may need to adjust 'Status' or 'AssignedTo' if the column names are different.
        select_fields = "Title,Date,Created,Status,AssignedTo/Title"
        
        endpoint = (f"{SHAREPOINT_SITE_URL}/_api/web/lists/getbytitle('{SHAREPOINT_LIST_NAME}')/items?"
                    f"$select={select_fields}&$expand=AssignedTo&"
                    f"$filter=Created ge datetime'{ninety_days_ago}'&$top=5000")

        print(f"Fetching data from '{SHAREPOINT_LIST_NAME}'...")
        while endpoint:
            try:
                response = requests.get(endpoint, headers=self.headers, auth=self.auth, verify=False)
                response.raise_for_status()
                data = response.json()['d']
                all_items.extend(data['results'])
                endpoint = data.get('__next')
            except requests.exceptions.RequestException as e:
                print(f"Error fetching list '{SHAREPOINT_LIST_NAME}': {e}")
                break
        return all_items

def get_username_from_assigned_to(assigned_to_field):
    """Extracts the username from the 'AssignedTo' field if it exists."""
    if assigned_to_field and isinstance(assigned_to_field, dict) and 'Title' in assigned_to_field:
        # Example format: {'Title': 'Doe, John'} -> 'doe, john'
        return assigned_to_field['Title'].lower()
    return 'unassigned'

def process_data_into_dataframe(raw_items):
    """Converts the raw list data into a clean pandas DataFrame for production calculation."""
    records = []
    for item in raw_items:
        assigned_user = get_username_from_assigned_to(item.get('AssignedTo'))
        
        # Use 'Created' date as the primary date for tracking
        created_date = item.get('Created', '').split('T')[0]
        if not created_date:
            continue

        records.append({
            'user': assigned_user,
            'date': created_date,
            'status': item.get('Status', 'Unknown'),
            'ticket_count': 1 # Each row represents one ticket
        })
    return pd.DataFrame(records)

if __name__ == "__main__":
    # Securely get the Service Account credentials from GitHub Secrets
    sp_user = os.getenv('SHAREPOINT_USERNAME')
    sp_pass = os.getenv('SHAREPOINT_PASSWORD')
    
    # 1. Fetch Data
    manager = SharePointManager(username=sp_user, password=sp_pass)
    raw_data = manager.fetch_all_from_list()

    # 2. Process Data and Perform Calculations
    df = process_data_into_dataframe(raw_data)
    
    if not df.empty:
        # Convert date string to datetime object for calculations
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate daily ticket counts for each user
        daily_summary = df.groupby(['user', 'date'])['ticket_count'].sum().reset_index()
        
        # Rename 'ticket_count' to 'Productive' to match the graph's expectation
        # and add a zero 'NPT' column.
        daily_summary = daily_summary.rename(columns={'ticket_count': 'Productive'})
        daily_summary['NPT'] = 0

        # Convert to JSON format for the web app
        result = daily_summary.to_json(orient="records", date_format="iso")
    else:
        result = "[]" # Empty array if no data

    # 3. Save to File
    with open('production_data.json', 'w') as f:
        f.write(result)

    print(f"Successfully processed and saved data to production_data.json")

