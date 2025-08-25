import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from requests.exceptions import RequestException
import os
import json



# -------------------------- (My Helper Methods) ------------------------------

OUTPUT_PATH = os.environ.get("INPUT_OUTPUT_PATH", "data/issue-comments.json")
def load_existing_and_last_updated(output_path=OUTPUT_PATH):
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        return [], None

    # Find max updated_at (fallback to created_at if needed)
    last = None
    for c in existing:
        ts = c.get("updated_at") or c.get("created_at") or c.get("updated_at_iso") or c.get("created_at_iso")
        if ts and (last is None or ts > last):  # ISO 8601 Z strings compare lexicographically
            last = ts
    return existing, last

def trim_comments(c):
    """
    Return a cleaned-up version of a GitHub issue comment, 
    removing heavy user metadata and reactions.
    """
    
    slimmed = dict(c)  # shallow copy of the whole comment
    verbose_user_keys = ["node_id", "avatar_url", "gravatar_id", "url", \
        "html_url", "followers_url", "following_url", "gists_url", \
        "starred_url", "subscriptions_url", "organizations_url", "repos_url", \
        "events_url", "received_events_url"]

    slimmed.pop("reactions", None)
    if "user" in slimmed:
        user = dict(slimmed["user"])  # shallow copy so we can mutate safely
        for key in verbose_user_keys:
            user.pop(key, None)
        slimmed["user"] = user
    return slimmed

def to_assessment_record(c: dict) -> dict:
    """
    Build a more compact and clear record external use and keep a slim 'raw' record for lossless provenance.
    """
    login   = (c.get("user") or {}).get("login", "")
    body    = c.get("body") or ""
    created = c.get("created_at")
    updated = c.get("updated_at")
    html    = c.get("html_url") or ""
    issue_url = c.get("issue_url") or ""
    
    issue_number = None
    try:
        # issue_url is like https://api.github.com/repos/{owner}/{repo}/issues/1694
        tail = issue_url.rstrip("/").split("/")[-1]
        issue_number = int(tail)
    except Exception:
        pass

    # - PR vs Issue: html_url contains /pull/ for PR issue comments
    is_pr_comment = "/pull/" in html

    # - reactions total
    rx = (c.get("reactions") or {})
    reactions_total = sum(rx.get(k, 0) for k in ["+1","-1","laugh","hooray","confused","heart","rocket","eyes"])

    # make a slim raw to avoid bloat (reuse your existing logic)
    raw_slim = trim_comments(c)

    return {
        # common keys needed for grouping/filtering on
        "id": c.get("id"),
        "owner": os.environ.get("INPUT_OWNER", "hackforla"),
        "repo":  os.environ.get("INPUT_REPO", "website"),
        "user_login": login,
        "author_association": c.get("author_association"),
        "issue_number": issue_number,
        "is_pr_comment": is_pr_comment,

        # timing & size
        "created_at_iso": created,
        "updated_at_iso": updated,
        "comment_length": len(body),

        # URLs
        "url": c.get("url"),
        "html_url": html,
        "issue_url": issue_url,
        
        # reactions
        "reactions_total": reactions_total,

        # optional provenance (lossless enough for debugging/spot checks)
        "raw": raw_slim,
    }


def next_link(resp) -> str | None:
    link = resp.headers.get("Link", "")
    # Example: <https://api.github.com/...&page=3>; rel="next", <...>; rel="last"
    for part in link.split(","):
        seg = part.strip()
        if 'rel="next"' in seg:
            start = seg.find("<") + 1
            end = seg.find(">", start)
            if start > 0 and end > start:
                return seg[start:end]
    return None




# -------------------------- (API Request Setup) ------------------------------

# "GH_TOKEN" is the "personal access token" needed to authenticate from GitHub
token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
if not token:
    raise SystemExit("Missing GH_TOKEN/GITHUB_TOKEN. Set one in the workflow env/secrets.")
owner = os.environ.get("INPUT_OWNER", "hackforla")
repo  = os.environ.get("INPUT_REPO", "website")

users_raw = os.environ.get("INPUT_USERS", \
                "JasonUranta,JackRichman,mgodoy2023,Zak234,anonymousanemone")
users = {u.strip() for u in users_raw.split(",") if u.strip()}
users_lower = {u.lower() for u in users}  # making user filtering case-insensitive

S = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 502, 503, 504],
    allowed_methods=frozenset(["GET"]),
)
S.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))


