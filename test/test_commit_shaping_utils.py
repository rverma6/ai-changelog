import pytest
from cli.commit_shaping_utils import (
    is_merge_commit,
    is_revert_commit,
    is_trivial_commit,
    shape_commits,
    TRIVIAL_COMMIT_PREFIXES # For potentially modifying in tests if needed
)

# --- Helper to create mock commit dicts ---
def create_commit(sha="abc", subject="test subject", author="Test Author", parents=None, body=""):
    if parents is None:
        parents = ["parent_sha"] if sha != "initial" else [] # Initial commit has 0 parents
    return {
        "sha": sha,
        "author": author,
        "date": "2023-01-01T12:00:00Z", # Dummy date
        "subject": subject,
        "body": body,
        "parent_shas": parents
    }

# --- Tests for individual checker functions ---

def test_is_merge_commit():
    assert is_merge_commit(create_commit(parents=[])) == False # Initial
    assert is_merge_commit(create_commit(parents=["p1"])) == False # Normal
    assert is_merge_commit(create_commit(parents=["p1", "p2"])) == True # Merge

def test_is_revert_commit():
    assert is_revert_commit(create_commit(subject="Revert \"feat: some feature\"")) == True
    assert is_revert_commit(create_commit(subject="revert this change now")) == True
    assert is_revert_commit(create_commit(subject="feat: new feature (not a revert)")) == False
    assert is_revert_commit(create_commit(subject="fixed a bug")) == False

def test_is_trivial_commit():
    assert is_trivial_commit(create_commit(subject="chore: updated dependencies")) == True
    assert is_trivial_commit(create_commit(subject="Ci: Fixed the pipeline")) == True # Test case insensitivity
    assert is_trivial_commit(create_commit(subject="test: added new tests")) == True
    assert is_trivial_commit(create_commit(subject="feat: amazing new feature")) == False
    assert is_trivial_commit(create_commit(subject="fix: critical bugfix")) == False
    # Assuming "docs:" is not in TRIVIAL_COMMIT_PREFIXES by default in the module
    assert is_trivial_commit(create_commit(subject="docs: explained how to use")) == False

# --- Tests for shape_commits ---

def test_shape_commits_empty_input():
    assert shape_commits([]) == []

def test_shape_commits_filters_merge_commits():
    commits = [
        create_commit(sha="c1", subject="Feature A"),
        create_commit(sha="m1", subject="Merge branch 'dev'", parents=["p1", "p2"]),
        create_commit(sha="c2", subject="Feature B")
    ]
    shaped = shape_commits(commits)
    assert len(shaped) == 2
    assert shaped[0]["sha"] == "c1"
    assert shaped[1]["sha"] == "c2"

def test_shape_commits_filters_revert_commits():
    commits = [
        create_commit(sha="c1", subject="Good commit"),
        create_commit(sha="r1", subject="Revert \"Bad commit\""),
        create_commit(sha="c2", subject="Another good commit")
    ]
    shaped = shape_commits(commits)
    assert len(shaped) == 2
    assert shaped[0]["sha"] == "c1"
    assert shaped[1]["sha"] == "c2"

def test_shape_commits_all_filtered():
    commits = [
        create_commit(sha="m1", subject="Merge remote-tracking branch 'origin/main'", parents=["p1","p2"]),
        create_commit(sha="r1", subject="Revert \"something\"")
    ]
    assert shape_commits(commits) == []

