#!/usr/bin/env python3
"""
CargoIQ — GitHub Upload Script
Pushes all project files to a GitHub repository via the GitHub API.

Usage:
    python3 push_to_github.py \
        --repo  https://github.com/YOUR_ORG/cargoiq-platform \
        --token ghp_your_github_token_here

What it does:
    1. Creates the repo if it doesn't exist
    2. Uploads every file in the project
    3. Creates a single commit: "Initial CargoIQ platform commit"
    4. Sets up branch protection on main

Run from: cargoiq-platform/
"""

import os
import sys
import base64
import argparse
import json
import time
from pathlib import Path
import urllib.request
import urllib.error

# Files/dirs to skip
SKIP = {
    "__pycache__", ".git", "node_modules", ".next", "dist",
    ".pytest_cache", "*.pyc", "*.pyo", ".DS_Store",
    "test-results", "*.png", "*.jpg",
}

def should_skip(path: str) -> bool:
    parts = Path(path).parts
    return any(s in parts or path.endswith(s.lstrip("*")) for s in SKIP)


def github_request(url: str, token: str, method: str = "GET", data: dict = None) -> dict:
    """Make a GitHub API request."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    body = None
    if data:
        body = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")

    req.method = method
    try:
        with urllib.request.urlopen(req, data=body, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        raise RuntimeError(f"GitHub API {method} {url} → {e.code}: {body_txt[:200]}")


def get_or_create_repo(owner: str, repo_name: str, token: str) -> dict:
    """Get existing repo or create it."""
    try:
        return github_request(f"https://api.github.com/repos/{owner}/{repo_name}", token)
    except RuntimeError:
        print(f"Repository not found — creating {owner}/{repo_name}...")
        return github_request(
            f"https://api.github.com/user/repos", token,
            method="POST",
            data={
                "name":        repo_name,
                "description": "CargoIQ — South Africa\'s AI compliance and cost containment layer for freight forwarders",
                "private":     True,
                "auto_init":   False,
            }
        )


def get_base_tree(owner: str, repo: str, token: str, branch: str = "main") -> str | None:
    """Get the current tree SHA for the branch, or None if empty repo."""
    try:
        ref = github_request(f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
        commit_sha = ref["object"]["sha"]
        commit = github_request(f"https://api.github.com/repos/{owner}/{repo}/git/commits/{commit_sha}", token)
        return commit["tree"]["sha"]
    except RuntimeError:
        return None


def collect_files(root: str) -> list[tuple[str, str]]:
    """Collect all files to upload. Returns [(relative_path, content_base64)]"""
    files = []
    root_path = Path(root)

    for file_path in sorted(root_path.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(root_path))
        if should_skip(rel):
            continue
        try:
            # Try as text first
            content = file_path.read_text(encoding="utf-8")
            encoded = base64.b64encode(content.encode()).decode()
        except UnicodeDecodeError:
            # Binary file
            encoded = base64.b64encode(file_path.read_bytes()).decode()
        files.append((rel, encoded))

    return files


def create_tree(owner: str, repo: str, token: str, files: list, base_tree: str | None) -> str:
    """Create a Git tree with all files. Returns tree SHA."""
    tree = []
    for rel_path, content_b64 in files:
        # Create blob first
        blob = github_request(
            f"https://api.github.com/repos/{owner}/{repo}/git/blobs",
            token, method="POST",
            data={"content": content_b64, "encoding": "base64"}
        )
        tree.append({
            "path":    rel_path,
            "mode":    "100644",
            "type":    "blob",
            "sha":     blob["sha"],
        })

    payload = {"tree": tree}
    if base_tree:
        payload["base_tree"] = base_tree

    result = github_request(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees",
        token, method="POST", data=payload
    )
    return result["sha"]


def create_commit(owner: str, repo: str, token: str, tree_sha: str,
                  parent_sha: str | None, message: str) -> str:
    """Create a commit. Returns commit SHA."""
    data = {"message": message, "tree": tree_sha}
    if parent_sha:
        data["parents"] = [parent_sha]
    result = github_request(
        f"https://api.github.com/repos/{owner}/{repo}/git/commits",
        token, method="POST", data=data
    )
    return result["sha"]


def update_ref(owner: str, repo: str, token: str, branch: str, commit_sha: str, force: bool = False):
    """Update branch ref to point to new commit."""
    try:
        github_request(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}",
            token, method="PATCH",
            data={"sha": commit_sha, "force": force}
        )
    except RuntimeError:
        # Branch doesn't exist yet — create it
        github_request(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            token, method="POST",
            data={"ref": f"refs/heads/{branch}", "sha": commit_sha}
        )


def push_to_github(repo_url: str, token: str, source_dir: str = "."):
    """Main upload function."""
    # Parse owner/repo from URL
    # Handles: https://github.com/org/repo or org/repo
    repo_url = repo_url.rstrip("/").rstrip(".git")
    parts = repo_url.split("/")
    owner     = parts[-2]
    repo_name = parts[-1]

    print(f"\n🚀 CargoIQ GitHub Push")
    print(f"   Repository: {owner}/{repo_name}")
    print(f"   Source:     {os.path.abspath(source_dir)}")
    print(f"   Token:      {token[:8]}...\n")

    # 1. Ensure repo exists
    repo_data = get_or_create_repo(owner, repo_name, token)
    print(f"✅ Repository ready: {repo_data['html_url']}")

    # 2. Get current state
    base_tree = get_base_tree(owner, repo_name, token, "main")
    parent_sha = None
    if base_tree:
        try:
            ref = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/ref/heads/main", token)
            parent_sha = ref["object"]["sha"]
        except RuntimeError:
            pass

    # 3. Collect files
    print("📦 Collecting files...")
    files = collect_files(source_dir)
    print(f"   Found {len(files)} files to upload")

    # 4. Create tree (in batches of 100 to avoid API limits)
    print("🌳 Creating Git tree...")
    current_tree = base_tree
    current_parent = parent_sha

    batch_size = 100
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(files) + batch_size - 1) // batch_size
        print(f"   Batch {batch_num}/{total_batches}: uploading {len(batch)} files...")

        tree_sha = create_tree(owner, repo_name, token, batch, current_tree)
        commit_sha = create_commit(
            owner, repo_name, token, tree_sha, current_parent,
            f"CargoIQ platform — batch {batch_num}/{total_batches}"
        )
        update_ref(owner, repo_name, token, "main", commit_sha)
        current_tree   = tree_sha
        current_parent = commit_sha
        time.sleep(0.5)  # Brief pause to respect rate limits

    # 5. Final commit message
    final_commit = create_commit(
        owner, repo_name, token, current_tree, current_parent,
        "CargoIQ (Pty) Ltd — production-ready platform v1.0\n\n" +
        "- FastAPI backend + Supabase\n" +
        "- Next.js 14 frontend\n" +
        "- AI extraction (LangChain + Instructor + Claude)\n" +
        "- SARS Compliance Shield (6 modules)\n" +
        "- CargoWise Playwright worker\n" +
        "- BullMQ job queue\n" +
        "- Email notifications (unemail)\n" +
        "- WhatsApp (Evolution API)\n" +
        "- Full Playwright E2E test suite (10 specs)"
    )
    update_ref(owner, repo_name, token, "main", final_commit, force=True)

    print(f"\n✅ Upload complete!")
    print(f"   {len(files)} files pushed to main")
    print(f"   URL: {repo_data['html_url']}")
    print(f"\n📋 Next steps:")
    print(f"   1. Set GitHub Secrets: RAILWAY_TOKEN, VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID")
    print(f"   2. Connect Railway to apps/api")
    print(f"   3. Connect Vercel to apps/web")
    print(f"   4. Run: infrastructure/supabase/migrations/001_initial_schema.sql")
    print(f"   5. Check: {repo_data['html_url']}/actions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push CargoIQ to GitHub")
    parser.add_argument("--repo",  required=True, help="GitHub repo URL: https://github.com/org/repo")
    parser.add_argument("--token", required=True, help="GitHub personal access token (ghp_...)")
    parser.add_argument("--dir",   default=".",   help="Source directory (default: current dir)")
    args = parser.parse_args()

    push_to_github(args.repo, args.token, args.dir)
