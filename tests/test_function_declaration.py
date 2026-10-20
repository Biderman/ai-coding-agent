"""Kontrakty czterech deklaracji; rejestracja nie wykonuje narzędzi."""

import inspect
import json

import pytest

from call_function import available_functions
from functions.get_files_info import get_files_info, schema_get_files_info
from functions.get_file_content import schema_get_file_content
from functions.run_python_file import run_python_file, schema_run_python_file
from functions.write_file import schema_write_file


# Porównujemy pełny format Chat Completions, łącznie z opisami i kontraktem argumentów.
EXPECTED_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_files_info",
            "description": "Lists files in a specified directory relative to the working directory, providing file size and directory status",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path to list files from, relative to the working directory (default is the working directory itself)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_content",
            "description": "Reads a text file relative to the working directory, returning up to 10000 characters with a truncation notice when needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the file to read, relative to the working directory"
                    }
                },
                "required": [
                    "file_path"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_file",
            "description": "Executes a Python file relative to the working directory with optional arguments and returns its output",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the Python file to execute, relative to the working directory"
                    },
                    "args": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Optional separate command-line arguments, not a shell command; omitting args or passing an empty list adds no arguments"
                    }
                },
                "required": [
                    "file_path"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Creates or overwrites a file relative to the working directory with the provided text content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the file to create or overwrite, relative to the working directory"
                    },
                    "content": {
                        "type": "string",
                        "description": "Text to write to the file; an empty string is allowed"
                    }
                },
                "required": [
                    "file_path",
                    "content"
                ]
            }
        }
    }
]


def test_exactly_four_complete_unique_schemas_are_registered():
    # Kolejność i tożsamość wykrywają pominięcie, podmianę lub zdublowanie deklaracji.
    declarations = [
        schema_get_files_info,
        schema_get_file_content,
        schema_run_python_file,
        schema_write_file,
    ]
    assert available_functions == EXPECTED_SCHEMAS
    assert all(actual is declared for actual, declared in zip(available_functions, declarations))
    names = [schema["function"]["name"] for schema in available_functions]
    assert names == ["get_files_info", "get_file_content", "run_python_file", "write_file"]
    assert len(set(names)) == 4
    assert json.loads(json.dumps(available_functions)) == EXPECTED_SCHEMAS


@pytest.mark.parametrize(
    "schema, properties, required",
    [
        (schema_get_files_info, {"directory"}, []),
        (schema_get_file_content, {"file_path"}, ["file_path"]),
        (schema_run_python_file, {"file_path", "args"}, ["file_path"]),
        (schema_write_file, {"file_path", "content"}, ["file_path", "content"]),
    ],
)
def test_parameter_contract_and_trusted_base_not_exposed(schema, properties, required):
    # To kontrola deklaracji, nie walidator propozycji w aplikacji.
    parameters = schema["function"]["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == properties
    assert parameters.get("required", []) == required
    assert "working_directory" not in json.dumps(schema)


def test_directory_and_args_are_optional_and_empty_content_is_allowed():
    # Brak args i [] znaczą brak dodatkowych argumentów; content musi istnieć, lecz może być "".
    assert inspect.signature(get_files_info).parameters["directory"].default == "."
    assert inspect.signature(run_python_file).parameters["args"].default is None
    parameters = schema_run_python_file["function"]["parameters"]
    assert "args" not in parameters["required"]
    assert parameters["properties"]["args"]["type"] == "array"
    assert parameters["properties"]["args"]["items"] == {"type": "string"}
    write_parameters = schema_write_file["function"]["parameters"]
    assert "content" in write_parameters["required"]
    assert write_parameters["properties"]["content"]["type"] == "string"
    assert "minLength" not in write_parameters["properties"]["content"]
