# SimpleCursor

SimpleCursor is a tiny single-file coding agent that demonstrates agent loops, tool calling, context gathering, system prompting, and human approval gates in terminal output.

## Setup

```bash
pip install -r requirements.txt
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your_key_here
```

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

## Run

```bash
python simplecursor.py "Add a greet(name) function to sample/hello.py and print a test call" --auto-approve
```

## CLI

```bash
python simplecursor.py "<task in plain English>" [--verbose] [--auto-approve] [--max-steps N]
```

## Smoke test command

```bash
python simplecursor.py --auto-approve "Add a greet(name) function to sample/hello.py and print a test call"
```

## Out of scope in v1 (production additions)

- Streaming responses
- Diff/patch-based edits
- Codebase indexing/embeddings
- API retry/recovery logic
- Multi-provider/model-selection UI
- Parallel tool calls, persistence, auth, telemetry
- Editing outside the working directory
