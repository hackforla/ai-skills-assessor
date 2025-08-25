import os
import json
import requests
import csv
import logging
import time


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Script paths
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, "target_org.json")
OUTPUT_FILE = os.path.join(script_dir, "org_contr.csv")

# --- GitHub token from secret ---
GITHUB_TOKEN = os.environ.get("PAT")
if not GITHUB_TOKEN:
    logging.error("PAT token not found in environment. Make sure to set it as a secret in GitHub Actions.")
    exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Load configuration
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

ORG = config.get("org")
USERS = config.get("users", [])

if not ORG:
    logging.error("Org not specified in config.")
    exit(1)
    
if not USERS:
    logging.error("User(s) not specified in config.")
    exit(1)

# --- Helper functions ---

def fetch_repos(org):
    """Fetch all repos for an organization."""
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos"
        params = {"per_page": 100, "page": page}
        resp = requests.get(url, headers=HEADERS, params=params)

        if resp.status_code != 200:
            logging.error(f"Error fetching repos for org {org}: {resp.status_code} {resp.text}")
            break

        data = resp.json()
        if not data:
            break

        repos.extend([r["full_name"] for r in data])
        page += 1
        time.sleep(0.5)  # slight delay to avoid rate limits

    logging.info(f"Found {len(repos)} repos in org {org}")
    return repos


def fetch_contributions(repo, users):
    """Fetch issues and PRs for given users in a repo."""
    results = []
    page = 1

    while True:
        query = f"repo:{repo} " + " ".join([f"involves:{u}" for u in users])

        url = "https://api.github.com/search/issues"
        params = {"q": query, "per_page": 100, "page": page}
        resp = requests.get(url, headers=HEADERS, params=params)

        if resp.status_code != 200:
            logging.error(f"Error fetching contributions for {repo}: {resp.status_code} {resp.text}")
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            results.append({
                "user": item["user"]["login"] if item.get("user") else "unknown",
                "repo": repo,
                "number": item["number"],
                "type": "PR" if "pull_request" in item else "Issue"
            })

        if "next" not in resp.links:
            break

        page += 1
        time.sleep(1)  # avoid secondary rate limits

    return results


def org_fetcher(org, users):
    all_results = []
    repos = fetch_repos(org)

    for repo in repos:
        logging.info(f"Fetching contributions in {repo}...")
        repo_results = fetch_contributions(repo, users)
        all_results.extend(repo_results)

    # Create output folder if it doesn't exist
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user", "repo", "number", "type"])
        writer.writeheader()
        writer.writerows(all_results)

    logging.info(f"Complete. Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    org_fetcher(ORG, USERS)
