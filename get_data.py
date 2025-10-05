    import os
    import json
    from datetime import datetime, timedelta
    import requests
    from requests_ntlm import HttpNtlmAuth
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # --- This is configured with your SharePoint site ---
    SHAREPOINT_SITES = [
        {
            "name": "Testing Failure Tracker",
            "url": "https://share.amazon.com/sites/Testing_failure_tracker",
            "lists": ["Internal Tickets Tracker"]
        },
        # You can add more sites here in the future
    ]
    # ----------------------------------------------------

    class SharePointFetcher:
        def __init__(self, username: str, password: str):
            self.auth = HttpNtlmAuth(username, password)
            self.headers = {'Accept': 'application/json;odata=verbose'}

        def _fetch_all_list_items(self, site_url: str, list_name: str) -> list:
            """Fetches all items from a SharePoint list with pagination."""
            all_items = []
            # Fetches items created in the last 90 days. You can change this value.
            ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # This query selects common fields. You may need to customize the $select clause
            # if your list has different column names you want to display.
            endpoint = (f"{site_url}/_api/web/lists/getbytitle('{list_name}')/items?"
                        f"$select=ID,Title,Created,Author/Title&$expand=Author&"
                        f"$filter=Created ge datetime'{ninety_days_ago}'&$top=5000")

            while endpoint:
                try:
                    response = requests.get(endpoint, headers=self.headers, auth=self.auth, verify=False)
                    response.raise_for_status()
                    data = response.json()['d']
                    all_items.extend(data['results'])
                    endpoint = data.get('__next')
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching data for list '{list_name}': {e}")
                    return []
            return all_items

        def fetch_all_data(self, site_configs: list) -> dict:
            """Fetches data from all configured SharePoint sites."""
            all_data = {}
            for site in site_configs:
                site_name, site_url = site["name"], site["url"]
                print(f"Processing site: {site_name}...")
                all_data[site_name] = {}
                for list_name in site["lists"]:
                    print(f"  Fetching list: {list_name}...")
                    items = self._fetch_all_list_items(site_url, list_name)
                    all_data[site_name][list_name] = items
                    print(f"  -> Found {len(items)} items.")
            return all_data

    if __name__ == "__main__":
        sp_user = os.getenv('SHAREPOINT_USERNAME')
        sp_pass = os.getenv('SHAREPOINT_PASSWORD')

        if not sp_user or not sp_pass:
            raise ValueError("SHAREPOINT_USERNAME and SHAREPOINT_PASSWORD environment variables not set.")

        fetcher = SharePointFetcher(username=sp_user, password=sp_pass)
        sharepoint_data = fetcher.fetch_all_data(SHAREPOINT_SITES)

        with open('data.json', 'w') as f:
            json.dump(sharepoint_data, f, indent=4)
        
        print("Data successfully fetched from SharePoint and saved to data.json")
    
