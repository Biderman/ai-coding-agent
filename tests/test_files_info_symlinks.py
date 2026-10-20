"""Regresje symlinków listowania na kontrolowanych danych tymczasowych."""

import os
from pathlib import Path

import pytest

from functions.get_files_info import get_files_info


def block_external_metadata(monkeypatch, *forbidden_paths):
    # Wartownicy blokują link i jego zewnętrzny cel, ale przepuszczają legalne ścieżki.
    forbidden = tuple(Path(path) for path in forbidden_paths)
    original_getsize = os.path.getsize
    original_isdir = os.path.isdir

    def check_path(path):
        candidate = Path(path)
        if any(candidate == root or root in candidate.parents for root in forbidden):
            pytest.fail("Listowanie próbowało odczytać zewnętrzne metadane.")

    def guarded_getsize(path):
        check_path(path)
        return original_getsize(path)

    def guarded_isdir(path):
        check_path(path)
        return original_isdir(path)

    monkeypatch.setattr(os.path, "getsize", guarded_getsize)
    monkeypatch.setattr(os.path, "isdir", guarded_isdir)


@pytest.mark.parametrize("directory", ["external", "external/nested"])
def test_external_directory_symlink_is_rejected_before_listing_or_metadata(
    tmp_path, monkeypatch, directory
):
    # Także symlink rodzica nie może przenieść żądanego katalogu poza bazę.
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()
    outside = tmp_path / "outside"
    (outside / "nested").mkdir(parents=True)
    link = working_directory / "external"
    link.symlink_to(outside, target_is_directory=True)
    block_external_metadata(monkeypatch, link, outside)

    def forbidden_listdir(*args, **kwargs):
        pytest.fail("Odrzucony katalog dotarł do listdir().")

    monkeypatch.setattr(os, "listdir", forbidden_listdir)
    assert get_files_info(str(working_directory), directory) == (
        f'Error: Cannot list "{directory}" as it is outside the permitted working directory'
    )


def test_external_file_and_directory_entries_are_skipped_without_metadata(
    tmp_path, monkeypatch
):
    # Zwykłe wpisy nadal mają pełny format, a zewnętrzne linki nie są statowane.
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()
    (working_directory / "sample.txt").write_text("abc", encoding="utf-8")
    nested = working_directory / "nested"
    nested.mkdir()
    nested_size = nested.stat().st_size
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("Kontrolowane dane poza bazą", encoding="utf-8")
    outside_directory = tmp_path / "outside-directory"
    outside_directory.mkdir()
    file_link = working_directory / "external-file"
    file_link.symlink_to(outside_file)
    directory_link = working_directory / "external-directory"
    directory_link.symlink_to(outside_directory, target_is_directory=True)
    block_external_metadata(
        monkeypatch, file_link, directory_link, outside_file, outside_directory
    )

    assert set(get_files_info(str(working_directory)).splitlines()) == {
        "- sample.txt: file_size=3 bytes, is_dir=False",
        f"- nested: file_size={nested_size} bytes, is_dir=True",
    }


def test_internal_file_and_directory_symlinks_keep_names_and_standard_format(tmp_path):
    # Legalne symlinki zachowują nazwy wpisów i metadane rzeczywistych celów w bazie.
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()
    target_file = working_directory / "sample.txt"
    target_file.write_text("abc", encoding="utf-8")
    target_directory = working_directory / "nested"
    target_directory.mkdir()
    (target_directory / "hidden.txt").write_text("abc", encoding="utf-8")
    directory_size = target_directory.stat().st_size
    (working_directory / "linked-file").symlink_to(target_file)
    (working_directory / "linked-directory").symlink_to(
        target_directory, target_is_directory=True
    )

    assert set(get_files_info(str(working_directory)).splitlines()) == {
        "- sample.txt: file_size=3 bytes, is_dir=False",
        f"- nested: file_size={directory_size} bytes, is_dir=True",
        "- linked-file: file_size=3 bytes, is_dir=False",
        f"- linked-directory: file_size={directory_size} bytes, is_dir=True",
    }


def test_internal_directory_symlink_can_be_requested_directly(tmp_path):
    # Rozwiązanie legalnego linku nie blokuje zwykłego listowania wskazanego katalogu.
    working_directory = tmp_path / "calculator"
    target_directory = working_directory / "pkg"
    target_directory.mkdir(parents=True)
    (target_directory / "sample.txt").write_text("abc", encoding="utf-8")
    (working_directory / "linked").symlink_to(target_directory, target_is_directory=True)

    assert get_files_info(str(working_directory), "linked") == (
        "- sample.txt: file_size=3 bytes, is_dir=False"
    )


def test_working_directory_itself_may_be_a_symlink(tmp_path):
    # Baza i cel muszą być porównywane po rozwiązaniu symlinków obu ścieżek.
    real_directory = tmp_path / "real-calculator"
    real_directory.mkdir()
    (real_directory / "sample.txt").write_text("abc", encoding="utf-8")
    working_directory = tmp_path / "calculator"
    working_directory.symlink_to(real_directory, target_is_directory=True)

    assert get_files_info(str(working_directory)) == (
        "- sample.txt: file_size=3 bytes, is_dir=False"
    )
