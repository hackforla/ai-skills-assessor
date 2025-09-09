#!/usr/bin/env python3
import os
import sys
import json
import time
import logging
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout


# ========================= Configuration & Defaults =========================

OUTPUT_PATH = os.environ.get("INPUT_OUTPUT_PATH", "data/issue_comments.json")
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 15  # seconds
BASE_BACKOFF = 5      # seconds
MAX_BACKOFF  = 60     # seconds

# Prefer GITHUB_TOKEN (Actions) and fall back to GH_TOKEN
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
if not token:
    raise SystemExit("Missing GITHUB_TOKEN/GH_TOKEN. Set one in the workflow env/secrets.")

owner = os.environ.get("INPUT_OWNER", "hackforla")
repo  = os.environ.get("INPUT_REPO", "website")
include_pr_reviews = os.environ.get("INPUT_INCLUDE_PR_REVIEWS", "false").lower() in {"1","true","yes","on"}

users_raw = os.environ.get(
    "INPUT_USERS",
    "JasonUranta,JackRichman,mgodoy2023,Zak234,anonymousanemone"
)
whitelist = [u.strip() for u in users_raw.split(",") if u.strip() and u.strip() != "*"]
users = set(whitelist)
users_lower = {u.lower() for u in users}  # case-insensitive filter; empty means keep all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ================================ Helpers ===================================

def load_existing_and_last_updated(output_path: str = OUTPUT_PATH):
    """Load existing JSON array and return (list, last_updated_iso)."""
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if not isinstance(existing, list):
            logger.warning(f"Existing file is not a JSON list: {output_path}")
            return [], None
    except FileNotFoundError:
        return [], None
    except Exception as e:
        logger.warning(f"Failed to read existing file {output_path}: {e}")
        return [], None

    last = None
    for c in existing:
        ts = (
            c.get("updated_at_iso")
            or c.get("updated_at")
            or c.get("created_at_iso")
            or c.get("created_at")
        )
        if ts and (last is None or ts > last):  # ISO 8601 Z strings compare lexicographically
            last = ts
    return existing, last


def trim_comments(c: dict) -> dict:
    """Return a cleaned-up version of a GitHub issue/review comment (lean user; no reactions)."""
    slimmed = dict(c)  # shallow copy
    verbose_user_keys = [
        "node_id", "avatar_url", "gravatar_id", "url", "html_url", "followers_url",
        "following_url", "gists_url", "starred_url", "subscriptions_url",
        "organizations_url", "repos_url", "events_url", "received_events_url",
    ]
    slimmed.pop("reactions", None)
    if "user" in slimmed and isinstance(slimmed["user"], dict):
        user = dict(slimmed["user"])
        for key in verbose_user_keys:
            user.pop(key, None)
        slimmed["user"] = user
    return slimmed


def to_assessment_record(c: dict, owner: str, repo: str) -> dict:
    """
    Build a compact, assessment-ready record for /issues/comments and keep a slim 'raw' record for provenance.
    """
    login      = (c.get("user") or {}).get("login", "")
    body       = c.get("body") or ""
    created    = c.get("created_at")
    updated    = c.get("updated_at")
    html       = c.get("html_url") or ""
    issue_url  = c.get("issue_url") or ""

    # Extract issue number if possible
    issue_number = None
    try:
        tail = issue_url.rstrip("/").split("/")[-1]
        issue_number = int(tail)
    except Exception:
        pass

    # PR vs Issue: html_url contains /pull/ for PR issue comments
    is_pr_comment = "/pull/" in (html or "")

    # reactions total (from API object, not slimmed)
    rx = (c.get("reactions") or {})
    reactions_total = sum(
        rx.get(k, 0) for k in ["+1", "-1", "laugh", "hooray", "confused", "heart", "rocket", "eyes"]
    )

    return {
        # common keys for grouping/filtering
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
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

        # provenance
        "raw": trim_comments(c),
    }