def test_shape_commits_consecutive_trivial_same_author():
    # Newest first in input list
    commits = [
        create_commit(sha="c1_trivial_A", subject="chore: task 1", author="Author A"),
        create_commit(sha="c2_trivial_A", subject="style: format code", author="Author A"),
        create_commit(sha="c3_nontrivial_A", subject="feat: new thing", author="Author A"),
        create_commit(sha="c4_trivial_A", subject="ci: pipeline fix", author="Author A"),
        create_commit(sha="c5_trivial_A", subject="test: add a test", author="Author A"),
        create_commit(sha="c6_trivial_B", subject="chore: task B", author="Author B"),
    ]
    # Expected: c1, c3, c4, c6 (c2 is skipped due to c1; c5 is skipped due to c4)
    shaped = shape_commits(commits)
    expected_shas = ["c1_trivial_A", "c3_nontrivial_A", "c4_trivial_A", "c6_trivial_B"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 4

def test_shape_commits_trivial_interspersed_with_nontrivial():
    commits = [
        create_commit(sha="c1_trivial_A", subject="chore: task 1", author="Author A"),
        create_commit(sha="c2_nontrivial_A", subject="feat: new thing", author="Author A"),
        create_commit(sha="c3_trivial_A", subject="style: format code", author="Author A"), # Kept, as c2 was non-trivial
        create_commit(sha="c4_trivial_A", subject="test: more tests", author="Author A"), # Skipped due to c3
    ]
    # Expected: c1, c2, c3
    shaped = shape_commits(commits)
    expected_shas = ["c1_trivial_A", "c2_nontrivial_A", "c3_trivial_A"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 3

def test_shape_commits_no_shaping_needed():
    commits = [
        create_commit(sha="c1", subject="feat: Feature A", author="Author A"),
        create_commit(sha="c2", subject="fix: Bugfix B", author="Author B"),
        create_commit(sha="c3", subject="feat: Feature C", author="Author A"),
    ]
    shaped = shape_commits(commits)
    assert len(shaped) == 3
    assert [c["sha"] for c in shaped] == ["c1", "c2", "c3"]

def test_shape_commits_only_one_commit():
    commits = [create_commit(sha="c1", subject="feat: Only one")]
    assert shape_commits(commits) == commits

    trivial_commit = [create_commit(sha="c1_trivial", subject="chore: only one trivial")]
    assert shape_commits(trivial_commit) == trivial_commit

def test_shape_commits_trivial_nontrivial_trivial_same_author():
    commits = [
        create_commit(sha="c1_trivial_A", subject="chore: setup", author="Author A"),
        create_commit(sha="c2_nontrivial_A", subject="feat: core logic", author="Author A"),
        create_commit(sha="c3_trivial_A", subject="style: linting", author="Author A"),
    ]
    # Expected: All should be kept. c1 is kept. c2 is non-trivial, kept. 
    # c3 is trivial, but last kept (c2) was non-trivial, so c3 is kept.
    shaped = shape_commits(commits)
    expected_shas = ["c1_trivial_A", "c2_nontrivial_A", "c3_trivial_A"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 3

def test_shape_commits_long_trivial_sequence_then_author_switch():
    commits = [
        create_commit(sha="c1_T_A", subject="chore: A1", author="Author A"),
        create_commit(sha="c2_T_A", subject="ci: A2", author="Author A"),
        create_commit(sha="c3_T_A", subject="test: A3", author="Author A"),
        create_commit(sha="c4_T_B", subject="chore: B1", author="Author B"), # Different author
        create_commit(sha="c5_T_B", subject="style: B2", author="Author B"),
    ]
    # Expected: c1_T_A (newest of A's sequence), c4_T_B (newest of B's sequence)
    shaped = shape_commits(commits)
    expected_shas = ["c1_T_A", "c4_T_B"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 2

def test_shape_commits_trivial_commits_around_filtered_commit():
    # Test if shaping correctly processes sequences after merge/revert filtering
    commits = [
        create_commit(sha="c1_T_A", subject="chore: A1", author="Author A"),
        create_commit(sha="m1_Merge", subject="Merge branch 'dev'", author="Author M", parents=["p1", "p2"]),
        create_commit(sha="c2_T_A", subject="style: A2", author="Author A"), # This is "older" than c1_T_A
        create_commit(sha="c3_NT_A", subject="feat: A3", author="Author A"),
        create_commit(sha="r1_Revert", subject="Revert \"bad thing\"", author="Author R"),
        create_commit(sha="c4_T_A", subject="test: A4", author="Author A"),
    ]
    # After pass 1 (filtering m1, r1): [c1_T_A, c2_T_A, c3_NT_A, c4_T_A]
    # Pass 2 shaping:
    # 1. Keep c1_T_A. last_author=A, last_trivial=True
    # 2. c2_T_A: current_author=A, current_trivial=True. Matches last. Skip c2_T_A.
    # 3. Keep c3_NT_A. last_author=A, last_trivial=False
    # 4. Keep c4_T_A. last_author=A, last_trivial=True (different from c3's last_trivial)
    # Expected: [c1_T_A, c3_NT_A, c4_T_A]
    shaped = shape_commits(commits)
    expected_shas = ["c1_T_A", "c3_NT_A", "c4_T_A"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 3

def test_shape_commits_complex_sequence_multiple_authors_and_types():
    commits = [
        create_commit(sha="T1_A", subject="chore: A setup", author="Author A"),      # Kept
        create_commit(sha="T2_A", subject="ci: A pipeline", author="Author A"),      # Skipped (due to T1_A)
        create_commit(sha="NT1_B", subject="feat: B feature", author="Author B"),    # Kept
        create_commit(sha="M1", subject="Merge stuff", author="Author M", parents=["p","q"]), # Filtered
        create_commit(sha="T3_A", subject="style: A lint", author="Author A"),       # Kept (last kept NT1_B)
        create_commit(sha="R1", subject="Revert change", author="Author R"),         # Filtered
        create_commit(sha="NT2_A", subject="fix: A critical bug", author="Author A"),# Kept (last kept T3_A)
        create_commit(sha="T4_B", subject="test: B tests", author="Author B"),       # Kept (last kept NT2_A)
        create_commit(sha="T5_B", subject="perf: B optimize", author="Author B"),    # Skipped (due to T4_B)
        create_commit(sha="T6_A", subject="chore: A cleanup", author="Author A"),    # Kept (last kept T4_B)
    ]
    # Expected after filtering M1, R1:
    # [T1_A, T2_A, NT1_B, T3_A, NT2_A, T4_B, T5_B, T6_A]
    # Expected after shaping pass 2:
    # T1_A (kept)
    # T2_A (skipped by T1_A)
    # NT1_B (kept)
    # T3_A (kept, prev NT1_B)
    # NT2_A (kept, prev T3_A)
    # T4_B (kept, prev NT2_A)
    # T5_B (skipped by T4_B)
    # T6_A (kept, prev T4_B)
    shaped = shape_commits(commits)
    expected_shas = ["T1_A", "NT1_B", "T3_A", "NT2_A", "T4_B", "T6_A"]
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 6

def test_shape_commits_all_trivial_same_author():
    commits = [
        create_commit(sha="T1_A", subject="chore: A1", author="Author A"),
        create_commit(sha="T2_A", subject="ci: A2", author="Author A"),
        create_commit(sha="T3_A", subject="test: A3", author="Author A"),
    ]
    shaped = shape_commits(commits)
    expected_shas = ["T1_A"] # Only the newest
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 1

def test_shape_commits_all_trivial_different_authors():
    commits = [
        create_commit(sha="T1_A", subject="chore: A1", author="Author A"),
        create_commit(sha="T2_B", subject="ci: B1", author="Author B"),
        create_commit(sha="T3_C", subject="test: C1", author="Author C"),
    ]
    shaped = shape_commits(commits)
    expected_shas = ["T1_A", "T2_B", "T3_C"] # All kept
    assert [c["sha"] for c in shaped] == expected_shas
    assert len(shaped) == 3

# More complex scenarios can be added here