S.headers.update({
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})
params = {"page": 1, "per_page": 100}
existing_data, last_seen = load_existing_and_last_updated()
if last_seen:
    params["since"] = last_seen
print(f"Fetching comments for {owner}/{repo} "
      f"(since={params.get('since','ALL')}) "
      f"-> {OUTPUT_PATH}")




tmp_ndjson = OUTPUT_PATH + ".new.ndjson"
new_count = 0

endpoint = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
url = endpoint  # first call uses endpoint+params
first_request = True

BASE_BACKOFF = 5      # (seconds)
MAX_BACKOFF  = 60     # (max seconds)
backoff      = BASE_BACKOFF
page_idx     = 1      # purely for logging/debug

# ------------------------- (API Request Handling) ----------------------------


with open(tmp_ndjson, "w", encoding="utf-8") as tmp:
    while url:
        # Only pass params on the very first request
        req_params = params if first_request else None
        first_request = False
        
        try:
            response = S.get(url, params=req_params, timeout=10)
        except RequestException as e:
            print(f"[Page #{page_idx}]. Network error: {e}. Retrying in {backoff}s…")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue  # retry after a short pause
        
        if response.status_code in (403, 429):
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset = response.headers.get("X-RateLimit-Reset")
                body = (response.text or "").lower()
                secondary = ("secondary rate limit" in body) or ("abuse detection" in body)

                if remaining == "0" or secondary or response.status_code == 429:
                    if isinstance(reset, str) and reset.isdigit():
                        wait = min(max(int(reset) - int(time.time()) + 2, BASE_BACKOFF), 600) # hard cap at 10 min just in case
                        print(f"[Page #{page_idx}]. Rate limited (secondary={secondary}). "
                            f"Sleeping {wait}s until reset…")
                        time.sleep(wait)
                        backoff = BASE_BACKOFF  # reset backoff after a reset-based sleep
                    else:
                        # Fall back to capped exponential backoff if reset is missing/weird
                        print(f"[Page #{page_idx}]. Rate limited but no usable reset header. "
                            f"Sleeping {backoff}s…")
                        time.sleep(backoff)
                        backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
        
        if response.status_code in (502, 503, 504):
                print(f"[Page #{page_idx}]. Server error {response.status_code}. Retrying in {backoff}s…")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue
        
        if response.status_code != 200:
            print(f"GitHub API error: {response.status_code} - {response.text}")
            break
        
        try:
            data = response.json() or []
        except ValueError:
            print("Non-JSON response from GitHub; aborting.")
            break
        if data:
            for c in data:
                login = (c.get("user") or {}).get("login", "").lower()
                if not users_lower or login in users_lower:
                    record = to_assessment_record(c)
                    tmp.write(json.dumps(record, ensure_ascii=False))
                    tmp.write("\n")
                    new_count += 1
        backoff = BASE_BACKOFF 
        page_idx += 1
        url = next_link(response)
        if not url:
            break


# ------------------------- (File Merging and Deduping) -----------------------

by_id = {}
for c in existing_data:
    if isinstance(c, dict) and "id" in c:
        by_id[c["id"]] = c
            
try:
    with open(tmp_ndjson, "r", encoding="utf-8") as tmp:
        for line in tmp:
            if not line.strip():
                continue
            c = json.loads(line)
            cid = c.get("id")
            if cid is not None:
                by_id[cid] = c
except FileNotFoundError:
    pass 

# Optional: stable ordering (created_at if present)
def _key(c):
    return (c.get("created_at_iso") or c.get("created_at") or "9999-12-31T23:59:59Z", c.get("id") or 0)
out = sorted(by_id.values(), key=_key)

# ------------------------------ (File Saving) --------------------------------
# Ensure output directory exists
try:
    out_dir = os.path.dirname(OUTPUT_PATH) or "."
    os.makedirs(out_dir, exist_ok=True)
    out_tmp = OUTPUT_PATH + ".tmp"
    # Save to file
    with open(out_tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    os.replace(out_tmp, OUTPUT_PATH)

    try:
        if os.path.getsize(tmp_ndjson) == 0:
            os.remove(tmp_ndjson)
    except OSError:
        pass
    
    print(f"Comments added this update: {new_count}")
    print(f"Total comments after update: {len(out)}")
    
except OSError as e:
    print(f"File write error: {e}")
