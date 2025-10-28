#!/usr/bin/env python3
"""
Fetch issue comments (and optionally PR review comments) into a compact JSON DB.

Highlights:
- Safe incremental sync using per-endpoint watermarks and a -1s guard on 'since'.
- Full-resync support on demand or when config (users/owner/repo/include_pr_reviews) changes.
- Robust pagination with rate-limit handling, capped sleep, 304/ETag support (first page).
- Provenance-rich records with normalized timestamps and consistent keys.
- Oldest→newest sort for stable appends; clients can reverse if they prefer latest-first.
- Clear end-of-run logging and partial-success tolerance.
"""

from __future__ import annotations

import os
import json
import time
import shutil
import random
import logging
import hashlib
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta, timezone
from requests.exceptions import RequestException, Timeout
from typing import Any, Dict, Iterable, List, Optional, Tuple
from email.utils import parsedate_to_datetime

# ========================= Configuration & Defaults =========================

OUTPUT_PATH = os.environ.get("INPUT_OUTPUT_PATH", "../data/issue-comments.json")
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 30  # seconds
BASE_BACKOFF = 5      # seconds
MAX_BACKOFF  = 60     # seconds
MAX_TOTAL_SLEEP = 900 # cap total rate-limit sleep at 15 minutes per endpoint
MAX_CONSECUTIVE_FAILS = 5

REACTION_KEYS = ["+1", "-1", "laugh", "hooray", "confused", "heart", "rocket", "eyes"]

# Prefer GITHUB_TOKEN (Actions) and fall back to GH_TOKEN
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

if not token:
    raise SystemExit("Missing GITHUB_TOKEN/GH_TOKEN. Set one in the workflow env/secrets.")

# Raw env values first
owner_env = os.environ.get("INPUT_OWNER", "hackforla").strip()
repo_env  = os.environ.get("INPUT_REPO",  "website").strip()

# Normalize "owner/repo" passed in either var
def _split_owner_repo(o: str, r: str) -> tuple[str, str]:
    if "/" in r:
        o2, r2 = r.split("/", 1)
        return (o2.strip() or o, r2.strip() or r)
    if "/" in o:
        o2, r2 = o.split("/", 1)
        return (o2.strip() or o2, r2.strip() or r)
    return (o, r)

owner, repo = _split_owner_repo(owner_env, repo_env)

# Users filter:
# "*" means ALL, empty -> curated default list
DEFAULT_USERS = "JasonUranta,JackRichman,mgodoy2023,Zak234,anonymousanemone"
users_env = (os.environ.get("INPUT_USERS", "").strip())
if users_env == "":
    users_env = DEFAULT_USERS

if users_env == "*":
    users_lower: Optional[set[str]] = None
else:
    parsed = {u.strip().lower() for u in users_env.split(",") if u.strip()}
    users_lower = parsed if parsed else {u.strip().lower() for u in DEFAULT_USERS.split(",")}

include_pr_reviews = os.environ.get("INPUT_INCLUDE_PR_REVIEWS", "false").lower() in {"1","true","yes","on"}
full_resync_input  = os.environ.get("INPUT_FULL_RESYNC", "false").lower() in {"1","true","yes","on"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("issue-comments-fetcher")

# ================================ Helpers ===================================

def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _min_updated(items: Iterable[dict]) -> Optional[datetime]:
    m: Optional[datetime] = None
    for c in items:
        ts = c.get("updated_at") or c.get("created_at")
        dt = _parse_iso(ts)
        if dt and (m is None or dt < m):
            m = dt
    return m

def build_session(tok: str) -> requests.Session:
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
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "issue-comments-fetcher/1.4",
    })
    return s

def load_existing(output_path: str = OUTPUT_PATH) -> List[dict]:
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning(f"Existing file is not a JSON list: {output_path}")
            return []
        return data
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning(f"Failed to read existing file {output_path}: {e}")
        try:
            shutil.move(output_path, output_path + ".corrupt")
            logger.warning(f"Moved corrupted JSON to {output_path}.corrupt")
        except Exception:
            pass
        return []

