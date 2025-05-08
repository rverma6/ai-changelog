import git
from datetime import datetime, timezone

def get_commits(
    repo_path: str,
    since_tag: str | None = None,
    since_date_str: str | None = None
) -> list[dict]:
    """
    Fetches commit data from a Git repository.

    Args:
        repo_path: Path to the Git repository.
        since_tag: Fetch commits since this tag (exclusive of the tag's commit).
        since_date_str: Fetch commits since this date (RFC 3339 string, e.g., "2023-01-01T00:00:00Z").

    Returns:
        A list of dictionaries, where each dictionary contains:
        {
            "sha": str,
            "author": str,
            "date": str (ISO 8601 format),
            "subject": str,
            "body": str,
            "parent_shas": list[str]
        }

    Raises:
        ValueError: If tag is not found, date format is invalid, or
                    neither since_tag nor since_date_str is provided.
        git.exc.GitCommandError, git.exc.InvalidGitRepositoryError,
        git.exc.NoSuchPathError: For Git-related errors.
    """
    if not since_tag and not since_date_str:
        raise ValueError("Either 'since_tag' or 'since_date_str' must be provided.")
    if since_tag and since_date_str:
        raise ValueError("'since_tag' and 'since_date_str' are mutually exclusive.")

    try:
        repo = git.Repo(repo_path)
    except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError) as e:
        raise e # Re-raise the specific gitpython exception

    commits_iter_args = {}

    if since_tag:
        try:
            # Ensure the tag exists and get its commit
            tag_object = next(t for t in repo.tags if t.name == since_tag)
            # We want commits *after* this tag. The range <tag>..HEAD works.
            commits_iter_args['rev'] = f'{tag_object.commit.hexsha}..HEAD'
        except StopIteration:
            raise ValueError(f"Tag '{since_tag}' not found in repository.")
    elif since_date_str:
        try:
            # Validate RFC 3339 date format.
            # `fromisoformat` handles 'Z' for UTC correctly in Python 3.11+
            # For broader compatibility or if 'Z' needs manual handling:
            if since_date_str.endswith('Z'):
                datetime.fromisoformat(since_date_str[:-1] + '+00:00')
            else:
                datetime.fromisoformat(since_date_str)
            # Pass the original string to gitpython, as it handles date parsing well.
            commits_iter_args['since'] = since_date_str
        except ValueError:
            raise ValueError(f"Invalid RFC 3339 date format: '{since_date_str}'")
    
    # iter_commits returns newest first by default.
    # If neither since_tag nor since_date was specified (which our initial check prevents),
    # we might fetch all commits up to HEAD by default (e.g. commits_iter_args['rev'] = 'HEAD').
    # However, the logic above ensures one of the conditions is met.

    collected_commits = []
    for commit in repo.iter_commits(**commits_iter_args):
        message_lines = commit.message.splitlines(keepends=False)
        subject = message_lines[0] if message_lines else ""
        body = "\n".join(message_lines[1:]) if len(message_lines) > 1 else ""
        
        # Get parent SHAs
        parent_shas = [p.hexsha for p in commit.parents]

        collected_commits.append({
            "sha": commit.hexsha,
            "author": commit.author.name,
            "date": commit.committed_datetime.isoformat(), # ISO 8601 format
            "subject": subject,
            "body": body,
            "parent_shas": parent_shas
        })
        
    return collected_commits
