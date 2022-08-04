from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import punctuation
from compiler import call_function, define_function_content, define_function_header


TOKENS = {
    # Reserved Keywords
    "fungsi": 100,
    "tampilkan": 101,
    # Special Punctuations
    "(": 500,
    ")": 501,
    "{": 502,
    "}": 503,
    '"': 504,
    ";": 505,
    " ": 506,
    # EOF (End Of File)
    "\0": 999,
}


# Generate reserved keyword from tokens dict
list_of_punctuation = [p for p in f"{punctuation} "]
RESERVED_KEYWORD = [
    keyword for keyword in TOKENS.keys() if keyword not in list_of_punctuation
].extend(["utama"])


def token_to_string(token: int) -> str:
    """
    Convert back the token number to
    its corresponding token string
    """

    return list(TOKENS.keys())[list(TOKENS.values()).index(token)]


def error(statement, line_number=None) -> None:
    """
    Show error statement if there are any, including
    the line number in which the error happened
    """

    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}")
    exit(EX_SOFTWARE)


def search(program_buffer: str, pos: int, line_number: int, token_str: str) -> int:
    parsed_buffer = ""

    for cur_pos, char in enumerate(program_buffer[pos:]):
        parsed_buffer += char

        if parsed_buffer in TOKENS.keys():
            if (
                TOKENS[parsed_buffer] != TOKENS[" "] or TOKENS[token_str] == TOKENS[" "]
            ) and TOKENS[parsed_buffer] != TOKENS[token_str]:
                error(
                    f"Expecting '{token_str}' but got '{token_to_string(TOKENS[parsed_buffer])}'",
                    line_number,
                )
            elif TOKENS[parsed_buffer] == TOKENS[token_str]:
                return pos + cur_pos + 1

            parsed_buffer = ""

        if char == "\n":
            line_number += 1
            parsed_buffer = ""

    # Token string could not be found, should error
    return -1


def parse_parameters(token_list: list) -> list:
    parameters = []

    for pos, token in enumerate(token_list):
        if (
            token == TOKENS['"']
            and len([x for x in token_list[pos:] if x == TOKENS['"']]) % 2 != 0
        ):
            parameters.append(token_list[pos - 1])

    return parameters


def parse_program(program_buffer: str) -> list:
    is_entrypoint_exist = False

    token_list = []
    declared_functions = []
    parsed_params = []

    parsed_buffer = ""
    line_number = 1

    """
    {
        0: Global Scope
        1: Local Function Scope
        ...: More Local Scope (nested function)
    } 
    """
    scope_level = 0

    program_bytecodes = []
    function_bytecodes = []
    header_bytecodes = []
    content_bytecodes = []

    for pos, char in enumerate(program_buffer[:-2]):
        parsed_buffer += char

        match char:
            case "(":
                # Start to parse function name backward
                if token_list[-2] == TOKENS["fungsi"]:
                    # Function definition
                    if parsed_buffer[:-1] == "utama":
                        is_entrypoint_exist = True

                    if parsed_buffer[:-1] in declared_functions:
                        error(
                            f"'{parsed_buffer[:-1]}' function is already declared before",
                            line_number,
                        )

                    declared_functions.append(parsed_buffer[:-1])
                else:
                    # Function call
                    if parsed_buffer[:-1] in declared_functions:
                        error(
                            f"'{parsed_buffer[:-1]}' function is not declared anywhere",
                            line_number,
                        )

                token_list.append(parsed_buffer[:-1])
                token_list.append(TOKENS["("])
                parsed_buffer = ""

            case ")":
                # Start to parse function parameter backward
                opening_brace_pos = (
                    len(token_list) - 1 - token_list[::-1].index(TOKENS["("])
                )
                parsed_params = parse_parameters(token_list[opening_brace_pos:])

                if token_list[opening_brace_pos - 3] == TOKENS["fungsi"]:
                    # Function definition
                    if search(program_buffer, pos + 1, line_number, "{") == -1:
                        error("Expecting '{' but have reached the End Of File")
                else:
                    # Function call
                    function_name = (
                        token_to_string(
                            (cur_token := token_list[opening_brace_pos - 2])
                        )
                        if cur_token in TOKENS.keys()
                        else cur_token
                    )

                    if scope_level == 0:
                        program_bytecodes.extend(
                            call_function(
                                function_name,
                                parsed_params,
                                line_number,
                                True,
                            )
                        )
                    else:
                        content_bytecodes.extend(
                            call_function(
                                function_name,
                                parsed_params,
                                line_number,
                                False,
                            )
                        )

            case '"':
                # Start to parse string inside double quote backward
                if TOKENS['"'] in token_list:
                    if (
                        len([token for token in token_list if token == TOKENS['"']]) % 2
                        != 0
                    ):
                        # Closing double quote
                        token_list.append(parsed_buffer[:-1])
                        token_list.append(TOKENS['"'])

                    parsed_buffer = ""
                    continue

            case "{":
                if len(declared_functions) == 0:
                    error("Unexpected '{'", line_number)

                header_bytecodes.extend(
                    define_function_header(
                        declared_functions[-1],
                        parsed_params,
                        declared_functions[-1] == "utama",
                        line_number,
                    )
                )

                scope_level = 1
                parsed_params = []

            case "}":
                if len(declared_functions) == 0:
                    error("Unexpected '}'", line_number)

                function_bytecodes.extend(
                    define_function_content(
                        declared_functions[-1],
                        {
                            "header": header_bytecodes,
                            "content": content_bytecodes,
                        },
                        declared_functions[-1] == "utama",
                        line_number,
                    )
                )

                program_bytecodes.extend(function_bytecodes)

                scope_level = 0
                header_bytecodes = []
                content_bytecodes = []
                function_bytecodes = []

        if parsed_buffer in TOKENS.keys():
            token_list.append(TOKENS[parsed_buffer])
            parsed_buffer = ""

        if char == "\n":
            line_number += 1
            parsed_buffer = ""

        if len(token_list) > 0:
            if token_list[-1] == TOKENS["fungsi"]:
                if search(program_buffer, pos + 1, line_number, " ") == -1:
                    error("Expecting ' ' but have reached the End Of File")

    token_list.append(TOKENS["\0"])

    if not is_entrypoint_exist:
        error(
            "Entrypoint is not exist, you should create it first using `utama()` function"
        )

    return program_bytecodes
