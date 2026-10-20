"""Kontrakty dispatchera 007: atrapy narzędzi i jawnie zaufane dane tymczasowe."""

import json
from functools import wraps
from types import SimpleNamespace

import pytest

import call_function as dispatcher
from functions.get_file_content import get_file_content
from functions.get_files_info import get_files_info
from functions.run_python_file import run_python_file
from functions.write_file import write_file


# Tożsamość funkcji sprawdzamy osobno; atrapy nigdy nie uruchamiają ich ciał.
REAL_FUNCTIONS = {
    "get_files_info": get_files_info,
    "get_file_content": get_file_content,
    "run_python_file": run_python_file,
    "write_file": write_file,
}
JSON_ERROR = "Error: Nieprawidłowy JSON argumentów wywołania narzędzia."
OBJECT_ERROR = "Error: Argumenty wywołania narzędzia muszą być obiektem JSON."
ARGUMENT_ERROR = "Error: Nieprawidłowe argumenty wywołania narzędzia."


def make_tool_call(name, arguments, call_id="call-offline"):
    # Minimalny obiekt SDK zachowuje identyfikator oraz surowe pole arguments.
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.fixture
def execution_spies(monkeypatch):
    # wraps udostępnia prawdziwe sygnatury dla bind(), lecz wykonanie pozostaje atrapą.
    calls = []

    def make_stub(name, function):
        @wraps(function)
        def stub(**kwargs):
            calls.append((name, kwargs))
            return f"wynik:{name}"

        return stub

    for name, function in REAL_FUNCTIONS.items():
        monkeypatch.setitem(dispatcher.function_map, name, make_stub(name, function))
    return calls


def test_only_four_real_executable_functions_are_registered():
    # Rejestr wykonawczy nie może zawierać schematów, aliasów ani dodatkowych operacji.
    assert set(dispatcher.function_map) == set(REAL_FUNCTIONS)
    assert all(callable(function) for function in dispatcher.function_map.values())
    assert all(
        dispatcher.function_map[name] is function
        for name, function in REAL_FUNCTIONS.items()
    )
    assert {schema["function"]["name"] for schema in dispatcher.available_functions} == set(
        REAL_FUNCTIONS
    )


@pytest.mark.parametrize(
    "name, arguments",
    [
        ("get_files_info", {"directory": "pkg"}),
        ("get_file_content", {"file_path": "notes.txt"}),
        ("run_python_file", {"file_path": "trusted.py", "args": ["--label", "a b"]}),
        ("run_python_file", {"file_path": "trusted.py", "args": []}),
        ("run_python_file", {"file_path": "trusted.py"}),
        ("write_file", {"file_path": "notes.txt", "content": "Zażółć\n"}),
        ("write_file", {"file_path": "empty.txt", "content": ""}),
    ],
)
def test_dispatch_unpacks_keywords_and_returns_matching_tool_message(
    execution_spies, capsys, name, arguments
):
    # Każda ścieżka używa **kwargs i przenosi wynik z ID bez dodatkowego przetwarzania.
    result = dispatcher.call_function(make_tool_call(name, json.dumps(arguments), "call-17"))

    assert execution_spies == [(name, {**arguments, "working_directory": "./calculator"})]
    assert result == {
        "role": "tool",
        "tool_call_id": "call-17",
        "content": f"wynik:{name}",
    }
    assert capsys.readouterr().out == f" - Calling function: {name}\n"


@pytest.mark.parametrize("arguments", [None, "", "{}"])
def test_empty_arguments_select_default_listing(execution_spies, arguments):
    # Jedynie None i pusty tekst dostają domyślny obiekt; opcjonalny directory pozostaje pominięty.
    dispatcher.call_function(make_tool_call("get_files_info", arguments))

    assert execution_spies == [("get_files_info", {"working_directory": "./calculator"})]


@pytest.mark.parametrize("verbose", [False, True])
def test_logs_model_arguments_without_injecting_trusted_base(
    execution_spies, capsys, verbose
):
    # Baza aplikacji nie jest argumentem modelu, a wynik wypisuje dopiero main.py.
    arguments = {"file_path": "notes.txt", "content": "wynik prywatny"}

    dispatcher.call_function(make_tool_call("write_file", json.dumps(arguments)), verbose=verbose)

    expected = " - Calling function: write_file"
    if verbose:
        expected += f"({arguments})"
    assert capsys.readouterr().out == expected + "\n"
    assert execution_spies[0][1]["working_directory"] == "./calculator"


