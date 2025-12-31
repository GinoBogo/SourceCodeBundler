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

import json
import os
import re
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, ttk


# ==============================================================================
# Constants

CONFIG_FILE = "source_code_bundler.json"
DEFAULT_EXTENSIONS = [".py", ".rs", ".c", ".h", ".cpp", ".hpp", ".css"]
SEPARATOR_MARKER = "[[ SCB ]]"

COMMENT_SYNTAX = {
    ".py": "#",
    ".rs": "///",
    ".c": "//",
    ".h": "//",
    ".cpp": "//",
    ".hpp": "//",
    ".css": "/*",
}


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

    total_files = len(matching_files)

    with output_path.open("w", encoding="utf-8") as outfile:
        for index, file_path in enumerate(matching_files, 1):
            # Initialize variables
            rel_path_display = str(file_path.name)
            comment_char = "//"

            # Default error markers to prevent UnboundLocalError
            err_start = (
                f"{comment_char} {SEPARATOR_MARKER} ERROR START: {rel_path_display}"
            )
            err_msg_prefix = f"{comment_char} {SEPARATOR_MARKER} ERROR:"
            err_end = f"{comment_char} {SEPARATOR_MARKER} ERROR END: {rel_path_display}"

            try:
                suffix = file_path.suffix.lower()
                comment_char = COMMENT_SYNTAX.get(suffix, "//")
                is_css_file = suffix == ".css"

                # Calculate relative path preserving source directory name
                source_parent = source_path.parent

                # Path relative to parent
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

                # Construct markers
                if is_css_file:
                    start_marker = f"{comment_char} {SEPARATOR_MARKER} START FILE: {rel_path_display} */"
                    end_marker = f"{comment_char} {SEPARATOR_MARKER} END FILE: {rel_path_display} */"
                    err_start = f"{comment_char} {SEPARATOR_MARKER} ERROR START: {rel_path_display} */"
                    err_msg_prefix = f"{comment_char} {SEPARATOR_MARKER} ERROR:"
                    err_end = f"{comment_char} {SEPARATOR_MARKER} ERROR END: {rel_path_display} */"
                else:
                    start_marker = f"{comment_char} {SEPARATOR_MARKER} START FILE: {rel_path_display}"
                    end_marker = f"{comment_char} {SEPARATOR_MARKER} END FILE: {rel_path_display}"
                    err_start = f"{comment_char} {SEPARATOR_MARKER} ERROR START: {rel_path_display}"
                    err_msg_prefix = f"{comment_char} {SEPARATOR_MARKER} ERROR:"
                    err_end = f"{comment_char} {SEPARATOR_MARKER} ERROR END: {rel_path_display}"

                # Write Start
                outfile.write(f"{start_marker}\n")

                # Write Content
                content = file_path.read_text(encoding="utf-8")
                outfile.write(content)
                if not content.endswith("\n"):
                    outfile.write("\n")

                # Write End
                outfile.write(f"{end_marker}\n\n")

            except Exception as e:
                error_msg = (
                    "Cannot read file (binary or unsupported encoding)"
                    if isinstance(e, UnicodeDecodeError)
                    else str(e)
                )
                # Note: If exception occurs before markers are defined, this
                # might fail, but path calculation is robust.
                outfile.write(
                    f"{err_start}\n{err_msg_prefix} {error_msg}\n{err_end}\n\n"
                )

            if progress_callback:
                progress_callback(index, total_files)


