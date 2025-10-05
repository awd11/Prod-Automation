import os
import json
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests_ntlm import HttpNtlmAuth
import urllib3
from flask import Flask, jsonify
from flask_cors import CORS
import getpass # For securely reading passwords

# --- CONFIGURATION ---
SHAREPOINT_SITE_URL = 'https://share.amazon.com/sites/Testing_failure_tracker'
SHAREPOINT_LIST_NAME = 'Internal Tickets Tracker'

# --- SHAREPOINT MANAGER CLASS (from your code) ---
class SharePointManager:
    def __init__(self, username: str, password: str):
        self.auth = HttpNtlmAuth(username, password)
        self.headers = {'Accept': 'application/json;odata=verbose'}

    def fetch_data(self):
        all_items = []
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%-m-%dT%H:%M:%SZ')
        select_fields = "Title,Date,Created,Status,AssignedTo/Title"
        endpoint = (f"{SHAREPOINT_SITE_URL}/_api/web/lists/getbytitle('{SHAREPOINT_LIST_NAME}')/items?"
                    f"$select={select_fields}&$expand=AssignedTo&"
                    f"$filter=Created ge datetime'{ninety_days_ago}'&$top=5000")

        print(f"Fetching live data from '{SHAREPOINT_LIST_NAME}'...")
        response = requests.get(endpoint, headers=self.headers, auth=self.auth, verify=False)
        response.raise_for_status()
        data = response.json()['d']
        all_items.extend(data['results'])
        print(f"Successfully fetched {len(all_items)} items.")
        return all_items

# --- DATA PROCESSING LOGIC ---
def process_data_for_dashboard(raw_items):
    records = []
    for item in raw_items:
        assigned_to = item.get('AssignedTo')
        user = assigned_to['Title'].lower() if assigned_to and 'Title' in assigned_to else 'unassigned'
        created_date = item.get('Created', '').split('T')[0]
        if not created_date: continue
        records.append({
            'user': user, 'date': created_date,
            'status': item.get('Status', 'Unknown'), 'ticket_count': 1
        })
    df = pd.DataFrame(records)
    if df.empty: return "[]"
    
    df['date'] = pd.to_datetime(df['date'])
    daily_summary = df.groupby(['user', 'date'])['ticket_count'].sum().reset_index()
    daily_summary = daily_summary.rename(columns={'ticket_count': 'Productive'})
    daily_summary['NPT'] = 0
    return daily_summary.to_json(orient="records", date_format="iso")

# --- FLASK WEB SERVER ---
app = Flask(__name__)
CORS(app) # Allows the GitHub page to talk to this local server

# Global variable to hold the SharePoint manager instance
sp_manager = None

@app.route('/data')
def get_sharepoint_data():
    if not sp_manager:
        return jsonify({"error": "Server not initialized with credentials."}), 500
    try:
        raw_data = sp_manager.fetch_data()
        processed_json = process_data_for_dashboard(raw_data)
        return processed_json, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("--- SharePoint Local Data Bridge ---")
    sp_user = input("Enter your SharePoint username: ")
    sp_pass = getpass.getpass("Enter your SharePoint password: ")
    
    sp_manager = SharePointManager(username=sp_user, password=sp_pass)
    
    print("\nServer is running. Keep this window open.")
    print("Your team can now view the dashboard on the GitHub Pages site.")
    print("Access the data at: http://127.0.0.1:5000/data")
    
    # Host on 0.0.0.0 to make it accessible on the local network if needed
    app.run(host='0.0.0.0', port=5000)

