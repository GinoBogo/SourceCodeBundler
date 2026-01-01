#!/usr/bin/env python3
"""
Source Code Bundler

A utility for merging multiple source code files into a single file and
splitting them back into individual files. Supports multiple programming
languages with appropriate comment syntax for headers.

Author: Gino Bogo
License: MIT
Version: 1.0
"""

import argparse
import json
import os
import re
import sys
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, ttk


# ==============================================================================
# Constants

# fmt: off
CONFIG_FILE      = "source_code_bundler.json"
SEPARATOR_MARKER = "[[ SCB ]]"
CHECKED_CHAR     = "✓"
UNCHECKED_CHAR   = "☐"

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
    ".rs": "///",
    ".c": "//",
    ".h": "//",
    ".cpp": "//",
    ".hpp": "//",
    ".css": "/*",
}

# Regex patterns for splitting
START_PATTERN         = re.compile(r"^(\S+)\s+\[\[ SCB \]\] START FILE:\s+(.+?)(?:\s*\*/)?$")
END_PATTERN           = re.compile(r"^(\S+)\s+\[\[ SCB \]\] END FILE:\s+(.+?)(?:\s*\*/)?$")
ERROR_START_PATTERN   = re.compile(r"^(\S+)\s+\[\[ SCB \]\] ERROR START:\s+(.+?)(?:\s*\*/)?$")
ERROR_MESSAGE_PATTERN = re.compile(r"^(\S+)\s+\[\[ SCB \]\] ERROR:\s+(.+?)(?:\s*\*/)?$")
ERROR_END_PATTERN     = re.compile(r"^(\S+)\s+\[\[ SCB \]\] ERROR END:\s+(.+?)(?:\s*\*/)?$")
# fmt: on


# ==============================================================================
# Configuration Helpers


def load_config():
    """Loads configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    """Saves configuration to the JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


# ==============================================================================
# GUI Helpers


def select_directory(title="Select Directory"):
    """Helper function to select a directory with a dialog."""
    return filedialog.askdirectory(title=title)


def select_file(title="Select File", filetypes=None):
    """Helper function to select a file with a dialog."""
    return filedialog.askopenfilename(title=title, filetypes=filetypes)


def save_file_dialog(title="Save File", filetypes=None):
    """Helper function to save a file with a dialog."""
    return filedialog.asksaveasfilename(title=title, filetypes=filetypes)


# ==============================================================================
# Core Logic


def read_file_content(file_path):
    """Attempts to read file content using multiple encodings."""
    for encoding in ["utf-8", "cp1252", "latin-1"]:
        try:
            with file_path.open("r", encoding=encoding, newline="") as f:
                content = f.read()
                if "\0" in content:
                    raise ValueError("Binary content detected")
                return content
        except (UnicodeDecodeError, ValueError):
            continue
    raise UnicodeDecodeError(
        "utf-8", b"", 0, 1, "Failed to decode with supported encodings"
    )


