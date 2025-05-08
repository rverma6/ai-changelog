from typing import List, Dict, Any

# Define "trivial" commit prefixes
# These are commit types often less relevant for a user-facing changelog.
# 'docs:' might be an exception if doc changes are important for users.
TRIVIAL_COMMIT_PREFIXES = (
    "chore:", "style:", "refactor:", "test:", "ci:", "build:", "perf:"
    # "docs:", # You might want to include or exclude docs based on preference
)

def is_merge_commit(commit: Dict[str, Any]) -> bool:
    """Identifies a merge commit based on parent count."""
    # A merge commit typically has more than one parent.
    # Standard fast-forward merges might only have one, but those usually
    # don't have a "Merge branch..." message.
    # Actual merge commits (creating a merge node) will have len(parent_shas) > 1.
    return len(commit.get("parent_shas", [])) > 1

def is_revert_commit(commit: Dict[str, Any]) -> bool:
    """Identifies a revert commit by its subject line."""
    subject = commit.get("subject", "").lower()
    return subject.startswith("revert ") # Common prefix for revert commits

def is_trivial_commit(commit: Dict[str, Any]) -> bool:
    """Identifies a trivial commit by its subject prefix."""
    subject = commit.get("subject", "").lower()
    return subject.startswith(TRIVIAL_COMMIT_PREFIXES)

def shape_commits(commits_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Shapes and filters a list of commit data.
    - Filters out merge commits.
    - Filters out revert commits.
    - Combines consecutive trivial commits by the same author (keeps the newest of sequence).
    """
    if not commits_data:
        return []

    # 1. Filter out merge and revert commits first
    # We iterate in reverse (chronological order, oldest to newest) to make
    # consecutive commit logic easier, then reverse back at the end.
    # However, get_commits already returns newest first. Let's stick to that order.
    
    # Pass 1: Filter out merge and revert commits
    filtered_commits_pass1 = []
    for commit in commits_data: # commits_data is newest first
        if is_merge_commit(commit):
            # Optionally, log that a merge commit was skipped
            # print(f"Skipping merge commit: {commit['sha'][:7]} - {commit['subject']}")
            continue
        if is_revert_commit(commit):
            # Optionally, log that a revert commit was skipped
            # print(f"Skipping revert commit: {commit['sha'][:7]} - {commit['subject']}")
            # More advanced: try to find and also remove the commit it reverted, if desired.
            # For now, just skip the revert itself.
            continue
        filtered_commits_pass1.append(commit)

    if not filtered_commits_pass1:
        return []

    # Pass 2: Combine/filter consecutive trivial commits by the same author
    shaped_commits = []
    last_kept_commit_author = None
    last_kept_commit_was_trivial = False # Tracks if the last *kept* commit was trivial

    for commit in filtered_commits_pass1: # Iterating newest to oldest
        current_commit_is_trivial = is_trivial_commit(commit)
        current_commit_author = commit.get("author")

        # Skip if current is trivial, by the same author as the last kept commit,
        # AND the last kept commit was also trivial.
        if current_commit_is_trivial and \
           current_commit_author == last_kept_commit_author and \
           last_kept_commit_was_trivial:
            continue
        
        shaped_commits.append(commit)
        last_kept_commit_author = current_commit_author
        last_kept_commit_was_trivial = current_commit_is_trivial
        
    return shaped_commits
