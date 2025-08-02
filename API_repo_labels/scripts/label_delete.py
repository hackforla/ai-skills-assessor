from urllib.parse import quote
import requests
import os
import sys
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


def get_all_labels(owner, repo, headers):
    labels = []
    page = 1

    # fetches all label from target repo
    while True:

        # API endpoint to specified repo label
        url = f"https://api.github.com/repos/{owner}/{repo}/labels?per_page=100&page={page}"
        logging.info(f"Fetching labels from: {url}")

        # error check while attempting to fetch labels
        try:
            response = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            sys.exit(1)

        logging.info(f"Status code: {response.status_code}")
        logging.info(f"Response preview: {response.text[:200]}")

        if response.status_code != 200:
            logging.error(f"Failed to get labels. HTTP {response.status_code}: {response.text}")
            sys.exit(1)

        batch = response.json()

        if not batch:
            break  
        
        # flips page for labels
        labels.extend(batch)
        page += 1
    return labels


def delete_labels(owner, repo, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    logging.info(f"Using token: {'yes' if token else 'no'}")
    logging.info(f"Target repo: {owner}/{repo}")

    existing_labels = get_all_labels(owner, repo, headers)
    logging.info("Found labels:", [label['name'] for label in existing_labels])

    # deletes all labels found
    for label in existing_labels:
        label_name = label['name']
        delete_url = f"https://api.github.com/repos/{owner}/{repo}/labels/{quote(label_name)}"
        print(f"Deleting label: {label_name} -> {delete_url}")

        # error check while attempting to delete specified label
        try:
            del_response = requests.delete(delete_url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            continue

        if del_response.status_code == 204:
            logging.info(f"Deleted label: {label_name}")
        else:
            logging.error(f"Failed to delete label: {label_name} - HTTP {del_response.status_code}: {del_response.text}")


if __name__ == "__main__":
    # configure all three to use this file
    # hard code owner and repo and set GH_TOKEN
    owner = "sandy3w"
    repo = "HfLA-label-test"
    token = os.environ.get("GH_TOKEN")

    if not all([owner, repo, token]):
        logging.error("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    delete_labels(owner, repo, token)

