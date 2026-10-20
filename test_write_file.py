from pathlib import Path

from functions.write_file import write_file


def _restore_file(path: Path, original: bytes | None) -> None:
    # None oznacza brak pliku przed testem; usuwamy tylko jego nową kopię.
    # Istniejącą treść odtwarzamy bajtowo, bez zmiany kodowania i końców linii.
    if original is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(original)


def main() -> None:
    lorem = Path("calculator/lorem.txt")
    morelorem = Path("calculator/pkg/morelorem.txt")

    # Nie podążamy za zastanym symlinkiem przy tworzeniu kopii danych testowych.
    checked_paths = (Path("calculator"), Path("calculator/pkg"), lorem, morelorem)
    if any(path.is_symlink() for path in checked_paths):
        raise ValueError("Demonstracja wymaga ścieżek bez symlinków w calculator.")

    # Kopie w pamięci chronią zastane bajty obu plików; długi long_lorem nie jest modyfikowany.
    originals = {
        path: path.read_bytes() if path.exists() else None
        for path in (lorem, morelorem)
    }
    try:
        # Nadpisanie musi dać właściwy komunikat oraz dokładnie żądaną treść.
        result = write_file("calculator", "lorem.txt", "wait, this isn't lorem ipsum")
        print(result)
        assert result == 'Successfully wrote to "lorem.txt" (28 characters written)'
        assert lorem.read_text(encoding="utf-8") == "wait, this isn't lorem ipsum"

        # Drugi przykład sprawdza zapis w podkatalogu, także gdy plik już istnieje.
        result = write_file("calculator", "pkg/morelorem.txt", "lorem ipsum dolor sit amet")
        print(result)
        assert result == 'Successfully wrote to "pkg/morelorem.txt" (26 characters written)'
        assert morelorem.read_text(encoding="utf-8") == "lorem ipsum dolor sit amet"

        # Zewnętrzna ścieżka ma zakończyć się odmową, bez tworzenia /tmp/temp.txt.
        result = write_file("calculator", "/tmp/temp.txt", "this should not be allowed")
        print(result)
        assert result == 'Error: Cannot write to "/tmp/temp.txt" as it is outside the permitted working directory'
    finally:
        # Sprzątamy również po błędnym wyniku/asercji. Zagnieżdżone finally próbuje
        # odtworzyć drugi plik nawet wtedy, gdy odtwarzanie pierwszego zgłosi błąd.
        try:
            _restore_file(lorem, originals[lorem])
        finally:
            _restore_file(morelorem, originals[morelorem])


if __name__ == "__main__":
    main()
