import asyncio
import os
from openai import AsyncOpenAI, OpenAIError # AsyncOpenAI for async operations
from pathlib import Path
import sys

# --- Configuration ---
# API Key will be read automatically from the OPENAI_API_KEY environment variable
# client = AsyncOpenAI() # Initialize client (can be done globally or per function)

DEFAULT_PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "base.txt"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_TEMPERATURE = 0.7 # 0.0 for more deterministic, 1.0 for more random/creative
MAX_TOKENS_SUMMARY = 100  # Max tokens for the *generated summary* (not total prompt + summary)

# Global client instance is often convenient
# Ensure API key is available or client instantiation will fail later.
# It's good practice to ensure OPENAI_API_KEY is set before this module is heavily used.
async_client = None

def get_openai_client():
    global async_client
    if async_client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise OpenAIError(
                "The OPENAI_API_KEY environment variable is not set. "
                "Please set it before running the application."
            )
        async_client = AsyncOpenAI()
    return async_client

async def load_prompt_template(prompt_file_override: str | Path | None = None) -> str:
    """Loads the prompt template from the file."""
    target_prompt_file = Path(prompt_file_override) if prompt_file_override else DEFAULT_PROMPT_FILE_PATH
    try:
        with open(target_prompt_file, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found at {target_prompt_file}")
    except Exception as e:
        raise Exception(f"Error loading prompt file {target_prompt_file}: {e}")

async def summarize_commit_message(
    commit_message: str,
    repo_name: str = "this project", # Default if not provided
    date_range: str = "recent changes", # Default if not provided
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_file_override: str | Path | None = None # New parameter
) -> str | None:
    """
    Summarizes a single commit message using the OpenAI API.

    Args:
        commit_message: The full commit message string.
        repo_name: The name of the repository for context.
        date_range: A string describing the date range for context.
        model: The OpenAI model to use.
        temperature: The sampling temperature.
        prompt_file_override: Optional path to a custom prompt file.

    Returns:
        The summarized bullet point as a string, or None if an error occurs.
    """
    try:
        client = get_openai_client()

        prompt_template = await load_prompt_template(prompt_file_override=prompt_file_override)
        
        placeholders = {
            "{{REPO_NAME}}": repo_name,
            "{{DATE_RANGE}}": date_range,
            "{{COMMIT_MESSAGE_PLACEHOLDER}}": commit_message,
        }

        # Ensure all expected placeholders are in the template
        for ph in placeholders.keys():
            if ph not in prompt_template:
                raise ValueError(f"Prompt template ({prompt_file_override or DEFAULT_PROMPT_FILE_PATH}) must contain '{ph}'.")

        formatted_prompt = prompt_template
        for ph, value in placeholders.items():
            formatted_prompt = formatted_prompt.replace(ph, str(value))
        
        parts = formatted_prompt.split("User:", 1)
        system_content = ""
        user_content = formatted_prompt 

        if len(parts) == 2:
            system_part = parts[0].replace("System:", "").strip()
            if system_part:
                 system_content = system_part
            user_content = parts[1].strip()
        elif formatted_prompt.lower().startswith("system:"):
            system_content = formatted_prompt.replace("System:", "").strip()
            user_content = "" 
        
        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if user_content:
            messages.append({"role": "user", "content": user_content})
        else:
             raise ValueError("User content for the prompt is empty after parsing. Cannot make API call.")

        # Check if messages list is empty (e.g. parsing failed or no content)
        if not messages or not any(msg.get('content') for msg in messages):
             raise ValueError("Prompt resulted in empty content to send to API.")

        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=MAX_TOKENS_SUMMARY,
        )

        summary = completion.choices[0].message.content
        return summary.strip() if summary else None

    except OpenAIError as e:
        print(f"OpenAI API error: {e}", file=sys.stderr) # Print errors to stderr
        return None
    except FileNotFoundError as e:
        print(f"Prompt file error: {e}", file=sys.stderr)
        return None
    except ValueError as e: 
        print(f"Prompt formatting or content error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during summarization: {e}", file=sys.stderr)
        return None

# Example usage (for testing this module directly, if needed)
# async def main():
#     # Ensure OPENAI_API_KEY is set in your environment
#     if not os.getenv("OPENAI_API_KEY"):
#         print("Please set the OPENAI_API_KEY environment variable.")
#         return
#
#     sample_commit = "feat(parser): Add new advanced parsing capabilities for complex data structures\n\nThis commit introduces a more sophisticated parsing engine that can handle nested objects and arrays, improving the tool's flexibility with diverse input formats. It also includes performance optimizations."
#     summary = await summarize_commit_message(sample_commit)
#     if summary:
#         print(f"Original: {sample_commit}")
#         print(f"Summary: {summary}")
#
# if __name__ == '__main__':
#    asyncio.run(main())
