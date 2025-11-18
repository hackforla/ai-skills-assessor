from urllib.parse import quote
import requests
import os
import sys
import logging
import time

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


def get_all_labels(owner, repo, headers):
    labels = []
    page = 1
    retries = 3
    backoff = 5

    # fetches all label from target repo
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/labels?per_page=100&page={page}"
        logging.info(f"Fetching labels from: {url}")

        attempt = 0
        while attempt < retries:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                logging.info(f"Status code: {response.status_code}")
                logging.info(f"Response preview: {response.text[:200]}")

                if response.status_code != 200:
                    logging.error(f"Failed to get labels. HTTP {response.status_code}: {response.text}")
                    sys.exit(1)

                batch = response.json()
                break  

            except requests.exceptions.RequestException as e:
                attempt += 1
                logging.warning(f"Request failed ({attempt}/{retries}): {e}")
                if attempt < retries:
                    sleep_time = backoff * (2 ** (attempt - 1))  
                    logging.info(f"Retrying after {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logging.error("Max retries reached, exiting.")
                    sys.exit(1)

        if not batch:
            break 
        
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
    
    for label in existing_labels:
        label_name = label['name']
        
        # Only delete if label starts with "x-" or contains a semicolon
        if not (label_name.startswith("x-")):
            continue
        
        delete_url = f"https://api.github.com/repos/{owner}/{repo}/labels/{quote(label_name)}"

        # error check while attempting to delete specified label
        try:
            del_response = requests.delete(delete_url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            continue

        if del_response.status_code == 204:
            logging.info(f"Deleted label: {label_name}")
        else:
            if handle_rate_limit(del_response):
                continue  # Retry deletion after sleep
            logging.error(f"Failed to delete label: {label_name} - HTTP {del_response.status_code}: {del_response.text}")


def handle_rate_limit(response):
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_time = int(response.headers["X-RateLimit-Reset"])
        wait_seconds = max(reset_time - int(time.time()) + 5, 5)
        logging.warning(f"Rate limit reached, sleeping for {wait_seconds} seconds...")
        time.sleep(wait_seconds)
        return True
    return False

if __name__ == "__main__":
    owner = os.environ.get("REPO_OWNER")
    repo = os.environ.get("REPO_NAME")
    token = os.environ.get("GH_TOKEN")

    if not all([owner, repo, token]):
        logging.error("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    delete_labels(owner, repo, token)

