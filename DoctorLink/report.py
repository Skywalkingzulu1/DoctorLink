#!/usr/bin/env python3
"""
Generate a concise technical stack summary and a progress report for the
DoctorLink project by extracting recent commit activity, open issues,
and pull‑request metrics via the GitHub REST API.
"""

import os
import sys
import datetime
from collections import Counter
from typing import List, Dict, Any

import requests

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
GITHUB_API = "https://api.github.com"
# Expected environment variables:
#   GITHUB_TOKEN - Personal access token with repo scope
#   REPO_OWNER  - GitHub username or organization
#   REPO_NAME   - Repository name (e.g., "DoctorLink")
TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")

if not all([TOKEN, OWNER, REPO]):
    sys.stderr.write(
        "Error: GITHUB_TOKEN, REPO_OWNER, and REPO_NAME environment variables must be set.\n"
    )
    sys.exit(1)

HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def github_get(url: str, params: Dict[str, Any] = None) -> Any:
    """Perform a GET request to the GitHub API and return parsed JSON."""
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        sys.stderr.write(f"GitHub API error {response.status_code}: {response.text}\n")
        sys.exit(1)
    return response.json()


def paginate(url: str, params: Dict[str, Any] = None) -> List[Any]:
    """Collect all items from a paginated GitHub endpoint."""
    items = []
    page = 1
    while True:
        p = params.copy() if params else {}
        p.update({"per_page": 100, "page": page})
        batch = github_get(url, p)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


# ----------------------------------------------------------------------
# Data extraction
# ----------------------------------------------------------------------
def recent_commits(days: int = 7) -> List[Dict[str, Any]]:
    """Return commits made in the last `days` days."""
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat() + "Z"
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/commits"
    commits = paginate(url, {"since": since})
    return commits


def open_issues() -> List[Dict[str, Any]]:
    """Return all open issues (excluding pull requests)."""
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/issues"
    issues = paginate(url, {"state": "open", "filter": "all"})
    # GitHub treats PRs as issues with a "pull_request" key; filter them out
    return [i for i in issues if "pull_request" not in i]


def pull_requests() -> List[Dict[str, Any]]:
    """Return all pull requests (open and closed)."""
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls"
    prs = paginate(url, {"state": "all"})
    return prs


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------
def tech_stack_summary() -> str:
    """
    Infer a minimal technical stack from repository metadata.
    This implementation looks at the repository's topics and primary language.
    """
    repo_url = f"{GITHUB_API}/repos/{OWNER}/{REPO}"
    repo_data = github_get(repo_url)
    language = repo_data.get("language", "Unknown")
    topics = repo_data.get("topics", [])
    # Simple heuristic: map common topics to stack components
    stack_components = {
        "python": "Python",
        "django": "Django",
        "fastapi": "FastAPI",
        "react": "React",
        "vue": "Vue.js",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "Google Cloud",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB",
    }
    inferred = [stack_components[t] for t in topics if t in stack_components]
    if language and language not in inferred:
        inferred.insert(0, language)
    return ", ".join(inferred) if inferred else "Not enough data"


def progress_report() -> str:
    """Compile a concise progress report."""
    commits = recent_commits()
    issues = open_issues()
    prs = pull_requests()

    # Commit stats
    commit_count = len(commits)
    authors = Counter(c["commit"]["author"]["name"] for c in commits if c.get("commit"))
    top_author, top_count = authors.most_common(1)[0] if authors else ("N/A", 0)

    # Issue stats
    open_issue_count = len(issues)

    # PR stats
    open_prs = [pr for pr in prs if pr["state"] == "open"]
    merged_prs = [pr for pr in prs if pr.get("merged_at")]
    closed_prs = [pr for pr in prs if pr["state"] == "closed" and not pr.get("merged_at")]

    report = {
        "Technical Stack": tech_stack_summary(),
        "Commits (last 7d)": commit_count,
        "Top Commit Author": f"{top_author} ({top_count} commits)",
        "Open Issues": open_issue_count,
        "Open PRs": len(open_prs),
        "Merged PRs": len(merged_prs),
        "Closed PRs (unmerged)": len(closed_prs),
    }

    # Render as a human‑readable block
    lines = ["=== DoctorLink Progress Report ==="]
    for key, value in report.items():
        lines.append(f"{key}: {value}")
    lines.append("=== End of Report ===")
    return "\n".join(lines)


def main() -> None:
    print(progress_report())


if __name__ == "__main__":
    main()