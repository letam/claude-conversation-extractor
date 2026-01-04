# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Conversation Extractor is a Python CLI tool that extracts Claude Code conversations from undocumented JSONL files stored in `~/.claude/projects/` and converts them to readable formats (Markdown, JSON, HTML). This is a published PyPI package with zero dependencies (pure stdlib).

**Key characteristics:**
- Published package: `pip install claude-conversation-extractor`
- Zero external dependencies (stdlib only) for core functionality
- Cross-platform: Windows, macOS, Linux
- Python 3.8+ support
- Current version: 1.1.2

## Common Commands

### Development Setup
```bash
# Clone and setup
git clone https://github.com/ZeroSumQuant/claude-conversation-extractor.git
cd claude-conversation-extractor
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install dev dependencies
pip install -r requirements/dev.txt
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_extract_claude_logs_aligned.py

# Run specific test
pytest tests/test_search.py::TestSearchConversations::test_search_basic
```

### Code Quality
```bash
# Lint all source files
flake8 src/ --max-line-length=100

# Format code with black
black src/ tests/

# Security check
bandit -r src/
```

### Manual Testing
```bash
# Test main CLI commands
claude-extract --help
claude-extract --list
claude-search "test query"
claude-start  # Interactive UI with ASCII banner

# Test module imports
python -c "from extract_claude_logs import ClaudeConversationExtractor; print('OK')"
```

### Building and Publishing
```bash
# Build package
python -m build

# Check package
twine check dist/*

# Test locally
pip install dist/claude-conversation-extractor-*.whl

# Publish (GitHub Actions handles this automatically on release)
# Manual: twine upload dist/*
```

## Architecture Overview

### Module Structure

The codebase is organized into 5 main modules in `src/`:

1. **extract_claude_logs.py** (~1000 lines) - Core extraction engine
   - `ClaudeConversationExtractor` class handles all JSONL parsing
   - Reads from `~/.claude/projects/*/chat_*.jsonl`
   - Exports to Markdown, JSON, HTML formats
   - Handles both simple and detailed (with tool use) extraction modes
   - Main entry point: `launch_interactive()`

2. **interactive_ui.py** (~280 lines) - Terminal UI with ASCII banner
   - `InteractiveUI` class provides menu-driven interface
   - Shows ASCII art logo and interactive prompts
   - Integrates with search and extraction functionality
   - Launched via `claude-start` or `claude-extract` commands

3. **search_conversations.py** (~840 lines) - Search engine
   - `ConversationSearcher` class with relevance ranking
   - Supports full-text search, regex patterns, date filtering
   - Optional spaCy integration for semantic search
   - Returns `SearchResult` objects with context and scoring

4. **realtime_search.py** (~540 lines) - Interactive search UI
   - `RealTimeSearch` class with live-updating results
   - Cross-platform keyboard handling (Windows/Unix)
   - Arrow key navigation and real-time filtering
   - Threading-based search with debouncing

5. **search_cli.py** (~150 lines) - Direct search command
   - Simple CLI for `claude-search` command
   - No terminal control, just text output
   - Groups results by conversation file

### Data Flow

```
~/.claude/projects/
└── <project-id>/
    └── chat_<session-id>.jsonl  (undocumented JSONL format)
           ↓
    ClaudeConversationExtractor
           ↓
    parse_message_entries() → extract_conversation()
           ↓
    format_as_markdown() / format_as_json() / format_as_html()
           ↓
    ~/Desktop/Claude logs/claude-conversation-YYYY-MM-DD-<id>.md
```

### Key Design Patterns

**JSONL Parsing Strategy:**
- Each line in `chat_*.jsonl` is a separate JSON object
- Message types: `user`, `assistant`, `tool_use`, `tool_result`, `system`
- Content can be strings or arrays of content blocks
- Method `_extract_text_content()` handles all content format variations

**Import Pattern (all modules):**
```python
# Handle both package and direct execution
try:
    from .extract_claude_logs import ClaudeConversationExtractor
except ImportError:
    from extract_claude_logs import ClaudeConversationExtractor
```
This allows modules to work both as installed package and direct scripts.

**Output Directory Selection:**
The extractor tries multiple locations in order:
1. User-specified via `--output`
2. `~/Desktop/Claude logs`
3. `~/Documents/Claude logs`
4. `~/Claude logs`
5. `./claude-logs` (fallback)

**Detailed vs Simple Mode:**
- Simple mode (`--detailed` not set): Only user/assistant messages
- Detailed mode (`--detailed`): Includes tool use, tool results, system messages
- Preview extraction always uses simple mode for readability

## Entry Points (pyproject.toml)

Four CLI commands are registered:
```toml
[project.scripts]
claude-extract = "extract_claude_logs:launch_interactive"
claude-logs = "extract_claude_logs:launch_interactive"  # backward compat
claude-start = "extract_claude_logs:launch_interactive"
claude-search = "search_cli:main"
```

## Testing Strategy

- **97% test coverage** across all modules
- Test fixtures in `tests/fixtures/sample_conversations.py`
- Grouped by concern:
  - `test_extract_*` - Extraction functionality
  - `test_search_*` - Search features
  - `test_realtime_search_*` - Interactive search UI
  - `test_interactive_ui.py` - Menu-driven UI
  - `test_error_handling.py` - Edge cases

**Testing philosophy:**
- Use `tmp_path` fixtures for file operations
- Mock JSONL files with realistic Claude data structures
- Test cross-platform compatibility (Windows paths, etc.)

## Version Management

Version is defined in **one place only**: `pyproject.toml`

When preparing a release:
1. Update version in `pyproject.toml`
2. Commit with message like "Bump version to X.Y.Z"
3. Create git tag: `git tag vX.Y.Z`
4. Push with tags: `git push --tags`
5. GitHub Actions automatically publishes to PyPI

## Claude Code-Specific Notes

**When reading JSONL parsing code:**
The JSONL format is undocumented and reverse-engineered. The structure includes:
- Nested message objects with `role` and `content` fields
- Content can be string or array of `{type: "text", text: "..."}` blocks
- Tool use stored in separate entry types
- Base64 encoding not currently used but may exist in some fields

**When adding new export formats:**
Follow the pattern in `format_as_markdown()`, `format_as_json()`, `format_as_html()`. All format methods:
- Accept `conversation: List[Dict]` and `metadata: Dict`
- Return formatted string
- Handle both simple and detailed modes

**When modifying search:**
The search system has two modes:
1. **Simple CLI** (`search_cli.py`) - Direct text output
2. **Real-time UI** (`realtime_search.py`) - Interactive with threading

Both use the same `ConversationSearcher` backend but present results differently.
