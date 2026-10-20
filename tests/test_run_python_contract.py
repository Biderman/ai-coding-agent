"""Kontrakt Run Python sprawdzany wyłącznie z atrapą subprocess.run."""

import importlib
import subprocess
import sys
from unittest.mock import Mock

import pytest

run_python_module = importlib.import_module("functions.run_python_file")
run_python_file = run_python_module.run_python_file


@pytest.fixture(autouse=True)
def process_stub(monkeypatch):
    # Każdy test otrzymuje atrapę: żaden plik-fixture nie trafia do interpretera.
    stub = Mock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
    )
    monkeypatch.setattr(run_python_module.subprocess, "run", stub)
    return stub


@pytest.fixture
def python_fixture(tmp_path):
    # Zagnieżdżony plik pozwala odróżnić cwd bazy od katalogu samego skryptu.
    working_directory = tmp_path / "workspace"
    script = working_directory / "nested" / "script.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "# Fixture tekstowa; testy nigdy nie wykonują tego pliku.\n",
        encoding="utf-8",
    )
    return working_directory, script


@pytest.mark.parametrize("args", [None, [], ["3 + 5"], ["--label", "tekst ze spacjami"]])
def test_command_preserves_argument_boundaries_and_execution_options(
    python_fixture, process_stub, args
):
    # Atrapa rejestruje listę i opcje; spacje nie mogą rozbić jednego argumentu.
    working_directory, script = python_fixture

    result = run_python_file(str(working_directory), "nested/script.py", args)

    process_stub.assert_called_once_with(
        [sys.executable, str(script.resolve()), *(args or [])],
        cwd=str(working_directory.resolve()),
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    assert result == "No output produced"


def test_omitted_arguments_use_default_none(python_fixture, process_stub):
    # Pominięcie opcjonalnego argumentu musi pozostawić polecenie bez dodatków.
    working_directory, script = python_fixture

    run_python_file(str(working_directory), "nested/script.py")

    assert process_stub.call_args.args == ([sys.executable, str(script.resolve())],)
    process_stub.assert_called_once()


def test_relative_working_directory_is_resolved_before_process_call(
    python_fixture, process_stub, monkeypatch
):
    # Względna baza aplikacji zostaje rozstrzygnięta raz; cwd i cel są absolutne.
    working_directory, script = python_fixture
    monkeypatch.chdir(working_directory.parent)

    run_python_file("workspace", "nested/script.py")

    assert process_stub.call_args.args == ([sys.executable, str(script.resolve())],)
    assert process_stub.call_args.kwargs["cwd"] == str(working_directory.resolve())
    process_stub.assert_called_once()


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "expected"),
    [
        (0, "wynik\n", "", "STDOUT:\nwynik\n"),
        (0, "", "diagnostyka\n", "STDERR:\ndiagnostyka\n"),
        (
            0,
            "wynik\n",
            "diagnostyka\n",
            "STDOUT:\nwynik\n\nSTDERR:\ndiagnostyka\n",
        ),
        (0, "", "", "No output produced"),
        (0, " \n", "\t", "STDOUT:\n \n\nSTDERR:\n\t"),
        (7, "wynik", "", "Process exited with code 7\nSTDOUT:\nwynik"),
        (7, "", "błąd", "Process exited with code 7\nSTDERR:\nbłąd"),
        (
            7,
            "wynik",
            "błąd",
            "Process exited with code 7\nSTDOUT:\nwynik\nSTDERR:\nbłąd",
        ),
        (7, "", "", "Process exited with code 7\nNo output produced"),
        (-9, "", "", "Process exited with code -9\nNo output produced"),
    ],
)
def test_process_result_keeps_exit_code_and_both_streams(
    python_fixture, process_stub, returncode, stdout, stderr, expected
):
    # CompletedProcess jest symulowany: sprawdzamy format i treść, bez integracji procesu.
    working_directory, _ = python_fixture
    process_stub.return_value = subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )

    result = run_python_file(str(working_directory), "nested/script.py")

    assert result == expected
    process_stub.assert_called_once()


@pytest.mark.parametrize(
    "path_kind", ["parent", "absolute", "similar_prefix", "outside_missing", "outside_directory"]
)
def test_outside_paths_are_rejected_before_file_and_suffix_checks(
    python_fixture, process_stub, path_kind
):
    # Odmowa zakresu ma pierwszeństwo również dla katalogu i brakującego pliku .txt.
    working_directory, _ = python_fixture
    outside = working_directory.parent / "outside"
    outside.mkdir()
    outside_file = outside / "script.py"
    outside_file.write_text("# Zewnętrzna fixture, bez wykonania.\n", encoding="utf-8")
    similar_directory = working_directory.parent / "workspace-other"
    similar_directory.mkdir()
    (similar_directory / "script.py").write_text("# Fixture.\n", encoding="utf-8")
    paths = {
        "parent": "../outside/script.py",
        "absolute": str(outside_file),
        "similar_prefix": "../workspace-other/script.py",
        "outside_missing": "../outside/missing.txt",
        "outside_directory": "../outside",
    }
    file_path = paths[path_kind]

    result = run_python_file(str(working_directory), file_path)

    assert result == (
        f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
    )
    process_stub.assert_not_called()


