import os
import subprocess
import sys


def run_python_file(
    working_directory: str, file_path: str, args: list[str] | None = None
) -> str:
    try:
        # Porównujemy rzeczywiste lokalizacje, także przy symlinkach rodziców.
        # To kontrola ścieżki w tej chwili, a nie izolacja uprawnień procesu.
        working_dir_abs = os.path.realpath(working_directory)
        target_file = os.path.realpath(os.path.join(working_dir_abs, file_path))
        if os.path.commonpath([working_dir_abs, target_file]) != working_dir_abs:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'

        # Kolejność jest częścią kontraktu: najpierw zwykły plik, potem rozszerzenie.
        if not os.path.isfile(target_file):
            return f'Error: "{file_path}" does not exist or is not a regular file'
        if not file_path.endswith(".py"):
            return f'Error: "{file_path}" is not a Python file'

        # Każdy argument zostaje osobnym elementem; nie interpretujemy składni powłoki.
        # sys.executable zachowuje interpreter i środowisko uruchamiającej aplikacji.
        command = [sys.executable, target_file]
        if args is not None:
            command.extend(args)
        result = subprocess.run(
            command,
            cwd=working_dir_abs,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )

        # Niezerowy kod nie usuwa strug: zachowujemy także stderr przy kodzie 0.
        parts = []
        if result.returncode != 0:
            parts.append(f"Process exited with code {result.returncode}")
        if not result.stdout and not result.stderr:
            parts.append("No output produced")
        else:
            if result.stdout:
                parts.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                parts.append(f"STDERR:\n{result.stderr}")
        return "\n".join(parts)
    except Exception as exc:
        # Timeout i błędy uruchomienia są błędami narzędzia, odrębnymi od returncode.
        return f"Error: executing Python file: {exc}"


# Deklaracja opisuje dane dla modelu; nie wykonuje ani nie autoryzuje operacji.
schema_run_python_file = {
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
}
