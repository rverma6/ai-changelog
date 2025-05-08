import pytest
import sys
from unittest import mock # Use unittest.mock for patching
from pathlib import Path

# Assuming OpenAIError is the base class or a specific one you want to catch
from openai import OpenAIError

# Module under test
from cli import llm_utils

# --- Test Data ---
MOCK_PROMPT_TEMPLATE = """System:
Context: Repo '{{REPO_NAME}}', Range '{{DATE_RANGE}}'.
User:
Summarize: {{COMMIT_MESSAGE_PLACEHOLDER}}
Bullet:"""

MOCK_COMMIT_MESSAGE = "feat(parser): implement new parsing logic\n\nHandles more cases."
MOCK_REPO_NAME = "TestRepo"
MOCK_DATE_RANGE = "2024-01-01 to 2024-01-31"
EXPECTED_SUMMARY = "Implemented new parsing logic handling more cases."

# --- Mock Structures ---
# Build mock response simulating openai client structure
# Needs nesting: completion -> choices -> [choice] -> message -> content
mock_api_message = mock.Mock()
mock_api_message.content = f" {EXPECTED_SUMMARY} " # Include spaces to test strip()

mock_api_choice = mock.Mock()
mock_api_choice.message = mock_api_message

mock_api_completion = mock.Mock()
mock_api_completion.choices = [mock_api_choice]

# --- Tests ---

@pytest.mark.asyncio # Mark test as async
async def test_summarize_commit_message_success():
    """Tests the happy path with successful API call."""
    # Fix 1: Assign AsyncMock to the create method
    mock_create_method = mock.AsyncMock(return_value=mock_api_completion)
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method # Assign the AsyncMock here

    # Patch the functions within the llm_utils module
    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=MOCK_PROMPT_TEMPLATE) as mock_load, \
         mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client) as mock_get_client:

        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME,
            date_range=MOCK_DATE_RANGE
        )

        # Assertions
        assert summary == EXPECTED_SUMMARY # Check if whitespace was stripped
        mock_load.assert_awaited_once_with(prompt_file_override=None)
        mock_get_client.assert_called_once()

        # Fix 3: Use correct assertion helper
        mock_create_method.assert_awaited_once()
        _, call_kwargs = mock_create_method.call_args
        
        # Check model, temp, max_tokens passed correctly (using defaults)
        assert call_kwargs.get('model') == llm_utils.DEFAULT_MODEL
        assert call_kwargs.get('temperature') == llm_utils.DEFAULT_TEMPERATURE
        assert call_kwargs.get('max_tokens') == llm_utils.MAX_TOKENS_SUMMARY
        
        # Check messages structure
        expected_messages = [
             {'role': 'system', 'content': f"Context: Repo '{MOCK_REPO_NAME}', Range '{MOCK_DATE_RANGE}'."},
             {'role': 'user', 'content': f"Summarize: {MOCK_COMMIT_MESSAGE}\nBullet:"}
        ]
        assert call_kwargs.get('messages') == expected_messages

@pytest.mark.asyncio
async def test_summarize_commit_message_custom_params_and_prompt():
    """Tests passing custom model, temp, and prompt file."""
    custom_model = "gpt-4-turbo"
    custom_temp = 0.2
    custom_prompt_path = Path("prompts/custom_prompt.txt")
    custom_prompt_content = "Custom Prompt for {{REPO_NAME}} ({{DATE_RANGE}}): {{COMMIT_MESSAGE_PLACEHOLDER}}"
    
    # Fix 1: Assign AsyncMock to the create method
    mock_create_method = mock.AsyncMock(return_value=mock_api_completion)
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method

    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=custom_prompt_content) as mock_load, \
         mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client) as mock_get_client:

        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME, # Still provide context args
            date_range=MOCK_DATE_RANGE,
            model=custom_model,
            temperature=custom_temp,
            prompt_file_override=custom_prompt_path
        )

        assert summary == EXPECTED_SUMMARY
        mock_load.assert_awaited_once_with(prompt_file_override=custom_prompt_path) # Check override used
        mock_get_client.assert_called_once()

        # Fix 3: Use correct assertion helper
        mock_create_method.assert_awaited_once()
        _, call_kwargs = mock_create_method.call_args
        assert call_kwargs.get('model') == custom_model
        assert call_kwargs.get('temperature') == custom_temp
        
        # Check messages derived from the custom prompt (no system part expected here)
        expected_user_message = f"Custom Prompt for {MOCK_REPO_NAME} ({MOCK_DATE_RANGE}): {MOCK_COMMIT_MESSAGE}"
        assert any(msg['role'] == 'user' and msg['content'] == expected_user_message for msg in call_kwargs.get('messages', [])), \
               f"Expected user message not found in {call_kwargs.get('messages')}"