def to_assessment_record_from_review(c: dict, owner: str, repo: str) -> dict:
    """Compact record builder for /pulls/comments (PR review comments)."""
    login      = (c.get("user") or {}).get("login", "")
    body       = c.get("body") or ""
    created    = c.get("created_at")
    updated    = c.get("updated_at")
    html       = c.get("html_url") or ""
    pr_url     = c.get("pull_request_url") or ""  # e.g., .../pulls/123

    pr_number = None
    try:
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
    except Exception:
        pass

    rx = (c.get("reactions") or {})
    reactions_total = sum(rx.get(k, 0) for k in ["+1","-1","laugh","hooray","confused","heart","rocket","eyes"])

    record = {
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
        "user_login": login,
        "author_association": c.get("author_association"),
        "issue_number": pr_number,        # normalize under the same key
        "is_pr_comment": True,            # it’s on a PR
        "is_review_comment": True,        # distinguish from issue-style PR comments

        "created_at_iso": created,
        "updated_at_iso": updated,
        "comment_length": len(body),

        "url": c.get("url"),
        "html_url": html,
        "issue_url": pr_url,              # keep key name consistent

        "reactions_total": reactions_total,

        "raw": trim_comments(c),
    }

    # Optional: retain some review-specific hints
    if "path" in c:      record["file_path"] = c["path"]
    if "commit_id" in c: record["commit_id"] = c["commit_id"]

    return record


def next_link(resp) -> str | None:
    """Parse the RFC5988 Link header for rel='next'."""
    link = resp.headers.get("Link", "")
    # Example: <...&page=3>; rel="next", <...>; rel="last"
    for part in link.split(","):
        seg = part.strip()
        if 'rel="next"' in seg:
            start = seg.find("<") + 1
            end = seg.find(">", start)
            if start > 0 and end > start:
                return seg[start:end]
    return None


def build_session(token: str) -> requests.Session:
    """Return a configured requests.Session with retries and headers."""
    s = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
    s.headers.update({
        # GitHub accepts "token <...>" or "Bearer <...>"; Bearer works for GITHUB_TOKEN.
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "issue-comments-fetcher/1.0",
    })
    return s


def save_json_atomic(data, output_path: str):
    """Write pretty JSON atomically; ensure directory exists."""
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)


# ================================== Main ====================================