@pytest.mark.parametrize("supplied_base", ["../outside", "/tmp/outside", "", None, [], {}])
def test_model_working_directory_is_replaced_before_execution(
    execution_spies, capsys, supplied_base
):
    # Log verbose pokazuje propozycję, lecz wykonawca zawsze otrzymuje bazę z aplikacji.
    arguments = {"directory": ".", "working_directory": supplied_base}

    dispatcher.call_function(make_tool_call("get_files_info", json.dumps(arguments)), verbose=True)

    assert execution_spies == [
        ("get_files_info", {"directory": ".", "working_directory": "./calculator"})
    ]
    assert capsys.readouterr().out == f" - Calling function: get_files_info({arguments})\n"


def test_order_and_independent_call_ids_are_preserved(execution_spies):
    # Sekwencja dwóch wywołań odpowiada kolejności i identyfikatorom propozycji modelu.
    calls = [
        make_tool_call("write_file", '{"file_path": "a.txt", "content": "a"}', "call-a"),
        make_tool_call("get_file_content", '{"file_path": "a.txt"}', "call-b"),
    ]

    messages = [dispatcher.call_function(call) for call in calls]

    assert [name for name, _ in execution_spies] == ["write_file", "get_file_content"]
    assert messages == [
        {"role": "tool", "tool_call_id": "call-a", "content": "wynik:write_file"},
        {"role": "tool", "tool_call_id": "call-b", "content": "wynik:get_file_content"},
    ]


@pytest.mark.parametrize("verbose", [False, True])
def test_unknown_function_returns_error_message_without_execution(
    execution_spies, capsys, verbose
):
    # Nieznana nazwa jest wynikiem narzędzia i nie daje dostępu do arbitralnych funkcji.
    result = dispatcher.call_function(make_tool_call("delete_everything", "{}", "call-x"), verbose)

    assert result == {
        "role": "tool",
        "tool_call_id": "call-x",
        "content": "Error: Unknown function: delete_everything",
    }
    assert execution_spies == []
    suffix = "({})" if verbose else ""
    assert capsys.readouterr().out == f" - Calling function: delete_everything{suffix}\n"


@pytest.mark.parametrize(
    "raw_arguments, expected_error",
    [
        ('{"file_path": "PRIVATE_ARG",', JSON_ERROR),
        ("PRIVATE_ARG", JSON_ERROR),
        ('["PRIVATE_ARG"]', OBJECT_ERROR),
        ('"PRIVATE_ARG"', OBJECT_ERROR),
        ("null", OBJECT_ERROR),
        ("0", OBJECT_ERROR),
        ("false", OBJECT_ERROR),
        (0, JSON_ERROR),
        (False, JSON_ERROR),
        ([], JSON_ERROR),
        ({}, JSON_ERROR),
        (True, JSON_ERROR),
        (b'{}', JSON_ERROR),
    ],
)
@pytest.mark.parametrize("verbose", [False, True])
def test_invalid_json_or_raw_argument_type_never_executes_or_logs(
    execution_spies, capsys, raw_arguments, expected_error, verbose
):
    # Surowe dane nie mogą trafić do logu ani zmienić błędnego wejścia w domyślne listowanie.
    with pytest.raises(dispatcher.ToolCallError) as error:
        dispatcher.call_function(make_tool_call("get_files_info", raw_arguments), verbose)

    assert isinstance(error.value, ValueError)
    assert str(error.value) == expected_error
    assert "PRIVATE_ARG" not in str(error.value)
    assert execution_spies == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    "name, arguments",
    [
        ("get_file_content", {}),
        ("run_python_file", {}),
        ("write_file", {"file_path": "PRIVATE_ARG"}),
        ("write_file", {"content": "PRIVATE_ARG"}),
        ("get_files_info", {"unexpected": "PRIVATE_ARG"}),
        ("get_file_content", {"file_path": "PRIVATE_ARG", "unexpected": "PRIVATE_ARG"}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "unexpected": "PRIVATE_ARG"}),
        ("write_file", {"file_path": "PRIVATE_ARG", "content": "PRIVATE_ARG", "unexpected": "PRIVATE_ARG"}),
        ("get_files_info", {"directory": None}),
        ("get_files_info", {"directory": 7}),
        ("get_files_info", {"directory": []}),
        ("get_file_content", {"file_path": False}),
        ("run_python_file", {"file_path": {"PRIVATE_ARG": "value"}}),
        ("write_file", {"file_path": "PRIVATE_ARG", "content": None}),
        ("write_file", {"file_path": 7, "content": "PRIVATE_ARG"}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "args": None}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "args": "PRIVATE_ARG"}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "args": ["ok", 7]}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "args": [False]}),
        ("run_python_file", {"file_path": "PRIVATE_ARG", "args": {"PRIVATE_ARG": "value"}}),
    ],
)
def test_incompatible_arguments_are_rejected_before_log_and_execution(
    execution_spies, capsys, name, arguments
):
    # Sygnatura i proste typy chronią granicę wywołania bez wypisywania wartości argumentów.
    with pytest.raises(dispatcher.ToolCallError) as error:
        dispatcher.call_function(make_tool_call(name, json.dumps(arguments)), verbose=True)

    assert str(error.value) == ARGUMENT_ERROR
    assert "PRIVATE_ARG" not in str(error.value)
    assert execution_spies == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("name", [None, 0, False, [], {}])
