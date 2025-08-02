import requests
import json
import os
import sys
import base64
import re
import time
import logging
import requests

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# load in labels from labels_data.json
def load_labels():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, '..', 'data', 'labels_data.json') 
    with open(filepath, 'r') as f:
        return json.load(f)


def create_labels(owner, repo, labels, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
             
    existing_label_names = set()
    page = 1
    retires = 3
    backoff = 5

    while True:
        for attempt in range(retries):
            try:
                response = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/labels",
                    headers=headers,
                    params={"per_page": 100, "page": page},
                    timeout=10
                )
                response.raise_for_status()
                labels_page = response.json()
                break  # success
            except requests.exceptions.RequestException as e:
                logging.warning(f"Attempt {attempt + 1}/{retries} failed for page {page}: {e}")
                time.sleep(backoff * (2 ** attempt))
        else:
            logging.error("Exceeded retry limit fetching labels.")
            sys.exit(1)

        if not labels_page:
            break

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
            logging.info(f"Label '{label_name}' already exists, skipping creation.")
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
            logging.info(f"Created label: {label_name}")
            existing_label_names.add(normalized_label_name)  # Update set
            i += 1  # move to next label
        elif create_resp.status_code == 403:
            if create_resp.headers.get("X-RateLimit-Remaining") == "0":
                reset_time = int(create_resp.headers.get("X-RateLimit-Reset", str(int(time.time()) + 60)))
                sleep_duration = max(reset_time - int(time.time()) + 5, 5)
                logging.warning(f"Rate limit reached, sleeping for {sleep_duration}s...")
                time.sleep(sleep_duration)
                continue  # retry same label after sleeping
            else:
                logging.error(f"Access forbidden: {create_resp.text}")
                failed = True
                i += 1
        else:
            logging.error(f"Failed to create label: {label_name} - {create_resp.status_code} - {create_resp.text}")
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
        logging.error("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    labels_data = load_labels()
    create_labels(owner, repo, labels_data, token)