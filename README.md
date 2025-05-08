# AI-Powered Changelog Generator

This project automatically generates changelogs from recent Git commits and publishes them on a public webpage.

## Project Status

*("Under Development")*

## Setup

*(Instructions on how to set up the project will go here. This will be detailed later as per the project plan.)*

## Usage

*(.)*

## Architecture

*(A description of the project's architecture and design decisions will be added here.)*

## Contributing

*(Guidelines for contributing to the project, if applicable.)*

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Quick Start

1.  Clone the repository:
    ```bash
    git clone https://github.com/rverma6/ai-changelog.git 
    cd ai-changelog
    ```
2.  Set up a Python virtual environment (e.g., using `uv`):
    ```bash
    uv venv
    source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate  # On Windows
    ```
3.  Install the project and its dependencies:
    ```bash
    uv pip install -e ".[test]"
    ```
4.  Fetch recent commits (e.g., since May 1st, 2025, from the current repository):
    ```bash
    python -m cli fetch-commits --repo-path . --since-date "2025-05-01T00:00:00Z"
    ```
    This will print commit data as JSON to your terminal and stats to stderr. 
    To save to a file:
    ```bash
    python -m cli fetch-commits --repo-path . --since-date "2025-05-01T00:00:00Z" -o commits.json
    ```