@pytest.mark.asyncio
async def test_summarize_commit_message_api_error(capsys):
    """Tests handling of OpenAIError during API call."""
    # Fix 1: Assign AsyncMock to the create method with side_effect
    mock_create_method = mock.AsyncMock(side_effect=OpenAIError("Simulated API Error"))
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method

    # Fix 2: get_openai_client moved inside try block in production code
    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=MOCK_PROMPT_TEMPLATE), \
         mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client):

        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME,
            date_range=MOCK_DATE_RANGE
        )

        assert summary is None # Expect None on error
        # Fix 3: Use correct assertion helper
        mock_create_method.assert_awaited_once()

        # Check if error message was printed to stderr
        captured = capsys.readouterr()
        assert "OpenAI API error: Simulated API Error" in captured.err

@pytest.mark.asyncio
async def test_summarize_commit_message_prompt_not_found(capsys):
    """Tests handling of FileNotFoundError for the prompt file."""
    # Simulate load_prompt_template raising FileNotFoundError
    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, side_effect=FileNotFoundError("File missing")) as mock_load:
        
        # Fix 1 / Fix 3: Doesn't matter much here as create isn't called, but use AsyncMock for consistency
        mock_create_method = mock.AsyncMock()
        mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
        mock_client.chat.completions.create = mock_create_method
        with mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client):
            
            summary = await llm_utils.summarize_commit_message(
                commit_message=MOCK_COMMIT_MESSAGE,
                repo_name=MOCK_REPO_NAME,
                date_range=MOCK_DATE_RANGE
            )

            assert summary is None
            mock_load.assert_awaited_once() # Ensure load was attempted

            captured = capsys.readouterr()
            assert "Prompt file error: File missing" in captured.err
            # Fix 3: Use correct assertion helper
            mock_create_method.assert_not_awaited() # API call shouldn't happen

@pytest.mark.asyncio
async def test_summarize_commit_message_prompt_missing_placeholder(capsys):
    """Tests handling of ValueError if prompt is missing a placeholder."""
    invalid_prompt = "System: Just summarize User: {{COMMIT_MESSAGE_PLACEHOLDER}}" # Missing repo/date placeholders

    # Fix 1 / Fix 3: Doesn't matter much here as create isn't called, but use AsyncMock for consistency
    mock_create_method = mock.AsyncMock()
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method

    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=invalid_prompt), \
         mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client):

        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME,
            date_range=MOCK_DATE_RANGE
        )

        assert summary is None
        captured = capsys.readouterr()
        # Fix 4: Looser assertion
        assert "Prompt formatting or content error" in captured.err
        assert "must contain '{{REPO_NAME}}'" in captured.err

@pytest.mark.asyncio
async def test_summarize_commit_message_no_api_key(monkeypatch, capsys):
    """Tests failure if OPENAI_API_KEY is not set."""
    # Temporarily remove the API key from environment for this test
    monkeypatch.delenv("OPENAI_API_KEY", raising=False) 
    
    # Reset the global client in llm_utils so get_openai_client re-evaluates
    llm_utils.async_client = None 
    
    # Fix 1 / Fix 3: Doesn't matter much here as create isn't called, but use AsyncMock for consistency
    mock_create_method = mock.AsyncMock()
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method

    # Patch load_prompt_template just so the function can proceed to call get_openai_client
    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=MOCK_PROMPT_TEMPLATE):

        # Fix 2: With get_openai_client inside the try block, the error should now be caught
        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME,
            date_range=MOCK_DATE_RANGE
        )
        
        assert summary is None
        captured = capsys.readouterr()
        # The error is caught by the OpenAIError handler in summarize_commit_message now
        assert "OpenAI API error: The OPENAI_API_KEY environment variable is not set" in captured.err

    # Reset global client again after test if necessary for other tests
    llm_utils.async_client = None

@pytest.mark.asyncio
async def test_summarize_commit_message_empty_response():
    """Tests handling if API returns empty content."""
    mock_empty_api_message = mock.Mock()
    mock_empty_api_message.content = "" # Empty content
    mock_empty_api_choice = mock.Mock()
    mock_empty_api_choice.message = mock_empty_api_message
    mock_empty_api_completion = mock.Mock()
    mock_empty_api_completion.choices = [mock_empty_api_choice]

    # Fix 1: Assign AsyncMock to the create method
    mock_create_method = mock.AsyncMock(return_value=mock_empty_api_completion)
    mock_client = mock.AsyncMock(spec=llm_utils.AsyncOpenAI)
    mock_client.chat.completions.create = mock_create_method

    with mock.patch('cli.llm_utils.load_prompt_template', new_callable=mock.AsyncMock, return_value=MOCK_PROMPT_TEMPLATE), \
         mock.patch('cli.llm_utils.get_openai_client', return_value=mock_client):

        summary = await llm_utils.summarize_commit_message(
            commit_message=MOCK_COMMIT_MESSAGE,
            repo_name=MOCK_REPO_NAME,
            date_range=MOCK_DATE_RANGE
        )

        assert summary is None # Or potentially "" depending on exact desired behavior, None seems safer
