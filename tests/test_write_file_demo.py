"""Przywracanie danych przez demonstrację Write Files, także po awarii."""

from pathlib import Path

import pytest

import test_write_file as demo


@pytest.fixture(params=[False, True], ids=["morelorem-absent", "morelorem-present"])
def original_files(tmp_path, monkeypatch, request):
    # Wszystkie dane i katalog roboczy są tymczasowe, więc projektowe fixture pozostają nietknięte.
    monkeypatch.chdir(tmp_path)
    lorem = tmp_path / "calculator/lorem.txt"
    morelorem = tmp_path / "calculator/pkg/morelorem.txt"
    lorem.parent.mkdir()

    # Nietekstowy bajt i CRLF wykrywają przypadkową zmianę danych podczas odtwarzania kopii.
    lorem_bytes = "oryginalne lorem\r\n".encode("utf-8") * 1500 + b"\xff"
    lorem.write_bytes(lorem_bytes)
    morelorem_bytes = None
    if request.param:
        morelorem.parent.mkdir()
        morelorem_bytes = "wcześniejsze morelorem\r\n".encode("utf-8") + b"\xfe"
        morelorem.write_bytes(morelorem_bytes)

    return {lorem: lorem_bytes, morelorem: morelorem_bytes}


def _assert_original_files(original_files):
    # Istniejący plik wraca bajtowo; plik utworzony przez demo musi ponownie nie istnieć.
    for path, original in original_files.items():
        if original is None:
            assert not path.exists()
        else:
            assert path.read_bytes() == original


def test_demo_prints_expected_results_and_restores_files_on_repeated_run(original_files, capsys):
    expected_lines = [
        'Successfully wrote to "lorem.txt" (28 characters written)',
        'Successfully wrote to "pkg/morelorem.txt" (26 characters written)',
        'Error: Cannot write to "/tmp/temp.txt" as it is outside the permitted working directory',
    ]

    # Drugi przebieg sprawdza powtarzalność zarówno dla zastanego, jak i nowego morelorem.
    for _ in range(2):
        demo.main()

        output = capsys.readouterr()
        assert output.out.splitlines() == expected_lines
        assert output.err == ""
        _assert_original_files(original_files)


@pytest.mark.parametrize("failed_write_number", [1, 2], ids=["after-lorem", "after-morelorem"])
def test_demo_restores_files_after_exception_following_real_write(
    original_files, monkeypatch, failed_write_number
):
    real_write_file = demo.write_file
    write_count = 0

    # Atrapa naprawdę zapisuje treść i dopiero potem symuluje awarię pierwszego lub drugiego zapisu.
    # To sprawdza działanie finally po zmianie danych, a nie wyłącznie wyjątek przed operacją.
    def write_then_raise(working_directory, file_path, content):
        nonlocal write_count
        result = real_write_file(working_directory, file_path, content)
        write_count += 1
        if write_count == failed_write_number:
            assert (Path(working_directory) / file_path).read_bytes() == content.encode("utf-8")
            raise RuntimeError("awaria po rzeczywistym zapisie")
        return result

    monkeypatch.setattr(demo, "write_file", write_then_raise)

    with pytest.raises(RuntimeError, match="awaria po rzeczywistym zapisie"):
        demo.main()

    assert write_count == failed_write_number
    _assert_original_files(original_files)


def test_demo_restores_files_when_success_message_is_incorrect(original_files, monkeypatch):
    real_write_file = demo.write_file

    # Błędny komunikat po drugim rzeczywistym zapisie wywołuje asercję demonstracji.
    # Oba pliki są już wtedy zmienione i także ta ścieżka musi odtworzyć kopie.
    def write_then_return_bad_result(working_directory, file_path, content):
        result = real_write_file(working_directory, file_path, content)
        if file_path == "pkg/morelorem.txt":
            assert (Path(working_directory) / file_path).read_bytes() == content.encode("utf-8")
            return "niepoprawny komunikat sukcesu"
        return result

    monkeypatch.setattr(demo, "write_file", write_then_return_bad_result)

    with pytest.raises(AssertionError):
        demo.main()

    _assert_original_files(original_files)


def test_demo_preserves_course_file_state_and_original_long_sample(tmp_path, monkeypatch):
    # Pracujemy na tymczasowej kopii stanu kursowego, zachowując istniejące testy awarii i CRLF.
    long_sample = (Path(__file__).resolve().parents[1] / "calculator/long_lorem.txt").read_bytes()
    calculator = tmp_path / "calculator"
    (calculator / "pkg").mkdir(parents=True)
    originals = {
        calculator / "lorem.txt": b"wait, this isn't lorem ipsum",
        calculator / "pkg/morelorem.txt": b"lorem ipsum dolor sit amet",
        calculator / "long_lorem.txt": long_sample,
    }
    for path, content in originals.items():
        path.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    # Kolejne uruchomienie nie przywraca starego długiego lorem ani nie usuwa morelorem.
    for _ in range(2):
        demo.main()
        for path, original in originals.items():
            assert path.read_bytes() == original