def main():
    session = build_session(token)

    params = {"page": 1, "per_page": 100}
    existing_data, last_seen = load_existing_and_last_updated(OUTPUT_PATH)
    if last_seen:
        params["since"] = last_seen

    logger.info(f"Fetching comments for {owner}/{repo} (since={params.get('since','ALL')}) -> {OUTPUT_PATH}")

    issues_endpoint  = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    reviews_endpoint = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments"

    tmp_ndjson = OUTPUT_PATH + ".new.ndjson"
    backoff   = BASE_BACKOFF
    page_idx  = 1
    new_count = 0

    # --------- Page streaming + filter → NDJSON (issues + optional reviews) ---------

    def fetch_stream(endpoint_url: str, record_builder, label: str):
        """Stream one endpoint, respecting rate limits, writing NDJSON lines with the right record builder."""
        nonlocal page_idx, backoff, new_count  # reuse progress counters/backoff across phases

        url = endpoint_url
        first_request = True  # each endpoint sends params on its own first page

        while url:
            req_params = params if first_request else None
            first_request = False

            try:
                response = session.get(url, params=req_params, timeout=REQUEST_TIMEOUT)
            except (RequestException, Timeout) as e:
                logger.warning(f"[{label}] [Page #{page_idx}] Network error: {e}. Retrying in {backoff}s…")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            # Prefer Retry-After; fallback to X-RateLimit-Reset; else exponential backoff
            if response.status_code in (403, 429):
                remaining = response.headers.get("X-RateLimit-Remaining")
                body = (response.text or "").lower()
                secondary = ("secondary rate limit" in body) or ("abuse detection" in body)

                if remaining == "0" or secondary or response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if isinstance(retry_after, str) and retry_after.isdigit():
                        wait = min(int(retry_after), 600)
                        used_header = "retry-after"
                    else:
                        reset = response.headers.get("X-RateLimit-Reset")
                        if isinstance(reset, str) and reset.isdigit():
                            wait = min(max(int(reset) - int(time.time()) + 2, BASE_BACKOFF), 600)
                            used_header = "rate-limit-reset"
                        else:
                            wait = backoff
                            used_header = "exponential"
                            backoff = min(backoff * 2, MAX_BACKOFF)

                    logger.warning(f"[{label}] [Page #{page_idx}] Rate limited (via={used_header}). Sleeping {wait}s…")
                    time.sleep(wait)
                    if used_header != "exponential":
                        backoff = BASE_BACKOFF  # reset backoff after handled sleep
                    continue

            if response.status_code in (500, 502, 503, 504):
                logger.warning(f"[{label}] [Page #{page_idx}] Server error {response.status_code}. Retrying in {backoff}s…")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            if response.status_code != 200:
                logger.error(f"[{label}] GitHub API {response.status_code}: {response.text[:500]}")
                sys.exit(1)

            # Parse JSON once
            try:
                data = response.json() or []
            except ValueError:
                logger.error(f"[{label}] Non-JSON response from GitHub; aborting.")
                sys.exit(1)

            # Progress logging (best effort)
            last_url = response.links.get("last", {}).get("url")
            if last_url:
                from urllib.parse import urlparse, parse_qs
                try:
                    last_page = parse_qs(urlparse(last_url).query).get("page", ["?"])[0]
                    logger.info(f"[{label}] Page {page_idx}/{last_page}")
                except Exception:
                    logger.info(f"[{label}] Page {page_idx}")
            else:
                logger.info(f"[{label}] Page {page_idx}")

            # Good page → reset backoff
            backoff = BASE_BACKOFF

            # Stream-filter writes with the right builder
            if data:
                for c in data:
                    login = (c.get("user") or {}).get("login", "").lower()
                    if not users_lower or login in users_lower:
                        rec = record_builder(c, owner, repo)
                        tmp.write(json.dumps(rec, ensure_ascii=False))
                        tmp.write("\n")
                        new_count += 1

            page_idx += 1
            url = next_link(response)
            if not url:
                break

    # Always start fresh so temp NDJSON cannot balloon across runs
    try:
        with open(tmp_ndjson, "w", encoding="utf-8") as tmp:
            # Phase 1: /issues/comments
            fetch_stream(issues_endpoint, to_assessment_record, "issues")

            # Phase 2: /pulls/comments (optional)
            if include_pr_reviews:
                logger.info("Include PR review comments enabled — fetching /pulls/comments")
                fetch_stream(reviews_endpoint, to_assessment_record_from_review, "reviews")

    except OSError as e:
        logger.error(f"Failed writing temp NDJSON: {e}")
        # Non-fatal; merge whatever exists.

    # --------- Merge & dedupe with existing ---------
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
    except Exception as e:
        logger.warning(f"Failed to read temp NDJSON: {e}")

    # Stable ordering by updated/created then id
    def _key(c: dict):
        return (
            c.get("updated_at_iso") or c.get("created_at_iso")
            or c.get("updated_at") or c.get("created_at")
            or "9999-12-31T23:59:59Z",
            c.get("id") or 0
        )

    out = sorted(by_id.values(), key=_key)

    # --------- Save final JSON (atomic) ---------
    try:
        save_json_atomic(out, OUTPUT_PATH)
        # Always remove temp NDJSON so it can't grow forever
        try:
            if os.path.exists(tmp_ndjson):
                os.remove(tmp_ndjson)
        except OSError:
            pass

        logger.info(f"Comments added this update: {new_count}")
        logger.info(f"Total comments after update: {len(out)}")
    except OSError as e:
        logger.error(f"File write error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

