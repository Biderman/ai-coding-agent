"""Skrypt Run Python: sześć wywołań i wydruk, bez rzeczywistego procesu."""

from unittest.mock import Mock, call

import test_run_python_file as demo


def test_demo_calls_six_examples_and_prints_stub_results(monkeypatch, capsys):
    # Zastępujemy całe narzędzie, więc test dotyczy wyłącznie sterowania demonstracją.
    # Nie potwierdza wykonania kalkulatora ani integracji subprocess.
    results = [f"wynik atrapy {number}" for number in range(1, 7)]
    run_stub = Mock(side_effect=results)
    monkeypatch.setattr(demo, "run_python_file", run_stub)

    demo.main()

    # Kolejność i osobny argument ze spacjami muszą odpowiadać sześciu przykładom lekcji.
    assert run_stub.call_args_list == [
        call("calculator", "main.py"),
        call("calculator", "main.py", ["3 + 5"]),
        call("calculator", "tests.py"),
        call("calculator", "../main.py"),
        call("calculator", "nonexistent.py"),
        call("calculator", "lorem.txt"),
    ]

    # Każda etykieta poprzedza wynik właściwej atrapy; drukowanie nie gubi żadnego przykładu.
    labels = [
        "Result for main.py (no arguments):",
        "Result for main.py (3 + 5):",
        "Result for tests.py:",
        "Result for ../main.py:",
        "Result for nonexistent.py:",
        "Result for lorem.txt:",
    ]
    expected_lines = []
    for label, result in zip(labels, results, strict=True):
        expected_lines.extend([label, result])
    output = capsys.readouterr()

    assert output.out == "\n".join(expected_lines) + "\n"
    assert output.err == ""
