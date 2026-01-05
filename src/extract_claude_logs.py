#!/usr/bin/env python3
"""
Extract clean conversation logs from Claude Code's internal JSONL files

This tool parses the undocumented JSONL format used by Claude Code to store
conversations locally in ~/.claude/projects/ and exports them as clean,
readable markdown files.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ClaudeConversationExtractor:
    """Extract and convert Claude Code conversations from JSONL to markdown."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the extractor with Claude's directory and output location."""
        self.claude_dir = Path.home() / ".claude" / "projects"

        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Try multiple possible output directories
            possible_dirs = [
                Path.home() / "Desktop" / "Claude logs",
                Path.home() / "Documents" / "Claude logs",
                Path.home() / "Claude logs",
                Path.cwd() / "claude-logs",
            ]

            # Use the first directory we can create
            for dir_path in possible_dirs:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    # Test if we can write to it
                    test_file = dir_path / ".test"
                    test_file.touch()
                    test_file.unlink()
                    self.output_dir = dir_path
                    break
                except Exception:
                    continue
            else:
                # Fallback to current directory
                self.output_dir = Path.cwd() / "claude-logs"
                self.output_dir.mkdir(exist_ok=True)

        print(f"📁 Saving logs to: {self.output_dir}")

    def find_sessions(self, project_path: Optional[str] = None) -> List[Path]:
        """Find all JSONL session files, sorted by most recent first."""
        if project_path:
            search_dir = self.claude_dir / project_path
        else:
            search_dir = self.claude_dir

        sessions = []
        if search_dir.exists():
            for jsonl_file in search_dir.rglob("*.jsonl"):
                sessions.append(jsonl_file)
        return sorted(sessions, key=lambda x: x.stat().st_mtime, reverse=True)

    def extract_conversation(self, jsonl_path: Path, detailed: bool = False) -> List[Dict[str, str]]:
        """Extract conversation messages from a JSONL file.
        
        Args:
            jsonl_path: Path to the JSONL file
            detailed: If True, include tool use, MCP responses, and system messages
        """
        conversation = []

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Extract user messages
                        if entry.get("type") == "user" and "message" in entry:
                            msg = entry["message"]
                            if isinstance(msg, dict) and msg.get("role") == "user":
                                content = msg.get("content", "")
                                text = self._extract_text_content(content, detailed=detailed)

                                if text and text.strip():
                                    conversation.append(
                                        {
                                            "role": "user",
                                            "content": text,
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )

                        # Extract assistant messages
                        elif entry.get("type") == "assistant" and "message" in entry:
                            msg = entry["message"]
                            if isinstance(msg, dict) and msg.get("role") == "assistant":
                                content = msg.get("content", [])
                                text = self._extract_text_content(content, detailed=detailed)

                                if text and text.strip():
                                    conversation.append(
                                        {
                                            "role": "assistant",
                                            "content": text,
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )
                        
                        # Include tool use and system messages if detailed mode
                        elif detailed:
                            # Extract tool use events
                            if entry.get("type") == "tool_use":
                                tool_data = entry.get("tool", {})
                                tool_name = tool_data.get("name", "unknown")
                                tool_input = tool_data.get("input", {})
                                conversation.append(
                                    {
                                        "role": "tool_use",
                                        "content": f"🔧 Tool: {tool_name}\nInput: {json.dumps(tool_input, indent=2)}",
                                        "timestamp": entry.get("timestamp", ""),
                                    }
                                )
                            
                            # Extract tool results
                            elif entry.get("type") == "tool_result":
                                result = entry.get("result", {})
                                output = result.get("output", "") or result.get("error", "")
                                conversation.append(
                                    {
                                        "role": "tool_result",
                                        "content": f"📤 Result:\n{output}",
                                        "timestamp": entry.get("timestamp", ""),
                                    }
                                )
                            
                            # Extract system messages
                            elif entry.get("type") == "system" and "message" in entry:
                                msg = entry.get("message", "")
                                if msg:
                                    conversation.append(
                                        {
                                            "role": "system",
                                            "content": f"ℹ️ System: {msg}",
                                            "timestamp": entry.get("timestamp", ""),
                                        }
                                    )

                    except json.JSONDecodeError:
                        continue
                    except Exception:
                        # Silently skip problematic entries
                        continue

        except Exception as e:
            print(f"❌ Error reading file {jsonl_path}: {e}")

        return conversation

    def _extract_text_content(self, content, detailed: bool = False) -> str:
        """Extract text from various content formats Claude uses.

        Args:
            content: The content to extract from
            detailed: If True, include tool use blocks, thinking, and other metadata
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Extract text from content array
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif detailed and item.get("type") == "thinking":
                        # Include thinking blocks in detailed mode (verbose mode)
                        thinking = item.get("thinking", "")
                        if thinking:
                            text_parts.append(f"\n💭 Thinking:\n{thinking}\n")
                    elif detailed and item.get("type") == "tool_use":
                        # Include tool use details in detailed mode
                        tool_name = item.get("name", "unknown")
                        tool_input = item.get("input", {})
                        text_parts.append(f"\n🔧 Using tool: {tool_name}")
                        text_parts.append(f"Input: {json.dumps(tool_input, indent=2)}\n")
                    elif detailed and item.get("type") == "tool_result":
                        # Include tool results in detailed mode (e.g., agent outputs)
                        tool_use_id = item.get("tool_use_id", "")
                        result_content = item.get("content", "")

                        # Tool result content can be a string or nested array
                        if isinstance(result_content, list):
                            # Extract text from nested content
                            result_text = self._extract_text_content(result_content, detailed=True)
                        else:
                            result_text = str(result_content)

                        if result_text:
                            text_parts.append(f"\n📤 Tool Result:")
                            if tool_use_id:
                                text_parts.append(f"Tool Use ID: {tool_use_id}")
                            text_parts.append(result_text)
            return "\n".join(text_parts)
        else:
            return str(content)

    def display_conversation(self, jsonl_path: Path, detailed: bool = False) -> None:
        """Display a conversation in the terminal with pagination.
        
        Args:
            jsonl_path: Path to the JSONL file
            detailed: If True, include tool use and system messages
        """
        try:
            # Extract conversation
            messages = self.extract_conversation(jsonl_path, detailed=detailed)
            
            if not messages:
                print("❌ No messages found in conversation")
                return
            
            # Get session info
            session_id = jsonl_path.stem
            
            # Clear screen and show header
            print("\033[2J\033[H", end="")  # Clear screen
            print("=" * 60)
            print(f"📄 Viewing: {jsonl_path.parent.name}")
            print(f"Session: {session_id[:8]}...")
            
            # Get timestamp from first message
            first_timestamp = messages[0].get("timestamp", "")
            if first_timestamp:
                try:
                    dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                    print(f"Date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception:
                    pass
            
            print("=" * 60)
            print("↑↓ to scroll • Q to quit • Enter to continue\n")
            
            # Display messages with pagination
            lines_shown = 8  # Header lines
            lines_per_page = 30
            
            for i, msg in enumerate(messages):
                role = msg["role"]
                content = msg["content"]
                
                # Format role display
                if role == "user" or role == "human":
                    print(f"\n{'─' * 40}")
                    print(f"👤 HUMAN:")
                    print(f"{'─' * 40}")
                elif role == "assistant":
                    print(f"\n{'─' * 40}")
                    print(f"🤖 CLAUDE:")
                    print(f"{'─' * 40}")
                elif role == "tool_use":
                    print(f"\n🔧 TOOL USE:")
                elif role == "tool_result":
                    print(f"\n📤 TOOL RESULT:")
                elif role == "system":
                    print(f"\nℹ️ SYSTEM:")
                else:
                    print(f"\n{role.upper()}:")
                
                # Display content (limit very long messages)
                lines = content.split('\n')
                max_lines_per_msg = 50
                
                for line_idx, line in enumerate(lines[:max_lines_per_msg]):
                    # Wrap very long lines
                    if len(line) > 100:
                        line = line[:97] + "..."
                    print(line)
                    lines_shown += 1
                    
                    # Check if we need to paginate
                    if lines_shown >= lines_per_page:
                        response = input("\n[Enter] Continue • [Q] Quit: ").strip().upper()
                        if response == "Q":
                            print("\n👋 Stopped viewing")
                            return
                        # Clear screen for next page
                        print("\033[2J\033[H", end="")
                        lines_shown = 0
                
                if len(lines) > max_lines_per_msg:
                    print(f"... [{len(lines) - max_lines_per_msg} more lines truncated]")
                    lines_shown += 1
            
            print("\n" + "=" * 60)
            print("📄 End of conversation")
            print("=" * 60)
            input("\nPress Enter to continue...")
            
        except Exception as e:
            print(f"❌ Error displaying conversation: {e}")
            input("\nPress Enter to continue...")

    def save_as_markdown(
        self, conversation: List[Dict[str, str]], session_path: Path
    ) -> Optional[Path]:
        """Save conversation as clean markdown file."""
        if not conversation:
            return None

        # Extract project name and session ID from path
        project_name = session_path.parent.name
        session_id = session_path.stem
        # Remove 'chat_' prefix if present
        if session_id.startswith('chat_'):
            session_id = session_id[5:]

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                # Parse ISO timestamp
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
                time_str = ""
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = ""

        filename = f"claude-conversation-{project_name}-{date_str}-{session_id[:8]}.md"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Claude Conversation Log\n\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Date: {date_str}")
            if time_str:
                f.write(f" {time_str}")
            f.write("\n\n---\n\n")

            for msg in conversation:
                role = msg["role"]
                content = msg["content"]
                
                if role == "user":
                    f.write("## 👤 User\n\n")
                    f.write(f"{content}\n\n")
                elif role == "assistant":
                    f.write("## 🤖 Claude\n\n")
                    f.write(f"{content}\n\n")
                elif role == "tool_use":
                    f.write("### 🔧 Tool Use\n\n")
                    f.write(f"{content}\n\n")
                elif role == "tool_result":
                    f.write("### 📤 Tool Result\n\n")
                    f.write(f"{content}\n\n")
                elif role == "system":
                    f.write("### ℹ️ System\n\n")
                    f.write(f"{content}\n\n")
                else:
                    f.write(f"## {role}\n\n")
                    f.write(f"{content}\n\n")
                f.write("---\n\n")

        return output_path
    
    def save_as_json(
        self, conversation: List[Dict[str, str]], session_path: Path
    ) -> Optional[Path]:
        """Save conversation as JSON file."""
        if not conversation:
            return None

        # Extract project name and session ID from path
        project_name = session_path.parent.name
        session_id = session_path.stem
        # Remove 'chat_' prefix if present
        if session_id.startswith('chat_'):
            session_id = session_id[5:]

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")

        filename = f"claude-conversation-{project_name}-{date_str}-{session_id[:8]}.json"
        output_path = self.output_dir / filename

        # Create JSON structure
        output = {
            "session_id": session_id,
            "date": date_str,
            "message_count": len(conversation),
            "messages": conversation
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
    
    def _format_markdown_to_html(self, text: str) -> str:
        """Convert markdown formatting to HTML with syntax highlighting support.

        Handles:
        - Code blocks with language-specific syntax highlighting
        - Inline code spans
        - Bold text
        - Italic text
        """
        import re

        # First escape HTML entities
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        # Handle code blocks with language specification (```language\ncode\n```)
        def replace_code_block(match):
            language = match.group(1) or ""
            code = match.group(2)
            # Unescape for code blocks since they're already escaped
            code = code.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            lang_class = f' class="language-{language}"' if language else ""
            return f'<pre><code{lang_class}>{code}</code></pre>'

        text = re.sub(r'```(\w+)?\n(.*?)```', replace_code_block, text, flags=re.DOTALL)

        # Handle inline code (`code`)
        def replace_inline_code(match):
            code = match.group(1)
            # Unescape for inline code
            code = code.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            return f'<code>{code}</code>'

        text = re.sub(r'`([^`]+)`', replace_inline_code, text)

        # Handle bold (**text** or __text__)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

        # Handle italic (*text* or _text_) - but not within words
        text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<em>\1</em>', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)

        return text

    def _detect_detailed_content(self, conversation: List[Dict[str, str]]) -> Dict[str, bool]:
        """Detect which detailed content types are present in conversation."""
        has_thinking = False
        has_tool_results = False
        has_tool_uses = False
        has_system = False

        for msg in conversation:
            content = msg.get("content", "")
            if "💭 Thinking:" in content:
                has_thinking = True
            if "📤 Tool Result:" in content:
                has_tool_results = True
            if "🔧 Using tool:" in content:
                has_tool_uses = True
            if msg.get("role") == "system":
                has_system = True

        return {
            "thinking": has_thinking,
            "tool_results": has_tool_results,
            "tool_uses": has_tool_uses,
            "system": has_system
        }

    def _wrap_collapsible_sections(self, content: str) -> str:
        """Wrap detailed content sections in collapsible divs."""
        import re

        # Pattern to match any section marker
        section_marker = r'(?:💭 Thinking:|📤 Tool Result:|🔧 Using tool:)'

        # Wrap thinking blocks
        content = re.sub(
            rf'(💭 Thinking:.*?)(?=\n{section_marker}|$)',
            r'<div class="collapsible-section section-thinking" onclick="this.classList.toggle(\'collapsed\')">\1</div>',
            content,
            flags=re.DOTALL
        )

        # Wrap tool results
        content = re.sub(
            rf'(📤 Tool Result:.*?)(?=\n{section_marker}|$)',
            r'<div class="collapsible-section section-tool-result" onclick="this.classList.toggle(\'collapsed\')">\1</div>',
            content,
            flags=re.DOTALL
        )

        # Wrap tool uses
        content = re.sub(
            rf'(🔧 Using tool:.*?)(?=\n{section_marker}|$)',
            r'<div class="collapsible-section section-tool-use" onclick="this.classList.toggle(\'collapsed\')">\1</div>',
            content,
            flags=re.DOTALL
        )

        return content

    def save_as_html(
        self, conversation: List[Dict[str, str]], session_path: Path
    ) -> Optional[Path]:
        """Save conversation as HTML file with syntax highlighting."""
        if not conversation:
            return None

        # Detect detailed content types
        detailed_content = self._detect_detailed_content(conversation)
        has_any_detailed = any(detailed_content.values())

        # Extract project name and session ID from path
        project_name = session_path.parent.name
        session_id = session_path.stem
        # Remove 'chat_' prefix if present
        if session_id.startswith('chat_'):
            session_id = session_id[5:]

        # Get timestamp from first message
        first_timestamp = conversation[0].get("timestamp", "")
        if first_timestamp:
            try:
                dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")
                time_str = ""
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = ""

        filename = f"claude-conversation-{project_name}-{date_str}-{session_id[:8]}.html"
        output_path = self.output_dir / filename

        # HTML template with modern styling and Highlight.js
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Conversation - {session_id[:8]}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin: 0 0 10px 0;
        }}
        .metadata {{
            color: #666;
            font-size: 0.9em;
        }}
        .message {{
            background: white;
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .user {{
            border-left: 4px solid #3498db;
        }}
        .assistant {{
            border-left: 4px solid #2ecc71;
        }}
        .tool_use {{
            border-left: 4px solid #f39c12;
            background: #fffbf0;
        }}
        .tool_result {{
            border-left: 4px solid #e74c3c;
            background: #fff5f5;
        }}
        .system {{
            border-left: 4px solid #95a5a6;
            background: #f8f9fa;
        }}
        .role {{
            font-weight: bold;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }}
        .content {{
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.5;
        }}
        .content pre {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
            border: 1px solid #e1e4e8;
        }}
        .content pre code {{
            background: transparent;
            padding: 0;
            border-radius: 0;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 0.9em;
            line-height: 1.45;
        }}
        .content code {{
            background: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 0.9em;
            border: 1px solid #e1e4e8;
        }}
        .content strong {{
            font-weight: 600;
            color: #24292e;
        }}
        .content em {{
            font-style: italic;
            color: #24292e;
        }}

        /* Toggle controls */
        .toggle-bar {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .toggle-bar h3 {{
            margin: 0 0 10px 0;
            font-size: 1em;
            color: #555;
        }}
        .toggle-controls {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .toggle-btn {{
            padding: 8px 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: #fff;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
            user-select: none;
        }}
        .toggle-btn:hover {{
            background: #f8f9fa;
            border-color: #6c757d;
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .toggle-btn:active {{
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }}

        /* Collapsible sections */
        .collapsible-section {{
            border-left: 3px solid #dee2e6;
            padding-left: 12px;
            margin: 10px 0;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .collapsible-section:hover {{
            border-left-color: #adb5bd;
            background: #f8f9fa;
        }}
        .collapsible-section.collapsed {{
            max-height: 70px;
            overflow: hidden;
        }}
        .collapsible-section.collapsed:after {{
            content: " [Click to expand...]";
            color: #6c757d;
            font-style: italic;
        }}
        .section-thinking {{
            border-left-color: #9b59b6;
        }}
        .section-tool-result {{
            border-left-color: #e74c3c;
        }}
        .section-tool-use {{
            border-left-color: #f39c12;
        }}
        .section-system {{
            border-left-color: #95a5a6;
        }}

        /* System messages collapsible */
        .message.system {{
            cursor: pointer;
        }}
        .message.system.collapsed {{
            max-height: 70px;
            overflow: hidden;
            position: relative;
        }}
        .message.system.collapsed:after {{
            content: " [Click to expand...]";
            color: #6c757d;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Claude Conversation Log</h1>
        <div class="metadata">
            <p>Session ID: {session_id}</p>
            <p>Date: {date_str} {time_str}</p>
            <p>Messages: {len(conversation)}</p>
        </div>
    </div>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

            # Add toggle bar if detailed content exists
            if has_any_detailed:
                f.write('    <div class="toggle-bar">\n')
                f.write('        <h3>Quick Actions:</h3>\n')
                f.write('        <div class="toggle-controls">\n')

                if detailed_content["thinking"]:
                    f.write('            <button class="toggle-btn" data-collapse="thinking">💭 Collapse Thinking</button>\n')

                if detailed_content["tool_uses"]:
                    f.write('            <button class="toggle-btn" data-collapse="tool-uses">🔧 Collapse Tool Uses</button>\n')

                if detailed_content["tool_results"]:
                    f.write('            <button class="toggle-btn" data-collapse="tool-results">📤 Collapse Tool Results</button>\n')

                if detailed_content["system"]:
                    f.write('            <button class="toggle-btn" data-collapse="system">ℹ️ Collapse System</button>\n')

                f.write('            <button class="toggle-btn" onclick="document.querySelectorAll(\'.collapsible-section, .message.system\').forEach(el => el.classList.remove(\'collapsed\'))">✨ Expand All</button>\n')

                f.write('        </div>\n')
                f.write('    </div>\n')

            for msg in conversation:
                role = msg["role"]
                content = msg["content"]

                # Format markdown to HTML with syntax highlighting
                formatted_content = self._format_markdown_to_html(content)

                # Wrap detailed sections in collapsible divs
                formatted_content = self._wrap_collapsible_sections(formatted_content)

                role_display = {
                    "user": "👤 User",
                    "assistant": "🤖 Claude",
                    "tool_use": "🔧 Tool Use",
                    "tool_result": "📤 Tool Result",
                    "system": "ℹ️ System"
                }.get(role, role)

                f.write(f'    <div class="message {role}">\n')
                f.write(f'        <div class="role">{role_display}</div>\n')
                f.write(f'        <div class="content">{formatted_content}</div>\n')
                f.write(f'    </div>\n')

            # Add Highlight.js script at the end for syntax highlighting
            f.write("""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script>
        // Initialize syntax highlighting
        hljs.highlightAll();

        // Collapse all buttons - one-way action
        document.querySelectorAll('[data-collapse]').forEach(btn => {
            btn.addEventListener('click', function() {
                const type = this.getAttribute('data-collapse');
                let selector = '';

                if (type === 'thinking') {
                    selector = '.section-thinking';
                } else if (type === 'tool-uses') {
                    selector = '.section-tool-use';
                } else if (type === 'tool-results') {
                    selector = '.section-tool-result';
                } else if (type === 'system') {
                    selector = '.message.system';
                }

                // Collapse all sections of this type
                if (selector) {
                    document.querySelectorAll(selector).forEach(el => {
                        el.classList.add('collapsed');
                    });
                }
            });
        });

        // Individual sections toggle on click
        document.querySelectorAll('.collapsible-section').forEach(section => {
            section.addEventListener('click', function(e) {
                this.classList.toggle('collapsed');
            });
        });

        // System messages toggle on click
        document.querySelectorAll('.message.system').forEach(msg => {
            msg.addEventListener('click', function(e) {
                this.classList.toggle('collapsed');
            });
        });

        // Keyboard shortcuts for collapsing
        document.addEventListener('keydown', function(e) {
            // Alt+T to collapse all thinking
            if (e.altKey && e.key === 't') {
                e.preventDefault();
                const btn = document.querySelector('[data-collapse="thinking"]');
                if (btn) btn.click();
            }
            // Alt+U to collapse all tool uses
            if (e.altKey && e.key === 'u') {
                e.preventDefault();
                const btn = document.querySelector('[data-collapse="tool-uses"]');
                if (btn) btn.click();
            }
            // Alt+R to collapse all tool results
            if (e.altKey && e.key === 'r') {
                e.preventDefault();
                const btn = document.querySelector('[data-collapse="tool-results"]');
                if (btn) btn.click();
            }
            // Alt+S to collapse all system messages
            if (e.altKey && e.key === 's') {
                e.preventDefault();
                const btn = document.querySelector('[data-collapse="system"]');
                if (btn) btn.click();
            }
            // Alt+E to expand all
            if (e.altKey && e.key === 'e') {
                e.preventDefault();
                document.querySelectorAll('.collapsible-section, .message.system').forEach(el => {
                    el.classList.remove('collapsed');
                });
            }
        });
    </script>
</body>
</html>""")

        return output_path

    def save_conversation(
        self, conversation: List[Dict[str, str]], session_path: Path, format: str = "markdown"
    ) -> Optional[Path]:
        """Save conversation in the specified format.

        Args:
            conversation: The conversation data
            session_path: Full path to the session file
            format: Output format ('markdown', 'json', 'html')
        """
        if format == "markdown":
            return self.save_as_markdown(conversation, session_path)
        elif format == "json":
            return self.save_as_json(conversation, session_path)
        elif format == "html":
            return self.save_as_html(conversation, session_path)
        else:
            print(f"❌ Unsupported format: {format}")
            return None

    def get_conversation_preview(self, session_path: Path) -> Tuple[str, int]:
        """Get a preview of the conversation's first real user message and message count."""
        try:
            first_user_msg = ""
            msg_count = 0
            
            with open(session_path, 'r', encoding='utf-8') as f:
                for line in f:
                    msg_count += 1
                    if not first_user_msg:
                        try:
                            data = json.loads(line)
                            # Check for user message
                            if data.get("type") == "user" and "message" in data:
                                msg = data["message"]
                                if msg.get("role") == "user":
                                    content = msg.get("content", "")
                                    
                                    # Handle list content (common format in Claude JSONL)
                                    if isinstance(content, list):
                                        for item in content:
                                            if isinstance(item, dict) and item.get("type") == "text":
                                                text = item.get("text", "").strip()
                                                
                                                # Skip tool results
                                                if text.startswith("tool_use_id"):
                                                    continue
                                                
                                                # Skip interruption messages
                                                if "[Request interrupted" in text:
                                                    continue
                                                
                                                # Skip Claude's session continuation messages
                                                if "session is being continued" in text.lower():
                                                    continue
                                                
                                                # Remove XML-like tags (command messages, etc)
                                                import re
                                                text = re.sub(r'<[^>]+>', '', text).strip()
                                                
                                                # Skip command outputs  
                                                if "is running" in text and "…" in text:
                                                    continue
                                                
                                                # Handle image references - extract text after them
                                                if text.startswith("[Image #"):
                                                    parts = text.split("]", 1)
                                                    if len(parts) > 1:
                                                        text = parts[1].strip()
                                                
                                                # If we have real user text, use it
                                                if text and len(text) > 3:  # Lower threshold to catch "hello"
                                                    first_user_msg = text[:100].replace('\n', ' ')
                                                    break
                                    
                                    # Handle string content (less common but possible)
                                    elif isinstance(content, str):
                                        import re
                                        content = content.strip()
                                        
                                        # Remove XML-like tags
                                        content = re.sub(r'<[^>]+>', '', content).strip()
                                        
                                        # Skip command outputs
                                        if "is running" in content and "…" in content:
                                            continue
                                        
                                        # Skip Claude's session continuation messages
                                        if "session is being continued" in content.lower():
                                            continue
                                        
                                        # Skip tool results and interruptions
                                        if not content.startswith("tool_use_id") and "[Request interrupted" not in content:
                                            if content and len(content) > 3:  # Lower threshold to catch short messages
                                                first_user_msg = content[:100].replace('\n', ' ')
                        except json.JSONDecodeError:
                            continue
                            
            return first_user_msg or "No preview available", msg_count
        except Exception as e:
            return f"Error: {str(e)[:30]}", 0

    def list_recent_sessions(self, limit: int = None) -> List[Path]:
        """List recent sessions with details."""
        sessions = self.find_sessions()

        if not sessions:
            print("❌ No Claude sessions found in ~/.claude/projects/")
            print("💡 Make sure you've used Claude Code and have conversations saved.")
            return []

        print(f"\n📚 Found {len(sessions)} Claude sessions:\n")
        print("=" * 80)

        # Show all sessions if no limit specified
        sessions_to_show = sessions[:limit] if limit else sessions
        for i, session in enumerate(sessions_to_show, 1):
            # Clean up project name (remove hyphens, make readable)
            project = session.parent.name.replace('-', ' ').strip()
            if project.startswith("Users"):
                project = "~/" + "/".join(project.split()[2:]) if len(project.split()) > 2 else "Home"
            
            session_id = session.stem
            modified = datetime.fromtimestamp(session.stat().st_mtime)

            # Get file size
            size = session.stat().st_size
            size_kb = size / 1024
            
            # Get preview and message count
            preview, msg_count = self.get_conversation_preview(session)

            # Print formatted info
            print(f"\n{i}. 📁 {project}")
            print(f"   📄 Session: {session_id[:8]}...")
            print(f"   📅 Modified: {modified.strftime('%Y-%m-%d %H:%M')}")
            print(f"   💬 Messages: {msg_count}")
            print(f"   💾 Size: {size_kb:.1f} KB")
            print(f"   📝 Preview: \"{preview}...\"")

        print("\n" + "=" * 80)
        return sessions[:limit]

    def extract_multiple(
        self, sessions: List[Path], indices: List[int],
        format: str = "markdown", detailed: bool = False
    ) -> Tuple[int, int]:
        """Extract multiple sessions by index.

        Args:
            sessions: List of session paths
            indices: Indices to extract
            format: Output format ('markdown', 'json', 'html')
            detailed: If True, include tool use and system messages
        """
        success = 0
        total = len(indices)

        for idx in indices:
            if 0 <= idx < len(sessions):
                session_path = sessions[idx]
                conversation = self.extract_conversation(session_path, detailed=detailed)
                if conversation:
                    output_path = self.save_conversation(conversation, session_path, format=format)
                    success += 1
                    msg_count = len(conversation)
                    print(
                        f"✅ {success}/{total}: {output_path.name} "
                        f"({msg_count} messages)"
                    )
                else:
                    print(f"⏭️  Skipped session {idx + 1} (no conversation)")
            else:
                print(f"❌ Invalid session number: {idx + 1}")

        return success, total


def main():
    parser = argparse.ArgumentParser(
        description="Extract Claude Code conversations to clean markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                    # List all available sessions
  %(prog)s --extract 1               # Extract the most recent session
  %(prog)s --extract 1,3,5           # Extract specific sessions
  %(prog)s --recent 5                # Extract 5 most recent sessions
  %(prog)s --all                     # Extract all sessions
  %(prog)s --output ~/my-logs        # Specify output directory
  %(prog)s --search "python error"   # Search conversations
  %(prog)s --search-regex "import.*" # Search with regex
  %(prog)s --format json --all       # Export all as JSON
  %(prog)s --format html --extract 1 # Export session 1 as HTML
  %(prog)s --detailed --extract 1    # Include tool use & system messages
        """,
    )
    parser.add_argument("--list", action="store_true", help="List recent sessions")
    parser.add_argument(
        "--extract",
        type=str,
        help="Extract specific session(s) by number (comma-separated)",
    )
    parser.add_argument(
        "--all", "--logs", action="store_true", help="Extract all sessions"
    )
    parser.add_argument(
        "--recent", type=int, help="Extract N most recent sessions", default=0
    )
    parser.add_argument(
        "--output", type=str, help="Output directory for markdown files"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit for --list command (default: show all)", default=None
    )
    parser.add_argument(
        "--interactive",
        "-i",
        "--start",
        "-s",
        action="store_true",
        help="Launch interactive UI for easy extraction",
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export mode: 'logs' for interactive UI",
    )

    # Search arguments
    parser.add_argument(
        "--search", type=str, help="Search conversations for text (smart search)"
    )
    parser.add_argument(
        "--search-regex", type=str, help="Search conversations using regex pattern"
    )
    parser.add_argument(
        "--search-date-from", type=str, help="Filter search from date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--search-date-to", type=str, help="Filter search to date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--search-speaker",
        choices=["human", "assistant", "both"],
        default="both",
        help="Filter search by speaker",
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", help="Make search case-sensitive"
    )
    
    # Export format arguments
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "html"],
        default="markdown",
        help="Output format for exported conversations (default: markdown)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include tool use, MCP responses, and system messages in export"
    )

    args = parser.parse_args()

    # Handle interactive mode
    if args.interactive or (args.export and args.export.lower() == "logs"):
        from interactive_ui import main as interactive_main

        interactive_main()
        return

    # Initialize extractor with optional output directory
    extractor = ClaudeConversationExtractor(args.output)

    # Handle search mode
    if args.search or args.search_regex:
        from datetime import datetime

        from search_conversations import ConversationSearcher

        searcher = ConversationSearcher()

        # Determine search mode and query
        if args.search_regex:
            query = args.search_regex
            mode = "regex"
        else:
            query = args.search
            mode = "smart"

        # Parse date filters
        date_from = None
        date_to = None
        if args.search_date_from:
            try:
                date_from = datetime.strptime(args.search_date_from, "%Y-%m-%d")
            except ValueError:
                print(f"❌ Invalid date format: {args.search_date_from}")
                return

        if args.search_date_to:
            try:
                date_to = datetime.strptime(args.search_date_to, "%Y-%m-%d")
            except ValueError:
                print(f"❌ Invalid date format: {args.search_date_to}")
                return

        # Speaker filter
        speaker_filter = None if args.search_speaker == "both" else args.search_speaker

        # Perform search
        print(f"🔍 Searching for: {query}")
        results = searcher.search(
            query=query,
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            speaker_filter=speaker_filter,
            case_sensitive=args.case_sensitive,
            max_results=30,
        )

        if not results:
            print("❌ No matches found.")
            return

        print(f"\n✅ Found {len(results)} matches across conversations:")

        # Group and display results
        results_by_file = {}
        for result in results:
            if result.file_path not in results_by_file:
                results_by_file[result.file_path] = []
            results_by_file[result.file_path].append(result)

        # Store file paths for potential viewing
        file_paths_list = []
        for file_path, file_results in results_by_file.items():
            file_paths_list.append(file_path)
            print(f"\n{len(file_paths_list)}. 📄 {file_path.parent.name} ({len(file_results)} matches)")
            # Show first match preview
            first = file_results[0]
            print(f"   {first.speaker}: {first.matched_content[:100]}...")

        # Offer to view conversations
        if file_paths_list:
            print("\n" + "=" * 60)
            try:
                view_choice = input("\nView a conversation? Enter number (1-{}) or press Enter to skip: ".format(
                    len(file_paths_list))).strip()
                
                if view_choice.isdigit():
                    view_num = int(view_choice)
                    if 1 <= view_num <= len(file_paths_list):
                        selected_path = file_paths_list[view_num - 1]
                        extractor.display_conversation(selected_path, detailed=args.detailed)
                        
                        # Offer to extract after viewing
                        extract_choice = input("\n📤 Extract this conversation? (y/N): ").strip().lower()
                        if extract_choice == 'y':
                            conversation = extractor.extract_conversation(selected_path, detailed=args.detailed)
                            if conversation:
                                if args.format == "json":
                                    output = extractor.save_as_json(conversation, selected_path)
                                elif args.format == "html":
                                    output = extractor.save_as_html(conversation, selected_path)
                                else:
                                    output = extractor.save_as_markdown(conversation, selected_path)
                                print(f"✅ Saved: {output.name}")
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Cancelled")
        
        return

    # Default action is to list sessions
    if args.list or (
        not args.extract
        and not args.all
        and not args.recent
        and not args.search
        and not args.search_regex
    ):
        sessions = extractor.list_recent_sessions(args.limit)

        if sessions and not args.list:
            print("\nTo extract conversations:")
            print("  claude-extract --extract <number>      # Extract specific session")
            print("  claude-extract --recent 5              # Extract 5 most recent")
            print("  claude-extract --all                   # Extract all sessions")

    elif args.extract:
        sessions = extractor.find_sessions()

        # Parse comma-separated indices
        indices = []
        for num in args.extract.split(","):
            try:
                idx = int(num.strip()) - 1  # Convert to 0-based index
                indices.append(idx)
            except ValueError:
                print(f"❌ Invalid session number: {num}")
                continue

        if indices:
            print(f"\n📤 Extracting {len(indices)} session(s) as {args.format.upper()}...")
            if args.detailed:
                print("📋 Including detailed tool use and system messages")
            success, total = extractor.extract_multiple(
                sessions, indices, format=args.format, detailed=args.detailed
            )
            print(f"\n✅ Successfully extracted {success}/{total} sessions")

    elif args.recent:
        sessions = extractor.find_sessions()
        limit = min(args.recent, len(sessions))
        print(f"\n📤 Extracting {limit} most recent sessions as {args.format.upper()}...")
        if args.detailed:
            print("📋 Including detailed tool use and system messages")

        indices = list(range(limit))
        success, total = extractor.extract_multiple(
            sessions, indices, format=args.format, detailed=args.detailed
        )
        print(f"\n✅ Successfully extracted {success}/{total} sessions")

    elif args.all:
        sessions = extractor.find_sessions()
        print(f"\n📤 Extracting all {len(sessions)} sessions as {args.format.upper()}...")
        if args.detailed:
            print("📋 Including detailed tool use and system messages")

        indices = list(range(len(sessions)))
        success, total = extractor.extract_multiple(
            sessions, indices, format=args.format, detailed=args.detailed
        )
        print(f"\n✅ Successfully extracted {success}/{total} sessions")


def launch_interactive():
    """Launch the interactive UI directly, or handle search if specified."""
    import sys
    
    # If no arguments provided, launch interactive UI
    if len(sys.argv) == 1:
        try:
            from .interactive_ui import main as interactive_main
        except ImportError:
            from interactive_ui import main as interactive_main
        interactive_main()
    # Check if 'search' was passed as an argument
    elif len(sys.argv) > 1 and sys.argv[1] == 'search':
        # Launch real-time search with viewing capability
        try:
            from .realtime_search import RealTimeSearch, create_smart_searcher
            from .search_conversations import ConversationSearcher
        except ImportError:
            from realtime_search import RealTimeSearch, create_smart_searcher
            from search_conversations import ConversationSearcher
        
        # Initialize components
        extractor = ClaudeConversationExtractor()
        searcher = ConversationSearcher()
        smart_searcher = create_smart_searcher(searcher)
        
        # Run search
        rts = RealTimeSearch(smart_searcher, extractor)
        selected_file = rts.run()
        
        if selected_file:
            # View the selected conversation
            extractor.display_conversation(selected_file)
            
            # Offer to extract
            try:
                extract_choice = input("\n📤 Extract this conversation? (y/N): ").strip().lower()
                if extract_choice == 'y':
                    conversation = extractor.extract_conversation(selected_file)
                    if conversation:
                        output = extractor.save_as_markdown(conversation, selected_file)
                        print(f"✅ Saved: {output.name}")
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Cancelled")
    else:
        # If other arguments are provided, run the normal CLI
        main()


if __name__ == "__main__":
    main()
