import pytest
import git
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Assuming cli.git_utils is accessible.
# If 'cli' is a top-level package, and 'tests' is also top-level,
# you might need to adjust PYTHONPATH or use package installation (e.g. editable install)
# for robust imports. For now, let's try a relative path assuming a certain structure
# or that pytest handles path adjustments.
# A common way is to have your project installed in editable mode, then direct imports work.
# For now, let's assume your project root is in PYTHONPATH when running pytest.
from cli.git_utils import get_commits # This might need adjustment based on your execution context

# Pytest fixture to create a temporary Git repository for testing
@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """
    Creates a temporary Git repository with some history and returns its path.
    tmp_path is a pytest fixture providing a temporary directory unique to the test.
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)
    
    # Configure author for commits (important for gitpython)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test Author").release()
        cw.set_value("user", "email", "test@example.com").release()

    # Create some commits
    # Commit 1 (oldest)
    file1 = repo_path / "file1.txt"
    file1.write_text("Initial content")
    repo.index.add([str(file1)])
    commit_time_c1 = datetime.now(timezone.utc) - timedelta(days=5)
    repo.index.commit("Initial commit (C1)", commit_date=commit_time_c1, author_date=commit_time_c1)
    
    # Commit 2
    file1.write_text("Updated content in file1")
    repo.index.add([str(file1)])
    commit_time_c2 = datetime.now(timezone.utc) - timedelta(days=4)
    repo.index.commit("Second commit (C2)\n\nSome body for C2.", commit_date=commit_time_c2, author_date=commit_time_c2)
    repo.create_tag("v0.1.0", ref='HEAD', message="Tag v0.1.0 points to C2")

    # Commit 3
    file2 = repo_path / "file2.txt"
    file2.write_text("New file")
    repo.index.add([str(file2)])
    commit_time_c3 = datetime.now(timezone.utc) - timedelta(days=3)
    repo.index.commit("Third commit (C3)", commit_date=commit_time_c3, author_date=commit_time_c3)

    # Commit 4 (newest)
    file1.write_text("Final content for file1")
    repo.index.add([str(file1)])
    commit_time_c4 = datetime.now(timezone.utc) - timedelta(days=2)
    repo.index.commit("Fourth commit (C4)", commit_date=commit_time_c4, author_date=commit_time_c4)
    repo.create_tag("v0.2.0", ref='HEAD', message="Tag v0.2.0 points to C4")

    return repo_path


# --- Test Cases ---

def test_get_commits_since_tag(temp_git_repo: Path):
    # Test fetching commits since tag v0.1.0 (C2). Expect C3, C4.
    commits = get_commits(repo_path=str(temp_git_repo), since_tag="v0.1.0")
    assert len(commits) == 2
    assert commits[0]["subject"] == "Fourth commit (C4)" # Newest first
    assert commits[1]["subject"] == "Third commit (C3)"
    assert commits[0]["body"] == ""
    assert "sha" in commits[0]
    assert "author" in commits[0]
    assert "date" in commits[0]


def test_get_commits_since_date(temp_git_repo: Path):
    # C3 was 3 days ago, C4 was 2 days ago.
    # Fetch commits since 3.5 days ago. Should get C3 and C4.
    since_date_dt = datetime.now(timezone.utc) - timedelta(days=3, hours=12)
    since_date_str = since_date_dt.isoformat()
    
    commits = get_commits(repo_path=str(temp_git_repo), since_date_str=since_date_str)
    assert len(commits) == 2
    assert commits[0]["subject"] == "Fourth commit (C4)"
    assert commits[1]["subject"] == "Third commit (C3)"


def test_get_commits_tag_not_found(temp_git_repo: Path):
    with pytest.raises(ValueError, match="Tag 'nonexistent-tag' not found"):
        get_commits(repo_path=str(temp_git_repo), since_tag="nonexistent-tag")


def test_get_commits_invalid_date_format(temp_git_repo: Path):
    with pytest.raises(ValueError, match="Invalid RFC 3339 date format"):
        get_commits(repo_path=str(temp_git_repo), since_date_str="2023/01/01")


def test_get_commits_no_since_condition(temp_git_repo: Path):
    with pytest.raises(ValueError, match="Either 'since_tag' or 'since_date_str' must be provided."):
        get_commits(repo_path=str(temp_git_repo))


def test_get_commits_mutually_exclusive_conditions(temp_git_repo: Path):
    with pytest.raises(ValueError, match="'since_tag' and 'since_date_str' are mutually exclusive."):
        get_commits(repo_path=str(temp_git_repo), since_tag="v0.1.0", since_date_str="2023-01-01T00:00:00Z")


def test_get_commits_invalid_repo_path():
    with pytest.raises(git.exc.NoSuchPathError): # Or InvalidGitRepositoryError depending on how deep it gets
        get_commits(repo_path="/path/to/nonexistent/repo", since_date_str="2023-01-01T00:00:00Z")
    
    # Test for a path that exists but is not a git repo
    empty_dir = Path("empty_non_git_dir_for_test")
    empty_dir.mkdir(exist_ok=True)
    with pytest.raises(git.exc.InvalidGitRepositoryError):
         get_commits(repo_path=str(empty_dir), since_date_str="2023-01-01T00:00:00Z")
    shutil.rmtree(empty_dir) # Clean up


def test_commit_structure_and_body(temp_git_repo: Path):
    # Test fetching commits since tag v0.1.0 (C2). Expect C3, C4.
    # C2 itself had a body. C3 and C4 do not.
    # Let's fetch since just before C2 to include C2.
    c2_date = datetime.now(timezone.utc) - timedelta(days=4, hours=1) # Just before C2
    since_date_str = c2_date.isoformat()

    commits = get_commits(repo_path=str(temp_git_repo), since_date_str=since_date_str)
    assert len(commits) == 3 # C4, C3, C2
    
    commit_c4 = next(c for c in commits if c["subject"] == "Fourth commit (C4)")
    commit_c3 = next(c for c in commits if c["subject"] == "Third commit (C3)")
    commit_c2 = next(c for c in commits if c["subject"] == "Second commit (C2)")

    assert commit_c4["body"] == ""
    assert commit_c3["body"] == ""
    assert commit_c2["body"] == "\nSome body for C2."
    
    for commit in commits:
        assert isinstance(commit["sha"], str)
        assert len(commit["sha"]) == 40 # Standard SHA-1 hex length
        assert isinstance(commit["author"], str)
        assert commit["author"] == "Test Author"
        assert isinstance(commit["date"], str)
        # Check if date is valid ISO 8601
        parsed_date = datetime.fromisoformat(commit["date"])
        assert parsed_date.tzinfo is not None 
        assert isinstance(commit["subject"], str)
        assert isinstance(commit["body"], str)
