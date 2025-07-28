import requests
import json
import os
import sys
import base64
import re
import time

# load in labels from labels_data.json
def load_labels():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, 'data', 'labels_data.json') 
    with open(filepath, 'r') as f:
        return json.load(f)


def create_labels(owner, repo, labels, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
             
    existing_label_names = set()
    page = 1

    # fetches all existing labels from target repo
    while True:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/labels",
            headers=headers,
            params={"per_page": 100, "page": page}
        )
        if response.status_code != 200:
            print(f"Failed to fetch labels: {response.status_code} - {response.text}")
            sys.exit(1)

        labels_page = response.json()
        if not labels_page:
            break  # no more pages
        
        # for every page of label, update existing label set and flips page
        existing_label_names.update(label['name'].strip().lower() for label in labels_page)
        page += 1

    failed = False
    i = 0
    while i < len(labels):
        # retrives name of the label to be created (from list)
        label = labels[i]
        label_name = label['label_name'].strip()
        normalized_label_name = label_name.lower()

        # if label to be created exists, skip
        if normalized_label_name in existing_label_names:
            print(f"Label '{label_name}' already exists, skipping creation.")
            i += 1
            continue
        
        # POST endpoint to create label
        create_resp = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/labels",
            headers=headers,
            json={
                "name": label_name,
                "description": label['description'][:100],
                "color": label['color']
            }
        )

        if create_resp.status_code == 201:
            print(f"Created label: {label_name}")
            existing_label_names.add(normalized_label_name)  # Update set
            i += 1  # move to next label
        elif create_resp.status_code == 403 and "rate limit" in create_resp.text.lower():
            # rest if GitHub API rate limit is reached
            print("Rate limit hit, sleeping for 15 seconds...")
            time.sleep(15)
            # Do NOT increment i, retry same label after sleep
        else:
            print(f"Failed to create label: {label_name} - {create_resp.status_code} - {create_resp.text}")
            failed = True
            i += 1  # skip this label, move on

    if failed:
        sys.exit(1)
    else:
        sys.exit(0)

        
if __name__ == "__main__":
    owner = os.environ.get("REPO_OWNER")
    repo = os.environ.get("REPO_NAME")
    token = os.environ.get("GH_TOKEN")

    if not all([owner, repo, token]):
        print("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    labels_data = load_labels()
    create_labels(owner, repo, labels_data, token)