def split_source_code(source_file, output_dir, progress_callback=None):
    """
    Reconstructs individual source files from a combined file created by
    merge_source_code.

    Args:
        source_file: Combined source file to split
        output_dir: Directory where individual files will be created
        progress_callback: Optional callback for progress updates
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_file)
    content = source_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    total_lines = len(lines)
    current_file = None
    current_line = 0

    # Regex patterns (handle CSS comments)
    start_pattern = r"^(\S+)\s+\[\[ SCB \]\] START FILE:\s+(.+?)(?:\s*\*/)?$"
    end_pattern = r"^(\S+)\s+\[\[ SCB \]\] END FILE:\s+(.+?)(?:\s*\*/)?$"
    error_start_pattern = r"^(\S+)\s+\[\[ SCB \]\] ERROR START:\s+(.+?)(?:\s*\*/)?$"
    error_message_pattern = r"^(\S+)\s+\[\[ SCB \]\] ERROR:\s+(.+?)(?:\s*\*/)?$"
    error_end_pattern = r"^(\S+)\s+\[\[ SCB \]\] ERROR END:\s+(.+?)(?:\s*\*/)?$"

    while current_line < len(lines):
        if progress_callback and current_line % 100 == 0:
            progress_callback(current_line, total_lines)

        line = lines[current_line]
        stripped = line.strip()

        # Check START marker
        start_match = re.match(start_pattern, stripped)
        if start_match:
            if current_file:
                current_file.close()
                current_file = None

            original_path_str = start_match.group(2)

            # Parse as POSIX path
            posix_path = PurePosixPath(original_path_str)

            # Remove leading ./
            posix_parts = list(posix_path.parts)
            if posix_parts and posix_parts[0] == ".":
                posix_parts = posix_parts[1:]

            # Check path traversal
            safe_parts = []
            for part in posix_parts:
                if part == "..":
                    # Skip parent refs
                    continue
                elif part and part != ".":
                    safe_parts.append(part)

            # Check absolute path
            is_absolute_looking = False
            if safe_parts:
                # Unix absolute path
                if original_path_str.startswith("/"):
                    is_absolute_looking = True
                # Windows absolute path
                elif len(original_path_str) > 1 and original_path_str[1] == ":":
                    is_absolute_looking = True
                elif original_path_str.startswith("\\\\"):
                    is_absolute_looking = True

            if is_absolute_looking and safe_parts:
                # Keep filename only
                safe_parts = [safe_parts[-1]] if safe_parts else []

            # Platform-specific path
            if safe_parts:
                safe_path_str = os.path.join(*safe_parts)
                safe_path = Path(safe_path_str)
            else:
                safe_path = Path(".")

            target_path = output_path / safe_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                current_file = target_path.open("w", encoding="utf-8")
            except Exception as e:
                print(f"Cannot create file {target_path}: {e}")
                current_file = None

            # Skip START line
            current_line += 1
            continue

        # Check END marker
        end_match = re.match(end_pattern, stripped)
        if end_match and current_file:
            current_file.close()
            current_file = None

            # Skip END line
            current_line += 1
            if current_line < len(lines) and not lines[current_line].strip():
                current_line += 1  # Skip empty line
            continue

        # Check ERROR START
        error_start_match = re.match(error_start_pattern, stripped)
        if error_start_match:
            # Skip error block
            while current_line < len(lines):
                line_stripped = lines[current_line].strip()
                if re.match(error_end_pattern, line_stripped):
                    # Skip ERROR END
                    current_line += 1
                    while current_line < len(lines) and not lines[current_line].strip():
                        current_line += 1
                    break
                current_line += 1
            continue

        # Skip error messages
        if re.match(error_message_pattern, stripped):
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


def run_gui():
    """Initializes and runs the graphical user interface."""
    # ==========================================================================
    # Main GUI
    root = tk.Tk()
    root.title("Source Code Bundler")

    window_width = 600
    window_height = 300

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
    progress_var = tk.DoubleVar()
    saved_extensions = config.get("extensions", {})
    extension_vars = {
        ext: tk.BooleanVar(value=saved_extensions.get(ext, True))
        for ext in DEFAULT_EXTENSIONS
    }

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

        # Create checkbox images
        img_checked = tk.PhotoImage(width=14, height=14)
        img_unchecked = tk.PhotoImage(width=14, height=14)
        for img in (img_checked, img_unchecked):
            img.put("#000000", to=(0, 0, 14, 1))
            img.put("#000000", to=(0, 13, 14, 14))
            img.put("#000000", to=(0, 0, 1, 14))
            img.put("#000000", to=(13, 0, 14, 14))
            img.put("#FFFFFF", to=(1, 1, 13, 13))

        for i in range(3):
            img_checked.put("#000000", (3 + i, 6 + i))
        for i in range(5):
            img_checked.put("#000000", (5 + i, 8 - i))

        def toggle_check(event):
            """Toggle the checkbox state for the selected extension."""
            item_id = tree.identify_row(event.y)
            if not item_id:
                return

            ext = tree.item(item_id, "values")[0]
            current_val = extension_vars[ext].get()
            new_val = not current_val
            extension_vars[ext].set(new_val)

            img = img_checked if new_val else img_unchecked
            tree.item(item_id, image=img)

        for ext in DEFAULT_EXTENSIONS:
            is_checked = extension_vars[ext].get()
            img = img_checked if is_checked else img_unchecked
            tree.insert("", "end", text=f" {ext}", values=(ext,), image=img)

        tree.bind("<Button-1>", toggle_check)

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=20)

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

                split_source_code(src, dst, progress_callback=update_progress)
                messagebox.showinfo(
                    "Operation Complete", f"Successfully split source code into:\n{dst}"
                )
            else:
                if not src_path.is_dir():
                    messagebox.showerror(
                        "Invalid Source", "Source must be a directory in merge mode."
                    )
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
                messagebox.showinfo(
                    "Operation Complete",
                    f"Successfully bundled source code into:\n{dst}",
                )
        except Exception as error:
            messagebox.showerror("Operation Failed", str(error))

        progress_var.set(0)

    def toggle_operation_mode():
        """Update UI labels when operation mode changes."""
        if is_split_mode.get():
            source_label.config(text="Source File:")
            destination_label.config(text="Output Directory:")
        else:
            source_label.config(text="Source Directory:")
            destination_label.config(text="Output File:")

    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # First frame: Inputs
    input_frame = ttk.LabelFrame(main_frame, text="Configuration", padding=10)
    input_frame.pack(fill=tk.BOTH, expand=True)
    input_frame.columnconfigure(1, weight=1)

    source_label = ttk.Label(input_frame, text="Source Directory:")
    source_label.grid(row=0, column=0, sticky=tk.E, pady=5)

    source_entry = ttk.Entry(input_frame, textvariable=source_var)
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

    destination_entry = ttk.Entry(input_frame, textvariable=dest_var)
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
        save_config(config)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
