#!/usr/bin/env python3
"""
Source Code Bundler

A utility for merging multiple source code files into a single file and
splitting them back into individual files. Supports multiple programming
languages with appropriate comment syntax for headers.

Author: Gino Bogo
License: MIT
Version: 1.1
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, ttk
from typing import Any, Callable, List, Optional, cast


# ==============================================================================
# Constants

# fmt: off
CONFIG_FILE        = "source_code_bundler.json"
GUI_CHECKED_CHAR   = "✓"
GUI_UNCHECKED_CHAR = "☐"
FILE_ENCODINGS     = ["utf-8", "cp1252", "latin-1"]
BUTTON_WIDTH       = 10

DEFAULT_EXTENSIONS = [
    ".py",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".css"]

COMMENT_SYNTAX = {
    ".py": "#",
    ".rs": "//",
    ".c": "//",
    ".h": "//",
    ".cpp": "//",
    ".hpp": "//",
    ".css": "/*",
}

SEPARATOR_MARKER = "[[ SCB ]]"

# Index Constants
START_FILE_INDEX  = f"{SEPARATOR_MARKER} FILE INDEX START"
END_FILE_INDEX    = f"{SEPARATOR_MARKER} FILE INDEX END"

# Merge Constants
START_FILE_MERGE  = f"{SEPARATOR_MARKER} START FILE:"
END_FILE_MERGE    = f"{SEPARATOR_MARKER} END FILE:"
START_ERROR_MERGE = f"{SEPARATOR_MARKER} START ERROR:"
ERROR_MSG_MERGE   = f"{SEPARATOR_MARKER} ERROR:"
END_ERROR_MERGE   = f"{SEPARATOR_MARKER} END ERROR:"

# Split Regex Patterns
def _create_split_pattern(marker):
    """Creates a regex pattern for splitting content based on a marker.

    Args:
        marker: The marker string to look for.

    Returns:
        re.Pattern: Compiled regex pattern.
    """
    return re.compile(r"^(\S+)\s+" + re.escape(marker) + r"\s+(.+?)(?:\s*\*/)?$")

START_FILE_SPLIT  = _create_split_pattern(START_FILE_MERGE)
END_FILE_SPLIT    = _create_split_pattern(END_FILE_MERGE)
START_ERROR_SPLIT = _create_split_pattern(START_ERROR_MERGE)
ERROR_MSG_SPLIT   = _create_split_pattern(ERROR_MSG_MERGE)
END_ERROR_SPLIT   = _create_split_pattern(END_ERROR_MERGE)
# fmt: on


# ==============================================================================
# Configuration Helpers


def load_config() -> dict:
    """Loads configuration from the JSON file.

    Returns:
        dict: Configuration dictionary, empty dict if file doesn't exist or is
            invalid.
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    """Saves configuration to the JSON file.

    Args:
        config: Configuration dictionary to save.
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


# ==============================================================================
# File I/O Helpers


def _is_binary_content(content: str) -> bool:
    """Checks if content appears to be binary based on control characters.

    Args:
        content: The string content to check.

    Returns:
        bool: True if content appears to be binary, False otherwise.
    """
    if not content:
        return False

    # Sample first 8KB
    sample = content[:8192]

    # Count non-printable characters (excluding common whitespace)
    # \t (9), \n (10), \r (13), \f (12) are common in text
    text_controls = {9, 10, 12, 13}

    non_printable_count = sum(
        1 for c in sample if not c.isprintable() and ord(c) not in text_controls
    )

    # If more than 10% non-printable, consider it binary
    return (non_printable_count / len(sample)) > 0.10


def _matches_filter(path: Path, filters: Optional[List[dict]]) -> bool:
    """Checks if path matches any active filter rule.

    Args:
        path: The file path to check.
        filters: List of filter dictionaries.

    Returns:
        bool: True if the path matches a filter, False otherwise.
    """
    if not filters:
        return False

    for f in filters:
        if not f.get("active", True):
            continue
        rule = f.get("rule", "").strip()
        if not rule:
            continue

        # Check if rule matches the filename or any part of the path
        if fnmatch.fnmatch(path.name, rule) or any(
            fnmatch.fnmatch(part, rule) for part in path.parts
        ):
            return True
    return False


def _collect_files(
    source_path: Path, extensions: List[str], filters: Optional[List[dict]]
) -> List[Path]:
    """Collects files matching extensions and filters.

    Args:
        source_path: Root directory to scan.
        extensions: List of allowed file extensions.
        filters: List of filter dictionaries.

    Returns:
        List[Path]: List of matching file paths.
    """
    matching_files = []
    for file_path in source_path.rglob("*"):
        if file_path.is_file() and not any(
            part.startswith(".") for part in file_path.parts
        ):
            if _matches_filter(file_path, filters):
                continue

            if file_path.suffix.lower() in extensions:
                matching_files.append(file_path)
    return matching_files


def _get_markers(suffix: str, rel_path: str) -> dict:
    """Generates start, end, and error markers based on file extension.

    Args:
        suffix: File extension (e.g., '.py').
        rel_path: Relative path to display in markers.

    Returns:
        dict: Dictionary containing marker strings.
    """
    comment_char = COMMENT_SYNTAX.get(suffix, "//")
    is_css = suffix == ".css"

    markers = {
        "start": f"{comment_char} {START_FILE_MERGE} {rel_path}",
        "end": f"{comment_char} {END_FILE_MERGE} {rel_path}",
        "err_start": f"{comment_char} {START_ERROR_MERGE} {rel_path}",
        "err_msg_prefix": f"{comment_char} {ERROR_MSG_MERGE}",
        "err_end": f"{comment_char} {END_ERROR_MERGE} {rel_path}",
        "err_msg_suffix": "",
    }

    if is_css:
        markers["start"] += " */"
        markers["end"] += " */"
        markers["err_start"] += " */"
        markers["err_end"] += " */"
        markers["err_msg_suffix"] = " */"

    return markers


def _resolve_split_path(output_dir: str, original_path_str: str) -> Optional[Path]:
    """Resolves and sanitizes the output path for splitting.

    Args:
        output_dir: Base output directory.
        original_path_str: Path string extracted from the bundle.

    Returns:
        Optional[Path]: Resolved path if safe, None otherwise.
    """
    try:
        posix_path = PurePosixPath(original_path_str)
        if posix_path.is_absolute():
            posix_path = posix_path.relative_to(posix_path.root)

        rel_path_str = str(posix_path)
        if os.path.isabs(rel_path_str):
            print(f"Skipping absolute path: {original_path_str}")
            return None

        full_path = os.path.abspath(os.path.join(output_dir, rel_path_str))
        base_path = os.path.abspath(output_dir)

        if not os.path.commonpath([base_path, full_path]) == base_path:
            print(f"Skipping unsafe path: {original_path_str}")
            return None

        return Path(full_path)
    except Exception as e:
        print(f"Error processing path {original_path_str}: {e}")
        return None


def _handle_file_collision(target_path: Path, overwrite: bool) -> Path:
    """Handles duplicate filenames by renaming or overwriting.

    Args:
        target_path: The intended file path.
        overwrite: Whether to overwrite existing files.

    Returns:
        Path: The final path to write to (may be renamed).

    Raises:
        RuntimeError: If too many duplicate files exist.
    """
    if target_path.exists() and not (overwrite and target_path.is_file()):
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        max_duplicates = 10000

        while target_path.exists():
            if counter > max_duplicates:
                raise RuntimeError(f"Too many duplicate files for {stem}{suffix}")
            target_path = target_path.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
        print(f"Duplicate filename detected. Renamed to: {target_path.name}")
    return target_path


def _skip_error_section(lines: List[str], current_line: int) -> int:
    """Skips lines until the end of an error block.

    Args:
        lines: List of all lines in the file.
        current_line: Index of the current line.

    Returns:
        int: Index of the line after the error block.
    """
    error_line_count = 0
    max_error_lines = 1000

    while current_line < len(lines) and error_line_count < max_error_lines:
        line_stripped = lines[current_line].strip()
        if END_ERROR_SPLIT.match(line_stripped):
            current_line += 1
            while current_line < len(lines) and not lines[current_line].strip():
                current_line += 1
            return current_line
        current_line += 1
        error_line_count += 1

    print("Warning: Error block exceeded max lines, skipping remaining content")
    return current_line


def read_file_content(file_path: Path) -> str:
    """Attempts to read file content using multiple encodings.

    Args:
        file_path: Path object pointing to the file to read.

    Returns:
        str: File content as string.

    Raises:
        UnicodeDecodeError: If file cannot be decoded with supported encodings.
    """
    for encoding in FILE_ENCODINGS:
        try:
            with file_path.open("r", encoding=encoding, newline="") as f:
                content = f.read()
                if _is_binary_content(content):
                    raise ValueError("Binary content detected")
                return content
        except (UnicodeDecodeError, ValueError):
            continue
    raise UnicodeDecodeError(
        "utf-8", b"", 0, 1, "Failed to decode with supported encodings"
    )


# ==============================================================================
# Core Logic Functions


def merge_source_code(
    source_dir: str,
    output_file: str,
    extensions: Optional[List[str]] = None,
    filters: Optional[List[dict]] = None,
    progress_callback: Optional[Callable] = None,
) -> int:
    """Recursively scans a directory and combines source files.

    Args:
        source_dir: Directory to scan for source files.
        output_file: Path to the output combined file.
        extensions: List of file extensions to include.
        filters: List of filter rules to exclude files/directories.
        progress_callback: Optional callback for progress updates (current, total).

    Returns:
        int: Estimated number of tokens for the bundled content.
    """
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    source_path = Path(source_dir).resolve()
    output_path = Path(output_file)

    # Collect matching files
    matching_files = _collect_files(source_path, extensions, filters)

    # Pre-calculate display paths and sort by path
    file_entries = []
    source_parent = source_path.parent

    for file_path in matching_files:
        if source_parent == source_path:
            # Handle root source_dir
            rel_path = file_path.relative_to(source_path)
            rel_path_display = (
                f"./{source_path.name}/{rel_path}"
                if source_path.name
                else f"./{rel_path}"
            )
        else:
            rel_path = file_path.relative_to(source_parent)
            rel_path_display = f"./{rel_path}"

        # Use POSIX paths
        posix_rel_path = PurePosixPath(rel_path_display)
        rel_path_display = str(posix_rel_path)
        file_entries.append((file_path, rel_path_display))

    file_entries.sort(key=lambda x: x[1])
    total_files = len(file_entries)

    # Calculate max path length for alignment
    max_path_len = max((len(dp) for _, dp in file_entries), default=0)

    # Pre-read files to generate index statistics and cache content
    content_cache = {}
    max_size_len = 0
    max_lines_len = 0
    for file_path, _ in file_entries:
        try:
            content = read_file_content(file_path)
            size_kb = len(content.encode("utf-8")) / 1024
            lines = content.count("\n") + 1
            size_str = f"{size_kb:.1f}"
            content_cache[file_path] = (content, size_str, lines, None)
            max_size_len = max(max_size_len, len(size_str))
            max_lines_len = max(max_lines_len, len(str(lines)))
        except Exception as e:
            content_cache[file_path] = (None, None, 0, e)

    # Determine bundle comment syntax
    bundle_suffix = output_path.suffix.lower()
    bundle_comment_char = COMMENT_SYNTAX.get(bundle_suffix, "#")
    is_css_bundle = bundle_suffix == ".css"
    total_chars = 0

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        if total_files > 0:
            # Write File Index
            def write_index_line(text: str):
                """Writes a line to the index section with appropriate comments."""
                nonlocal total_chars
                line = ""
                if is_css_bundle:
                    line = f"{bundle_comment_char} {text} */\n"
                else:
                    line = f"{bundle_comment_char} {text}\n"
                outfile.write(line)
                total_chars += len(line)

            write_index_line(START_FILE_INDEX)
            write_index_line(f"Total Files: {total_files}")
            write_index_line("")
            for file_path, display_path in file_entries:
                content, size_str, lines, error = content_cache[file_path]
                if content is not None:
                    write_index_line(
                        f"{display_path.ljust(max_path_len)} | SIZE: {size_str:>{max_size_len}}kb | LINES: {lines:>{max_lines_len}}"
                    )
                else:
                    write_index_line(
                        f"{display_path.ljust(max_path_len)} [Error reading file]"
                    )
            write_index_line(END_FILE_INDEX)
            outfile.write("\n")
            total_chars += 1

        for index, (file_path, rel_path_display) in enumerate(file_entries, 1):
            # Initialize variables
            suffix = file_path.suffix.lower()
            markers = _get_markers(suffix, rel_path_display)

            try:
                # Write Start
                s = f"{markers['start']}\n"
                outfile.write(s)
                total_chars += len(s)

                # Write Content (from cache)
                content, _, _, error = content_cache[file_path]
                if error:
                    raise error

                outfile.write(content)
                total_chars += len(content)
                if content and not content.endswith(("\n", "\r")):
                    outfile.write("\n")
                    total_chars += 1

                # Write End
                s = f"{markers['end']}\n\n"
                outfile.write(s)
                total_chars += len(s)

            except Exception as e:
                error_msg = (
                    "Cannot read file (binary or unsupported encoding)"
                    if isinstance(e, UnicodeDecodeError)
                    else str(e)
                )
                s = f"{markers['err_start']}\n{markers['err_msg_prefix']} {error_msg}{markers['err_msg_suffix']}\n{markers['err_end']}\n\n"
                outfile.write(s)
                total_chars += len(s)

            if progress_callback:
                progress_callback(index, total_files)

    return total_chars // 4


def split_source_code(
    source_file: str,
    output_dir: str,
    overwrite: bool = False,
    filters: Optional[List[dict]] = None,
    progress_callback: Optional[Callable] = None,
) -> None:
    """Reconstructs individual source files from a combined file.

    Args:
        source_file: Combined source file to split.
        output_dir: Directory where individual files will be created.
        overwrite: If True, overwrite existing files instead of renaming.
        filters: List of filter rules to exclude files/directories.
        progress_callback: Optional callback for progress updates (current, total).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_file)
    with source_path.open("r", encoding="utf-8", newline="") as f:
        content = f.read()
    lines = content.splitlines(keepends=True)

    total_lines = len(lines)
    current_file = None
    current_line = 0

    while current_line < len(lines):
        if progress_callback and current_line % 100 == 0:
            progress_callback(current_line, total_lines)

        line = lines[current_line]
        stripped = line.strip()

        # Check START marker
        start_match = START_FILE_SPLIT.match(stripped)
        if start_match:
            if current_file:
                current_file.close()
                current_file = None

            original_path_str = start_match.group(2)
            target_path = _resolve_split_path(output_dir, original_path_str)

            if target_path:
                if _matches_filter(target_path, filters):
                    print(f"Skipping filtered path: {original_path_str}")
                    current_file = None
                    current_line += 1
                    continue

                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path = _handle_file_collision(target_path, overwrite)
                    current_file = target_path.open("w", encoding="utf-8", newline="")
                except Exception as e:
                    print(f"Error creating file {target_path}: {e}")
                    current_file = None
            else:
                # Path resolution failed
                current_file = None

            # Skip START line
            current_line += 1
            continue

        # Check END marker
        end_match = END_FILE_SPLIT.match(stripped)
        if end_match and current_file:
            current_file.close()
            current_file = None

            # Skip END line
            current_line += 1
            if current_line < len(lines) and not lines[current_line].strip():
                current_line += 1  # Skip empty line
            continue

        # Check ERROR START
        error_start_match = START_ERROR_SPLIT.match(stripped)
        if error_start_match:
            current_line = _skip_error_section(lines, current_line)
            continue

        # Skip error messages
        if ERROR_MSG_SPLIT.match(stripped):
            current_line += 1
            continue

        # Write content
        if current_file:
            current_file.write(line)

        current_line += 1

    if current_file:
        current_file.close()

    if progress_callback:
        progress_callback(total_lines, total_lines)