def merge_source_code(
    source_dir,
    output_file,
    extensions=None,
    progress_callback=None,
):
    """
    Recursively scans a directory for source files with specified extensions,
    combines them into a single output file with descriptive headers.

    Args:
        source_dir: Directory to scan for source files
        output_file: Path to the output combined file
        extensions: List of file extensions to include
        progress_callback: Optional callback for progress updates
    """
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    source_path = Path(source_dir).resolve()
    output_path = Path(output_file)

    # Collect matching files
    matching_files = []
    for file_path in source_path.rglob("*"):
        if file_path.is_file() and not any(
            part.startswith(".") for part in file_path.parts
        ):
            if file_path.suffix.lower() in extensions:
                matching_files.append(file_path)

    # Pre-calculate display paths and sort by path
    files_with_paths = []
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
        files_with_paths.append((file_path, rel_path_display))

    files_with_paths.sort(key=lambda x: x[1])
    total_files = len(files_with_paths)

    # Calculate max path length for alignment
    max_path_len = max((len(dp) for _, dp in files_with_paths), default=0)

    # Pre-read files to generate index statistics and cache content
    file_results = {}
    max_size_len = 0
    max_lines_len = 0
    for file_path, _ in files_with_paths:
        try:
            content = read_file_content(file_path)
            size_kb = len(content.encode("utf-8")) / 1024
            lines = content.count("\n") + 1
            size_str = f"{size_kb:.1f}"
            file_results[file_path] = (content, size_str, lines, None)
            max_size_len = max(max_size_len, len(size_str))
            max_lines_len = max(max_lines_len, len(str(lines)))
        except Exception as e:
            file_results[file_path] = (None, None, 0, e)

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        if total_files > 0:
            # Write File Index
            outfile.write(f"# {SEPARATOR_MARKER} FILE INDEX START\n")
            outfile.write(f"# Total Files: {total_files}\n")
            outfile.write("# \n")
            for file_path, display_path in files_with_paths:
                content, size_str, lines, error = file_results[file_path]
                if content is not None:
                    outfile.write(
                        f"# {display_path.ljust(max_path_len)} | SIZE: {size_str:>{max_size_len}}kb | LINES: {lines:>{max_lines_len}}\n"
                    )
                else:
                    outfile.write(
                        f"# {display_path.ljust(max_path_len)} [Error reading file]\n"
                    )
            outfile.write(f"# {SEPARATOR_MARKER} FILE INDEX END\n\n")

        for index, (file_path, rel_path_display) in enumerate(files_with_paths, 1):
            # Initialize variables
            comment_char = "//"

            # Default error markers to prevent UnboundLocalError
            err_start = (
                f"{comment_char} {SEPARATOR_MARKER} ERROR START: {rel_path_display}"
            )
            err_msg_prefix = f"{comment_char} {SEPARATOR_MARKER} ERROR:"
            err_end = f"{comment_char} {SEPARATOR_MARKER} ERROR END: {rel_path_display}"

            suffix = file_path.suffix.lower()
            comment_char = COMMENT_SYNTAX.get(suffix, "//")
            is_css_file = suffix == ".css"

            # Construct markers
            # fmt: off
            if is_css_file:
                start_marker   = f"/* {SEPARATOR_MARKER} START FILE: {rel_path_display} */"
                end_marker     = f"/* {SEPARATOR_MARKER} END FILE: {rel_path_display} */"
                err_start      = f"/* {SEPARATOR_MARKER} ERROR START: {rel_path_display} */"
                err_msg_prefix = f"/* {SEPARATOR_MARKER} ERROR:"
                err_end        = f"/* {SEPARATOR_MARKER} ERROR END: {rel_path_display} */"
                err_msg_suffix = " */"
            else:
                start_marker   = f"{comment_char} {SEPARATOR_MARKER} START FILE: {rel_path_display}"
                end_marker     = f"{comment_char} {SEPARATOR_MARKER} END FILE: {rel_path_display}"
                err_start      = f"{comment_char} {SEPARATOR_MARKER} ERROR START: {rel_path_display}"
                err_msg_prefix = f"{comment_char} {SEPARATOR_MARKER} ERROR:"
                err_end        = f"{comment_char} {SEPARATOR_MARKER} ERROR END: {rel_path_display}"
                err_msg_suffix = "" 
                # fmt: on

            try:

                # Write Start
                outfile.write(f"{start_marker}\n")

                # Write Content (from cache)
                content, _, _, error = file_results[file_path]
                if error:
                    raise error

                outfile.write(content)
                if content and not content.endswith(("\n", "\r")):
                    outfile.write("\n")

                # Write End
                outfile.write(f"{end_marker}\n\n")

            except Exception as e:
                error_msg = (
                    "Cannot read file (binary or unsupported encoding)"
                    if isinstance(e, UnicodeDecodeError)
                    else str(e)
                )
                outfile.write(
                    f"{err_start}\n{err_msg_prefix} {error_msg}{err_msg_suffix}\n{err_end}\n\n"
                )

            if progress_callback:
                progress_callback(index, total_files)


