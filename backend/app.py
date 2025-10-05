# backend/app.py
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import pytz
import logging
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# requests-ntlm is required
import requests
from requests_ntlm import HttpNtlmAuth
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config from env ---
SITE_URL = os.environ.get("SHAREPOINT_SITE_URL", "https://share.amazon.com/sites/Audible%20team%20production%20data")
SP_USERNAME = os.environ.get("SHAREPOINT_USERNAME", "")
SP_PASSWORD = os.environ.get("SHAREPOINT_PASSWORD", "")

if not SP_USERNAME or not SP_PASSWORD:
    logger.warning("SHAREPOINT_USERNAME or SHAREPOINT_PASSWORD not set. Backend will fail when calling SharePoint.")

# --- Cleaned SharePointManager (streamlit removed) ---
class SharePointManager:
    def __init__(self, username: str, password: str, site_url: str):
        self.username = username
        self.password = password
        self.digest_value = None
        self.auth = HttpNtlmAuth(username, password)
        self.site_url = site_url
        self.headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose'
        }
        # lists used in your original script (single SP for testing is fine)
        self.list_names = [
            'Firsttime_Prod_Audible_V4',
            'Image_Buk_2024_V9',
            '3P Ingestion Workflow',
            'ACX+QA+2024',
            'NPT'
        ]

    def get_form_digest_value(self) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.site_url}/_api/contextinfo",
                headers=self.headers,
                auth=self.auth,
                verify=False
            )
            response.raise_for_status()
            return response.json()['d']['GetContextWebInformation']['FormDigestValue']
        except Exception as e:
            logger.exception("error getting form digest")
            return None

    def _fetch_pages(self, url: str) -> List[Dict]:
        auth = self.auth
        all_data = []
        def fetch(url_):
            r = requests.get(url_, headers={'Accept': 'application/json;odata=verbose'}, auth=auth, verify=False)
            r.raise_for_status()
            return r.json()

        res = fetch(url)
        all_data.extend(res['d']['results'])
        while '__next' in res['d']:
            res = fetch(res['d']['__next'])
            all_data.extend(res['d']['results'])
        return all_data

    def _cached_fetch_data(self, list_name:str, start_date:str, end_date:str, filter_query:Optional[str]=None):
        # convert to UTC zulu strings
        ist = pytz.timezone('Asia/Kolkata')
        utc = pytz.UTC
        start_dt = datetime.strptime(start_date, '%m/%d/%Y').replace(tzinfo=ist).astimezone(utc)
        end_dt = datetime.strptime(end_date, '%m/%d/%Y').replace(hour=23, minute=59, second=59).replace(tzinfo=ist).astimezone(utc)
        s = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        e = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        if list_name == 'NPT':
            base_url = (f"{self.site_url}/_api/web/lists/getbytitle('{list_name}')/items?"
                        f"$select=ID,Title,Date,NPT_x0020_Reason,Minutes,Comments&"
                        f"$filter=Date ge datetime'{s}' and Date le datetime'{e}'")
        else:
            base_url = (f"{self.site_url}/_api/web/lists/getbytitle('{list_name}')/items?"
                        f"$select=ID,Title,Date,Actual_x0020_minutes,Process_x0020_and_x0020_Type_x00&"
                        f"$filter=Date ge datetime'{s}' and Date le datetime'{e}'")

        if filter_query:
            base_url += f" and {filter_query}"

        base_url += "&$top=10000"
        try:
            rows = self._fetch_pages(base_url)
        except Exception as exc:
            logger.exception("fetch error")
            raise

        total_minutes = 0
        process_types = {}
        detailed_data = []
        for item in rows:
            if list_name == 'NPT':
                minutes = float(item.get('Minutes', 0) or 0)
                process = item.get('NPT_x0020_Reason', '') or ''
            else:
                minutes = float(item.get('Actual_x0020_minutes', 0) or 0)
                process = item.get('Process_x0020_and_x0020_Type_x00', '') or ''

            total_minutes += minutes
            process_types[process] = process_types.get(process, 0) + 1

            # parse date
            date_str = item.get('Date')
            try:
                item_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC).astimezone(ist)
            except Exception:
                # fallback
                item_date = datetime.utcnow().astimezone(ist)

            detailed_item = {
                'Title': item.get('Title',''),
                'Date': item_date.strftime('%Y-%m-%d'),
                'Minutes': minutes,
                'Process': process
            }
            if list_name == 'NPT':
                detailed_item['Comments'] = item.get('Comments','')

            detailed_data.append(detailed_item)

        return round(total_minutes,2), process_types, detailed_data

    # wrapper used by endpoints
    def fetch_data(self, list_name:str, start_date:str, end_date:str, filter_query:Optional[str]=None):
        return self._cached_fetch_data(list_name, start_date, end_date, filter_query)

    def submit_npt(self, username:str, reason:str, minutes:int, comments:str, npt_date:date):
        digest = self.get_form_digest_value()
        if not digest:
            raise RuntimeError("Could not get form digest value")
        ist = pytz.timezone('Asia/Kolkata')
        npt_date_dt = ist.localize(datetime.combine(npt_date, datetime.min.time()))
        formatted = npt_date_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        item_data = {
            "__metadata": {"type": "SP.Data.NPTListItem"},
            "Title": f"i:0#.w|ant\\{username}",
            "Date": formatted,
            "NPT_x0020_Reason": reason,
            "Minutes": int(minutes),
            "Comments": comments
        }
        headers = {**self.headers, 'X-RequestDigest': digest}
        url = f"{self.site_url}/_api/web/lists/getbytitle('NPT')/items"
        r = requests.post(url, json=item_data, headers=headers, auth=self.auth, verify=False)
        if r.status_code not in (200,201):
            logger.error("Submit NPT failed: %s %s", r.status_code, r.text)
            raise RuntimeError("Submit failed")
        return True


