import os
import sys
import shutil
import filecmp
import pathlib

from waves import _settings


def available_files(root_directory: pathlib.Path | str,
                    relative_paths: list[str]) -> tuple[list[pathlib.Path], list[str]]:
    """Build a list of files at ``relative_paths`` with respect to the root ``root_directory`` directory

    Returns a list of absolute paths and a list of any relative paths that were not found. Falls back to a full
    recursive search of ``relative_paths`` with ``pathlib.Path.rglob`` to enable pathlib style pattern matching.

    :param root_directory: Relative or absolute root path to search. Relative paths are converted to absolute paths with
        respect to the current working directory before searching.
    :param relative_paths: Relative paths to search for. Directories are searched recursively for files.

    :returns: available_files, not_found
    """
    root_directory = pathlib.Path(root_directory).resolve()
    if isinstance(relative_paths, str):
        relative_paths = [relative_paths]

    available_files = []
    not_found = []
    for relative_path in relative_paths:
        file_list = []
        absolute_path = root_directory / relative_path
        if absolute_path.is_file():
            file_list.append(absolute_path)
        elif absolute_path.is_dir():
            file_list = [path for path in absolute_path.rglob("*") if path.is_file()]
        else:
            file_list = [path for path in root_directory.rglob(relative_path) if path.is_file()]
        if file_list:
            available_files.extend(file_list)
        else:
            not_found.append(relative_path)
    available_files.sort()
    not_found.sort()
    return available_files, not_found


def build_source_files(
    root_directory: str,
    relative_paths: list[str],
    exclude_patterns: list[str] = _settings._fetch_exclude_patterns
) -> tuple[list[pathlib.Path], list[str]]:
    """Wrap :meth:`available_files` and trim list based on exclude patterns

    If no source files are found, an empty list is returned.

    :param str root_directory: Relative or absolute root path to search. Relative paths are converted to absolute paths with
        respect to the current working directory before searching.
    :param list relative_paths: Relative paths to search for. Directories are searched recursively for files.
    :param list exclude_patterns: list of strings to exclude from the root_directory directory tree if the path contains a
        matching string.

    :returns: source_files, not_found
    :rtype: tuple of lists
    """
    # TODO: Save the list of excluded files and return
    source_files, not_found = available_files(root_directory, relative_paths)
    source_files = [path for path in source_files if not any(map(str(path).__contains__, exclude_patterns))]
    return source_files, not_found


def longest_common_path_prefix(file_list: str | pathlib.Path | list[str | pathlib.Path]) -> pathlib.Path:
    """Return the longest common file path prefix.

    The edge case of a single path is handled by returning the parent directory

    :param file_list: List of path-like objects

    :returns: longest common path prefix
    """
    if isinstance(file_list, str) or isinstance(file_list, pathlib.Path):
        file_list = [file_list]
    file_list = [pathlib.Path(path) for path in file_list]
    number_of_files = len(file_list)
    if number_of_files < 1:
        raise RuntimeError("No files in 'file_list'")
    elif number_of_files == 1:
        longest_common_path = file_list[0].parent
    else:
        longest_common_path = pathlib.Path(os.path.commonpath(file_list))
    return longest_common_path


def build_destination_files(destination: str | pathlib.Path,
                            requested_paths: list[str | pathlib.Path]) -> tuple[list, list]:
    """Build destination file paths from the requested paths, truncating the longest possible source prefix path

    :param destination: String or pathlike object for the destination directory
    :param requested_paths: List of requested file paths

    :returns: destination files, existing files
    """
    destination = pathlib.Path(destination).resolve()
    longest_common_requested_path = longest_common_path_prefix(requested_paths)
    destination_files = [destination / path.relative_to(longest_common_requested_path) for path in requested_paths]
    existing_files = [path for path in destination_files if path.exists()]
    return destination_files, existing_files


def build_copy_tuples(destination: str | pathlib.Path, requested_paths_resolved: list,
                      overwrite: bool = False) -> tuple[tuple]:
    """
    :param destination: String or pathlike object for the destination directory
    :param requested_paths_resolved: List of absolute requested file paths

    :returns: requested and destination file path pairs
    """
    destination_files, existing_files = build_destination_files(destination, requested_paths_resolved)
    copy_tuples = tuple(zip(requested_paths_resolved, destination_files))
    if not overwrite and existing_files:
        copy_tuples = tuple((requested_path, destination_file) for requested_path, destination_file in copy_tuples if
                            destination_file not in existing_files)
    return copy_tuples


