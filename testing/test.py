import requests
from datetime import datetime, timedelta, timezone
import pytz
import json

def fetch_upcoming_launches(limit=10):
    print("Fetching upcoming launches...")
    url = f"https://ll.thespacedevs.com/2.2.0/launch/upcoming/?search=spacex&limit={limit}"
    response = requests.get(url)

    if response.status_code == 429:
        wait_time = int(response.headers.get("Retry-After", 60))
        print(f"Rate limited. Using cached data from 'json_dump.json'. Retry after {wait_time} seconds.")

        if os.path.exists("json_dump.json"):
            with open("json_dump.json", "r") as f:
                data = json.load(f)
        else:
            print("No cached file found. Returning empty list.")
            return []
    elif response.status_code == 200:
        data = response.json()
        with open("json_dump.json", "w") as f:
            json.dump(data, f, indent=2)
    else:
        print(f"Unexpected error: {response.status_code}")
        return []

    if 'results' not in data:
        print("Malformed response: 'results' key missing.")
        return []

    now_utc = datetime.now(timezone.utc)
    launches = [
        l for l in data['results']
        if datetime.strptime(l['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) > now_utc
    ]

    launches.sort(key=lambda x: x['net'])
    ist = pytz.timezone('Asia/Kolkata')
    for launch in launches:
        utc_dt = datetime.strptime(launch['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        launch['date_ist'] = utc_dt.astimezone(ist)
        vid_url = launch.get('vidURLs', [])
        launch['webcast'] = vid_url[0] if vid_url else 'N/A'

    return launches[:limit]

fetch_upcoming_launches()