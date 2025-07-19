import requests
import json
import os
import sys
import base64
import re

def load_labels():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, 'data', 'labels_data.json') 
    with open(filepath, 'r') as f:
        return json.load(f)

""" def get_repo_metadata(owner, repo, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    desc = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers).json().get("description") or ""
    topics = requests.get(f"https://api.github.com/repos/{owner}/{repo}/topics", headers=headers).json().get("names") or []
    langs = list(requests.get(f"https://api.github.com/repos/{owner}/{repo}/languages", headers=headers).json().keys())
    readme_base64 = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers).json().get('content') or ""

    try:
        readme_text = base64.b64decode(readme_base64).decode('utf-8')
    except Exception:
        readme_text = ""
    
    return " ".join([desc] + topics + langs + [readme_text]).lower()


def match_labels(repo_text, labels_data):
    matched = []
    words = re.findall(r'\b\w+\b', repo_text)
    words_set = set(words)
    
    for label in labels_data:
        for kw in label["keywords"]:
            if kw.lower() in words_set:
                print(f"Keyword matched: '{kw}' for label '{label['label_name']}'")
                matched.append(label)
                break
    
    return matched
 """

def create_labels(owner, repo, labels, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    
    
    # deleting previous labels
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/labels",
        headers=headers
    )
    existing_labels = response.json()

    # deleting previous labels
    for label in existing_labels:
        label_name = label['name']
        delete_url = f"https://api.github.com/repos/{owner}/{repo}/labels/{label_name}"
        del_response = requests.delete(delete_url, headers=headers)

        if del_response.status_code == 204:
            print(f"Deleted label: {label_name}")
        else:
            print(f"Failed to delete label: {label_name} - {del_response.status_code}")
            
    for label in labels:
        requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/labels",
            headers=headers,
            json={
                "name": label['label_name'],
                "description": label['description'][:100],
                "color": label['color']
            }
        )
        
        
if __name__ == "__main__":
    owner = os.environ.get("REPO_OWNER")
    repo = os.environ.get("REPO_NAME")
    token = os.environ.get("GH_TOKEN")

    if not all([owner, repo, token]):
        print("Missing required environment variables: REPO_OWNER, REPO_NAME, GH_TOKEN")
        sys.exit(1)

    labels_data = load_labels()
    # repo_text = get_repo_metadata(owner, repo, token)
    # matched_labels = match_labels(repo_text, labels_data)
    # create_labels(owner, repo, matched_labels, token)
    create_labels(owner, repo, labels_data, token)