def conditional_copy(copy_tuples: tuple[tuple]) -> None:
    """Copy when destination file doesn't exist or doesn't match source file content

    Uses Python ``shutil.copyfile``, so meta data isn't preserved. Creates intermediate parent directories prior to
    copy, but doesn't raise exceptions on existing parent directories.

    :param copy_tuples: Tuple of source, destination pathlib.Path pairs, e.g. ``((source, destination), ...)``
    """
    for source_file, destination_file in copy_tuples:
        # If the root_directory and destination file contents are the same, don't perform unnecessary file I/O
        if not destination_file.exists() or not filecmp.cmp(source_file, destination_file, shallow=False):
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, destination_file)


def print_list(things_to_print: list, prefix: str = "\t", stream=sys.stdout) -> None:
    """Print a list to the specified stream, one line per item

    :param list things_to_print: List of items to print
    :param str prefix: prefix to print on each line before printing the item
    :param file-like stream: output stream. Defaults to ``sys.stdout``.
    """
    for item in things_to_print:
        print(f"{prefix}{item}", file=stream)


def recursive_copy(root_directory: str | pathlib.Path, relative_paths: list[str | pathlib.Path],
                   destination: str | pathlib.Path, requested_paths: list[str | pathlib.Path] | None = None,
                   tutorial: int = None, overwrite: bool = False, dry_run: bool = False, print_available: bool = False) -> int:
    """Recursively copy requested paths from root_directory/relative_paths directories into destination directory using
    the shortest possible shared source prefix.

    If files exist, report conflicting files and exit with a non-zero return code unless overwrite is specified.

    :param root_directory: String or pathlike object for the root_directory directory
    :param relative_paths: List of string or pathlike objects describing relative paths to search for in
        root_directory
    :param destination: String or pathlike object for the destination directory
    :param requested_paths: list of relative path-like objects that subset the files found in the
        ``root_directory`` ``relative_paths``
    :param tutorial: Integer to fetch all necessary files for the specified tutorial number
    :param overwrite: Boolean to overwrite any existing files in destination directory
    :param dry_run: Print the destination tree and exit. Short circuited by ``print_available``
    :param print_available: Print the available source files and exit. Short circuits ``dry_run``
    """
    if tutorial is not None:
        try:
            requested_paths = []
            for x in range(0, tutorial + 1):
                requested_paths.extend(_settings._tutorial_paths[x])
        except KeyError:
            print(f"The tutorial number requested ('{tutorial}') does not exist.", file=sys.stderr)
            return 1
    if not requested_paths:
        requested_paths = []
    # Build source tree
    source_files, missing_relative_paths = build_source_files(root_directory, relative_paths)
    longest_common_source_path = longest_common_path_prefix(source_files)
    if print_available:
        print("Available source files:")
        print_list([path.relative_to(longest_common_source_path) for path in source_files])

    # Down select to requested file list
    if requested_paths:
        requested_paths_resolved, missing_requested_paths = build_source_files(longest_common_source_path, requested_paths)
    else:
        requested_paths_resolved = source_files
        missing_requested_paths = []
    if not requested_paths_resolved:
        print(f"Did not find any requested files in '{longest_common_source_path}'", file=sys.stderr)
        return 1

    # Build source/destination pairs
    destination = pathlib.Path(destination).resolve()
    copy_tuples = build_copy_tuples(destination, requested_paths_resolved, overwrite=overwrite)
    if len(copy_tuples) != len(requested_paths_resolved):
        print(f"Found conflicting files in destination '{destination}'. Use '--overwrite' to replace existing files.",
              file=sys.stderr)

    # User I/O
    if dry_run:
        print("Files to create:")
        print_list([destination for _, destination in copy_tuples])
    if print_available or dry_run:
        return 0

    # Do the work if there are any files left to copy
    conditional_copy(copy_tuples)

    return 0
