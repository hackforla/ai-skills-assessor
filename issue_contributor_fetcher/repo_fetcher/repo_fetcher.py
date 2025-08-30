import os
import json
import requests
import csv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# set up

script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, "target_repo.json")


# set in bash using: export GH_TOKEN="<your token>"
GITHUB_TOKEN = os.environ.get("GH_TOKEN")

if not GITHUB_TOKEN:
    logging.error("Please set GH_TOKEN environment variable.")
    exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# retrieves repo info, returns error if no repo
# users can be empty, if empty returns data for all contributors
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

REPO = config.get("repo")
USERS = config.get("users", []) 

if not REPO:
    logging.error("Repo not specified in config.")
    exit(1)

# helper function, if user specified
def fetch_issues_for_user(repo, user):
    """Returns a list of dicts with issue/PR info for a given user in the repo."""
    results = []
    page = 1
    while True:
        query = f"repo:{repo} involves:{user}"
        url = f"https://api.github.com/search/issues"
        params = {"q": query, "per_page": 100, "page": page}
        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code != 200:
            logging.error(f"GitHub API error {response.status_code}: {response.text}")
            break

        data = response.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            results.append({
                "user": user,
                "repo": repo,
                "number": item["number"],
                "type": "PR" if "pull_request" in item else "Issue"
            })

        # Pagination
        if "next" not in response.links:
            break
        page += 1
        
        time.sleep(1)

    return results

# helper function, if no user specified
def fetch_all_contributors(repo):
    """
    Fetches all issues and PRs in the repo, returning a list of dicts like:
    { "user": <username>, "repo": <repo>, "number": <number>, "type": "PR"/"Issue" }
    """
    results = []
    page = 1

    while True:
        query = f"repo:{repo}"
        url = "https://api.github.com/search/issues"
        params = {"q": query, "per_page": 100, "page": page}
        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code != 200:
            logging.error(f"GitHub API error {response.status_code}: {response.text}")
            break

        data = response.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if "user" in item and item["user"]:
                results.append({
                    "user": item["user"]["login"],
                    "repo": repo,
                    "number": item["number"],
                    "type": "PR" if "pull_request" in item else "Issue"
                })

        page += 1
        time.sleep(1)  # avoid hitting secondary rate limits

    return results


def repo_fetcher(repo, users):
    all_results = []

    if users:
        for user in users:
            logging.info(f"Fetching issues/PRs for {user} in {repo}...")
            user_results = fetch_issues_for_user(repo, user)
            all_results.extend(user_results)
    else:
        logging.info(f"No users specified. Fetching all issues/PRs for {repo}...")
        all_results = fetch_all_contributors(repo)
        logging.info(f"Found {len(all_results)} issues/PRs.")

    # OUTPUT CSV
    output_file = os.path.join(script_dir, "poc_results.csv")
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user", "repo", "number", "type"])
        writer.writeheader()
        writer.writerows(all_results)

    logging.info(f"POC complete. Results written to {output_file}")



if __name__ == "__main__":
    repo_fetcher(REPO, USERS)
