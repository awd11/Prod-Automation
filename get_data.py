import os
import json
from datetime import datetime, timedelta
import requests
from requests_ntlm import HttpNtlmAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Credentials will be read from GitHub Secrets ---
USERNAME = os.getenv('SHAREPOINT_USERNAME')
PASSWORD = os.getenv('SHAREPOINT_PASSWORD')

# Using the SharePointManager class architecture you provided
class SharePointManager:
    def __init__(self, username: str, password: str):
        if not username or not password:
            raise ValueError("SHAREPOINT_USERNAME and SHAREPOINT_PASSWORD environment variables are not set.")
        
        self.username = username
        self.password = password
        self.auth = HttpNtlmAuth(username, password)
        self.site_url = 'https://share.amazon.com/sites/Testing_failure_tracker'
        self.headers = {'Accept': 'application/json;odata=verbose'}
        # The list to fetch data from
        self.list_names = ['Internal Tickets Tracker']

    def _fetch_list_data(self, list_name: str) -> list:
        """
        Fetches all items from a single SharePoint list using pagination.
        This logic is adapted from your original _cached_fetch_data method.
        """
        all_items = []
        # Querying data from the last 90 days.
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # A generic query to get common fields. You can customize $select for more columns.
        endpoint = (f"{self.site_url}/_api/web/lists/getbytitle('{list_name}')/items?"
                    f"$select=ID,Title,Created,Status,Severity,AssignedTo/Title&$expand=AssignedTo&"
                    f"$filter=Created ge datetime'{ninety_days_ago}'&$top=5000")

        print(f"  Fetching from endpoint: {list_name}")
        while endpoint:
            try:
                response = requests.get(endpoint, headers=self.headers, auth=self.auth, verify=False)
                response.raise_for_status()
                data = response.json()['d']
                all_items.extend(data['results'])
                # Get the URL for the next page of results, if it exists
                endpoint = data.get('__next')
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data for list '{list_name}': {e}")
                return [] # Return empty on error to not break the whole process
        return all_items

    def fetch_all_data(self) -> dict:
        """
        Fetches data from all lists defined in self.list_names.
        """
        all_data = {
            "Testing Failure Tracker": {}
        }
        
        print(f"Processing site: {self.site_url}...")
        for list_name in self.list_names:
            items = self._fetch_list_data(list_name)
            all_data["Testing Failure Tracker"][list_name] = items
            print(f"  -> Found {len(items)} items in '{list_name}'.")
            
        return all_data

# Main execution block
if __name__ == "__main__":
    try:
        # Initialize your SharePointManager with the credentials
        manager = SharePointManager(username=USERNAME, password=PASSWORD)
        
        # Fetch the data using the method from your class
        sharepoint_data = manager.fetch_all_data()

        # Save the output to a JSON file for the webpage
        with open('data.json', 'w') as f:
            json.dump(sharepoint_data, f, indent=4)
        
        print("Data successfully fetched using SharePointManager and saved to data.json")

    except Exception as e:
        print(f"A critical error occurred: {e}")
        # Exit with a failure code to make the error visible in GitHub Actions
        exit(1)

