"""Testy kontraktu Write Files na izolowanych danych tymczasowych."""

import pytest

from functions.write_file import write_file


@pytest.mark.parametrize("content", ["bez końca linii", "Zażółć gęślą jaźń 🌍"])
def test_new_file_preserves_exact_content_and_character_count(tmp_path, content):
    # Wynik liczy znaki, a odczyt bajtów wykrywa zmianę kodowania lub dodaną nową linię.
    result = write_file(str(tmp_path), "new.txt", content)

    assert result == f'Successfully wrote to "new.txt" ({len(content)} characters written)'
    assert (tmp_path / "new.txt").read_bytes() == content.encode("utf-8")


def test_overwrite_replaces_previous_content_completely(tmp_path):
    # Krótsza nowa treść musi usunąć także końcówkę wcześniejszego pliku.
    target = tmp_path / "existing.txt"
    target.write_bytes(b"previous content that must disappear\n")

    result = write_file(str(tmp_path), "existing.txt", "nowa")

    assert result == 'Successfully wrote to "existing.txt" (4 characters written)'
    assert target.read_bytes() == b"nowa"


def test_empty_content_truncates_existing_file(tmp_path):
    # Pusty tekst jest poprawnym zapisem i również zastępuje poprzednią treść.
    target = tmp_path / "empty.txt"
    target.write_text("wcześniejszy tekst", encoding="utf-8")

    result = write_file(str(tmp_path), "empty.txt", "")

    assert result == 'Successfully wrote to "empty.txt" (0 characters written)'
    assert target.read_bytes() == b""


def test_creates_nested_parent_directories(tmp_path):
    # Dozwolona ścieżka może wymagać utworzenia więcej niż jednego katalogu.
    result = write_file(str(tmp_path), "pkg/nested/result.txt", "treść")

    assert result == 'Successfully wrote to "pkg/nested/result.txt" (5 characters written)'
    assert (tmp_path / "pkg/nested/result.txt").read_text(encoding="utf-8") == "treść"


def test_directory_target_is_rejected_without_write_operations(tmp_path, monkeypatch):
    # Odmowa dla katalogu musi nastąpić przed próbą tworzenia katalogów lub otwarcia pliku.
    directory = tmp_path / "existing"
    directory.mkdir()
    sentinel = directory / "keep.txt"
    sentinel.write_bytes(b"unchanged")

    def forbidden_operation(*args, **kwargs):
        pytest.fail("Odmowa dla katalogu powinna poprzedzać operacje zapisu.")

    monkeypatch.setattr("os.makedirs", forbidden_operation)
    monkeypatch.setattr("builtins.open", forbidden_operation)

    result = write_file(str(tmp_path), "existing", "nadpisanie")

    assert result == 'Error: Cannot write to "existing" as it is a directory'
    assert sentinel.read_bytes() == b"unchanged"
    assert set(directory.iterdir()) == {sentinel}


@pytest.mark.parametrize("path_kind", ["parent", "similar_prefix", "absolute"])
def test_outside_path_is_rejected_before_any_write(tmp_path, monkeypatch, path_kind):
    # Każdy wariant wychodzi poza bazę; podobny prefiks nazwy nie oznacza jej podkatalogu.
    working_directory = tmp_path / "workspace"
    working_directory.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_bytes(b"unchanged")
    paths = {
        "parent": "../outside/new/deep/result.txt",
        "similar_prefix": "../workspace-other/new/result.txt",
        "absolute": str(outside / "absolute/new/result.txt"),
    }
    file_path = paths[path_kind]

    def forbidden_operation(*args, **kwargs):
        pytest.fail("Niedozwolona ścieżka dotarła do operacji zapisu.")

    monkeypatch.setattr("os.makedirs", forbidden_operation)
    monkeypatch.setattr("builtins.open", forbidden_operation)

    result = write_file(str(working_directory), file_path, "blocked")

    assert result == (
        f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
    )
    assert list(working_directory.iterdir()) == []
    assert sentinel.read_bytes() == b"unchanged"
    assert set(outside.iterdir()) == {sentinel}
    assert not (tmp_path / "workspace-other").exists()