def split_source_code(source_file, output_dir, overwrite=False, progress_callback=None):
    """
    Reconstructs individual source files from a combined file created by
    merge_source_code.

    Args:
        source_file: Combined source file to split
        output_dir: Directory where individual files will be created
        overwrite: If True, overwrite existing files instead of renaming
        progress_callback: Optional callback for progress updates
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
        start_match = START_PATTERN.match(stripped)
        if start_match:
            if current_file:
                current_file.close()
                current_file = None

            original_path_str = start_match.group(2)

            try:
                # Sanitize path using os.path.abspath and os.path.commonpath
                # First, treat the path as POSIX to handle forward slashes from the bundle format
                posix_path = PurePosixPath(original_path_str)

                # If absolute, make it relative to root (strip leading /)
                if posix_path.is_absolute():
                    posix_path = posix_path.relative_to(posix_path.root)

                # Convert to string (this keeps forward slashes)
                rel_path_str = str(posix_path)

                # Ensure the path is not absolute for the current OS (e.g. drive
                # letters on Windows)
                if os.path.isabs(rel_path_str):
                    print(f"Skipping absolute path: {original_path_str}")
                    current_file = None
                    current_line += 1
                    continue

                # Resolve full path
                full_path = os.path.abspath(os.path.join(output_dir, rel_path_str))
                base_path = os.path.abspath(output_dir)

                # Check if the resolved path is within the output directory
                if not os.path.commonpath([base_path, full_path]) == base_path:
                    print(f"Skipping unsafe path: {original_path_str}")
                    current_file = None
                    current_line += 1
                    continue

                target_path = Path(full_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Avoid overwriting existing files by appending a counter
                if target_path.exists() and not (overwrite and target_path.is_file()):
                    stem = target_path.stem
                    suffix = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_path.with_name(f"{stem}_{counter}{suffix}")
                        counter += 1
                    print(
                        f"Duplicate filename detected. Renamed to: {target_path.name}"
                    )

                current_file = target_path.open("w", encoding="utf-8", newline="")
            except Exception as e:
                print(f"Error processing path {original_path_str}: {e}")
                current_file = None

            # Skip START line
            current_line += 1
            continue

        # Check END marker
        end_match = END_PATTERN.match(stripped)
        if end_match and current_file:
            current_file.close()
            current_file = None

            # Skip END line
            current_line += 1
            if current_line < len(lines) and not lines[current_line].strip():
                current_line += 1  # Skip empty line
            continue

        # Check ERROR START
        error_start_match = ERROR_START_PATTERN.match(stripped)
        if error_start_match:
            # Skip error block
            while current_line < len(lines):
                line_stripped = lines[current_line].strip()
                if ERROR_END_PATTERN.match(line_stripped):
                    # Skip ERROR END
                    current_line += 1
                    while current_line < len(lines) and not lines[current_line].strip():
                        current_line += 1
                    break
                current_line += 1
            continue

        # Skip error messages
        if ERROR_MESSAGE_PATTERN.match(stripped):
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


# ==============================================================================
# Execution Modes


def run_cli():
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

    parser.add_argument(
        "--extensions",
        nargs="+",
        default=DEFAULT_EXTENSIONS,
        help=f"List of file extensions to include (default: {' '.join(DEFAULT_EXTENSIONS)})",
    )

    args = parser.parse_args()

    if args.merge:
        source, output = args.merge
        print(f"Merging files from '{source}' to '{output}'...")
        try:
            merge_source_code(source, output, extensions=args.extensions)
            print("Merge completed successfully.")
        except Exception as e:
            print(f"Error during merge: {e}")
    elif args.split:
        source, output = args.split
        print(f"Splitting files from '{source}' to '{output}'...")
        try:
            split_source_code(source, output)
            print("Split completed successfully.")
        except Exception as e:
            print(f"Error during split: {e}")


def run_gui():
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

    filetypes_list = [(f"{ext} files", f"*{ext}") for ext in DEFAULT_EXTENSIONS]
    filetypes_list.extend([("Text files", "*.txt"), ("All files", "*.*")])

    source_var = tk.StringVar()
    dest_var = tk.StringVar()
    is_split_mode = tk.BooleanVar(value=False)
    overwrite_mode = tk.BooleanVar(value=config.get("overwrite_mode", False))
    progress_var = tk.DoubleVar()
    saved_extensions = config.get("extensions", {})
    extension_vars = {
        ext: tk.BooleanVar(value=saved_extensions.get(ext, True))
        for ext in DEFAULT_EXTENSIONS
    }

    merge_source_history = config.get("merge_source_history", [])
    merge_dest_history = config.get("merge_dest_history", [])
    split_source_history = config.get("split_source_history", [])
    split_dest_history = config.get("split_dest_history", [])

    def select_source_action():
        """Open file dialog for source selection based on current mode."""
        if is_split_mode.get():
            selected = select_file(
                "Select Bundled Source File",
                filetypes_list,
            )
        else:
            selected = select_directory("Select Source Directory")

        if selected:
            source_var.set(selected)

    def select_destination_action():
        """Open file dialog for destination selection based on current mode."""
        if is_split_mode.get():
            selected = select_directory("Select Output Directory")
        else:
            selected = save_file_dialog("Save Bundled Output", filetypes_list)

        if selected:
            dest_var.set(selected)

    def update_progress(current, total):
        """Update progress bar based on current progress."""
        if total > 0:
            percentage = (current / total) * 100
            progress_var.set(percentage)
            root.update_idletasks()

    def options_action():
        """Open a dialog to select file extensions."""
        dialog = tk.Toplevel(root)
        dialog.title("Options")
        dialog.geometry("300x350")
        dialog.minsize(300, 350)

        ttk.Label(dialog, text="Include Extensions:").pack(pady=10)

        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        tree = ttk.Treeview(list_frame, show="tree", selectmode="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def toggle_check(event):
            """Toggle the checkbox state for the selected extension."""
            item_id = tree.identify_row(event.y)
            if not item_id:
                return

            ext = tree.item(item_id, "values")[0]
            current_val = extension_vars[ext].get()
            new_val = not current_val
            extension_vars[ext].set(new_val)

            char = CHECKED_CHAR if new_val else UNCHECKED_CHAR
            tree.item(item_id, text=f" {char} {ext}")

        for ext in DEFAULT_EXTENSIONS:
            is_checked = extension_vars[ext].get()
            char = CHECKED_CHAR if is_checked else UNCHECKED_CHAR
            tree.insert("", "end", text=f" {char} {ext}", values=(ext,))

        tree.bind("<Button-1>", toggle_check)

        ttk.Button(
            dialog, text="Close", command=dialog.destroy, width=10, cursor="hand2"
        ).pack(pady=20)

    def update_history(src, dst):
        """Updates the history for source and destination comboboxes."""
        if is_split_mode.get():
            s_hist = split_source_history
            d_hist = split_dest_history
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

    def execute_action():
        """Execute merge or split operation based on current mode."""
        src = source_var.get()
        dst = dest_var.get()

        if not src or not dst:
            messagebox.showwarning(
                "Missing Information",
                "Please specify both source and destination paths.",
            )
            return

        # Validate paths
        src_path = Path(src)
        if not src_path.exists():
            messagebox.showerror(
                "Invalid Source", f"Source path does not exist:\n{src}"
            )
            return

        progress_var.set(0)

        try:
            if is_split_mode.get():
                if not src_path.is_file():
                    messagebox.showerror(
                        "Invalid Source", "Source must be a file in split mode."
                    )
                    return

                split_source_code(
                    src,
                    dst,
                    overwrite=overwrite_mode.get(),
                    progress_callback=update_progress,
                )
                update_history(src, dst)
                messagebox.showinfo(
                    "Operation Complete", f"Successfully split source code into:\n{dst}"
                )
            else:
                if not src_path.is_dir():
                    messagebox.showerror(
                        "Invalid Source", "Source must be a directory in merge mode."
                    )
                    return

                dst_path = Path(dst)
                if dst_path.exists():
                    if not messagebox.askyesno(
                        "Confirm Overwrite",
                        f"The file '{dst_path.name}' already exists.\nDo you want to overwrite it?",
                    ):
                        return

                active_extensions = [
                    ext for ext, var in extension_vars.items() if var.get()
                ]
                merge_source_code(
                    src,
                    dst,
                    extensions=active_extensions,
                    progress_callback=update_progress,
                )
                update_history(src, dst)
                messagebox.showinfo(
                    "Operation Complete",
                    f"Successfully bundled source code into:\n{dst}",
                )
        except Exception as error:
            messagebox.showerror("Operation Failed", str(error))

        progress_var.set(0)

    def toggle_operation_mode():
        """Update UI labels when operation mode changes."""
        current_source = source_var.get()
        current_dest = dest_var.get()
        source_var.set(current_dest)
        dest_var.set(current_source)

        if is_split_mode.get():
            source_label.config(text="Source File:")
            destination_label.config(text="Output Directory:")
            source_entry["values"] = split_source_history
            destination_entry["values"] = split_dest_history
            overwrite_check.config(state="normal")
        else:
            source_label.config(text="Source Directory:")
            destination_label.config(text="Output File:")
            source_entry["values"] = merge_source_history
            destination_entry["values"] = merge_dest_history
            overwrite_check.config(state="disabled")

    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # First frame: Inputs
    input_frame = ttk.LabelFrame(main_frame, text="Configuration", padding=10)
    input_frame.pack(fill=tk.BOTH, expand=True)
    input_frame.columnconfigure(1, weight=1)

    source_label = ttk.Label(input_frame, text="Source Directory:")
    source_label.grid(row=0, column=0, sticky=tk.E, pady=5)

    source_entry = ttk.Combobox(
        input_frame, textvariable=source_var, values=merge_source_history
    )
    source_entry.grid(row=0, column=1, sticky=tk.W + tk.E, padx=5)

    source_button = ttk.Button(
        input_frame,
        text="Browse",
        command=select_source_action,
        width=10,
        cursor="hand2",
    )
    source_button.grid(row=0, column=2, padx=5, pady=5)

    destination_label = ttk.Label(input_frame, text="Output File:")
    destination_label.grid(row=1, column=0, sticky=tk.E, pady=5)

    destination_entry = ttk.Combobox(
        input_frame, textvariable=dest_var, values=merge_dest_history
    )
    destination_entry.grid(row=1, column=1, sticky=tk.W + tk.E, padx=5)

    destination_button = ttk.Button(
        input_frame,
        text="Save As",
        command=select_destination_action,
        width=10,
        cursor="hand2",
    )
    destination_button.grid(row=1, column=2, padx=5, pady=5)

    mode_frame = ttk.Frame(input_frame)
    mode_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)

    ttk.Radiobutton(
        mode_frame,
        text="Merge Mode",
        variable=is_split_mode,
        value=False,
        command=toggle_operation_mode,
    ).pack(side=tk.LEFT, padx=(0, 10))

    ttk.Radiobutton(
        mode_frame,
        text="Split Mode",
        variable=is_split_mode,
        value=True,
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
        command=options_action,
        width=10,
        cursor="hand2",
    )
    options_button.pack(side=tk.LEFT, padx=5)

    execute_button = ttk.Button(
        button_frame,
        text="Execute",
        command=execute_action,
        width=10,
        cursor="hand2",
    )
    execute_button.pack(side=tk.LEFT, padx=5)

    def on_closing():
        """Save configuration and close the application."""
        config["geometry"] = root.geometry()
        config["extensions"] = {ext: var.get() for ext, var in extension_vars.items()}
        config["overwrite_mode"] = overwrite_mode.get()
        config["merge_source_history"] = merge_source_history
        config["merge_dest_history"] = merge_dest_history
        config["split_source_history"] = split_source_history
        config["split_dest_history"] = split_dest_history
        save_config(config)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
