import click
import json
import sys
import git # Required for git.exc exceptions
import asyncclick as click
import asyncio
import os

# Assuming git_utils.py is in the same 'cli' directory and 'cli' is treated as a package
from .git_utils import get_commits
from .llm_utils import summarize_commit_message, DEFAULT_PROMPT_FILE_PATH # Import the new utility and DEFAULT_PROMPT_FILE_PATH
from .commit_shaping_utils import shape_commits # Import the new shaper

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
    Also prints basic stats (commit count, unique authors) to stderr.
    """
    if not since_tag and not since_date:
        click.echo("Error: Either --since-tag or --since-date must be provided.", err=True)
        sys.exit(1)

    try:
        commits_data = get_commits(
            repo_path=repo_path,
            since_tag=since_tag,
            since_date_str=since_date
        )

        if not commits_data:
            click.echo("No commits found in the specified range.", err=True)
            # Output an empty list if that's the desired JSON output for no commits
            json_output = json.dumps([], indent=2)
        else:
            commit_count = len(commits_data)
            unique_authors = len(set(c['author'] for c in commits_data))
            click.echo(f"Fetched {commit_count} commit(s) by {unique_authors} unique author(s).", err=True)
            json_output = json.dumps(commits_data, indent=2)

        if output_file == '-':
            click.echo(json_output) # JSON to stdout
        else:
            try:
                # Ensure output directory exists if specified in path
                # For simplicity, this example assumes output_file is just a filename
                # or the directory already exists. For a robust CLI, you might want:
                # import os
                # os.makedirs(os.path.dirname(output_file), exist_ok=True)
                # (Only if os.path.dirname(output_file) is not empty)
                with open(output_file, 'w') as f:
                    f.write(json_output)
                click.echo(f"Commit data written to {output_file}", err=True) # Status to stderr
            except IOError as e:
                click.echo(f"Error writing to output file {output_file}: {e}", err=True)
                sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (git.exc.GitCommandError, git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError) as e:
        click.echo(f"Git error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e.__class__.__name__} - {e}", err=True)
        sys.exit(1)

@cli.command("generate-summary")
@click.option(
    '--repo-path', '-r',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    help="Path to the Git repository (e.g., '.'). If not provided, --input-commits-file is required."
)
@click.option(
    '--since-tag',
    default=None,
    type=str,
    help="Fetch commits since this tag (exclusive). Requires --repo-path."
)
@click.option(
    '--since-date',
    default=None,
    type=str,
    help="Fetch commits since this date (RFC 3339 format). Requires --repo-path."
)
@click.option(
    '--input-commits-file', '-i',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help="Path to a JSON file containing commit data (e.g., from fetch-commits)."
)
@click.option(
    '--output-file', '-o',
    type=click.Path(dir_okay=False, writable=True, allow_dash=True),
    default='-', # Default to stdout
    help="Output file for the summarized changelog. Use '-' for stdout (default)."
)
@click.option(
    '--dry-run',
    is_flag=True,
    help="Simulate the process and show what would be sent to the LLM, without making API calls."
)
@click.option(
    '--model',
    default=None, # Will use DEFAULT_MODEL from llm_utils if None
    type=str,
    help="OpenAI model to use for summarization (e.g., gpt-4o)."
)
@click.option(
    '--temperature',
    default=None, # Will use DEFAULT_TEMPERATURE from llm_utils if None
    type=click.FloatRange(0.0, 2.0),
    help="Sampling temperature for the LLM (0.0 to 2.0)."
)
@click.option(
    '--prompt-file',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    default=None, 
    help="Path to a custom prompt template file (overrides prompts/base.txt)."
)
async def generate_summary_command(
    repo_path: str | None,
    since_tag: str | None,
    since_date: str | None,
    input_commits_file: str | None,
    output_file: str,
    dry_run: bool,
    model: str | None,
    temperature: float | None,
    prompt_file: str | None
):
    """
    Fetches commits, summarizes them using an LLM, and outputs a changelog.
    """
    raw_commits_data = []
    source_description = ""

    if input_commits_file:
        if repo_path or since_tag or since_date:
            click.echo("Warning: If --input-commits-file is provided, "
                        "--repo-path, --since-tag, and --since-date are ignored.", err=True)
        try:
            with open(input_commits_file, 'r') as f:
                raw_commits_data = json.load(f)
            source_description = f"from {input_commits_file}"
        except json.JSONDecodeError:
            click.echo(f"Error: Could not decode JSON from {input_commits_file}", err=True)
            raise click.Abort()
        except IOError:
            click.echo(f"Error: Could not read from {input_commits_file}", err=True)
            raise click.Abort()
    elif repo_path:
        if not since_tag and not since_date:
            click.echo("Error: If using --repo-path, either --since-tag or --since-date must be provided.", err=True)
            raise click.Abort()
        try:
            raw_commits_data = get_commits(
                repo_path=repo_path,
                since_tag=since_tag,
                since_date_str=since_date
            )
            source_description = f"from repository {repo_path}"
        except Exception as e: # Catch errors from get_commits
            click.echo(f"Error fetching commits: {e}", err=True)
            raise click.Abort()
    else:
        click.echo("Error: Either --repo-path (with since conditions) or --input-commits-file must be provided.", err=True)
        raise click.Abort()

    if not raw_commits_data:
        click.echo(f"No raw commits found {source_description}.", err=True)
        commits_data = []
    else:
        click.echo(f"Fetched {len(raw_commits_data)} raw commit(s) {source_description}.", err=True)
        click.echo("Applying shaping and de-duplication rules...", err=True)
        commits_data = shape_commits(raw_commits_data)
        if not commits_data:
            click.echo("No non-trivial commits remaining after shaping.", err=True)
        else:
            click.echo(f"{len(commits_data)} commit(s) remain after shaping.", err=True)
    
    if not commits_data and not dry_run: # No need to proceed if no commits and not a dry run
        if output_file == '-':
            click.echo("[]") # Output empty list for stdout
        else:
            try:
                with open(output_file, 'w') as f:
                    f.write("[]\n") # Output empty list to file
                click.echo(f"No summaries to generate. Output file {output_file} created with empty list.", err=True)
            except IOError as e:
                click.echo(f"Error writing to output file {output_file}: {e}", err=True)
                raise click.Abort()
        return

    # --- Determine context for the prompt ---
    final_repo_name = "this project"
    if repo_path:
        final_repo_name = os.path.basename(os.path.abspath(repo_path))
    
    final_date_range = "recent changes"
    if since_tag and since_date: # Unlikely scenario based on your arg parsing, but for completeness
        final_date_range = f"since tag '{since_tag}' and date '{since_date}'"
    elif since_tag:
        final_date_range = f"since tag '{since_tag}'"
    elif since_date:
        final_date_range = f"since {since_date}"
    # If using input_commits_file, date_range might be harder to determine accurately
    # unless it's stored in the file or passed as another option.
    # For now, if input_commits_file is used, it will use the default "recent changes".

    summaries = []
    if dry_run:
        click.echo("--- DRY RUN MODE ---", err=True)
        click.echo(f"Would process {len(commits_data)} commits for repo '{final_repo_name}' covering '{final_date_range}'.", err=True)
        for i, commit in enumerate(commits_data):
            full_commit_message = f"{commit.get('subject', '')}\n{commit.get('body', '')}".strip()
            click.echo(f"\nCommit {i+1}/{len(commits_data)} (SHA: {commit.get('sha', 'N/A')[:7]}):", err=True)
            click.echo(f"  Message to summarize:\n---\n{full_commit_message}\n---", err=True)
            # Simulate placeholder replacement for dry run log
            prompt_template_debug = "System: You are an expert for '{{REPO_NAME}}' covering '{{DATE_RANGE}}'. User: Commit: {{COMMIT_MESSAGE_PLACEHOLDER}}"
            debug_prompt = prompt_template_debug.replace("{{REPO_NAME}}", final_repo_name).replace("{{DATE_RANGE}}", final_date_range).replace("{{COMMIT_MESSAGE_PLACEHOLDER}}", full_commit_message)
            click.echo(f"  Effective Prompt Context (simplified): {debug_prompt[:200]}...", err=True)

            summaries.append({
                "sha": commit.get('sha'),
                "original_subject": commit.get('subject'),
                "summary": "[Dry run - No API call made]"
            })
        effective_prompt_path_for_debug = prompt_file if prompt_file else str(DEFAULT_PROMPT_FILE_PATH) # Use constant from llm_utils for default
        click.echo(f"  Using prompt template: {effective_prompt_path_for_debug}", err=True)
    else:
        click.echo(f"Summarizing {len(commits_data)} commit(s) for repo '{final_repo_name}' covering '{final_date_range}' using LLM...", err=True)
        
        llm_args = {}
        if model:
            llm_args['model'] = model
        if temperature is not None:
            llm_args['temperature'] = temperature
        if prompt_file: # Pass the prompt_file if provided to llm_utils
            llm_args['prompt_file_override'] = prompt_file 
            # Also ensure DEFAULT_PROMPT_FILE_PATH is available for dry_run log if needed
            # You'll need to import it at the top: from .llm_utils import DEFAULT_PROMPT_FILE_PATH

        async def process_commits():
            tasks = []
            for commit in commits_data:
                full_commit_message = f"{commit.get('subject', '')}\n{commit.get('body', '')}".strip()
                if not full_commit_message:
                    summaries.append({
                        "sha": commit.get('sha'),
                        "original_subject": commit.get('subject'),
                        "summary": "[Skipped - Empty commit message]"
                    })
                    continue
                
                tasks.append(summarize_commit_message(
                    full_commit_message,
                    repo_name=final_repo_name,
                    date_range=final_date_range,
                    **llm_args # llm_args now passes prompt_file_override if set
                ))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                commit_sha = commits_data[i].get('sha')
                original_subject = commits_data[i].get('subject')
                if isinstance(result, Exception):
                    click.echo(f"Error summarizing commit {commit_sha[:7]}: {result}", err=True)
                    summaries.append({
                        "sha": commit_sha,
                        "original_subject": original_subject,
                        "summary": f"[Error: {result}]"
                    })
                else:
                    summaries.append({
                        "sha": commit_sha,
                        "original_subject": original_subject,
                        "summary": result if result else "[No summary generated]"
                    })

        await process_commits()

    # Output the summaries
    output_content = json.dumps(summaries, indent=2)
    if output_file == '-':
        click.echo(output_content)
    else:
        try:
            with open(output_file, 'w') as f:
                f.write(output_content)
            click.echo(f"Summaries written to {output_file}", err=True)
        except IOError as e:
            click.echo(f"Error writing summaries to {output_file}: {e}", err=True)
            raise click.Abort()

# This allows running the CLI using `python -m cli ...`
if __name__ == '__main__':
    cli()