def last_seen_by_endpoint(existing: List[dict]) -> Dict[str, Optional[str]]:
    latest: Dict[str, Optional[str]] = {"issues": None, "reviews": None}
    for c in existing:
        src = c.get("source_endpoint")
        if src not in ("issues", "reviews"):
            src = "reviews" if c.get("is_review_comment") else "issues"
        ts = c.get("updated_at_iso") or c.get("created_at_iso") or c.get("updated_at") or c.get("created_at")
        if not ts:
            continue
        if latest[src] is None or ts > latest[src]:
            latest[src] = ts
    return latest

def decrement_one_second(iso_str: str) -> str:
    try:
        dt = _parse_iso(iso_str)
        if dt:
            return _iso(dt - timedelta(seconds=1))
    except Exception:
        pass
    return iso_str

def next_url(resp: requests.Response) -> Optional[str]:
    return (resp.links.get("next") or {}).get("url")

def save_json_atomic(data: List[dict], output_path: str) -> None:
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)

def save_markdown(data: List[dict], json_path: str) -> None:
    """Convert JSON records to Markdown and save alongside the JSON."""
    md_path = json_path.replace('.json', '.md')
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# GitHub Issue Comments - {owner}/{repo}\n\n")
        f.write(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n\n")
        f.write(f"Total comments: {len(data)}\n\n")
        f.write("---\n\n")
        
        for comment in data:
            user = comment.get('user_login', 'Unknown')
            created = comment.get('created_at_iso', 'Unknown')
            issue_num = comment.get('issue_number', '?')
            html_url = comment.get('html_url', '')
            body = comment.get('raw', {}).get('body', '')
            is_pr = comment.get('is_pr_comment', False)
            comment_type = "PR" if is_pr else "Issue"
            
            f.write(f"## [{comment_type} #{issue_num}]({html_url}) - @{user}\n\n")
            f.write(f"**Created:** {created}\n\n")
            f.write(f"{body}\n\n")
            f.write("---\n\n")

def _sanitize_for_filename(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in s)

def etag_path_for(endpoint_key: str) -> str:
    out_dir = os.path.dirname(OUTPUT_PATH) or "."
    os.makedirs(out_dir, exist_ok=True)
    o = _sanitize_for_filename(owner)
    r = _sanitize_for_filename(repo)
    return os.path.join(out_dir, f".etag.{o}.{r}.{endpoint_key}")

def read_etag(endpoint_key: str) -> Optional[str]:
    try:
        with open(etag_path_for(endpoint_key), "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None
    except Exception:
        return None

def write_etag(endpoint_key: str, etag: Optional[str]) -> None:
    if not etag:
        return
    try:
        with open(etag_path_for(endpoint_key), "w", encoding="utf-8") as f:
            f.write(etag)
    except Exception:
        pass

def trim_user(u: dict) -> dict:
    if not isinstance(u, dict):
        return u
    user = dict(u)
    verbose_user_keys = [
        "node_id", "avatar_url", "gravatar_id", "url", "followers_url",
        "following_url", "gists_url", "starred_url", "subscriptions_url",
        "organizations_url", "repos_url", "events_url", "received_events_url",
    ]
    for k in verbose_user_keys:
        user.pop(k, None)
    return user

def trim_comments(c: dict) -> dict:
    slimmed = dict(c)
    slimmed.pop("reactions", None)
    if "user" in slimmed and isinstance(slimmed["user"], dict):
        slimmed["user"] = trim_user(slimmed["user"])
    return slimmed

def to_assessment_record(c: dict, owner: str, repo: str, source_endpoint: str) -> dict:
    login      = (c.get("user") or {}).get("login", "")
    user_html  = (c.get("user") or {}).get("html_url")
    body       = c.get("body") or ""
    created    = c.get("created_at")
    updated    = c.get("updated_at")
    html       = c.get("html_url") or ""
    issue_url  = c.get("issue_url") or ""

    issue_number = None
    try:
        issue_number = int(issue_url.rstrip("/").split("/")[-1])
    except Exception:
        pass

    is_pr_comment = "/pull/" in (html or "")

    rx = (c.get("reactions") or {})
    reactions_breakdown = {k: rx.get(k, 0) for k in REACTION_KEYS}
    reactions_total = sum(reactions_breakdown.values())

    return {
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
        "source_endpoint": source_endpoint,
        "user_login": login,
        "user_html_url": user_html,
        "author_association": c.get("author_association"),
        "issue_number": issue_number,
        "pr_number": issue_number if is_pr_comment else None,
        "is_pr_comment": is_pr_comment,
        "is_review_comment": False,
        "created_at_iso": created,
        "updated_at_iso": updated,
        "comment_length": len(body),
        "url": c.get("url"),
        "html_url": html,
        "issue_url": issue_url,
        "reactions_total": reactions_total,
        "reactions_breakdown": reactions_breakdown,
        "raw": trim_comments(c),
    }

def to_assessment_record_from_review(c: dict, owner: str, repo: str, source_endpoint: str) -> dict:
    login      = (c.get("user") or {}).get("login", "")
    user_html  = (c.get("user") or {}).get("html_url")
    body       = c.get("body") or ""
    created    = c.get("created_at")
    updated    = c.get("updated_at")
    html       = c.get("html_url") or ""
    pr_url     = c.get("pull_request_url") or ""  # .../pulls/123

    pr_number = None
    try:
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
    except Exception:
        pass

    rx = (c.get("reactions") or {})
    reactions_breakdown = {k: rx.get(k, 0) for k in REACTION_KEYS}
    reactions_total = sum(reactions_breakdown.values())

    record = {
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
        "source_endpoint": source_endpoint,
        "user_login": login,
        "user_html_url": user_html,
        "author_association": c.get("author_association"),
        "issue_number": pr_number,
        "pr_number": pr_number,
        "is_pr_comment": True,
        "is_review_comment": True,
        "created_at_iso": created,
        "updated_at_iso": updated,
        "comment_length": len(body),
        "url": c.get("url"),
        "html_url": html,
        "issue_url": pr_url,
        "reactions_total": reactions_total,
        "reactions_breakdown": reactions_breakdown,
        "raw": trim_comments(c),
    }
    if "path" in c:      record["file_path"] = c["path"]
    if "commit_id" in c: record["commit_id"] = c["commit_id"]
    return record

# ------------------------- Sync Meta (config signature) ----------------------

def _users_signature() -> str:
    if users_lower is None:
        return "ALL"
    return ",".join(sorted(users_lower))

def _config_signature() -> str:
    payload = f"{owner}|{repo}|{include_pr_reviews}|{_users_signature()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _meta_path() -> str:
    out_dir = os.path.dirname(OUTPUT_PATH) or "."
    os.makedirs(out_dir, exist_ok=True)
    o = _sanitize_for_filename(owner)
    r = _sanitize_for_filename(repo)
    return os.path.join(out_dir, f".syncmeta.{o}.{r}.json")

def read_meta() -> dict:
    try:
        with open(_meta_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_meta(sig: str) -> None:
    try:
        with open(_meta_path(), "w", encoding="utf-8") as f:
            json.dump({"signature": sig, "written_at": _iso(datetime.now(timezone.utc))}, f, indent=2)
    except Exception:
        pass

# ============================== Fetch Core ===================================

def _parse_retry_after(value: Optional[str]) -> Optional[int]:
    """
    Returns seconds if Retry-After is a delta-seconds or HTTP-date.
    """
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return max(0, int(value))
    try:
        dt = parsedate_to_datetime(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(delta))
    except Exception:
        return None

def get_with_retries(session: requests.Session, url: str, params: Optional[dict], timeout: int,
                     backoff_state: Dict[str, Any], label: str) -> Optional[requests.Response]:
    backoff = backoff_state["backoff"]
    total_sleep = backoff_state["total_sleep"]

    try:
        resp = session.get(url, params=params, timeout=timeout)
    except (RequestException, Timeout) as e:
        logger.warning(f"[{label}] Network error: {e}. Retrying in {backoff}s…")
        time.sleep(backoff + random.uniform(0, 1.5))
        backoff_state["backoff"] = min(backoff * 2, MAX_BACKOFF)
        backoff_state["consecutive_failures"] = backoff_state.get("consecutive_failures", 0) + 1
        return None

    if resp.status_code in (403, 429):
        remaining = resp.headers.get("X-RateLimit-Remaining")
        try:
            rem_int = int(remaining) if remaining is not None else None
        except ValueError:
            rem_int = None

        body_lc = (resp.text or "").lower()
        secondary = ("secondary rate limit" in body_lc) or ("abuse detection" in body_lc)

        if rem_int == 0 or secondary or resp.status_code == 429:
            retry_after_hdr = resp.headers.get("Retry-After")
            wait = _parse_retry_after(retry_after_hdr)
            used = "retry-after" if wait is not None else None
            if wait is None:
                reset = resp.headers.get("X-RateLimit-Reset")
                try:
                    if reset is not None:
                        wait = max(int(reset) - int(time.time()) + 2, BASE_BACKOFF)
                        wait = min(wait, 600)
                        used = "rate-limit-reset"
                except ValueError:
                    pass
            if wait is None:
                wait = backoff_state["backoff"]
                used = "exponential"
                backoff_state["backoff"] = min(wait * 2, MAX_BACKOFF)

            if total_sleep + wait > MAX_TOTAL_SLEEP:
                logger.error(f"[{label}] Rate-limit sleep budget exceeded. Aborting this endpoint early.")
                backoff_state["abort"] = True
                return None

            jitter = random.uniform(0, 1.5)
            logger.warning(f"[{label}] Rate limited (via={used}). Sleeping {wait + jitter:.1f}s…")
            time.sleep(wait + jitter)
            backoff_state["total_sleep"] += wait
            if used != "exponential":
                backoff_state["backoff"] = BASE_BACKOFF
            backoff_state["consecutive_failures"] = 0
            return None

    if resp.status_code in (500, 502, 503, 504):
        logger.warning(f"[{label}] Server error {resp.status_code}. Retrying in {backoff_state['backoff']}s…")
        time.sleep(backoff_state["backoff"] + random.uniform(0, 1.0))
        backoff_state["backoff"] = min(backoff_state["backoff"] * 2, MAX_BACKOFF)
        backoff_state["consecutive_failures"] = backoff_state.get("consecutive_failures", 0) + 1
        return None

    if resp.status_code not in (200, 304):
        rid = resp.headers.get("X-GitHub-Request-Id", "?")
        logger.error(f"[{label}] GitHub API {resp.status_code} (request-id={rid}). Skipping this page.")
        if resp.status_code in (401, 404, 422):
            backoff_state["abort"] = True
        else:
            backoff_state["consecutive_failures"] = backoff_state.get("consecutive_failures", 0) + 1
        return None

    backoff_state["backoff"] = BASE_BACKOFF
    backoff_state["consecutive_failures"] = 0
    return resp

def probe_since_support(session: requests.Session, endpoint_url: str, params_with_since: dict, label: str) -> Tuple[bool, Optional[List[dict]], Optional[requests.Response]]:
    backoff_state = {"backoff": BASE_BACKOFF, "total_sleep": 0, "consecutive_failures": 0}
    resp = None
    for _ in range(5):
        resp = get_with_retries(session, endpoint_url, params_with_since, REQUEST_TIMEOUT, backoff_state, f"{label}-probe")
        if resp is None:
            if backoff_state.get("abort") or backoff_state.get("consecutive_failures", 0) >= MAX_CONSECUTIVE_FAILS:
                break
            continue
        if resp.status_code == 304:
            return True, [], resp
        for attempt in range(3):
            try:
                data = resp.json() or []
                break
            except ValueError:
                if attempt == 2:
                    logger.error(f"[{label}] Non-JSON response during probe; assuming since unsupported.")
                    return False, None, resp
                time.sleep(1)
        s = params_with_since.get("since")
        if s:
            earliest = _min_updated(data)
            if earliest and earliest < _parse_iso(s):
                logger.warning(f"[{label}] Endpoint appears to ignore 'since'; falling back to full fetch.")
                return False, data, resp
        return True, data, resp
    logger.warning(f"[{label}] Could not probe 'since' (transient). Assuming supported.")
    return True, None, None

def fetch_endpoint(session: requests.Session, endpoint_url: str, endpoint_key: str,
                   record_builder, label: str, since_iso: Optional[str], enable_conditional: bool) -> Tuple[int, List[dict]]:
    """
    Stream pages and return list of normalized records. Tolerates partial failures.
    Uses ETag for first page when enable_conditional is True and no 'since'.
    """
    new_count = 0
    results: List[dict] = []
    backoff_state: Dict[str, Any] = {"backoff": BASE_BACKOFF, "total_sleep": 0, "skipped_pages": 0, "consecutive_failures": 0}
    page_idx = 1
    attempted_pages = 0

    base_params: Dict[str, Any] = {"page": 1, "per_page": 100}
    first_page_data: Optional[List[dict]] = None
    first_resp: Optional[requests.Response] = None

    if enable_conditional and since_iso:
        base_params["since"] = decrement_one_second(since_iso)
        supports_since, first_page_data, first_resp = probe_since_support(session, endpoint_url, base_params, label)
        if not supports_since:
            base_params.pop("since", None)

    if enable_conditional and "since" not in base_params:
        etag = read_etag(endpoint_key)
        if etag:
            session.headers["If-None-Match"] = etag

    url = endpoint_url
    first_request = True
    while url:
        params = base_params if first_request else None
        first_request = False

        resp: Optional[requests.Response]
        data: List[dict] = []
        attempted_pages += 1

        if page_idx == 1 and first_page_data is not None and first_resp is not None:
            resp = first_resp
            data = first_page_data
        else:
            resp = get_with_retries(session, url, params, REQUEST_TIMEOUT, backoff_state, label)
            if resp is None:
                if backoff_state.get("abort"):
                    logger.error(f"[{label}] Aborting endpoint (non-retryable or policy).")
                    break
                if backoff_state.get("consecutive_failures", 0) >= MAX_CONSECUTIVE_FAILS:
                    logger.error(f"[{label}] Aborting endpoint after repeated failures.")
                    break
                continue

            if resp.status_code == 304:
                logger.info(f"[{label}] 304 Not Modified — no new data since last ETag.")
                break

            for attempt in range(3):
                try:
                    data = resp.json() or []
                    break
                except ValueError:
                    if attempt == 2:
                        rid = resp.headers.get("X-GitHub-Request-Id", "?")
                        logger.error(f"[{label}] Non-JSON response (request-id={rid}). Skipping this page.")
                        backoff_state["skipped_pages"] = backoff_state.get("skipped_pages", 0) + 1
                        backoff_state["consecutive_failures"] = backoff_state.get("consecutive_failures", 0) + 1
                    else:
                        time.sleep(1)

        last_url = (resp.links.get("last") or {}).get("url") if resp else None
        if last_url:
            from urllib.parse import urlparse, parse_qs
            try:
                last_page = (parse_qs(urlparse(last_url).query).get("page") or ["?"])[0]
                logger.info(f"[{label}] Page {page_idx}/{last_page} — fetched {len(data)} items")
            except Exception:
                logger.info(f"[{label}] Page {page_idx} — fetched {len(data)} items")
        else:
            logger.info(f"[{label}] Page {page_idx} — fetched {len(data)} items")

        if page_idx == 1 and resp is not None and enable_conditional:
            write_etag(endpoint_key, resp.headers.get("ETag"))

        if data:
            for c in data:
                login = (c.get("user") or {}).get("login", "").lower()
                if users_lower is None or login in users_lower:
                    rec = record_builder(c, owner, repo, endpoint_key)
                    if not rec.get("updated_at_iso") and c.get("updated_at"):
                        rec["updated_at_iso"] = c["updated_at"]
                    if not rec.get("created_at_iso") and c.get("created_at"):
                        rec["created_at_iso"] = c["created_at"]
                    results.append(rec)
                    new_count += 1

        page_idx += 1
        url = next_url(resp) if resp is not None else None

    if enable_conditional:
        session.headers.pop("If-None-Match", None)

    logger.info(
        f"[{label}] Summary: attempted_pages={attempted_pages}, "
        f"skipped_pages={backoff_state.get('skipped_pages', 0)}, "
        f"new_records={new_count}"
    )

    return new_count, results

# ================================== Main ====================================

def main() -> None:
    start_ts = time.time()
    session = build_session(token)

    effective_sig = _config_signature()
    meta = read_meta()
    config_changed = (meta.get("signature") != effective_sig)
    force_full_resync = full_resync_input or config_changed

    logger.info(
        f"Owner/Repo: {owner}/{repo}; include_pr_reviews={include_pr_reviews}; "
        f"users={'ALL' if users_lower is None else ','.join(sorted(users_lower))}; "
        f"output_path={OUTPUT_PATH}; full_resync={force_full_resync} "
        f"(config_changed={config_changed})"
    )

    existing_data = [] if force_full_resync else load_existing(OUTPUT_PATH)
    watermarks = None if force_full_resync else last_seen_by_endpoint(existing_data)

    issues_endpoint_url  = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    reviews_endpoint_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments"

    total_new = 0
    new_records: List[dict] = []

    n_issues, rec_issues = fetch_endpoint(
        session=session,
        endpoint_url=issues_endpoint_url,
        endpoint_key="issues",
        record_builder=to_assessment_record,
        label="issues",
        since_iso=None if force_full_resync else (watermarks or {}).get("issues"),
        enable_conditional=not force_full_resync,
    )
    total_new += n_issues
    new_records.extend(rec_issues)

    if include_pr_reviews:
        n_reviews, rec_reviews = fetch_endpoint(
            session=session,
            endpoint_url=reviews_endpoint_url,
            endpoint_key="reviews",
            record_builder=to_assessment_record_from_review,
            label="reviews",
            since_iso=None if force_full_resync else (watermarks or {}).get("reviews"),
            enable_conditional=not force_full_resync,
        )
        total_new += n_reviews
        new_records.extend(rec_reviews)

    by_id: Dict[Any, dict] = {}
    for c in (existing_data or []):
        if isinstance(c, dict) and "id" in c:
            by_id[c["id"]] = c
    for c in new_records:
        cid = c.get("id")
        if cid is not None:
            by_id[cid] = c

    def _key(c: dict) -> Tuple[str, Any]:
        t = (
            c.get("updated_at_iso") or
            c.get("created_at_iso") or
            "0000-01-01T00:00:00Z"
        )
        return (t, c.get("id") or 0)

    out = sorted(by_id.values(), key=_key)

    try:
        save_json_atomic(out, OUTPUT_PATH)
        save_markdown(out, OUTPUT_PATH)
        write_meta(effective_sig)  # persist current config signature after a successful write
        logger.info(f"Comments added this update: {total_new}")
        logger.info(f"Total comments after update: {len(out)}")
        if total_new == 0:
            logger.info("No new comments detected; output file unchanged.")
    except OSError as e:
        logger.error(f"File write error: {e}")
        raise SystemExit(1)
    finally:
        dur = time.time() - start_ts
        logger.info(f"Run completed in {dur:.1f}s")

if __name__ == "__main__":
    main()

