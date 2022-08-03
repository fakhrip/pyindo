from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import punctuation


TOKENS = {
    "fungsi": 0,
    "utama": 1,
    "tampilkan": 2,
    "(": 3,
    ")": 4,
    "{": 5,
    "}": 6,
    "\"": 7,
    ";": 8,
    " ": 9
}


list_of_punctuation = [p for p in f"{punctuation} "]
RESERVED_KEYWORD = [keyword for keyword in TOKENS.keys() if keyword not in list_of_punctuation]


def error(statement, line_number=None) -> None:
    """
    Show error statement if there are any, including
    the line number in which the error happened
    """

    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}")
    exit(EX_SOFTWARE)


def parse(program_buffer: str) -> list:
    is_entrypoint_exist = False

    token_list = []
    declared_functions = []

    parsed_buffer = ""
    line_number = 1

    for pos, char in enumerate(program_buffer):
        parsed_buffer += char

        if char == "\"":
            if TOKENS["\""] in token_list:
                if len([token for token in token_list if token == TOKENS["\""]]) % 2 != 0:
                    # Closing double quote
                    token_list.append(parsed_buffer[:-1])
                    token_list.append(TOKENS["\""])

                parsed_buffer = ""
                continue

        if parsed_buffer in TOKENS.keys():
            token_list.append(TOKENS[parsed_buffer])
            parsed_buffer = ""

        if char == "\n":
            line_number += 1
            parsed_buffer = ""

        if token_list[-1] == TOKENS["fungsi"]:
            if (next_char := program_buffer[pos + 1]) != " ":
                error(
                    f"Expecting ' ' but got '{next_char}'", line_number
                )

        if token_list[-1] == TOKENS["("]:
            if token_list[-3] == TOKENS["fungsi"]:
                # Function definition
                if token_list[-2] == TOKENS["utama"]:
                    is_entrypoint_exist = True
                else:
                    declared_functions.append(token_list[-2])
            else:
                # Function call
                if token_list[-2] in declared_functions:
                    # TODO: Create function call bytecode
                    print("TODO")
                else:
                    error(
                        f"'{token_list[-2]}' function is not declared yet", line_number
                    )

    if not is_entrypoint_exist:
        error(
            "Entrypoint is not exist, you should create it first using `utama()` function"
        )
