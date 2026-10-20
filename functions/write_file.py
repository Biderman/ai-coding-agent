import os


def write_file(working_directory: str, file_path: str, content: str) -> str:
    try:
        # Rozstrzygamy także symlinki w celu i istniejących katalogach nadrzędnych.
        # Kontrola dotyczy stanu teraz; nie usuwa wyścigu przed późniejszym open().
        working_dir_abs = os.path.realpath(working_directory)
        target_file = os.path.realpath(os.path.join(working_dir_abs, file_path))
        if os.path.commonpath([working_dir_abs, target_file]) != working_dir_abs:
            return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'

        # Katalogu nie wolno nadpisać plikiem, nawet gdy znajduje się w bazie.
        if os.path.isdir(target_file):
            return f'Error: Cannot write to "{file_path}" as it is a directory'

        # Skutki uboczne zaczynają się dopiero po walidacji obu warunków.
        # Tryb w zastępuje treść; newline="" zapobiega zmianie końców linii.
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8", newline="") as file:
            file.write(content)

        # Liczymy znaki wejściowego tekstu, a nie bajty zakodowanego UTF-8.
        return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
    except Exception as exc:
        # Błędy systemowe stają się tekstowym wynikiem narzędzia dla aplikacji.
        return f"Error: {exc}"


# Deklaracja opisuje dane dla modelu; nie wykonuje ani nie autoryzuje operacji.
schema_write_file = {
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
