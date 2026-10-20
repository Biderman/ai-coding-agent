
import os


def get_files_info(
    working_directory: str,
    directory: str = "."
) -> str:
    try:
        # Rozwiązujemy symlinki przed listowaniem; kontrola nie usuwa wyścigów TOCTOU.
        working_dir_abs = os.path.realpath(working_directory)

        target_dir = os.path.realpath(
            os.path.join(working_dir_abs, directory)
        )

        valid_target_dir = os.path.commonpath(
            [working_dir_abs, target_dir]
        ) == working_dir_abs

        if not valid_target_dir:
            return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'

        if not os.path.isdir(target_dir):
            return f'Error: "{directory}" is not a directory'

        results = []
        files = os.listdir(target_dir)

        for file in files:
            # Pomijamy zewnętrzne cele przed getsize/isdir, zachowując nazwy legalnych wpisów.
            path = os.path.realpath(os.path.join(target_dir, file))
            if os.path.commonpath([working_dir_abs, path]) != working_dir_abs:
                continue
            size = os.path.getsize(path)
            is_dir = os.path.isdir(path)

            results.append(
                f"- {file}: file_size={size} bytes, is_dir={is_dir}"
            )

        final_result = "\n".join(results)
        return final_result

    except Exception as e:
        return f"Error: {e}"


# To opis dla LLM, nie autoryzacja. Zaufana baza pozostaje poza argumentami modelu.
schema_get_files_info = {
    "type": "function",
    "function": {
        "name": "get_files_info",
        "description": "Lists files in a specified directory relative to the working directory, providing file size and directory status",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to list files from, relative to the working directory (default is the working directory itself)",
                },
            },
        },
    },
}
