"""Edukacyjny agent z wywołaniami narzędzi przez OpenRouter."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, OpenAI

from call_function import ToolCallError, available_functions, call_function
from prompts import system_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Agent — klient OpenRouter")
    parser.add_argument("user_prompt", help="Treść wiadomości do modelu")
    parser.add_argument("--verbose", action="store_true", help="Pokaż prompt i tokeny")
    args = parser.parse_args()

    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("Brak OPENROUTER_API_KEY. Uzupełnij lokalny plik .env.", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"User prompt: {args.user_prompt}")

    # Jedna historia w pamięci procesu: system i użytkownik nie są powielani w iteracjach.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": args.user_prompt},
    ]
    try:
        with OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=60.0,
            max_retries=0,
        ) as client:
            # Limit liczy requesty LLM, niezależnie od liczby narzędzi w pojedynczej odpowiedzi.
            for iteration in range(20):
                response = client.chat.completions.create(
                    model="minimax/minimax-m3.1-flash:free",
                    messages=messages,
                    tools=available_functions,
                )
                if args.verbose:
                    # Statystyki dotyczą bieżącej odpowiedzi, bez zmiany jednostek lub sumowania.
                    usage = response.usage
                    if usage is None:
                        print("Prompt tokens: unavailable")
                        print("Response tokens: unavailable")
                    else:
                        print(f"Prompt tokens: {usage.prompt_tokens}")
                        print(f"Response tokens: {usage.completion_tokens}")

                if not response.choices:
                    print("OpenRouter nie zwrócił żadnej odpowiedzi.", file=sys.stderr)
                    return 1

                message = response.choices[0].message
                # Jawnie wybieramy pola typu SDK zgodne z Chat Completions, także tekst przy tools.
                assistant_message = {"role": "assistant", "content": message.content}
                if message.tool_calls:
                    assistant_message["tool_calls"] = [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in message.tool_calls
                    ]
                messages.append(assistant_message)

                if message.tool_calls:
                    # Nie wykonujemy 20. propozycji, skoro jej wyniku nie można już odesłać do LLM.
                    if iteration == 19:
                        print("Error: Osiągnięto limit 20 wywołań LLM bez odpowiedzi końcowej.", file=sys.stderr)
                        return 1
                    for tool_call in message.tool_calls:
                        try:
                            result_message = call_function(tool_call, verbose=args.verbose)
                        except ToolCallError as exc:
                            # Błąd kończy całą pętlę, zanim niekompletny turn trafi do następnego requestu.
                            print(str(exc), file=sys.stderr)
                            return 1
                        if not result_message.get("content"):
                            raise ValueError("Error: Pusty wynik wywołania narzędzia.")
                        if not isinstance(result_message["content"], str):
                            raise ValueError("Error: Wynik wywołania narzędzia musi być tekstem.")
                        # Dispatcher paruje wynik z ID; kolejny request następuje po wszystkich wynikach.
                        messages.append(result_message)
                        if args.verbose:
                            print(f"-> {result_message['content']}")
                    continue

                # None i [] oznaczają finał. Zachowujemy dotychczasowy zwykły wydruk tekstu.
                content = message.content
                if not content or not content.strip():
                    print("OpenRouter nie zwrócił tekstu odpowiedzi.", file=sys.stderr)
                    return 1
                print(content)
                return 0
    except APIError as exc:
        # Ochrona obejmuje każdą iterację; nie ujawniamy treści wyjątku ani nagłówków.
        print(
            f"OpenRouter: {type(exc).__name__}. Sprawdź połączenie, klucz i limity.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
