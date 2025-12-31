# Source Code Bundler Tests

This directory contains unit tests for the Source Code Bundler application. The tests are implemented using Python's `unittest` framework in `test_source_code_bundler.py`.

## Test Suite Overview

### Core Functionality Tests
- **test_merge_and_split_cycle_basic**: Test basic merge-split cycle with multiple file types.
- **test_extension_filtering**: Test filtering by file extensions.
- **test_file_extension_case_insensitivity**: Test case-insensitive file extension matching.
- **test_merge_empty_directory**: Test merging an empty directory produces an empty file.

### Comment Syntax and Formatting Tests
- **test_css_marker_formatting**: Test CSS files have correctly formatted comment markers with closing tags.
- **test_css_comment_closing_correctness**: Test that CSS markers are proper CSS comments (opened and closed).
- **test_mixed_file_types_comment_syntax**: Test different file types get correct comment syntax.
- **test_regex_pattern_matching_for_css**: Test regex patterns correctly match CSS markers with comment delimiters.

### Path Handling and Security Tests
- **test_path_traversal_prevention**: Test sanitization of paths attempting directory traversal.
- **test_path_handling_for_root_directories**: Test path handling with nested and root-level files.
- **test_relative_path_calculation_edge_cases_safe**: Test edge cases in relative path calculation safely.

### Error Handling and Edge Cases Tests
- **test_binary_file_handling**: Test binary files result in error markers in bundle.
- **test_error_markers_defined_before_exception_robust**: Test error markers are defined before any exception can occur.
- **test_error_handling_in_split_function**: Test error handling when splitting corrupted bundle.
- **test_split_duplicate_filename_handling**: Test splitting handles duplicate filenames by renaming.

### File System Interaction Tests
- **test_symlink_handling**: Test symbolic links to files are followed and included.
- **test_symlinks_to_directories**: Test symlinks to directories are followed.
- **test_hidden_files_and_directories_exclusion**: Test hidden files and directories (starting with .) are excluded.

### Content Preservation Tests
- **test_empty_lines_and_whitespace_preservation**: Test empty lines and whitespace are preserved during merge/split.
- **test_empty_files_zero_bytes**: Test handling of empty files (0 bytes).
- **test_files_with_only_newlines**: Test files containing only newline characters.
- **test_mixed_line_endings**: Test files with mixed line endings (LF, CR, CRLF).

### Special Character and Unicode Tests
- **test_unicode_file_names_and_content**: Test Unicode file names and content are handled correctly.
- **test_files_with_special_characters_in_names**: Test files with special characters in names.

### Performance and Large Files Tests
- **test_large_files_handling**: Test handling of large files.
- **test_deeply_nested_directory_structure**: Test with deeply nested directory structure.
- **test_very_long_file_paths**: Test handling of very long file paths.

### Progress and Configuration Tests
- **test_progress_callback_frequency**: Test progress callback is called appropriately.
- **test_configuration_file_location_isolated**: Test configuration file handling with isolation.

## Running Tests

You can run the tests using the following command from the project root:

```bash
python3 tests/test_source_code_bundler.py
```

Or using the VS Code task "Run Tests".