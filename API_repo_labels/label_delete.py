from urllib.parse import quote
import requests
import os
import sys

def get_all_labels(owner, repo, headers):
    labels = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/labels?per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        batch = response.json()

        if not batch:
            break  # no more labels

        labels.extend(batch)
        page += 1
    return labels


def delete_labels(owner, repo, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    existing_labels = get_all_labels(owner, repo, headers)

    for label in existing_labels:
        label_name = label['name']
        delete_url = f"https://api.github.com/repos/{owner}/{repo}/labels/{quote(label_name)}"
        del_response = requests.delete(delete_url, headers=headers)

        if del_response.status_code == 204:
            print(f"Deleted label: {label_name}")
        else:
            print(f"Failed to delete label: {label_name} - {del_response.status_code}")

if __name__ == "__main__":
    owner = "sandy3w"
    repo = "HfLA-label-test"
    token = ""

    if not all([owner, repo, token]):
        print("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    delete_labels(owner, repo, token)
