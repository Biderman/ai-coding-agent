from io import StringIO
from pathlib import Path

import pytest

from config import MAX_CHARS
from functions.get_file_content import get_file_content


def test_long_lorem_file():
    # Oryginalna długa próbka pozostaje osobnym dowodem limitu znaków, niezależnie od danych kursowych.
    original = Path("calculator/long_lorem.txt").read_text(encoding="utf-8")
    assert len(original) >= 20_000

    result = get_file_content("calculator", "long_lorem.txt")
    marker = '[...File "long_lorem.txt" truncated at 10000 characters]'
    truncated = result == original[:10_000] + marker
    assert truncated
    assert len(result) == 10_000 + len(marker)

    print(f"long_lorem.txt length: {len(result)}")
    print(f"long_lorem.txt truncated: {truncated}")


def test_lorem_file():
    # To rzeczywisty stan danych po Write Files: dokładne bajty bez nowej linii i bez ucięcia.
    expected = "wait, this isn't lorem ipsum"
    assert Path("calculator/lorem.txt").read_bytes() == expected.encode("utf-8")
    result = get_file_content("calculator", "lorem.txt")
    assert result == expected
    print(f"lorem.txt content: {result}")


def test_morelorem_file():
    # Drugi plik kursowy również ma dokładną treść; odczyt nie podstawia gotowej odpowiedzi.
    expected = "lorem ipsum dolor sit amet"
    assert Path("calculator/pkg/morelorem.txt").read_bytes() == expected.encode("utf-8")
    result = get_file_content("calculator", "pkg/morelorem.txt")
    assert result == expected
    print(f"pkg/morelorem.txt content: {result}")


def test_main_file():
    result = get_file_content("calculator", "main.py")
    assert result == Path("calculator/main.py").read_text(encoding="utf-8")
    print("Result for main.py:")
    print(result)


def test_calculator_file():
    result = get_file_content("calculator", "pkg/calculator.py")
    assert result == Path("calculator/pkg/calculator.py").read_text(encoding="utf-8")
    print("Result for pkg/calculator.py:")
    print(result)


def test_outside_directory():
    result = get_file_content("calculator", "/bin/cat")
    assert result == 'Error: Cannot read "/bin/cat" as it is outside the permitted working directory'
    print("Result for /bin/cat:")
    print(result)


def test_missing_file():
    result = get_file_content("calculator", "pkg/does_not_exist.py")
    assert result == 'Error: File not found or is not a regular file: "pkg/does_not_exist.py"'
    print("Result for pkg/does_not_exist.py:")
    print(result)


@pytest.mark.parametrize("length", [0, 7, 10_000, 10_001])
def test_character_limit(tmp_path, length):
    content = "ą" * length
    (tmp_path / "content.txt").write_text(content, encoding="utf-8")

    result = get_file_content(str(tmp_path), "content.txt")
    if length <= 10_000:
        assert result == content
    else:
        assert result == content[:10_000] + '[...File "content.txt" truncated at 10000 characters]'


def test_directory_is_not_a_file():
    assert get_file_content("calculator", "pkg") == 'Error: File not found or is not a regular file: "pkg"'


def test_parent_and_sibling_paths_are_rejected(tmp_path, monkeypatch):
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    sibling = tmp_path / "calculator-other"
    sibling.mkdir()
    (sibling / "outside.txt").write_text("outside", encoding="utf-8")

    def forbidden_open(*args, **kwargs):
        pytest.fail("A forbidden path reached open().")

    monkeypatch.setattr("builtins.open", forbidden_open)
    for file_path in ("../outside.txt", "../calculator-other/outside.txt"):
        assert get_file_content(str(working_directory), file_path) == f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'


def test_symlink_outside_directory_is_rejected(tmp_path, monkeypatch):
    working_directory = tmp_path / "calculator"
    working_directory.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")
    (working_directory / "link.txt").symlink_to(outside_file)

    def forbidden_open(*args, **kwargs):
        pytest.fail("An outside symlink reached open().")

    monkeypatch.setattr("builtins.open", forbidden_open)
    assert get_file_content(str(working_directory), "link.txt") == 'Error: Cannot read "link.txt" as it is outside the permitted working directory'


def test_read_error_is_returned(tmp_path, monkeypatch):
    (tmp_path / "content.txt").write_text("content", encoding="utf-8")

    def fail_open(*args, **kwargs):
        raise PermissionError("read denied")

    monkeypatch.setattr("builtins.open", fail_open)
    assert get_file_content(str(tmp_path), "content.txt") == "Error: read denied"


def test_symlink_inside_directory_can_be_read(tmp_path):
    (tmp_path / "content.txt").write_text("inside", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(tmp_path / "content.txt")
    assert get_file_content(str(tmp_path), "link.txt") == "inside"


def test_large_file_uses_bounded_reads(tmp_path, monkeypatch):
    (tmp_path / "large.txt").touch()

    class BoundedReader(StringIO):
        def __init__(self):
            super().__init__("x" * (MAX_CHARS * 3))
            self.characters_read = 0

        def read(self, size=-1):
            assert 0 <= size <= MAX_CHARS, "Unbounded or oversized read"
            result = super().read(size)
            self.characters_read += len(result)
            assert self.characters_read <= MAX_CHARS + 1
            return result

    reader = BoundedReader()

    def fake_open(path, mode, *, encoding):
        assert mode == "r"
        assert encoding == "utf-8"
        return reader

    monkeypatch.setattr("builtins.open", fake_open)
    assert get_file_content(str(tmp_path), "large.txt") == (
        "x" * MAX_CHARS + '[...File "large.txt" truncated at 10000 characters]'
    )
    assert reader.characters_read == MAX_CHARS + 1
    assert reader.closed


def test_invalid_utf8_returns_error(tmp_path):
    (tmp_path / "invalid.txt").write_bytes(b"\xff")
    assert get_file_content(str(tmp_path), "invalid.txt").startswith("Error:")


if __name__ == "__main__":
    test_long_lorem_file()
    test_lorem_file()
    test_morelorem_file()
    test_main_file()
    test_calculator_file()
    test_outside_directory()
    test_missing_file()
