import requests
from requests_ntlm import HttpNtlmAuth
import pandas as pd
from datetime import datetime
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class SharePointClient:
    def __init__(self, site_url: str, username: str, password: str):
        self.site_url = site_url.rstrip('/')
        self.username = username
        self.password = password
        self.auth = HttpNtlmAuth(username, password)
        self.headers = {'Accept': 'application/json;odata=verbose'}

    def fetch_list(self, list_title: str, top: int = 5000) -> pd.DataFrame:
        """
        Fetches list items from SharePoint list and returns a DataFrame. 
        """
        url = f"{self.site_url}/_api/web/lists/getbytitle('{list_title}')/items?$top={top}"
        try:
            resp = requests.get(url, headers=self.headers, auth=self.auth, verify=False)
            resp.raise_for_status()
        except Exception as e:
            logger.error("Error fetching SharePoint list: %s", str(e))
            raise

        data = resp.json().get('d', {}).get('results', [])
        # If no data or keys mismatch, return empty df
        if not data:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.json_normalize(data)
        return df

    def fetch_with_query(self, list_title: str, filter_q: str, top: int = 5000) -> pd.DataFrame:
        """
        Fetch list items with an OData filter query.
        Example filter_q: "Process eq 'Automated Test Failures'"
        """
        url = f"{self.site_url}/_api/web/lists/getbytitle('{list_title}')/items?$filter={filter_q}&$top={top}"
        try:
            resp = requests.get(url, headers=self.headers, auth=self.auth, verify=False)
            resp.raise_for_status()
        except Exception as e:
            logger.error("Error with filtered fetch: %s", str(e))
            raise

        data = resp.json().get('d', {}).get('results', [])
        return pd.json_normalize(data)