def test_symlink_to_outside_file_is_rejected_without_overwrite(tmp_path, monkeypatch):
    # Nazwa w bazie nie wystarcza: dowiązanie wskazuje rzeczywisty plik poza nią.
    working_directory = tmp_path / "workspace"
    working_directory.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_bytes(b"original")
    link = working_directory / "linked.txt"
    link.symlink_to(outside_file)

    def forbidden_operation(*args, **kwargs):
        pytest.fail("Dowiązanie poza bazę dotarło do operacji zapisu.")

    monkeypatch.setattr("os.makedirs", forbidden_operation)
    monkeypatch.setattr("builtins.open", forbidden_operation)

    result = write_file(str(working_directory), "linked.txt", "blocked")

    assert result == (
        'Error: Cannot write to "linked.txt" as it is outside the permitted working directory'
    )
    assert outside_file.read_bytes() == b"original"
    assert link.is_symlink()


def test_symlink_parent_outside_base_does_not_create_directories(tmp_path, monkeypatch):
    # Cel jeszcze nie istnieje, ale istniejący rodzic jest dowiązaniem poza bazę.
    working_directory = tmp_path / "workspace"
    working_directory.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_bytes(b"unchanged")
    link = working_directory / "linked"
    link.symlink_to(outside, target_is_directory=True)
    file_path = "linked/new/deep/result.txt"

    def forbidden_operation(*args, **kwargs):
        pytest.fail("Dowiązany rodzic poza bazę dotarł do operacji zapisu.")

    monkeypatch.setattr("os.makedirs", forbidden_operation)
    monkeypatch.setattr("builtins.open", forbidden_operation)

    result = write_file(str(working_directory), file_path, "blocked")

    assert result == (
        f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
    )
    assert set(outside.iterdir()) == {sentinel}
    assert sentinel.read_bytes() == b"unchanged"
    assert link.is_symlink()


def test_symlink_parent_inside_base_allows_write(tmp_path):
    # Kontrola rzeczywistej lokalizacji dopuszcza dowiązanie, które pozostaje w bazie.
    actual_directory = tmp_path / "actual"
    actual_directory.mkdir()
    (tmp_path / "linked").symlink_to(actual_directory, target_is_directory=True)

    result = write_file(str(tmp_path), "linked/new.txt", "OK")

    assert result == 'Successfully wrote to "linked/new.txt" (2 characters written)'
    assert (actual_directory / "new.txt").read_bytes() == b"OK"


def test_working_directory_may_itself_be_a_symlink(tmp_path):
    # Baza i cel muszą być porównywane w tym samym, rzeczywistym układzie ścieżek.
    actual_directory = tmp_path / "actual"
    actual_directory.mkdir()
    working_directory = tmp_path / "workspace"
    working_directory.symlink_to(actual_directory, target_is_directory=True)

    result = write_file(str(working_directory), "new.txt", "OK")

    assert result == 'Successfully wrote to "new.txt" (2 characters written)'
    assert (actual_directory / "new.txt").read_bytes() == b"OK"


def test_open_error_is_returned_as_error_text(tmp_path, monkeypatch):
    # Atrapa odtwarza odmowę uprawnień niezależnie od praw użytkownika uruchamiającego test.
    def fail_open(*args, **kwargs):
        raise PermissionError("write denied")

    monkeypatch.setattr("builtins.open", fail_open)

    result = write_file(str(tmp_path), "new.txt", "blocked")

    assert result.startswith("Error:")
    assert "write denied" in result
    assert not (tmp_path / "new.txt").exists()


def test_parent_creation_error_is_returned_as_error_text(tmp_path, monkeypatch):
    # Atrapa błędu katalogu sprawdza granicę obsługi wyjątków przed otwarciem pliku.
    def fail_makedirs(*args, **kwargs):
        raise PermissionError("directory creation denied")

    monkeypatch.setattr("os.makedirs", fail_makedirs)

    result = write_file(str(tmp_path), "new/nested/result.txt", "blocked")

    assert result.startswith("Error:")
    assert "directory creation denied" in result
    assert not (tmp_path / "new").exists()


def test_regular_file_cannot_be_used_as_parent_directory(tmp_path):
    # Rzeczywisty błąd systemu plików uzupełnia symulowane odmowy operacji.
    parent_file = tmp_path / "parent.txt"
    parent_file.write_bytes(b"keep")

    result = write_file(str(tmp_path), "parent.txt/new.txt", "blocked")

    assert result.startswith("Error:")
    assert parent_file.read_bytes() == b"keep"


def test_write_error_is_returned_as_error_text(tmp_path, monkeypatch):
    # Symulujemy błąd samego zapisu bez zapełniania dysku; nie sprawdzamy rollbacku treści.
    class FailingFile:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def write(self, content):
            raise OSError("disk full")

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: FailingFile())

    result = write_file(str(tmp_path), "new.txt", "content")

    assert result.startswith("Error:")
    assert "disk full" in result