@pytest.mark.parametrize("file_path", ["missing.py", "missing.txt", "folder.py", "folder.txt"])
def test_missing_targets_and_directories_are_rejected_before_suffix_check(
    python_fixture, process_stub, file_path
):
    # Katalog z końcówką .py nadal nie jest plikiem; brak .txt nie przechodzi do rozszerzenia.
    working_directory, _ = python_fixture
    (working_directory / "folder.py").mkdir()
    (working_directory / "folder.txt").mkdir()

    result = run_python_file(str(working_directory), file_path)

    assert result == f'Error: "{file_path}" does not exist or is not a regular file'
    process_stub.assert_not_called()


@pytest.mark.parametrize("file_path", ["lorem.txt", "script.PY", "script.py.txt"])
def test_existing_non_python_file_is_rejected(python_fixture, process_stub, file_path):
    # Dokładne rozszerzenie .py sprawdzamy dopiero dla istniejącego zwykłego pliku.
    working_directory, _ = python_fixture
    (working_directory / file_path).write_text("dane tekstowe", encoding="utf-8")

    result = run_python_file(str(working_directory), file_path)

    assert result == f'Error: "{file_path}" is not a Python file'
    process_stub.assert_not_called()


def test_absolute_path_inside_base_is_permitted(python_fixture, process_stub):
    # Absolutna ścieżka jest dozwolona, jeśli jej rzeczywisty cel pozostaje w bazie.
    working_directory, script = python_fixture

    run_python_file(str(working_directory), str(script))

    assert process_stub.call_args.args == ([sys.executable, str(script.resolve())],)
    process_stub.assert_called_once()


@pytest.mark.parametrize("link_kind", ["file", "parent"])
def test_symlinks_leading_outside_base_are_rejected(
    python_fixture, process_stub, link_kind
):
    # Rozwiązujemy dowiązanie samego pliku i rodzica; sama nazwa w bazie nie wystarcza.
    working_directory, _ = python_fixture
    outside = working_directory.parent / "outside"
    outside.mkdir()
    outside_file = outside / "script.py"
    outside_file.write_text("# Zewnętrzna fixture, bez wykonania.\n", encoding="utf-8")
    if link_kind == "file":
        (working_directory / "linked.py").symlink_to(outside_file)
        file_path = "linked.py"
    else:
        (working_directory / "linked").symlink_to(outside, target_is_directory=True)
        file_path = "linked/script.py"

    result = run_python_file(str(working_directory), file_path)

    assert result == (
        f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
    )
    process_stub.assert_not_called()


def test_symlink_inside_base_uses_resolved_target(python_fixture, process_stub):
    # Dowiązanie wewnętrzne może wskazywać dozwolony plik; atrapa dostaje cel rzeczywisty.
    working_directory, script = python_fixture
    (working_directory / "linked.py").symlink_to(script)

    run_python_file(str(working_directory), "linked.py")

    assert process_stub.call_args.args == ([sys.executable, str(script.resolve())],)
    process_stub.assert_called_once()


def test_working_directory_may_be_a_symlink(python_fixture, process_stub):
    # Baza i plik są porównywane w tej samej przestrzeni rzeczywistych ścieżek.
    working_directory, script = python_fixture
    linked_base = working_directory.parent / "linked-workspace"
    linked_base.symlink_to(working_directory, target_is_directory=True)

    run_python_file(str(linked_base), "nested/script.py")

    assert process_stub.call_args.args == ([sys.executable, str(script.resolve())],)
    assert process_stub.call_args.kwargs["cwd"] == str(working_directory.resolve())
    process_stub.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        subprocess.TimeoutExpired(cmd=["python", "fixture.py"], timeout=30),
        OSError("process unavailable"),
    ],
)
def test_timeout_and_process_start_errors_return_required_prefix(
    python_fixture, process_stub, error
):
    # Atrapa odtwarza awarię startu lub limit czasu bez czekania i bez nowego procesu.
    working_directory, _ = python_fixture
    process_stub.side_effect = error

    result = run_python_file(str(working_directory), "nested/script.py")

    assert result == f"Error: executing Python file: {error}"
    process_stub.assert_called_once()
