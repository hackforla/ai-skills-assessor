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

if not USERS:
    logging.error("No users specified in config. Please provide at least one username.")
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

def fetch_contributions(repo, users, max_retries=5):
    """Fetch issues and PRs for specified users in a repo with rate-limit handling."""
    results = []

    for u in users:
        logging.info(f"Fetching contributions for user '{u}' in repo '{repo}'")
        page = 1
        while True:
            query = f"repo:{repo} involves:{u}"
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
                results.append({
                    "user": u,
                    "repo": repo,
                    "number": item["number"],
                    "type": "PR" if "pull_request" in item else "Issue"
                })

            if "next" not in resp.links:
                break

            page += 1
            time.sleep(1)  # avoid secondary rate limits

    return results


def org_fetcher(org, users, target_repos=None):
    all_results = []

    if target_repos:
        repos = target_repos
        logging.info(f"Fetching contributions for specified repos: {repos}")
    else:
        repos = fetch_repos(org)

    for repo in repos:
        if not repo_exists(repo):
            continue  # skip non-existent repos
        repo_results = fetch_contributions(repo, users)
        all_results.extend(repo_results)

    # Ensure output folder exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user", "repo", "number", "type"])
        writer.writeheader()
        writer.writerows(all_results)

    logging.info(f"Complete. Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    org_fetcher(ORG, USERS, REPOS)