def apply_patch(
    patch_file: str,
    target_dir: str,
    progress_callback: Optional[Callable] = None,
) -> None:
    """Applies a patch file to the target directory using the system 'patch' command.

    Args:
        patch_file: Path to the patch file.
        target_dir: Directory to apply the patch in.
        progress_callback: Optional callback for progress updates.

    Raises:
        FileNotFoundError: If 'patch' command is missing.
        RuntimeError: If patch application fails.
    """
    if not shutil.which("patch"):
        raise FileNotFoundError("The 'patch' command is not found in system PATH.")

    cmd = ["patch", "--batch", "--forward", "-p0", "-d", target_dir, "-i", patch_file]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Patch failed:\n{e.stderr}\n{e.stdout}")

    if progress_callback:
        progress_callback(100, 100)


# ==============================================================================
# GUI Helper Functions


class GMessageBox:
    """Custom message box with consistent font sizing."""

    @staticmethod
    def _draw_icon(canvas: tk.Canvas, icon: str) -> None:
        """Draws the specified icon onto the canvas."""
        # Use text characters for shapes to ensure antialiasing on all platforms
        # Circle: ● (U+25CF), Triangle: ▲ (U+25B2)

        font_family = "Segoe UI" if os.name == "nt" else "Helvetica"

        if icon == "information":
            # Blue circle with 'i'
            canvas.create_text(28, 28, text="●", fill="#0078D7", font=(font_family, 72))
            canvas.create_text(
                28, 28, text="i", fill="white", font=(font_family, 22, "bold")
            )
        elif icon == "warning":
            # Yellow triangle with '!'
            canvas.create_text(28, 28, text="▲", fill="#FFC107", font=(font_family, 64))
            canvas.create_text(
                28, 30, text="!", fill="black", font=(font_family, 22, "bold")
            )
        elif icon == "error":
            # Red circle with 'X'
            canvas.create_text(28, 28, text="●", fill="#E81123", font=(font_family, 72))
            canvas.create_text(
                28, 28, text="X", fill="white", font=(font_family, 20, "bold")
            )
        elif icon == "question":
            # Blue circle with '?'
            canvas.create_text(28, 28, text="●", fill="#0078D7", font=(font_family, 72))
            canvas.create_text(
                28, 28, text="?", fill="white", font=(font_family, 22, "bold")
            )

    @staticmethod
    def _create_dialog(
        title: str,
        message: str,
        buttons: List[tuple],
        icon: Optional[str] = None,
        rich_text: bool = False,
    ) -> Any:
        dialog = tk.Toplevel()
        root = dialog.master
        dialog.title(title)
        if root:
            dialog.transient(cast(tk.Wm, root))
        dialog.grab_set()
        dialog.resizable(False, False)

        # Use consistent font styling
        font_family = "Segoe UI" if os.name == "nt" else "Helvetica"
        font_size = 9 if os.name == "nt" else 10
        font_style = (font_family, font_size)

        # Get dialog background color
        bg_color = ttk.Style().lookup("TFrame", "background") or "#f0f0f0"

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        if icon:
            icon_canvas = tk.Canvas(
                content_frame,
                width=56,
                height=56,
                highlightthickness=0,
                bg=bg_color,
            )
            icon_canvas.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15))
            GMessageBox._draw_icon(icon_canvas, icon)

        if rich_text:
            # Calculate appropriate height based on content
            plain_message = message
            for tag in [
                "<b>",
                "</b>",
                "<i>",
                "</i>",
                "<u>",
                "</u>",
                "<red>",
                "</red>",
                "<blue>",
                "</blue>",
                "<green>",
                "</green>",
            ]:
                plain_message = plain_message.replace(tag, "")

            # Estimate height: ~40 characters per line, min 3 lines, max 10 lines
            estimated_height = min(max(len(plain_message) // 40 + 1, 3), 10)

            # Use Text widget for rich text support
            text_widget = tk.Text(
                content_frame,
                font=font_style,
                wrap=tk.WORD,
                width=40,
                height=estimated_height,
                relief=tk.FLAT,
                borderwidth=0,
                padx=0,
                pady=0,
                bg=bg_color,
                selectbackground=bg_color,
                inactiveselectbackground=bg_color,
                highlightthickness=0,
                exportselection=False,
            )
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Configure tags for formatting
            text_widget.tag_configure("bold", font=(font_family, font_size, "bold"))
            text_widget.tag_configure("italic", font=(font_family, font_size, "italic"))
            text_widget.tag_configure(
                "underline", font=(font_family, font_size, "normal", "underline")
            )
            text_widget.tag_configure("red", foreground="#E81123")
            text_widget.tag_configure("blue", foreground="#0078D7")
            text_widget.tag_configure("green", foreground="#107C10")

            # Rich text markup parsing with state tracking
            i = 0
            bold_on = False
            italic_on = False
            underline_on = False
            red_on = False
            blue_on = False
            green_on = False

            while i < len(message):
                if message.startswith("<b>", i):
                    bold_on = True
                    i += 3
                    continue
                elif message.startswith("</b>", i):
                    bold_on = False
                    i += 4
                    continue
                elif message.startswith("<i>", i):
                    italic_on = True
                    i += 3
                    continue
                elif message.startswith("</i>", i):
                    italic_on = False
                    i += 4
                    continue
                elif message.startswith("<u>", i):
                    underline_on = True
                    i += 3
                    continue
                elif message.startswith("</u>", i):
                    underline_on = False
                    i += 4
                    continue
                elif message.startswith("<red>", i):
                    red_on = True
                    i += 5
                    continue
                elif message.startswith("</red>", i):
                    red_on = False
                    i += 6
                    continue
                elif message.startswith("<blue>", i):
                    blue_on = True
                    i += 6
                    continue
                elif message.startswith("</blue>", i):
                    blue_on = False
                    i += 7
                    continue
                elif message.startswith("<green>", i):
                    green_on = True
                    i += 7
                    continue
                elif message.startswith("</green>", i):
                    green_on = False
                    i += 8
                    continue
                else:
                    # Insert character with current formatting
                    tags = []
                    if bold_on:
                        tags.append("bold")
                    if italic_on:
                        tags.append("italic")
                    if underline_on:
                        tags.append("underline")
                    if red_on:
                        tags.append("red")
                    if blue_on:
                        tags.append("blue")
                    if green_on:
                        tags.append("green")

                    text_widget.insert(tk.END, message[i], tuple(tags) if tags else ())
                    i += 1

            text_widget.config(state=tk.DISABLED)
        else:
            label = ttk.Label(
                content_frame,
                text=message,
                font=font_style,
                wraplength=350,
                justify=tk.LEFT,
            )
            label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Button setup
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        container = ttk.Frame(btn_frame)
        container.pack(anchor=tk.CENTER)
        result = None

        def on_btn(value):
            nonlocal result
            result = value
            dialog.destroy()

        # Create buttons
        for text, value, default in buttons:
            btn = ttk.Button(
                container,
                text=text,
                command=lambda v=value: on_btn(v),
                width=10,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=5)
            if default:
                btn.focus_set()
                dialog.bind("<Return>", lambda e, v=value: on_btn(v))

        # Keyboard shortcuts
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        # Center dialog
        dialog.update_idletasks()
        if root:
            x = root.winfo_x() + (root.winfo_width() - dialog.winfo_reqwidth()) // 2
            y = root.winfo_y() + (root.winfo_height() - dialog.winfo_reqheight()) // 2
            dialog.geometry(f"+{x}+{y}")

        dialog.wait_window()
        return result

    @staticmethod
    def showinfo(title: str, message: str, rich_text: bool = False) -> None:
        GMessageBox._create_dialog(
            title,
            message,
            [("OK", None, True)],
            icon="information",
            rich_text=rich_text,
        )

    @staticmethod
    def showwarning(title: str, message: str, rich_text: bool = False) -> None:
        GMessageBox._create_dialog(
            title, message, [("OK", None, True)], icon="warning", rich_text=rich_text
        )

    @staticmethod
    def showerror(title: str, message: str, rich_text: bool = False) -> None:
        GMessageBox._create_dialog(
            title, message, [("OK", None, True)], icon="error", rich_text=rich_text
        )

    @staticmethod
    def askyesno(title: str, message: str, rich_text: bool = False) -> Optional[bool]:
        return GMessageBox._create_dialog(
            title,
            message,
            [("Yes", True, True), ("No", False, False)],
            icon="question",
            rich_text=rich_text,
        )

    @staticmethod
    def showinfo_rich(title: str, message: str) -> None:
        """Show info dialog with rich text formatting."""
        GMessageBox.showinfo(title, message, rich_text=True)

    @staticmethod
    def showwarning_rich(title: str, message: str) -> None:
        """Show warning dialog with rich text formatting."""
        GMessageBox.showwarning(title, message, rich_text=True)

    @staticmethod
    def showerror_rich(title: str, message: str) -> None:
        """Show error dialog with rich text formatting."""
        GMessageBox.showerror(title, message, rich_text=True)

    @staticmethod
    def askyesno_rich(title: str, message: str) -> Optional[bool]:
        """Show question dialog with rich text formatting."""
        return GMessageBox.askyesno(title, message, rich_text=True)

    @staticmethod
    def askpassword(title: str, message: str) -> Optional[str]:
        """Show password input dialog with secure entry field."""
        dialog = tk.Toplevel()
        root = dialog.master
        dialog.title(title)
        if root:
            dialog.transient(cast(tk.Wm, root))
        dialog.grab_set()
        dialog.resizable(False, False)

        # Use consistent font styling
        font_family = "Segoe UI" if os.name == "nt" else "Helvetica"
        font_size = 9 if os.name == "nt" else 10
        font_style = (font_family, font_size)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Message label
        ttk.Label(main_frame, text=message, font=font_style, wraplength=300).pack(
            fill=tk.X, pady=(0, 10)
        )

        # Password entry field
        password_var = tk.StringVar()
        entry = ttk.Entry(main_frame, show="*", textvariable=password_var, width=30)
        entry.pack(fill=tk.X, pady=(0, 20))
        entry.focus_set()

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        container = ttk.Frame(btn_frame)
        container.pack(anchor=tk.CENTER)

        result = None

        def on_ok():
            nonlocal result
            result = password_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # OK and Cancel buttons
        ttk.Button(container, text="OK", command=on_ok, width=10, cursor="hand2").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            container, text="Cancel", command=on_cancel, width=10, cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        # Keyboard shortcuts
        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        # Center dialog on parent window
        dialog.update_idletasks()
        if root:
            x = root.winfo_x() + (root.winfo_width() - dialog.winfo_reqwidth()) // 2
            y = root.winfo_y() + (root.winfo_height() - dialog.winfo_reqheight()) // 2
            dialog.geometry(f"+{x}+{y}")

        dialog.wait_window()
        return result


def select_directory(title: str = "Select Directory") -> str:
    """Opens a directory selection dialog.

    Args:
        title: Dialog window title.

    Returns:
        str: Selected directory path or empty string if canceled.
    """
    return filedialog.askdirectory(title=title)


def select_file(title: str = "Select File", filetypes: Optional[List] = None) -> str:
    """Opens a file selection dialog.

    Args:
        title: Dialog window title.
        filetypes: List of file type tuples [(description, pattern)].

    Returns:
        str: Selected file path or empty string if canceled.
    """
    return filedialog.askopenfilename(title=title, filetypes=filetypes)


def save_file_dialog(title: str = "Save File", filetypes: Optional[List] = None) -> str:
    """Opens a save file dialog.

    Args:
        title: Dialog window title.
        filetypes: List of file type tuples [(description, pattern)].

    Returns:
        str: Selected save path or empty string if canceled.
    """
    return filedialog.asksaveasfilename(title=title, filetypes=filetypes)


def _create_rule_input_dialog(
    parent: tk.Toplevel, title: str, prompt_text: str, initial_value: str = ""
) -> Optional[str]:
    """Create a dialog to get a filter rule from the user.

    Args:
        parent: Parent window widget.
        title: Dialog title.
        prompt_text: Text to display in the dialog.
        initial_value: Initial value for the input field.

    Returns:
        Optional[str]: User input string, or None if canceled.
    """
    entry_var = tk.StringVar(value=initial_value)
    result = None

    def on_apply():
        """Handles the apply button click event."""
        nonlocal result
        result = entry_var.get().strip()
        if result:
            input_dialog.destroy()

    input_dialog = tk.Toplevel(parent)
    input_dialog.transient(parent)
    input_dialog.grab_set()
    input_dialog.title(title)
    input_dialog.minsize(320, 130)

    # Center dialog relative to parent
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (300 // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (150 // 2)
    input_dialog.geometry(f"300x150+{x}+{y}")

    content_frame = ttk.Frame(input_dialog, padding=10)
    content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    ttk.Label(content_frame, text=prompt_text).pack(anchor=tk.W, pady=(0, 5))

    entry = ttk.Entry(content_frame, textvariable=entry_var)
    entry.pack(fill=tk.X)
    entry.focus_set()
    entry.select_range(0, "end")
    entry.bind("<Return>", lambda e: on_apply())

    button_frame = ttk.Frame(input_dialog, padding=10)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X)

    btn_container = ttk.Frame(button_frame)
    btn_container.pack(anchor=tk.CENTER)

    ttk.Button(
        btn_container,
        text="Apply",
        command=on_apply,
        width=BUTTON_WIDTH,
        cursor="hand2",
    ).pack(side=tk.LEFT, padx=5, pady=10)
    ttk.Button(
        btn_container,
        text="Cancel",
        command=input_dialog.destroy,
        width=BUTTON_WIDTH,
        cursor="hand2",
    ).pack(side=tk.LEFT, padx=5, pady=10)

    input_dialog.wait_window()
    return result


# ==============================================================================
# GUI Callback Functions


def update_progress(
    current: int,
    total: int,
    progress_var: tk.DoubleVar,
    root: tk.Tk,
) -> None:
    """Update progress bar based on current progress.

    Args:
        current: Current progress value.
        total: Total value for 100% completion.
        progress_var: Progress bar variable.
        root: Tkinter root window.
    """
    if total > 0:
        percentage = (current / total) * 100
        progress_var.set(percentage)
        root.update_idletasks()


def toggle_checkbox(
    event: tk.Event,
    tree: ttk.Treeview,
    extension_vars: dict,
) -> None:
    """Toggle the checkbox state for the selected extension.

    Args:
        event: Mouse click event.
        tree: Treeview widget containing extensions.
        extension_vars: Dictionary of extension BooleanVars.
    """
    item_id = tree.identify_row(event.y)
    if not item_id:
        return

    ext = tree.item(item_id, "values")[0]
    current_val = extension_vars[ext].get()
    new_val = not current_val
    extension_vars[ext].set(new_val)

    char = GUI_CHECKED_CHAR if new_val else GUI_UNCHECKED_CHAR
    tree.item(item_id, text=f" {char} {ext}")


def update_history(
    src: str,
    dst: str,
    operation_mode: tk.StringVar,
    source_entry: ttk.Combobox,
    destination_entry: ttk.Combobox,
    merge_source_history: list,
    merge_dest_history: list,
    split_source_history: list,
    split_dest_history: list,
    patch_source_history: list,
    patch_dest_history: list,
) -> None:
    """Updates the history for source and destination comboboxes.

    Args:
        src: Source path.
        dst: Destination path.
        operation_mode: StringVar indicating operation mode.
        source_entry: Source combobox widget.
        destination_entry: Destination combobox widget.
        merge_source_history: Merge mode source history list.
        merge_dest_history: Merge mode destination history list.
        split_source_history: Split mode source history list.
        split_dest_history: Split mode destination history list.
        patch_source_history: Patch mode source history list.
        patch_dest_history: Patch mode destination history list.
    """
    mode = operation_mode.get()
    if mode == "split":
        s_hist = split_source_history
        d_hist = split_dest_history
    elif mode == "patch":
        s_hist = patch_source_history
        d_hist = patch_dest_history
    else:
        s_hist = merge_source_history
        d_hist = merge_dest_history

    if src in s_hist:
        s_hist.remove(src)
    s_hist.insert(0, src)
    del s_hist[10:]
    source_entry["values"] = s_hist

    if dst in d_hist:
        d_hist.remove(dst)
    d_hist.insert(0, dst)
    del d_hist[10:]
    destination_entry["values"] = d_hist


# ==============================================================================
# Execution Modes


def run_cli() -> None:
    """Parses command-line arguments and executes the requested operation."""
    parser = argparse.ArgumentParser(description="Source Code Bundler")

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--merge",
        nargs=2,
        metavar=("SOURCE_DIR", "OUTPUT_FILE"),
        help="Merge source files from directory to output file",
    )

    group.add_argument(
        "--split",
        nargs=2,
        metavar=("SOURCE_FILE", "OUTPUT_DIR"),
        help="Split bundled file to output directory",
    )

    group.add_argument(
        "--patch",
        nargs=2,
        metavar=("PATCH_FILE", "TARGET_DIR"),
        help="Apply a patch file to a target directory",
    )

    parser.add_argument(
        "--extensions",
        nargs="+",
        default=DEFAULT_EXTENSIONS,
        help=f"List of file extensions to include (default: {' '.join(DEFAULT_EXTENSIONS)})",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in split mode",
    )

    args = parser.parse_args()

    if args.merge:
        source, output = args.merge
        print(f"Merging files from '{source}' to '{output}'...")
        try:
            tokens = merge_source_code(source, output, extensions=args.extensions)
            print(f"Merge completed successfully. Estimated tokens: {tokens}")
        except Exception as e:
            print(f"Error during merge: {e}")
    elif args.split:
        source, output = args.split
        print(f"Splitting files from '{source}' to '{output}'...")
        try:
            split_source_code(source, output, overwrite=args.overwrite)
            print("Split completed successfully.")
        except Exception as e:
            print(f"Error during split: {e}")
    elif args.patch:
        patch_file, target_dir = args.patch
        print(f"Applying patch '{patch_file}' to '{target_dir}'...")
        try:
            apply_patch(patch_file, target_dir)
            print("Patch applied successfully.")
        except Exception as e:
            print(f"Error during patch: {e}")


def run_gui() -> None:
    """Initializes and runs the graphical user interface."""
    root = tk.Tk()
    root.title("Source Code Bundler")

    window_width = 600
    window_height = 340

    config = load_config()
    if "geometry" in config:
        root.geometry(config["geometry"])
    else:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = screen_width // 2 - window_width // 2
        center_y = screen_height // 2 - window_height // 2
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    root.minsize(window_width, window_height)

    style = ttk.Style()
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")
    elif (
        "vista" in available_themes and root.tk.call("tk", "windowingsystem") == "win32"
    ):
        style.theme_use("vista")

    style.configure("TNotebook.Tab", width=15, anchor="center")
    style.configure("Horizontal.TProgressbar", background="#4caf50")

    filetypes_list = [(f"{ext} files", f"*{ext}") for ext in DEFAULT_EXTENSIONS]
    filetypes_list.extend([("Text files", "*.txt"), ("All files", "*.*")])

    source_var = tk.StringVar()
    dest_var = tk.StringVar()
    operation_mode = tk.StringVar(value="merge")
    last_mode = "merge"
    overwrite_mode = tk.BooleanVar(value=config.get("overwrite_mode", False))
    progress_var = tk.DoubleVar()
    extensions_config = config.get("extensions", {})
    extension_vars = {
        ext: tk.BooleanVar(value=extensions_config.get(ext, True))
        for ext in DEFAULT_EXTENSIONS
    }

    merge_source_history = config.get("merge_source_history", [])
    merge_dest_history = config.get("merge_dest_history", [])
    split_source_history = config.get("split_source_history", [])
    split_dest_history = config.get("split_dest_history", [])
    patch_source_history = config.get("patch_source_history", [])
    patch_dest_history = config.get("patch_dest_history", [])
    filter_rules = config.get("filters", [])

    def select_source() -> None:
        """Opens file dialog for source selection based on current mode."""
        mode = operation_mode.get()
        if mode == "patch":
            selected = select_file(
                "Select Patch File",
                [("Patch files", "*.patch *.diff"), ("All files", "*.*")],
            )
        elif mode == "split":
            selected = select_file(
                "Select Bundled Source File",
                filetypes_list,
            )
        else:
            selected = select_directory("Select Source Directory")

        if selected:
            source_var.set(selected)

    def select_destination() -> None:
        """Opens file dialog for destination selection based on current mode."""
        mode = operation_mode.get()
        if mode == "split" or mode == "patch":
            selected = select_directory(
                "Select Output Directory"
                if mode == "split"
                else "Select Target Directory"
            )
        else:
            selected = save_file_dialog("Save Bundled Output", filetypes_list)

        if selected:
            dest_var.set(selected)

    def show_options() -> None:
        """Opens a dialog to select file extensions and filters."""
        dialog = tk.Toplevel(root)
        dialog.title("Options")
        dialog.geometry("350x400")
        dialog.minsize(300, 350)

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Extensions
        extensions_tab = ttk.Frame(notebook)
        notebook.add(extensions_tab, text="Extensions")

        ttk.Label(extensions_tab, text="Include Extensions:").pack(pady=10)

        list_frame = ttk.Frame(extensions_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        tree = ttk.Treeview(list_frame, show="tree", selectmode="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for ext in DEFAULT_EXTENSIONS:
            is_checked = extension_vars[ext].get()
            char = GUI_CHECKED_CHAR if is_checked else GUI_UNCHECKED_CHAR
            tree.insert("", "end", text=f" {char} {ext}", values=(ext,))

        tree.bind("<Button-1>", lambda e: toggle_checkbox(e, tree, extension_vars))

        # Tab 2: Filters
        filters_tab = ttk.Frame(notebook)
        notebook.add(filters_tab, text="Filters")

        filter_frame = ttk.Frame(filters_tab)
        filter_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        filter_frame.rowconfigure(0, weight=1)
        filter_frame.columnconfigure(0, weight=1)

        filter_tree = ttk.Treeview(
            filter_frame, columns=("check", "rule"), show="headings"
        )
        filter_tree.heading("check", text="")
        filter_tree.column("check", width=40, anchor="center", stretch=False)

        filter_tree.heading("rule", text="Filter Rule")
        filter_tree.column("rule", anchor="w", stretch=True)

        filter_tree.grid(row=0, column=0, sticky=tk.NSEW)

        scrollbar = ttk.Scrollbar(filter_frame, command=filter_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        filter_tree.config(yscrollcommand=scrollbar.set)

        def toggle_filter(event):
            """Toggles the active state of a filter rule on click."""
            item_id = filter_tree.identify_row(event.y)
            if not item_id:
                return
            vals = filter_tree.item(item_id, "values")
            new_char = (
                GUI_UNCHECKED_CHAR if vals[0] == GUI_CHECKED_CHAR else GUI_CHECKED_CHAR
            )
            filter_tree.item(item_id, values=(new_char, vals[1]))

        filter_tree.bind("<Button-1>", toggle_filter)

        def insert_filter():
            """Opens dialog to add a new filter rule."""
            rule = _create_rule_input_dialog(
                dialog, "Insert Filter", "Enter filter rule (e.g., node_modules):"
            )
            if rule:
                filter_tree.insert("", "end", values=(GUI_CHECKED_CHAR, rule))

        def edit_filter():
            """Opens dialog to edit the selected filter rule."""
            selected = filter_tree.selection()
            if not selected:
                return
            item = filter_tree.item(selected[0])
            new_rule = _create_rule_input_dialog(
                dialog, "Edit Filter", "Edit filter rule:", item["values"][1]
            )
            if new_rule:
                filter_tree.item(selected[0], values=(item["values"][0], new_rule))

        def remove_filter():
            """Removes the selected filter rule."""
            selected = filter_tree.selection()
            if selected:
                filter_tree.delete(selected[0])

        context_menu = tk.Menu(filter_tree, tearoff=0)
        context_menu.add_command(label="Insert", command=insert_filter)
        context_menu.add_command(label="Remove", command=remove_filter)
        context_menu.add_command(label="Edit", command=edit_filter)

        def show_context_menu(event):
            """Displays the context menu for filter rules."""
            item = filter_tree.identify_row(event.y)
            if item:
                filter_tree.selection_set(item)
                context_menu.entryconfig("Remove", state="normal")
                context_menu.entryconfig("Edit", state="normal")
            else:
                context_menu.entryconfig("Remove", state="disabled")
                context_menu.entryconfig("Edit", state="disabled")
            context_menu.post(event.x_root, event.y_root)

        filter_tree.bind("<Button-3>", show_context_menu)
        filter_tree.bind("<Escape>", lambda e: context_menu.unpost())

        filter_rules.sort(key=lambda x: x.get("rule", "").lower())
        for f in filter_rules:
            char = GUI_CHECKED_CHAR if f.get("active", True) else GUI_UNCHECKED_CHAR
            filter_tree.insert("", "end", values=(char, f["rule"]))

        def close_options():
            """Saves filter rules and closes the options dialog."""
            filter_rules.clear()
            for child in filter_tree.get_children():
                vals = filter_tree.item(child, "values")
                active = vals[0] == GUI_CHECKED_CHAR
                filter_rules.append({"rule": vals[1], "active": active})
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_options)

        ttk.Button(
            dialog,
            text="Close",
            command=close_options,
            width=BUTTON_WIDTH,
            cursor="hand2",
        ).pack(pady=(10, 20))

        # Center dialog
        dialog.update_idletasks()
        if root:
            x = root.winfo_x() + (root.winfo_width() - dialog.winfo_reqwidth()) // 2
            y = root.winfo_y() + (root.winfo_height() - dialog.winfo_reqheight()) // 2
            dialog.geometry(f"+{x}+{y}")

    def run_operation() -> None:
        """Executes merge, split, or patch operation based on current mode."""
        src = source_var.get()
        dst = dest_var.get()
        mode = operation_mode.get()

        if not src or not dst:
            GMessageBox.showwarning(
                "Missing Information",
                "Please specify both source and destination paths.",
            )
            return

        # Validate paths
        src_path = Path(src)
        if not src_path.exists():
            GMessageBox.showerror(
                "Invalid Source", f"Source path does not exist:\n{src}"
            )
            return

        progress_var.set(0)

        try:
            if mode == "split":
                if not src_path.is_file():
                    GMessageBox.showerror(
                        "Invalid Source", "Source must be a file in split mode."
                    )
                    return

                split_source_code(
                    src,
                    dst,
                    overwrite=overwrite_mode.get(),
                    filters=filter_rules,
                    progress_callback=lambda c, t: update_progress(
                        c, t, progress_var, root
                    ),
                )
                update_history(
                    src,
                    dst,
                    operation_mode,
                    source_entry,
                    destination_entry,
                    merge_source_history,
                    merge_dest_history,
                    split_source_history,
                    split_dest_history,
                    patch_source_history,
                    patch_dest_history,
                )
                GMessageBox.showinfo(
                    "Operation Complete", f"Successfully split source code into:\n{dst}"
                )
            elif mode == "patch":
                if not src_path.is_file():
                    GMessageBox.showerror(
                        "Invalid Source", "Source must be a patch file."
                    )
                    return

                apply_patch(
                    src,
                    dst,
                    progress_callback=lambda c, t: update_progress(
                        c, t, progress_var, root
                    ),
                )
                update_history(
                    src,
                    dst,
                    operation_mode,
                    source_entry,
                    destination_entry,
                    merge_source_history,
                    merge_dest_history,
                    split_source_history,
                    split_dest_history,
                    patch_source_history,
                    patch_dest_history,
                )
                GMessageBox.showinfo(
                    "Operation Complete", "Patch applied successfully."
                )
            else:
                if not src_path.is_dir():
                    GMessageBox.showerror(
                        "Invalid Source", "Source must be a directory in merge mode."
                    )
                    return

                dst_path = Path(dst)
                if dst_path.exists():
                    if not GMessageBox.askyesno(
                        "Confirm Overwrite",
                        f"The file '{dst_path.name}' already exists.\nDo you want to overwrite it?",
                    ):
                        return

                active_extensions = [
                    ext for ext, var in extension_vars.items() if var.get()
                ]
                tokens = merge_source_code(
                    src,
                    dst,
                    extensions=active_extensions,
                    filters=filter_rules,
                    progress_callback=lambda c, t: update_progress(
                        c, t, progress_var, root
                    ),
                )
                update_history(
                    src,
                    dst,
                    operation_mode,
                    source_entry,
                    destination_entry,
                    merge_source_history,
                    merge_dest_history,
                    split_source_history,
                    split_dest_history,
                    patch_source_history,
                    patch_dest_history,
                )
                GMessageBox.showinfo(
                    "Operation Complete",
                    f"Successfully bundled source code into:\n{dst}\n\nEstimated Tokens: {tokens}",
                )
        except Exception as error:
            GMessageBox.showerror("Operation Failed", str(error))

        progress_var.set(0)

    def toggle_operation_mode() -> None:
        """Updates UI labels when operation mode changes."""
        nonlocal last_mode
        mode = operation_mode.get()

        if (last_mode == "merge" and mode == "split") or (
            last_mode == "split" and mode == "merge"
        ):
            src_val = source_var.get()
            dst_val = dest_var.get()
            source_var.set(dst_val)
            dest_var.set(src_val)

        last_mode = mode

        if mode == "split":
            source_label.config(text="Source File:")
            destination_label.config(text="Output Directory:")
            source_entry["values"] = split_source_history
            destination_entry["values"] = split_dest_history
            overwrite_check.config(state="normal")
        elif mode == "patch":
            source_label.config(text="Patch File:")
            destination_label.config(text="Target Directory:")
            source_entry["values"] = patch_source_history
            destination_entry["values"] = patch_dest_history
            overwrite_check.config(state="disabled")
        else:
            source_label.config(text="Source Directory:")
            destination_label.config(text="Output File:")
            source_entry["values"] = merge_source_history
            destination_entry["values"] = merge_dest_history
            overwrite_check.config(state="disabled")

    # Main GUI Layout
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # First frame: Inputs
    input_frame = ttk.LabelFrame(main_frame, text="Configuration", padding=10)
    input_frame.pack(fill=tk.BOTH, expand=True)
    input_frame.columnconfigure(1, weight=1)

    source_label = ttk.Label(
        input_frame, text="Source Directory:", width=15, anchor="e"
    )
    source_label.grid(row=0, column=0, sticky=tk.E, pady=5)

    source_entry = ttk.Combobox(
        input_frame, textvariable=source_var, values=merge_source_history
    )
    source_entry.grid(row=0, column=1, sticky=tk.W + tk.E, padx=5)

    source_button = ttk.Button(
        input_frame,
        text="Browse",
        command=select_source,
        width=BUTTON_WIDTH,
        cursor="hand2",
    )
    source_button.grid(row=0, column=2, padx=5, pady=5)

    destination_label = ttk.Label(
        input_frame, text="Output File:", width=15, anchor="e"
    )
    destination_label.grid(row=1, column=0, sticky=tk.E, pady=5)

    destination_entry = ttk.Combobox(
        input_frame, textvariable=dest_var, values=merge_dest_history
    )
    destination_entry.grid(row=1, column=1, sticky=tk.W + tk.E, padx=5)

    destination_button = ttk.Button(
        input_frame,
        text="Save As",
        command=select_destination,
        width=BUTTON_WIDTH,
        cursor="hand2",
    )
    destination_button.grid(row=1, column=2, padx=5, pady=5)

    mode_frame = ttk.Frame(input_frame)
    mode_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)

    ttk.Radiobutton(
        mode_frame,
        text="Merge Mode",
        variable=operation_mode,
        value="merge",
        command=toggle_operation_mode,
    ).pack(side=tk.LEFT, padx=(0, 10))

    ttk.Radiobutton(
        mode_frame,
        text="Split Mode",
        variable=operation_mode,
        value="split",
        command=toggle_operation_mode,
    ).pack(side=tk.LEFT, padx=(0, 10))

    ttk.Radiobutton(
        mode_frame,
        text="Patch Mode",
        variable=operation_mode,
        value="patch",
        command=toggle_operation_mode,
    ).pack(side=tk.LEFT)

    overwrite_check = ttk.Checkbutton(
        input_frame,
        text="Overwrite Mode",
        variable=overwrite_mode,
        state="disabled",
    )
    overwrite_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

    # Second frame: Actions
    action_frame = ttk.Frame(main_frame)
    action_frame.pack(fill=tk.BOTH, expand=True)
    action_frame.grid_propagate(True)
    action_frame.columnconfigure(0, weight=1)
    action_frame.rowconfigure(1, weight=1)

    progress_bar = ttk.Progressbar(action_frame, variable=progress_var, maximum=100)
    progress_bar.grid(row=0, column=0, sticky="ew", pady=(10, 5))

    button_frame = ttk.Frame(action_frame)
    button_frame.grid(row=1, column=0, pady=10, sticky="s")

    options_button = ttk.Button(
        button_frame,
        text="Options",
        command=show_options,
        width=BUTTON_WIDTH,
        cursor="hand2",
    )
    options_button.pack(side=tk.LEFT, padx=5)

    execute_button = ttk.Button(
        button_frame,
        text="Execute",
        command=run_operation,
        width=BUTTON_WIDTH,
        cursor="hand2",
    )
    execute_button.pack(side=tk.LEFT, padx=5)

    def on_closing() -> None:
        """Saves configuration and closes the application."""
        config["geometry"] = root.geometry()
        config["extensions"] = {ext: var.get() for ext, var in extension_vars.items()}
        config["overwrite_mode"] = overwrite_mode.get()
        config["merge_source_history"] = merge_source_history
        config["merge_dest_history"] = merge_dest_history
        config["split_source_history"] = split_source_history
        config["split_dest_history"] = split_dest_history
        config["patch_source_history"] = patch_source_history
        config["patch_dest_history"] = patch_dest_history
        config["filters"] = filter_rules
        save_config(config)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
