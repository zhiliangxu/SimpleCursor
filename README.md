# SimpleCursor

SimpleCursor is a tiny single-file coding agent that demonstrates agent loops, tool calling, context gathering, system prompting, and human approval gates in terminal output.

## Setup

```bash
pip install -r requirements.txt
```

### Option A — GitHub Models (recommended for the demo)

Create a fine-grained GitHub personal access token with `models:read` permission, then set it in your environment:

```bash
export GITHUB_TOKEN=your_github_token_here
```

```powershell
$env:GITHUB_TOKEN="your_github_token_here"
```

The agent will use GitHub Models (`openai/gpt-5.6-sol` by default) through the rate-limited inference API. You can browse available models at [github.com/marketplace/models](https://github.com/marketplace/models).

### Option B — OpenAI

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your_key_here
```

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

The agent will use `gpt-5.6-sol` by default.

If both environment variables are set, `GITHUB_TOKEN` takes precedence.

## Run

```bash
python simplecursor.py "Add a greet(name) function to sample/hello.py and print a test call" --auto-approve
```

## CLI

```bash
python simplecursor.py "<task in plain English>" [--verbose] [--auto-approve] [--max-steps N] [--model MODEL]
```

| Argument | Description |
|----------|-------------|
| `<task>` | Task in plain English (required) |
| `--verbose` | Print system prompt and message count per step |
| `--auto-approve` | Skip approval prompts (used by automated smoke tests) |
| `--max-steps N` | Override the loop bound (default 15) |
| `--model MODEL` | Override the selected provider's model (e.g. `gpt-4.1-mini` for OpenAI or `openai/gpt-4o-mini` for GitHub Models) |

## Smoke test command

```bash
python simplecursor.py --auto-approve "Add a greet(name) function to sample/hello.py and print a test call"
```

## Out of scope in v1 (production additions)

- Streaming responses
- Diff/patch-based edits
- Codebase indexing/embeddings
- API retry/recovery logic
- Parallel tool execution, persistence, managed credential storage, telemetry
- Editing outside the working directory
