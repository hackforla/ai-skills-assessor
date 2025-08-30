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
REPOS = config.get("repos", [])

if not ORG:
    logging.error("Org not specified in config.")
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
        time.sleep(0.5)

    logging.info(f"Found {len(repos)} repos in org {org}")
    return repos

def repo_exists(org, repo):
    """Check if a repo exists within the specified organization on GitHub."""
    full_name = f"{org}/{repo}"
    url = f"https://api.github.com/repos/{full_name}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return True
    elif resp.status_code == 404:
        logging.warning(f"Repo '{repo}' does not exist in org '{org}'. Skipping.")
        return False
    else:
        logging.error(f"Error checking repo '{repo}' in org '{org}': {resp.status_code} {resp.text}")
        return False

def fetch_contributions(repo, users=None, max_retries=5):
    """Fetch issues and PRs for specified users in a repo, or all if users is empty."""
    users = users or []
    results = []

    if not users:
        # Fetch all contributions in the repo
        users_to_query = [None]
    else:
        users_to_query = users

    for u in users_to_query:
        if u:
            logging.info(f"Fetching contributions for user '{u}' in repo '{repo}'")
            query = f"repo:{repo} involves:{u}"
        else:
            logging.info(f"Fetching all contributions in repo '{repo}'")
            query = f"repo:{repo}"

        page = 1
        while True:
            url = "https://api.github.com/search/issues"
            params = {"q": query, "per_page": 100, "page": page}

            for attempt in range(max_retries):
                resp = requests.get(url, headers=HEADERS, params=params)
                remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
                reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))

                if resp.status_code == 200:
                    break
                elif resp.status_code == 403 and "rate limit" in resp.text.lower():
                    wait_seconds = max(reset_time - time.time(), 5)
                    logging.warning(f"Rate limit hit. Waiting {int(wait_seconds)} seconds...")
                    time.sleep(wait_seconds)
                else:
                    logging.error(f"Error fetching contributions for {repo}: {resp.status_code} {resp.text}")
                    time.sleep(5)
            else:
                logging.error(f"Failed after {max_retries} retries for page {page} in {repo}")
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                assignees = item.get("assignees", [])
                if assignees:
                    # One row per assigned user
                    for assignee in assignees:
                        results.append({
                            "user": assignee["login"],
                            "repo": repo,
                            "number": item["number"],
                            "type": "PR" if "pull_request" in item else "Issue"
                        })
                else:
                    # If no assignees, still include the issue
                    results.append({
                        "user": "UNASSIGNED",
                        "repo": repo,
                        "number": item["number"],
                        "type": "PR" if "pull_request" in item else "Issue"
                    })

            if "next" not in resp.links:
                break

            page += 1
            time.sleep(1)

    return results



def org_fetcher(org, users=None, target_repos=None):
    users = users or []  # ensure it's a list even if None
    all_results = []

    if target_repos:
        logging.info(f"Fetching contributions for specified repos: {target_repos}")
        for repo in target_repos:
            full_repo_name = repo if '/' in repo else f"{org}/{repo}"
            repo_results = fetch_contributions(full_repo_name, users)
            all_results.extend(repo_results)
    else:
        repos = fetch_repos(org)
        for repo in repos:
            repo_results = fetch_contributions(repo, users)
            all_results.extend(repo_results)

    # Write CSV
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="") as f:
        fieldnames = ["user", "org", "repo", "number", "type"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in all_results:
            if "/" in item["repo"]:
                org_name, repo_name = item["repo"].split("/", 1)
            else:
                org_name, repo_name = org, item["repo"]
            writer.writerow({
                "user": item["user"],
                "org": org_name,
                "repo": repo_name,
                "number": item["number"],
                "type": item["type"]
            })
            
    logging.info(f"Complete. Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    org_fetcher(ORG, USERS, REPOS)

