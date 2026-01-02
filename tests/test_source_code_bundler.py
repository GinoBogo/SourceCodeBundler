#!/usr/bin/env python3
"""
Unit tests for the Source Code Bundler application.

Tests cover merging, splitting, error handling, security checks,
and various edge cases for file handling.

Author: Gino Bogo
License: MIT
Version: 1.1
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

# Add parent directory to path to import source_code_bundler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import source_code_bundler


class TestSourceCodeBundler(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_dir, "src")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.bundle_file = os.path.join(self.test_dir, "bundle.txt")

        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)

    def tearDown(self):
        """Clean up test environment after each test."""
        shutil.rmtree(self.test_dir)

    def _create_test_file(self, rel_path, content):
        """Helper: Create a test file with given relative path and content."""
        full_path = os.path.join(self.src_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return full_path

    # ============================================================================
    # Core Functionality Tests
    # ============================================================================

    def test_merge_and_split_cycle_basic(self):
        """Test basic merge-split cycle with multiple file types."""
        # Create source files
        test_files = {
            "main.py": "print('Hello World')\n",
            "utils/helper.py": "def help():\n    pass\n",
            "styles/main.css": "body { color: #333; }\n",
        }

        for path, content in test_files.items():
            self._create_test_file(path, content)

        # Merge files
        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py", ".css"]
        )
        self.assertTrue(os.path.exists(self.bundle_file), "Bundle file was not created")

        # Split files
        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        # Verify restored files
        src_dirname = os.path.basename(self.src_dir)
        for path, original_content in test_files.items():
            restored_path = os.path.join(self.output_dir, src_dirname, path)
            self.assertTrue(
                os.path.exists(restored_path), f"Restored file '{path}' does not exist"
            )

            with open(restored_path, "r", encoding="utf-8", newline="") as f:
                restored_content = f.read()

            self.assertEqual(
                restored_content,
                original_content,
                f"Content mismatch for file '{path}'",
            )

    def test_extension_filtering(self):
        """Test filtering by file extensions."""
        self._create_test_file("script.py", "print('python')")
        self._create_test_file("style.css", "body { color: red; }")
        self._create_test_file("readme.md", "# Readme")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("script.py", content)
        self.assertNotIn("style.css", content)
        self.assertNotIn("readme.md", content)

    def test_file_extension_case_insensitivity(self):
        """Test case-insensitive file extension matching."""
        test_files = {
            "test.PY": "# Uppercase extension",
            "Test.Cpp": "// C++ with mixed case",
            "STYLE.CSS": "/* CSS uppercase */",
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py", ".cpp", ".css"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        # All files should be included regardless of case
        self.assertIn("test.PY", content)
        self.assertIn("Test.Cpp", content)
        self.assertIn("STYLE.CSS", content)

    def test_merge_empty_directory(self):
        """Test merging an empty directory produces an empty file."""
        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )
        self.assertTrue(os.path.exists(self.bundle_file))
        self.assertEqual(os.path.getsize(self.bundle_file), 0)

    # ============================================================================
    # Comment Syntax and Formatting Tests
    # ============================================================================

    def test_css_marker_formatting(self):
        """Test CSS files have correctly formatted comment markers with closing tags."""
        self._create_test_file("style.css", "body { color: blue; }")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".css"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        src_dirname = os.path.basename(self.src_dir)

        expected_start = (
            f"/* {source_code_bundler.START_FILE_MERGE} {src_dirname}/style.css */"
        )
        expected_end = (
            f"/* {source_code_bundler.END_FILE_MERGE} {src_dirname}/style.css */"
        )

        self.assertIn(expected_start, content)
        self.assertIn(expected_end, content)

    def test_css_comment_closing_correctness(self):
        """Test that CSS markers are proper CSS comments (opened and closed)."""
        self._create_test_file("test.css", "body { color: red; }")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".css"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        marker = source_code_bundler.SEPARATOR_MARKER

        for line in lines:
            line = line.strip()
            if marker in line:
                if ".css" in line:
                    # CSS markers must be proper CSS comments
                    self.assertTrue(
                        line.startswith("/*") and line.endswith("*/"),
                        f"CSS marker '{line}' should start with /* and end with */",
                    )
                    # Ensure valid CSS comment (not nested)
                    self.assertEqual(
                        line.count("/*"),
                        1,
                        f"CSS marker '{line}' should have exactly one /*",
                    )
                    self.assertEqual(
                        line.count("*/"),
                        1,
                        f"CSS marker '{line}' should have exactly one */",
                    )

    def test_mixed_file_types_comment_syntax(self):
        """Test different file types get correct comment syntax."""
        test_files = {
            "script.py": "# Python file",
            "style.css": "/* CSS file */",
            "program.rs": "// Rust file",
            "code.cpp": "// C++ file",
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py", ".css", ".rs", ".cpp"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        marker = source_code_bundler.SEPARATOR_MARKER

        for line in lines:
            if marker in line:
                if ".css" in line:
                    self.assertTrue(line.strip().startswith("/*"))
                    self.assertTrue(line.strip().endswith("*/"))
                elif ".py" in line:
                    self.assertTrue(line.strip().startswith("#"))
                elif ".rs" in line or ".cpp" in line:
                    self.assertTrue(line.strip().startswith("//"))

    def test_regex_pattern_matching_for_css(self):
        """Test regex patterns correctly match CSS markers with comment delimiters."""
        test_content = [
            f"/* {source_code_bundler.START_FILE_MERGE} test.css */",
            "body { color: blue; }",
            f"/* {source_code_bundler.END_FILE_MERGE} test.css */",
            f"/* {source_code_bundler.START_ERROR_MERGE} test.css */",
            f"/* {source_code_bundler.END_ERROR_MERGE} test.css */",
        ]

        content = "\n".join(test_content)

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Test split function parsing
        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        # Verify file was created (proving regex matched)
        output_files = list(os.listdir(self.output_dir))
        self.assertEqual(
            len(output_files), 1, "CSS marker should trigger file creation"
        )
        self.assertEqual(output_files[0], "test.css")

        with open(
            os.path.join(self.output_dir, "test.css"), "r", encoding="utf-8", newline=""
        ) as f:
            self.assertEqual(f.read().strip(), "body { color: blue; }")

    # ============================================================================
    # Path Handling and Security Tests
    # ============================================================================

    def test_path_traversal_prevention(self):
        """Test that paths attempting directory traversal are skipped."""
        malicious_content = (
            f"// {source_code_bundler.START_FILE_MERGE} ../../etc/passwd\n"
            "malicious content\n"
            f"// {source_code_bundler.END_FILE_MERGE} ../../etc/passwd\n\n"
        )

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(malicious_content)

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        expected_path = os.path.join(self.output_dir, "etc", "passwd")
        self.assertFalse(os.path.exists(expected_path), "Unsafe path should be skipped")

    def test_path_traversal_prevention_robust(self):
        """Test robust prevention of path traversal using os.path.normpath."""
        # We attempt to write to the parent of output_dir (which is test_dir)
        traversal_content = (
            f"// {source_code_bundler.START_FILE_MERGE} ../outside.txt\n"
            "malicious content\n"
            f"// {source_code_bundler.END_FILE_MERGE} ../outside.txt\n\n"
            f"// {source_code_bundler.START_FILE_MERGE} subdir/../../outside_deep.txt\n"
            "deep malicious content\n"
            f"// {source_code_bundler.END_FILE_MERGE} subdir/../../outside_deep.txt\n\n"
            f"// {source_code_bundler.START_FILE_MERGE} safe/../safe.txt\n"
            "safe content\n"
            f"// {source_code_bundler.END_FILE_MERGE} safe/../safe.txt\n\n"
        )

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(traversal_content)

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        # Check malicious files do NOT exist in the parent directory
        outside_path = os.path.join(self.test_dir, "outside.txt")
        self.assertFalse(
            os.path.exists(outside_path), "Traversal ../outside.txt should be blocked"
        )

        outside_deep_path = os.path.join(self.test_dir, "outside_deep.txt")
        self.assertFalse(
            os.path.exists(outside_deep_path),
            "Traversal subdir/../../outside_deep.txt should be blocked",
        )

        # Check safe file DOES exist (safe/../safe.txt -> safe.txt)
        safe_path = os.path.join(self.output_dir, "safe.txt")
        self.assertTrue(
            os.path.exists(safe_path),
            "Safe traversal safe/../safe.txt should be allowed",
        )

    def test_path_handling_for_root_directories(self):
        """Test path handling with nested and root-level files."""
        # Create deep nested directory
        deep_dir = os.path.join(self.src_dir, "a", "b", "c")
        os.makedirs(deep_dir)

        deep_file = os.path.join(deep_dir, "deep.py")
        with open(deep_file, "w") as f:
            f.write("# Deep file")

        # Create root-level file
        root_file = os.path.join(self.src_dir, "root.py")
        with open(root_file, "w") as f:
            f.write("# Root file")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        # Split and verify
        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        expected_deep = os.path.join(
            self.output_dir, src_dirname, "a", "b", "c", "deep.py"
        )
        expected_root = os.path.join(self.output_dir, src_dirname, "root.py")

        self.assertTrue(os.path.exists(expected_deep))
        self.assertTrue(os.path.exists(expected_root))

    def test_relative_path_calculation_edge_cases_safe(self):
        """Test edge cases in relative path calculation safely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = os.path.join(temp_dir, "test_current.py")
            with open(test_file, "w") as f:
                f.write("# Test file")

            # Create output directory
            temp_output = os.path.join(temp_dir, "output")
            os.makedirs(temp_output)

            temp_bundle = os.path.join(temp_dir, "temp_bundle.txt")

            # Merge from temporary directory
            source_code_bundler.merge_source_code(
                temp_dir, temp_bundle, extensions=[".py"]
            )

            # Split
            source_code_bundler.split_source_code(temp_bundle, temp_output)

            # Verify creation
            output_files = os.listdir(temp_output)
            self.assertTrue(len(output_files) > 0)

            # Check restored file
            src_dirname = os.path.basename(temp_dir)
            restored_path = os.path.join(temp_output, src_dirname, "test_current.py")
            self.assertTrue(os.path.exists(restored_path))

    # ============================================================================
    # Error Handling and Edge Cases Tests
    # ============================================================================

    def test_binary_file_handling(self):
        """Test binary files result in error markers in bundle."""
        # Create file with invalid UTF-8 sequence
        bin_path = os.path.join(self.src_dir, "binary.dat")
        with open(bin_path, "wb") as f:
            f.write(b"\x00\x00\x00\x01")  # Null bytes indicating binary

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".dat"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("binary.dat", content)
        self.assertIn(source_code_bundler.START_ERROR_MERGE, content)
        self.assertIn("Cannot read file", content)

    def test_encoding_fallback(self):
        """Test that files with non-UTF-8 encoding (e.g. Latin-1) are handled."""
        # Create a file with Latin-1 content that is invalid in UTF-8
        # 'café' in Latin-1 is b'caf\xe9'. \xe9 is invalid start byte in UTF-8.
        latin1_content = b"caf\xe9"
        file_path = os.path.join(self.src_dir, "latin1.txt")
        with open(file_path, "wb") as f:
            f.write(latin1_content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".txt"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        # The content should be converted to UTF-8 in the bundle
        self.assertIn("café", content)

    def test_error_markers_defined_before_exception_robust(self):
        """Test error markers are defined before any exception can occur."""
        if os.name == "nt":  # Skip on Windows
            self.skipTest("File permission changes not reliable on Windows")

        restricted_dir = os.path.join(self.src_dir, "restricted")
        os.makedirs(restricted_dir)

        problematic_file = os.path.join(restricted_dir, "problem.py")
        with open(problematic_file, "w") as f:
            f.write("print('test')")

        original_permissions = None
        try:
            original_permissions = os.stat(problematic_file).st_mode
            os.chmod(problematic_file, 0o000)  # Make file unreadable

            source_code_bundler.merge_source_code(
                self.src_dir, self.bundle_file, extensions=[".py"]
            )

            self.assertTrue(os.path.exists(self.bundle_file))

            with open(self.bundle_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("problem.py", content)
            self.assertIn(source_code_bundler.START_ERROR_MERGE, content)
            self.assertIn(source_code_bundler.END_ERROR_MERGE, content)

        except PermissionError:
            self.skipTest("Cannot change file permissions in test environment")
        finally:
            if original_permissions is not None:
                try:
                    os.chmod(problematic_file, original_permissions)
                except Exception:
                    pass

    def test_error_handling_in_split_function(self):
        """Test error handling when splitting corrupted bundle."""
        corrupted_content = (
            f"// {source_code_bundler.START_FILE_MERGE} test.py\nprint('test')\n"
        )
        # Missing END FILE marker intentionally

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(corrupted_content)

        # Should not crash
        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

    @patch("builtins.print")
    def test_split_duplicate_filename_handling(self, mock_print):
        """Test splitting handles duplicate filenames by renaming."""
        duplicate_content = (
            f"// {source_code_bundler.START_FILE_MERGE} duplicate.txt\n"
            "Version 1\n"
            f"// {source_code_bundler.END_FILE_MERGE} duplicate.txt\n\n"
            f"// {source_code_bundler.START_FILE_MERGE} duplicate.txt\n"
            "Version 2\n"
            f"// {source_code_bundler.END_FILE_MERGE} duplicate.txt\n\n"
        )

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(duplicate_content)

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        file1 = os.path.join(self.output_dir, "duplicate.txt")
        file2 = os.path.join(self.output_dir, "duplicate_1.txt")

        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

        with open(file1, "r", encoding="utf-8", newline="") as f:
            self.assertEqual(f.read().strip(), "Version 1")

        with open(file2, "r", encoding="utf-8", newline="") as f:
            self.assertEqual(f.read().strip(), "Version 2")

    def test_split_overwrite_mode(self):
        """Test that overwrite mode overwrites existing files instead of renaming."""
        filename = "overwrite_test.txt"

        # Content in the bundle
        bundle_content = (
            f"// {source_code_bundler.START_FILE_MERGE} {filename}\n"
            "New Content\n"
            f"// {source_code_bundler.END_FILE_MERGE} {filename}\n\n"
        )

        with open(self.bundle_file, "w", encoding="utf-8") as f:
            f.write(bundle_content)

        # Create existing file with different content
        existing_file_path = os.path.join(self.output_dir, filename)
        with open(existing_file_path, "w", encoding="utf-8") as f:
            f.write("Old Content")

        # Run split with overwrite=True
        source_code_bundler.split_source_code(
            self.bundle_file, self.output_dir, overwrite=True
        )

        # Verify file content is updated
        with open(existing_file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        self.assertEqual(
            content, "New Content", "File should be overwritten with new content"
        )

        # Verify no duplicate file was created
        duplicate_path = os.path.join(self.output_dir, "overwrite_test_1.txt")
        self.assertFalse(
            os.path.exists(duplicate_path),
            "Duplicate file should not be created in overwrite mode",
        )

    # ============================================================================
    # File System Interaction Tests
    # ============================================================================

    def test_symlink_handling(self):
        """Test symbolic links to files are followed and included."""
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink not available")

        self._create_test_file("real.py", "print('real')")

        link_path = os.path.join(self.src_dir, "link.py")
        target_path = os.path.join(self.src_dir, "real.py")

        try:
            os.symlink(target_path, link_path)
        except OSError:
            self.skipTest("Permission denied to create symlink")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("real.py", content)
        self.assertIn("link.py", content)
        self.assertEqual(content.count("print('real')"), 2)

    def test_symlinks_to_directories(self):
        """Test symlinks to directories are followed."""
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink not available")

        real_dir = os.path.join(self.src_dir, "real_directory")
        os.makedirs(real_dir)

        self._create_test_file("real_directory/file1.py", "# File 1")
        self._create_test_file("real_directory/file2.py", "# File 2")

        link_path = os.path.join(self.src_dir, "link_to_dir")
        try:
            os.symlink(real_dir, link_path)
        except OSError:
            self.skipTest("Permission denied to create symlink")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Directory files should be included
        self.assertIn("file1.py", content)
        self.assertIn("file2.py", content)

    def test_hidden_files_and_directories_exclusion(self):
        """Test hidden files and directories (starting with .) are excluded."""
        test_files = {
            "regular.py": "# Regular file",
            ".hidden.py": "# Hidden file",
            "normal/.hidden.py": "# Hidden in directory",
            ".hidden_dir/file.py": "# File in hidden directory",
        }

        for path, content in test_files.items():
            self._create_test_file(path, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        with open(self.bundle_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("regular.py", content)
        self.assertNotIn(".hidden.py", content)
        self.assertNotIn(".hidden_dir", content)

    # ============================================================================
    # Content Preservation Tests
    # ============================================================================

    def test_empty_lines_and_whitespace_preservation(self):
        """Test empty lines and whitespace are preserved during merge/split."""
        test_content = """def test():
    # Function with empty lines
    
    print("Hello")
    
    # More empty lines
    
    return True
"""
        self._create_test_file("test.py", test_content)

        # Merge
        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        # Split
        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        # Verify
        src_dirname = os.path.basename(self.src_dir)
        restored_file = os.path.join(self.output_dir, src_dirname, "test.py")

        with open(restored_file, "r", encoding="utf-8", newline="") as f:
            restored_content = f.read()

        self.assertEqual(restored_content, test_content, "Whitespace not preserved")

    def test_empty_files_zero_bytes(self):
        """Test handling of empty files (0 bytes)."""
        test_files = {
            "empty.py": "",  # Zero bytes
            "empty.css": "",  # Zero bytes
            "empty.txt": "",  # Zero bytes
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py", ".css", ".txt"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for filename in test_files.keys():
            restored_path = os.path.join(self.output_dir, src_dirname, filename)
            self.assertTrue(
                os.path.exists(restored_path),
                f"Empty file '{filename}' was not restored",
            )

            with open(restored_path, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            self.assertEqual(
                content, "", f"Empty file '{filename}' should have no content"
            )

    def test_files_with_only_newlines(self):
        """Test files containing only newline characters."""
        test_cases = {
            "newlines1.py": "\n\n\n",  # Multiple newlines
            "newlines2.py": "\n",  # Single newline
            "newlines3.py": "\r\n\r\n",  # Windows-style newlines
        }

        for filename, content in test_cases.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for filename, original_content in test_cases.items():
            restored_path = os.path.join(self.output_dir, src_dirname, filename)
            self.assertTrue(
                os.path.exists(restored_path),
                f"File with only newlines '{filename}' was not restored",
            )

            with open(restored_path, "r", encoding="utf-8", newline="") as f:
                restored_content = f.read()
            self.assertEqual(
                restored_content,
                original_content,
                f"Newline content mismatch for '{filename}'",
            )

    def test_mixed_line_endings(self):
        """Test files with mixed line endings (LF, CR, CRLF)."""
        test_files = {
            "unix.py": "Line 1\nLine 2\nLine 3\n",  # Unix (LF)
            "windows.py": "Line 1\r\nLine 2\r\nLine 3\r\n",  # Windows (CRLF)
            "mac.py": "Line 1\rLine 2\rLine 3\r",  # Old Mac (CR)
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for filename, original_content in test_files.items():
            restored_path = os.path.join(self.output_dir, src_dirname, filename)
            self.assertTrue(
                os.path.exists(restored_path),
                f"File '{filename}' with mixed line endings was not restored",
            )

            with open(restored_path, "r", encoding="utf-8", newline="") as f:
                restored_content = f.read()

            self.assertEqual(
                restored_content,
                original_content,
                f"Line ending mismatch for '{filename}'",
            )

    # ============================================================================
    # Special Character and Unicode Tests
    # ============================================================================

    def test_unicode_file_names_and_content(self):
        """Test Unicode file names and content are handled correctly."""
        test_files = {
            "café.py": "# File with accented character\nprint('café')\n",
            "文件.py": "# Chinese filename\nprint('文件')\n",
            "test_emoji😀.py": "# File with emoji\nprint('😀')\n",
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for filename, original_content in test_files.items():
            restored_path = os.path.join(self.output_dir, src_dirname, filename)
            self.assertTrue(
                os.path.exists(restored_path),
                f"Unicode file '{filename}' was not restored",
            )

            with open(restored_path, "r", encoding="utf-8", newline="") as f:
                restored_content = f.read()
            self.assertEqual(
                restored_content,
                original_content,
                f"Content mismatch for Unicode file '{filename}'",
            )

    def test_files_with_special_characters_in_names(self):
        """Test files with special characters in names."""
        test_files = {
            "test space.py": "# File with space",
            "test-dash.py": "# File with dash",
            "test_underscore.py": "# File with underscore",
            "test.dot.py": "# File with multiple dots",
        }

        for filename, content in test_files.items():
            self._create_test_file(filename, content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for filename, original_content in test_files.items():
            restored_path = os.path.join(self.output_dir, src_dirname, filename)
            self.assertTrue(
                os.path.exists(restored_path),
                f"File with special chars '{filename}' was not restored",
            )

    # ============================================================================
    # Performance and Large Files Tests
    # ============================================================================

    def test_large_files_handling(self):
        """Test handling of large files."""
        large_content = "print('large file')\n" * 50000  # ~1MB
        self._create_test_file("large.py", large_content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        restored_path = os.path.join(self.output_dir, src_dirname, "large.py")

        self.assertTrue(os.path.exists(restored_path))

        with open(restored_path, "r", encoding="utf-8", newline="") as f:
            restored_content = f.read()

        # Verify content integrity
        self.assertTrue(restored_content.startswith("print('large file')\n"))
        self.assertTrue(restored_content.endswith("print('large file')\n"))

    def test_deeply_nested_directory_structure(self):
        """Test with deeply nested directory structure."""
        depth = 10
        path_parts = []
        current_path = self.src_dir

        for i in range(depth):
            dir_name = f"level_{i}"
            path_parts.append(dir_name)
            current_path = os.path.join(current_path, dir_name)
            os.makedirs(current_path, exist_ok=True)

            file_name = f"file_{i}.py"
            file_path = os.path.join(current_path, file_name)
            with open(file_path, "w") as f:
                f.write(f"# Level {i} file\nprint('level {i}')")

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        src_dirname = os.path.basename(self.src_dir)
        for i in range(depth):
            nested_path = os.path.join(src_dirname, *path_parts[: i + 1])
            file_path = os.path.join(self.output_dir, nested_path, f"file_{i}.py")
            self.assertTrue(
                os.path.exists(file_path), f"File at depth {i} was not restored"
            )

    def test_very_long_file_paths(self):
        """Test handling of very long file paths."""
        deep_path = "a" * 10 + "/" + "b" * 10 + "/" + "c" * 10
        filename = "x" * 50 + ".py"
        long_path = os.path.join(deep_path, filename)

        test_content = "# Very long path test\nprint('test')"
        self._create_test_file(long_path, test_content)

        source_code_bundler.merge_source_code(
            self.src_dir, self.bundle_file, extensions=[".py"]
        )

        source_code_bundler.split_source_code(self.bundle_file, self.output_dir)

        # Verify at least something was created
        output_files = []
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                output_files.append(os.path.join(root, file))

        self.assertGreater(len(output_files), 0, "No files created from long path")

    # ============================================================================
    # Progress and Configuration Tests
    # ============================================================================

    def test_progress_callback_frequency(self):
        """Test progress callback is called appropriately."""
        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        # Create many files to test progress updates
        for i in range(150):
            self._create_test_file(f"file{i}.txt", f"Content {i}")

        source_code_bundler.merge_source_code(
            self.src_dir,
            self.bundle_file,
            extensions=[".txt"],
            progress_callback=progress_callback,
        )

        self.assertGreater(len(callback_calls), 0, "Progress callback was never called")
        self.assertEqual(
            callback_calls[-1][0],
            callback_calls[-1][1],
            "Final callback should show 100%",
        )

        # Test split progress
        callback_calls.clear()

        source_code_bundler.split_source_code(
            self.bundle_file, self.output_dir, progress_callback=progress_callback
        )

        self.assertGreater(
            len(callback_calls), 0, "Split progress callback was never called"
        )

    def test_configuration_file_location_isolated(self):
        """Test configuration file handling with isolation."""
        original_config_file = source_code_bundler.CONFIG_FILE
        temp_config = None

        try:
            # Create temporary config file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                temp_config = f.name

            source_code_bundler.CONFIG_FILE = temp_config

            # Test config operations
            test_config = {
                "geometry": "600x300+100+100",
                "extensions": {".py": True, ".css": False},
            }

            source_code_bundler.save_config(test_config)
            loaded_config = source_code_bundler.load_config()

            self.assertIsInstance(loaded_config, dict)
            self.assertEqual(loaded_config["geometry"], "600x300+100+100")
            self.assertEqual(loaded_config["extensions"][".py"], True)
            self.assertEqual(loaded_config["extensions"][".css"], False)

        finally:
            source_code_bundler.CONFIG_FILE = original_config_file
            if temp_config and os.path.exists(temp_config):
                os.remove(temp_config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
