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
import math
import random
import shutil
import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout
from urllib3.util.retry import Retry


# ========================= Configuration & Defaults =========================

OUTPUT_PATH = os.environ.get("INPUT_OUTPUT_PATH", "../data/issue-comments.json")
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 30
BASE_BACKOFF = 5
MAX_BACKOFF = 60
MAX_TOTAL_SLEEP = 900
MAX_CONSECUTIVE_FAILS = 5

REACTION_KEYS = ["+1", "-1", "laugh", "hooray", "confused", "heart", "rocket", "eyes"]

token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
if not token:
    raise SystemExit("Missing GITHUB_TOKEN/GH_TOKEN. Set one in the workflow env/secrets.")

owner_env = os.environ.get("INPUT_OWNER", "hackforla").strip()
repo_env = os.environ.get("INPUT_REPO", "website").strip()
notes_env = os.environ.get("INPUT_NOTES", "").strip()


def _split_owner_repo(o: str, r: str) -> tuple[str, str]:
    if "/" in r:
        o2, r2 = r.split("/", 1)
        return (o2.strip() or o, r2.strip() or r)
    if "/" in o:
        o2, r2 = o.split("/", 1)
        return (o2.strip() or o2, r2.strip() or r)
    return (o, r)


owner, repo = _split_owner_repo(owner_env, repo_env)

DEFAULT_USERS = "JasonUranta,JackRichman,mgodoy2023,Zak234,anonymousanemone"
users_env = os.environ.get("INPUT_USERS", "").strip()
if users_env == "":
    users_env = DEFAULT_USERS

if users_env == "*":
    users_lower: Optional[set[str]] = None
else:
    parsed = {u.strip().lower() for u in users_env.split(",") if u.strip()}
    users_lower = parsed if parsed else {u.strip().lower() for u in DEFAULT_USERS.split(",")}

include_pr_reviews = os.environ.get("INPUT_INCLUDE_PR_REVIEWS", "false").lower() in {
    "1", "true", "yes", "on"
}

full_resync_input = os.environ.get("INPUT_FULL_RESYNC", "false").lower() in {
    "1", "true", "yes", "on"
}

commit_to_repo = os.environ.get("INPUT_COMMIT_TO_REPO", "false").lower() in {
    "1", "true", "yes", "on"
}

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


def build_session(tok: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
    session.headers.update({
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "issue-comments-fetcher/1.4",
    })
    return session


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _cache_dir() -> str:
    base_dir = os.path.dirname(OUTPUT_PATH) or "."
    return _ensure_dir(os.path.join(base_dir, "comment_cache"))


def load_existing(output_path: str) -> List[dict]:
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and isinstance(data.get("comments"), list):
            return data["comments"]
        if isinstance(data, list):
            return data

        logger.warning(f"Unexpected JSON structure: {output_path}")
        return []
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


def resolve_latest_existing_json_path(base_output_path: str) -> str:
    base = Path(base_output_path)
    if base.is_file():
        return str(base)
    if not base.parent.exists():
        return str(base)

    pattern = f"{base.stem}-*.json"
    candidates = list(base.parent.glob(pattern))
    if not candidates:
        return str(base)

    latest = sorted(candidates, key=lambda p: p.name)[-1]
    return str(latest)


def make_timestamped_output_paths(base_output_path: str, run_dt: datetime) -> Tuple[str, str]:
    base = Path(base_output_path)
    ts = run_dt.strftime("%Y%m%dT%H%M%SZ")
    json_name = f"{base.stem}-{ts}{base.suffix or '.json'}"
    md_name = f"{base.stem}-{ts}.md"
    return str(base.with_name(json_name)), str(base.with_name(md_name))


def save_json_atomic(data, output_path: str) -> None:
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)


