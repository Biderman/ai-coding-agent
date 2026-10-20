import json
from collections.abc import Callable
from inspect import signature

from functions.get_files_info import get_files_info, schema_get_files_info
from functions.get_file_content import get_file_content, schema_get_file_content
from functions.run_python_file import run_python_file, schema_run_python_file
from functions.write_file import write_file, schema_write_file

# Przekazujemy cztery deklaracje modelowi; sama rejestracja niczego nie uruchamia.
available_functions = [
    schema_get_files_info,
    schema_get_file_content,
    schema_run_python_file,
    schema_write_file,
]


# Jawna allowlista wiąże nazwy modelu z funkcjami; nie szukamy dowolnych obiektów w globals().
function_map: dict[str, Callable[..., str]] = {
    "get_files_info": get_files_info,
    "get_file_content": get_file_content,
    "run_python_file": run_python_file,
    "write_file": write_file,
}


class ToolCallError(ValueError):
    """Błąd wejścia z bezpiecznym komunikatem dla CLI, bez surowych argumentów."""


def call_function(tool_call, verbose: bool = False) -> dict:
    function_name = tool_call.function.name
    raw_arguments = tool_call.function.arguments
    # None i pusty tekst zachowują domyślne {}; inne typy, także falsy, są błędem.
    if raw_arguments is not None and not isinstance(raw_arguments, str):
        raise ToolCallError("Error: Nieprawidłowy JSON argumentów wywołania narzędzia.")
    try:
        function_args = json.loads(raw_arguments or "{}")
    except (ValueError, TypeError, RecursionError):
        raise ToolCallError("Error: Nieprawidłowy JSON argumentów wywołania narzędzia.") from None
    if not isinstance(function_args, dict):
        raise ToolCallError("Error: Argumenty wywołania narzędzia muszą być obiektem JSON.")
    if not isinstance(function_name, str):
        raise ToolCallError("Error: Nieprawidłowe argumenty wywołania narzędzia.")

    if function_name in function_map:
        # Bind sprawdza brakujące/nadmiarowe pola przed skutkami ubocznymi; nie sprawdza typów.
        # Ignorujemy bazę modelu, również gdy poda ją w nieprawidłowym typie.
        call_args = dict(function_args, working_directory="./calculator")
        try:
            signature(function_map[function_name]).bind(**call_args)
        except TypeError:
            raise ToolCallError("Error: Nieprawidłowe argumenty wywołania narzędzia.") from None
        if any(not isinstance(value, str) for key, value in call_args.items() if key != "args"):
            raise ToolCallError("Error: Nieprawidłowe argumenty wywołania narzędzia.")
        if "args" in call_args and (
            not isinstance(call_args["args"], list)
            or not all(isinstance(arg, str) for arg in call_args["args"])
        ):
            raise ToolCallError("Error: Nieprawidłowe argumenty wywołania narzędzia.")

    # Dopiero poprawne argumenty trafiają do logu; zwykły tryb nie pokazuje ich ani wyniku.
    if verbose:
        print(f" - Calling function: {function_name}({function_args})")
    else:
        print(f" - Calling function: {function_name}")
    if function_name not in function_map:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Error: Unknown function: {function_name}",
        }

    # Zaufana aplikacja narzuca bazę; realpath nie izoluje uprawnień uruchamianego Pythona.
    function_args["working_directory"] = "./calculator"
    result = function_map[function_name](**function_args)
    return {"role": "tool", "tool_call_id": tool_call.id, "content": result}
