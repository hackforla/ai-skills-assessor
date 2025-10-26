import os
import json
import requests
import csv
import logging
import time

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Build a shared session with retries
def build_session():
    s = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    return s

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# set up

script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, "poc_target_repo.json")


# set in bash using: export GH_TOKEN="<your token>"
GITHUB_TOKEN = (
    os.environ.get("PAT")
    or os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GH_TOKEN")
)
if not GITHUB_TOKEN:
    logging.error("GitHub token not found in env (PAT/GITHUB_TOKEN/GH_TOKEN).")
    raise SystemExit(1)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "org-contributions-fetcher/1.0",
}

# build session after header is defined
SESSION = build_session()
REQUEST_TIMEOUT = 15 


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
        response = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)


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
        response = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)

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

        if "next" not in response.links:
            break
        page += 1

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