def save_markdown(data: List[dict], md_path: str, metadata: Dict[str, Any]) -> None:
    out_dir = os.path.dirname(md_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    with open(md_path, "w", encoding="utf-8") as f:
        # metadata
        f.write("---\n")
        for key in [
            "owner", "repo", "fetched_at", "description",
            "input_owner", "input_repo", "input_usernames",
            "input_PR_comments", "output_path", "committed_to_repo",
            "input_notes", "total_comments", "new_comments",
        ]:
            if key not in metadata:
                continue
            value = metadata[key]
            if isinstance(value, list):
                f.write(f"{key}:\n")
                for item in value:
                    f.write(f"  - {item}\n")
            else:
                if isinstance(value, str) and ":" in value:
                    f.write(f'{key}: "{value}"\n')
                else:
                    f.write(f"{key}: {value}\n")
        f.write("---\n\n")

        f.write(f"# GitHub Issue Comments - {metadata.get('owner')}/{metadata.get('repo')}\n\n")
        f.write(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n\n")
        f.write(f"Total comments: {len(data)}\n\n---\n\n")

        for c in data:
            user = c.get("user_login", "Unknown")
            created = c.get("created_at_iso", "Unknown")
            issue_num = c.get("issue_number", "?")
            html_url = c.get("html_url", "")
            body = c.get("raw", {}).get("body", "")
            is_pr = c.get("is_pr_comment", False)
            comment_type = "PR" if is_pr else "Issue"

            f.write(f"## [{comment_type} #{issue_num}]({html_url}) - @{user}\n\n")
            f.write(f"**Created:** {created}\n\n")
            f.write(f"{body}\n\n---\n\n")


def _sanitize_for_filename(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in s)


def etag_path_for(endpoint_key: str) -> str:
    cache = _cache_dir()
    o = _sanitize_for_filename(owner)
    r = _sanitize_for_filename(repo)
    return os.path.join(cache, f".etag_{o}__{r}__{endpoint_key}.txt")


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


def _meta_path() -> str:
    cache = _cache_dir()
    o = _sanitize_for_filename(owner)
    r = _sanitize_for_filename(repo)
    return os.path.join(cache, f".meta_{o}__{r}.json")


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
    if not value:
        return None
    v = value.strip()
    if v.isdigit():
        return int(v)
    try:
        dt = parsedate_to_datetime(value)
        now = datetime.now(timezone.utc)
        return max(0, int((dt - now).total_seconds()))
    except Exception:
        return None


@dataclass
class EndpointWatermark:
    since: Optional[str] = None
    etag: Optional[str] = None


def fetch_endpoint(
    session: requests.Session,
    endpoint_url: str,
    endpoint_key: str,
    record_builder,
    label: str,
    since_iso: Optional[str],
    enable_conditional: bool,
) -> Tuple[int, List[dict]]:

    params = {"per_page": 100}
    if since_iso:
        params["since"] = since_iso

    logger.info(
        f"[{label}] Starting fetch for {endpoint_url} "
        f"(since={since_iso}, conditional={enable_conditional})"
    )

    total_new = 0
    collected: List[dict] = []
    backoff_state = {"backoff": BASE_BACKOFF, "abort": False}
    total_sleep = 0.0
    consecutive_fails = 0

    while True:
        if backoff_state["abort"]:
            logger.error(f"[{label}] Aborting due to rate-limit exhaustion.")
            break

        headers = {}
        etag = read_etag(endpoint_key) if enable_conditional else None
        if enable_conditional and etag:
            headers["If-None-Match"] = etag

        try:
            resp = session.get(
                endpoint_url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except Timeout:
            consecutive_fails += 1
            logger.warning(f"[{label}] Timeout (#{consecutive_fails})")
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                logger.error(f"[{label}] Too many timeouts. Aborting.")
                break
            time.sleep(BASE_BACKOFF)
            continue
        except RequestException as e:
            consecutive_fails += 1
            logger.warning(f"[{label}] Request error: {e!r}")
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                logger.error(f"[{label}] Too many errors. Aborting.")
                break
            time.sleep(BASE_BACKOFF)
            continue

        consecutive_fails = 0
        status = resp.status_code
        etag_new = resp.headers.get("ETag")

        if status == 304:
            logger.info(f"[{label}] 304 Not Modified")
            break

        if status == 403 and "rate limit" in (resp.text or "").lower():
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            limit_reset = resp.headers.get("X-RateLimit-Reset")

            wait = None
            used = None
            if retry_after is not None:
                wait = retry_after
                used = "Retry-After"
            elif limit_reset:
                try:
                    ts = int(limit_reset)
                    now = int(time.time())
                    if ts > now:
                        wait = min(ts - now, 600)
                        used = "rate-limit-reset"
                except ValueError:
                    pass

            if wait is None:
                wait = backoff_state["backoff"]
                used = "exponential"
                backoff_state["backoff"] = min(wait * 2, MAX_BACKOFF)

            if total_sleep + wait > MAX_TOTAL_SLEEP:
                logger.error(f"[{label}] Sleep budget exceeded. Aborting.")
                backoff_state["abort"] = True
                break

            jitter = min(5.0, wait * 0.1)
            sleep_for = wait + random.random() * jitter
            logger.warning(f"[{label}] Rate-limited ({used}); sleeping ~{sleep_for:.1f}s")
            time.sleep(sleep_for)
            total_sleep += sleep_for
            continue

        if status >= 400:
            logger.error(f"[{label}] HTTP {status}: {resp.text[:500]}")
            break

        try:
            items = resp.json()
        except ValueError:
            logger.error(f"[{label}] Bad JSON body")
            break

        if not isinstance(items, list):
            logger.error(f"[{label}] Expected a list, got: {items!r}")
            break

        if etag_new:
            write_etag(endpoint_key, etag_new)

        if not items:
            break

        logger.info(f"[{label}] Retrieved {len(items)} items")
        for c in items:
            rec = record_builder(c)
            if rec is not None:
                collected.append(rec)
                total_new += 1

        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break

        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                seg = part.split(";")[0].strip()
                if seg.startswith("<") and seg.endswith(">"):
                    next_url = seg[1:-1]
        if not next_url:
            break

        endpoint_url = next_url

    return total_new, collected


# ============================= Record Builders ===============================

def _within_users_filter(login: Optional[str]) -> bool:
    if users_lower is None:
        return True
    if not login:
        return False
    return login.lower() in users_lower


def _reactions_breakdown(raw: dict) -> Dict[str, int]:
    reactions = raw.get("reactions") or {}
    out = {}
    for k in REACTION_KEYS:
        v = reactions.get(k)
        if isinstance(v, int):
            out[k] = v
    return out


def trim_comments(raw: dict) -> dict:
    keys = [
        "id", "node_id", "body", "user", "author_association",
        "created_at", "updated_at", "url", "html_url",
        "pull_request_url", "issue_url", "reactions",
    ]
    return {k: raw.get(k) for k in keys}


def to_assessment_record_from_issue(c: dict) -> Optional[dict]:
    user = c.get("user") or {}
    login = user.get("login")
    user_html = user.get("html_url")

    if not _within_users_filter(login):
        return None

    created = c.get("created_at")
    updated = c.get("updated_at") or created
    body = c.get("body") or ""
    issue_url = c.get("issue_url") or ""
    html = c.get("html_url") or ""
    reactions_breakdown = _reactions_breakdown(c)
    reactions_total = sum(reactions_breakdown.values())

    try:
        issue_number = int(issue_url.rstrip("/").split("/")[-1])
    except Exception:
        issue_number = None

    return {
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
        "source_endpoint": "issues",
        "user_login": login,
        "user_html_url": user_html,
        "author_association": c.get("author_association"),
        "issue_number": issue_number,
        "pr_number": None,
        "is_pr_comment": False,
        "is_review_comment": False,
        "created_at_iso": created,
        "updated_at_iso": updated,
        "comment_length": len(body),
        "url": c.get("url"),
        "html_url": html,
        "issue_url": c.get("issue_url"),
        "reactions_total": reactions_total,
        "reactions_breakdown": reactions_breakdown,
        "raw": trim_comments(c),
    }


def to_assessment_record_from_review(c: dict) -> Optional[dict]:
    user = c.get("user") or {}
    login = user.get("login")
    user_html = user.get("html_url")

    if not _within_users_filter(login):
        return None

    created = c.get("created_at")
    updated = c.get("updated_at") or created
    body = c.get("body") or ""
    pr_url = c.get("pull_request_url") or ""
    html = c.get("html_url") or ""
    reactions_breakdown = _reactions_breakdown(c)
    reactions_total = sum(reactions_breakdown.values())

    try:
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
    except Exception:
        pr_number = None

    record = {
        "id": c.get("id"),
        "owner": owner,
        "repo": repo,
        "source_endpoint": "reviews",
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

    if "path" in c:
        record["file_path"] = c["path"]
    if "commit_id" in c:
        record["commit_id"] = c["commit_id"]

    return record


# ------------------------- Sync Meta (config signature) ----------------------

def _users_signature() -> str:
    if users_lower is None:
        return "ALL"
    return ",".join(sorted(users_lower))


def _config_signature() -> str:
    payload = f"{owner}|{repo}|{include_pr_reviews}|{_users_signature()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ================================== Main ====================================

def main() -> None:
    start_ts = time.time()
    session = build_session(token)
    run_dt = datetime.now(timezone.utc)

    effective_sig = _config_signature()
    meta = read_meta()
    config_changed = meta.get("signature") != effective_sig
    force_full_resync = full_resync_input or config_changed

    logger.info(
        f"Owner/Repo: {owner}/{repo}; include_pr_reviews={include_pr_reviews}; "
        f"users={'ALL' if users_lower is None else ','.join(sorted(users_lower))}; "
        f"output_path={OUTPUT_PATH}; full_resync={force_full_resync} "
        f"(config_changed={config_changed})"
    )

    existing_json_path = resolve_latest_existing_json_path(OUTPUT_PATH)
    logger.info(f"Using base JSON for incremental sync: {existing_json_path}")

    existing_data = [] if force_full_resync else load_existing(existing_json_path)
    watermarks = None if force_full_resync else {"issues": None, "reviews": None}

    if watermarks is not None:
        for c in existing_data:
            src = c.get("source_endpoint") or ("reviews" if c.get("is_review_comment") else "issues")
            ts = c.get("updated_at_iso") or c.get("created_at_iso")
            if not ts:
                continue
            prev = watermarks.get(src)
            if prev is None or ts > prev:
                watermarks[src] = ts

    issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments"

    total_new = 0
    new_records: List[dict] = []

    n_issues, rec_issues = fetch_endpoint(
        session,
        issues_url,
        "issues",
        to_assessment_record_from_issue,
        "issues",
        since_iso=None if force_full_resync else watermarks.get("issues"),
        enable_conditional=not force_full_resync,
    )
    total_new += n_issues
    new_records.extend(rec_issues)

    if include_pr_reviews:
        n_reviews, rec_reviews = fetch_endpoint(
            session,
            reviews_url,
            "reviews",
            to_assessment_record_from_review,
            "reviews",
            since_iso=None if force_full_resync else watermarks.get("reviews"),
            enable_conditional=not force_full_resync,
        )
        total_new += n_reviews
        new_records.extend(rec_reviews)

    # merge by id
    by_id: Dict[Any, dict] = {}
    for c in existing_data:
        if isinstance(c, dict) and "id" in c:
            by_id[c["id"]] = c
    for c in new_records:
        cid = c.get("id")
        if cid is not None:
            by_id[cid] = c

    def _key(c: dict) -> Tuple[str, Any]:
        t = (
            c.get("updated_at_iso")
            or c.get("created_at_iso")
            or "0000-01-01T00:00:00Z"
        )
        return t, c.get("id") or 0

    out = sorted(by_id.values(), key=_key)

    if users_env == "*":
        input_usernames = ["All users in the repo"]
    else:
        input_usernames = [u.strip() for u in users_env.split(",") if u.strip()]

    fetched_at_iso = _iso(run_dt)

    description = (
        "All issue comments"
        + (" and PR review comments" if include_pr_reviews else "")
        + " pulled from GitHub with pagination, incremental watermarks, and ETag support."
    )

    json_output, md_output = make_timestamped_output_paths(OUTPUT_PATH, run_dt)

    metadata = {
        "owner": owner,
        "repo": repo,
        "fetched_at": fetched_at_iso,
        "description": description,
        "input_owner": owner_env,
        "input_repo": repo_env,
        "input_usernames": input_usernames,
        "input_PR_comments": include_pr_reviews,
        "output_path": json_output,
        "committed_to_repo": commit_to_repo,
        "input_notes": notes_env,
        "total_comments": len(out),
        "new_comments": total_new,
    }

    payload = {"metadata": metadata, "comments": out}

    try:
        save_json_atomic(payload, json_output)
        save_markdown(out, md_output, metadata)
        write_meta(effective_sig)

        logger.info(f"Comments added this update: {total_new}")
        logger.info(f"Total comments: {len(out)}")
        logger.info(f"Wrote JSON: {json_output}")
        logger.info(f"Wrote MD: {md_output}")

        if total_new == 0:
            logger.info("No new comments detected.")

    except OSError as e:
        logger.error(f"File write error: {e}")
        raise SystemExit(1)
    finally:
        logger.info(f"Run completed in {time.time() - start_ts:.1f}s")


if __name__ == "__main__":
    main()
