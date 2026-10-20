"""Regression checks for the previous List Files contract, using temporary data."""

import pytest

from functions.get_files_info import get_files_info


def test_nested_directory_metadata_and_no_recursion(tmp_path):
    directory = tmp_path / "pkg"
    directory.mkdir()
    (directory / "sample.txt").write_text("abc", encoding="utf-8")
    nested = directory / "nested"
    nested.mkdir()
    (nested / "hidden.txt").write_text("hidden", encoding="utf-8")

    result = get_files_info(str(tmp_path), "pkg")
    assert set(result.splitlines()) == {
        "- sample.txt: file_size=3 bytes, is_dir=False",
        f"- nested: file_size={nested.stat().st_size} bytes, is_dir=True",
    }


@pytest.mark.parametrize("directory", ["../outside", "../calculator-other", "/bin"])
def test_outside_directory_rejected_before_listing(tmp_path, monkeypatch, directory):
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()

    def forbidden_listdir(*args, **kwargs):
        pytest.fail("A forbidden path reached listdir().")

    monkeypatch.setattr("os.listdir", forbidden_listdir)
    assert get_files_info(str(working_directory), directory) == (
        f'Error: Cannot list "{directory}" as it is outside the permitted working directory'
    )


@pytest.mark.parametrize("directory", ["missing", "file.txt"])
def test_non_directory_rejected(tmp_path, directory):
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    assert get_files_info(str(tmp_path), directory) == f'Error: "{directory}" is not a directory'


def test_empty_directory(tmp_path):
    assert get_files_info(str(tmp_path)) == ""


def test_listing_error_returns_error(tmp_path, monkeypatch):
    def fail_listdir(*args, **kwargs):
        raise PermissionError("listing denied")

    monkeypatch.setattr("os.listdir", fail_listdir)
    assert get_files_info(str(tmp_path)) == "Error: listing denied"
