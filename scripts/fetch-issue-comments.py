import requests
import time
from requests.exceptions import RequestException
import os
import json

# # handle returns "jasonuranta" or another string
# # issue_number returns a string or None
# handle = os.environ.get("INPUT_HANDLE")         # From workflow_dispatch input
# issue_number = os.environ.get("INPUT_ISSUE_NUMBER")  # Might be None



# "GH_TOKEN" is the "personal access token" needed to authenticate from GitHub
GH_TOKEN = os.environ["GH_TOKEN"]
owner = os.environ.get("INPUT_OWNER", "hackforla")
repo  = os.environ.get("INPUT_REPO", "website")

users_raw = os.environ.get(
    "INPUT_USERS",
    "JasonUranta,JackRichman,mgodoy2023,Zak234,anonymousanemone")
users = {u.strip() for u in users_raw.split(",") if u.strip()}
users_lower = {u.lower() for u in users}  # making user filtering case-insensitive


all_comments = []


headers = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
params = {"page": 1, "per_page": 100}


while True:
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
    except RequestException as e:
        print(f"Network error: {e}. Retrying in 5s…")
        time.sleep(5)
        continue  # retry after a short pause
    
    if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            body = (response.text or "").lower()
            secondary = ("secondary rate limit" in body) or ("abuse detection" in body)

            if remaining == "0" or secondary or response.status_code == 429:
                sleepy_time = (
                    max(int(reset) - int(time.time()) + 2, 5)
                    if reset and reset.isdigit()
                    else 10
                )
                print(f"Rate limited (secondary={secondary}). Sleeping {sleepy_time}s…")
                time.sleep(sleepy_time)
                continue  # retry after sleeping
    
    if response.status_code in (502, 503, 504):
            print(f"Server error {response.status_code}. Retrying in 5s…")
            time.sleep(5)
            continue
    
    if response.status_code != 200:
        print(f"GitHub API error: {response.status_code} - {response.text}")
        break
    
    data = response.json()
    if not data:
        print(f"No data returned from GitHub API Request.")
        break

    all_comments.extend(data)
    params["page"] += 1



filtered_comments = [c for c in all_comments if c["user"]["login"].lower() in users_lower]

# Ensure output directory exists
try:
    os.makedirs("data", exist_ok=True)
    # Save to file
    with open("data/issue_comments.json", "w") as f:
        json.dump(filtered_comments, f, indent=2)

    print(f"Total comments fetched: {len(all_comments)}")
    print(f"Comments from target users: {len(filtered_comments)}")
    
except OSError as e:
    print(f"File write error: {e}")