def test_non_string_function_name_is_rejected_without_execution_or_log(
    execution_spies, capsys, name
):
    # Nieprawidłowa nazwa nie może powodować TypeError przy wyszukiwaniu w słowniku.
    with pytest.raises(dispatcher.ToolCallError) as error:
        dispatcher.call_function(make_tool_call(name, "{}"), verbose=True)

    assert str(error.value) == ARGUMENT_ERROR
    assert execution_spies == []
    assert capsys.readouterr().out == ""


def test_dispatcher_keeps_empty_result_for_main_to_validate(monkeypatch):
    # Pusty wynik odczytu jest legalny w narzędziu; wyjątek wymagany przez 007 zgłasza main.
    @wraps(get_file_content)
    def empty_file(**kwargs):
        return ""

    monkeypatch.setitem(dispatcher.function_map, "get_file_content", empty_file)

    result = dispatcher.call_function(
        make_tool_call("get_file_content", '{"file_path": "empty.txt"}', "call-empty")
    )

    assert result == {"role": "tool", "tool_call_id": "call-empty", "content": ""}


def test_real_four_tools_operate_only_in_temporary_calculator(tmp_path, monkeypatch):
    # To jawna integracja: zapis, odczyt i zaufany subprocess obejmują wyłącznie fixture.
    calculator = tmp_path / "calculator"
    calculator.mkdir()
    trusted_script = calculator / "trusted.py"
    trusted_script.write_text(
        "import json\nimport os\nimport sys\n"
        "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    # Składnia powłoki pozostaje literalnym argumentem i nie tworzy dodatkowego procesu.
    arguments = ["tekst ze spacjami", "; touch NIE_TWORZ", "$(echo NIE_WYKONUJ)"]
    write_result = dispatcher.call_function(
        make_tool_call(
            "write_file",
            json.dumps({"file_path": "nested/note.txt", "content": "Zażółć\n"}),
            "call-write",
        )
    )
    read_result = dispatcher.call_function(
        make_tool_call("get_file_content", '{"file_path": "nested/note.txt"}', "call-read")
    )
    list_result = dispatcher.call_function(
        make_tool_call("get_files_info", '{"directory": "nested"}', "call-list")
    )
    run_result = dispatcher.call_function(
        make_tool_call(
            "run_python_file",
            json.dumps({"file_path": "trusted.py", "args": arguments}),
            "call-run",
        )
    )

    assert write_result == {
        "role": "tool",
        "tool_call_id": "call-write",
        "content": 'Successfully wrote to "nested/note.txt" (7 characters written)',
    }
    assert read_result == {"role": "tool", "tool_call_id": "call-read", "content": "Zażółć\n"}
    assert list_result == {
        "role": "tool",
        "tool_call_id": "call-list",
        "content": f"- note.txt: file_size={len('Zażółć'.encode('utf-8')) + 1} bytes, is_dir=False",
    }
    assert run_result["role"] == "tool"
    assert run_result["tool_call_id"] == "call-run"
    assert run_result["content"].startswith("STDOUT:\n")
    payload = json.loads(run_result["content"].removeprefix("STDOUT:\n"))
    assert payload == {"args": arguments, "cwd": str(calculator.resolve())}
    assert (calculator / "nested" / "note.txt").read_text(encoding="utf-8") == "Zażółć\n"
    assert not (calculator / "NIE_TWORZ").exists()
    assert set(tmp_path.iterdir()) == {calculator}