# instantiate manager
spm = SharePointManager(SP_USERNAME, SP_PASSWORD, SITE_URL)

# --- FastAPI app ---
app = FastAPI(title="SharePoint Proxy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change * to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic models for request/response ---
class FetchRequest(BaseModel):
    list_name: str
    start_date: str  # mm/dd/YYYY
    end_date: str
    filter_query: Optional[str] = None

class NPTSubmitRequest(BaseModel):
    username: str
    reason: str
    minutes: int
    comments: Optional[str] = ""
    npt_date: date

# endpoints
@app.get("/health")
def health():
    return {"ok": True, "site": SITE_URL}

@app.post("/fetch-list")
def fetch_list(req: FetchRequest):
    try:
        total, types, detailed = spm.fetch_data(req.list_name, req.start_date, req.end_date, req.filter_query)
        return {"total_minutes": total, "process_types": types, "detailed_data": detailed}
    except Exception as e:
        logger.exception("fetch-list error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-npt")
def submit_npt(req: NPTSubmitRequest):
    try:
        success = spm.submit_npt(req.username, req.reason, req.minutes, req.comments or "", req.npt_date)
        return {"success": True}
    except Exception as e:
        logger.exception("submit-npt error")
        raise HTTPException(status_code=500, detail=str(e))

# quick productivity calc endpoint (basic)
@app.post("/productivity")
def productivity(req: FetchRequest):
    """
    Compute simple productivity table for 'manager' vs 'individual' style like original code.
    For testing, we'll compute totals per user from available lists.
    """
    try:
        # fetch all lists (except NPT) and aggregate detailed rows
        combined: Dict[str, List[Dict]] = {}
        for list_name in spm.list_names:
            total, types, detailed = spm.fetch_data(list_name, req.start_date, req.end_date, req.filter_query)
            combined[list_name] = detailed

        # Build per-user totals
        user_totals: Dict[str, float] = {}
        for list_name, items in combined.items():
            for it in items:
                title = it.get('Title','')
                clean = title.split('\\')[-1] if '\\' in title else title
                mins = float(it.get('Minutes',0) or 0)
                user_totals[clean] = user_totals.get(clean,0) + mins

        result = [{"user": u, "minutes": m} for u,m in user_totals.items()]
        result = sorted(result, key=lambda x: x['user'])
        return {"data": result}
    except Exception as e:
        logger.exception("productivity error")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
