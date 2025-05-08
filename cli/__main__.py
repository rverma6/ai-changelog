import click
import json
import sys
import git # Required for git.exc exceptions

# Assuming git_utils.py is in the same 'cli' directory and 'cli' is treated as a package
from .git_utils import get_commits

@click.group()
def cli():
    """
    AI-Powered Changelog Generator CLI.
    Helps generate changelogs from Git commits.
    """
    pass

@cli.command("fetch-commits")
@click.option(
    '--repo-path', '-r',
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    help="Path to the Git repository (e.g., '.')."
)
@click.option(
    '--since-tag',
    default=None,
    type=str,
    help="Fetch commits since this tag (exclusive)."
)
@click.option(
    '--since-date',
    default=None,
    type=str,
    help="Fetch commits since this date (RFC 3339 format, e.g., '2023-01-01T00:00:00Z')."
)
@click.option(
    '--output-file', '-o',
    type=click.Path(dir_okay=False, writable=True, allow_dash=True),
    default='-', # Default to stdout
    help="Output file for the JSON data. Use '-' for stdout (default)."
)
def fetch_commits_command(repo_path: str, since_tag: str | None, since_date: str | None, output_file: str):
    """
    Fetches commits from a Git repository and outputs them as JSON.
    """
    # The get_commits function already handles these validation,
    # but Click can also enforce some of this with parameter groups or custom validation if needed.
    # For now, we rely on get_commits' internal validation.
    # However, one explicit check here for user experience is good:
    if not since_tag and not since_date:
        click.echo("Error: Either --since-tag or --since-date must be provided.", err=True)
        # You might want to use click.Context.exit(1) for better testing integration
        sys.exit(1) 
    # get_commits also checks for mutual exclusivity

    try:
        commits_data = get_commits(
            repo_path=repo_path,
            since_tag=since_tag,
            since_date_str=since_date # Pass the string directly
        )

        json_output = json.dumps(commits_data, indent=2)

        if output_file == '-':
            click.echo(json_output)
        else:
            try:
                with open(output_file, 'w') as f:
                    f.write(json_output)
                click.echo(f"Commit data successfully written to {output_file}")
            except IOError as e:
                click.echo(f"Error writing to output file {output_file}: {e}", err=True)
                sys.exit(1)

    except ValueError as e: # Catches errors from get_commits or json.dumps
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (git.exc.GitCommandError, git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError) as e:
        click.echo(f"Git error: {e}", err=True)
        sys.exit(1)
    except Exception as e: # Catch any other unexpected errors
        click.echo(f"An unexpected error occurred: {e.__class__.__name__} - {e}", err=True)
        sys.exit(1)

# This allows running the CLI using `python -m cli ...`
if __name__ == '__main__':
    cli()
