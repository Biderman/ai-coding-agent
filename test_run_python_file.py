from functions.run_python_file import run_python_file


def main() -> None:
    # Ten skrypt sam nie tworzy izolacji. Uruchamiaj go wyłącznie dla odczytanych,
    # znanych plików kalkulatora w środowisku o odpowiednio ograniczonym dostępie.
    print("Result for main.py (no arguments):")
    print(run_python_file("calculator", "main.py"))

    # Wyrażenie ze spacjami ma zostać jednym argumentem programu, nie poleceniem shell.
    print("Result for main.py (3 + 5):")
    print(run_python_file("calculator", "main.py", ["3 + 5"]))

    # unittest może pisać na stderr mimo poprawnego kodu zakończenia 0.
    print("Result for tests.py:")
    print(run_python_file("calculator", "tests.py"))

    # Trzy odmowy muszą wystąpić przed utworzeniem jakiegokolwiek procesu.
    print("Result for ../main.py:")
    print(run_python_file("calculator", "../main.py"))
    print("Result for nonexistent.py:")
    print(run_python_file("calculator", "nonexistent.py"))
    print("Result for lorem.txt:")
    print(run_python_file("calculator", "lorem.txt"))


if __name__ == "__main__":
    main()
