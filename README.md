# AI Coding Agent

A small Python CLI that uses an LLM to inspect and work on a toy calculator project. It demonstrates tool declarations, argument validation, a function dispatcher, and an agent loop with conversation history.

Built as an educational project while following Boot.dev's **Build an AI Agent** course, with implementation and regression tests assisted by OpenAI Codex.

## How it works

The client uses the OpenAI Python SDK with OpenRouter at `https://openrouter.ai/api/v1`. The model is currently fixed in `main.py` to `minimax/minimax-m3.1-flash:free`.

Each run starts with a system message and the user's prompt. The model can answer directly or request tools. The application preserves the assistant's tool calls and appends each result as a `role="tool"` message with its matching `tool_call_id`. All tools in one response finish, in order, before the next model request.

Conversation history stays in memory for that run. The loop allows at most **20 LLM requests**. If the twentieth response still requests tools, those new operations are skipped and the CLI exits with an error. A final answer on request 20 succeeds. This limit counts model requests; a response can contain multiple tool calls.

## Tools

The dispatcher allows exactly four functions and always supplies `./calculator` as their working directory. A model-supplied `working_directory` cannot change that base.

| Tool | Model arguments | Behavior |
| --- | --- | --- |
| `get_files_info` | Optional `directory`, default `.` | Lists immediate entries with their size and directory status. |
| `get_file_content` | `file_path` | Reads UTF-8 text, limited to 10,000 characters with a truncation notice. |
| `run_python_file` | `file_path`, optional `args` array of strings | Runs a Python file with separate arguments, a 30-second timeout, and `shell=False`. Returns stdout, stderr, and any nonzero exit code. |
| `write_file` | `file_path`, `content` | Creates parent directories and creates or overwrites a UTF-8 text file. Empty content is allowed. |

Tool arguments must be a JSON object compatible with the function signature. Invalid JSON, missing or extra arguments, and incompatible types stop processing before execution. Unknown function names produce an error tool message. The loop rejects empty or non-text tool results, including an empty file read or empty directory listing.

## Setup

Requirements: **Python 3.13 or newer** and **uv**. Run commands from the project root so `./calculator` resolves to the included toy project.

```bash
uv sync --locked
cp .env.example .env
```

The committed `.env.example` is intentionally empty. Open your local `.env` and add your own key using this format:

```dotenv
OPENROUTER_API_KEY=<your key>
```

Replace the placeholder with a dedicated OpenRouter key. Set a low provider-side spending cap before live use. The application does not enforce a monetary budget, and the model's `:free` identifier is not a billing guarantee.

Keep `.env`, API keys, and sensitive logs out of commits. `.env` and local environment files are ignored; `.env.example` is the exception. Review staged changes before publishing.

## Usage

Help requires no API key or model request:

```bash
uv run main.py --help
```

The following command makes live requests to OpenRouter and can execute tools:

```bash
uv run main.py "How does the calculator render results to the console?" --verbose
```

The ordinary output contains selected tool names and the final answer. `--verbose` also prints the user prompt, token counts for each response, tool arguments, and tool results. CLI diagnostics are currently in Polish. Avoid sensitive prompts and files: tool results become part of subsequent requests to the provider, and verbose output can expose their contents locally.

## Offline validation

Recorded validation for this version: **269 pytest cases passed**, plus **9 calculator unit tests passed**. These are separate checks. The client tests supply controlled model responses and block HTTP and `.env` loading; tool tests use temporary data and reviewed fixtures. Offline results do not demonstrate real model accuracy or a successful live API run.

```bash
uv run pytest -q
uv run python calculator/tests.py
uv run python calculator/main.py "3 + 7 * 2"
```

The last command runs the calculator directly, without an LLM, and produces:

```json
{
  "expression": "3 + 7 * 2",
  "result": 17
}
```

## Calculator scope

The calculator supports the binary operators `+`, `-`, `*`, and `/`, with multiplication and division evaluated before addition and subtraction. Separate every operand and operator with whitespace. Numeric literals are parsed with Python's `float`, including signed literals such as `-3`.

The parser has no support for parentheses, exponentiation, or standalone unary operators. It uses floating-point arithmetic rather than decimal or symbolic arithmetic. Successful expressions render JSON; malformed expressions and division errors print an `Error:` message. The calculator CLI currently returns the default process exit status even when it prints an error.

## Safety boundaries

**This application is not an isolated sandbox.** Use it only with a disposable, trusted copy of the included toy calculator and reviewed Python files.

Do not point it at other people's repositories, private files, secrets, or unverified code.

Resolved-path checks restrict the file tools and reject paths outside the fixed base, including external symlink targets. They do not prevent filesystem races or isolate a Python subprocess. A launched script inherits the process's permissions and environment, potentially including the API key, and can access files or the network beyond `./calculator`.

Tools execute without an approval step. A prompt asking for an explanation does not guarantee that the model will choose only read operations. Writes can overwrite files, and model-generated code must be reviewed before execution. Keep secrets, private data, and valuable working files out of the agent's environment. Request and subprocess timeouts do not provide process isolation or a spending limit.

## Learning context

This project documents a learning implementation of an LLM tool loop. Development and test authoring were assisted by Codex; the maintainer supplied requirements and reviewed behavior. Passing automated checks does not by itself establish independent mastery or course completion. This is an independent educational project, with no claim of affiliation with Boot.dev or OpenRouter.
