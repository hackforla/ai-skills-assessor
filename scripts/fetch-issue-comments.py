import requests
import os
import json

# # handle returns "jasonuranta" or another string
# # issue_number returns a string or None
# handle = os.environ.get("INPUT_HANDLE")         # From workflow_dispatch input
# issue_number = os.environ.get("INPUT_ISSUE_NUMBER")  # Might be None


users = set(["JasonUranta", "JackRichman", "mgodoy2023", "Zak234", "anonymousanemone"])

org = "hackforla" # "org" aka owner of "repo"
repo = "website"

# "PAT" or "GH_TOKEN" is the "personal access token" needed to authenticate from GitHub
GH_TOKEN = os.environ["GH_TOKEN"]


headers = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json"
}

all_comments = []
page = 1

while True:
    url = f"https://api.github.com/repos/{org}/{repo}/issues/comments?page={page}&per_page=100"
    response = requests.get(url, headers=headers)
    data = response.json()

    if not data or response.status_code != 200:
        print(f"GitHub API error: {response.status_code} - {response.text}")
        break

    all_comments.extend(data)
    page += 1
    
filtered_comments = [c for c in all_comments if c["user"]["login"] in users]

# Ensure output directory exists
os.makedirs("../data", exist_ok=True)


# Save to file
with open("../data/issue_comments.json", "w") as f:
    json.dump(filtered_comments, f, indent=2)

print(f"Total comments fetched: {len(all_comments)}")
print(f"Comments from target users: {len(filtered_comments)}")
