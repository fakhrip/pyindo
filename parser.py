from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import punctuation, ascii_letters, digits
from types import CodeType
from enum import Enum
from typing import NoReturn, Tuple
from compiler import call_function, define_function_content, define_function_header


class Context(Enum):
    ROUND_BRACKET = "()"
    CURLY_BRACKET = "{}"
    ANGLE_BRACKET = "<>"
    SQUARE_BRACKET = "[]"
    DOUBLE_QUOTE = '""'
    SINGLE_QUOTE = "''"


class Bracket(Enum):
    OPENING_CURLY_BRACKET = "{"
    CLOSING_CURLY_BRACKET = "}"
    OPENING_ROUND_BRACKET = "("
    CLOSING_ROUND_BRACKET = ")"
    OPENING_ANGLE_BRACKET = "<"
    CLOSING_ANGLE_BRACKET = ">"
    OPENING_SQUARE_BRACKET = "["
    CLOSING_SQUARE_BRACKET = "]"


class Punctuation(Enum):
    DOUBLEQUOTE = '"'
    SINGLEQUOTE = "'"
    SEMICOLON = ";"
    SPACE = " "
    COMMA = ","
    DOLLAR = "$"
    EOF = "\0"


class Keyword(Enum):
    FUNCTION = "fungsi"
    PRINT = "tampilkan"


TOKENS = {
    Keyword.FUNCTION: 100,
    Keyword.PRINT: 101,
    Bracket.OPENING_ROUND_BRACKET: 500,
    Bracket.CLOSING_ROUND_BRACKET: 501,
    Bracket.OPENING_CURLY_BRACKET: 502,
    Bracket.CLOSING_CURLY_BRACKET: 503,
    Punctuation.DOUBLEQUOTE: 504,
    Punctuation.SEMICOLON: 505,
    Punctuation.SPACE: 506,
    Punctuation.COMMA: 507,
    Punctuation.DOLLAR: 508,
    Punctuation.SINGLEQUOTE: 509,
    Punctuation.EOF: 999,
}

TOKEN_KEYS = [
    *[e.value for e in Bracket],
    *[e.value for e in Punctuation],
    *[e.value for e in Keyword],
]

TOKEN_VALUES = [*[e for e in Bracket], *[e for e in Punctuation], *[e for e in Keyword]]

# Generate reserved keyword from tokens dict
list_of_punctuation = [p for p in f"{punctuation} "]
RESERVED_KEYWORD = [
    *[keyword for keyword in TOKEN_KEYS if keyword not in list_of_punctuation],
    "utama",
]


def token_to_string(token: int) -> str:
    """
    Convert back the token number to
    its corresponding token string
    """

    return list(TOKENS.keys())[list(TOKENS.values()).index(token)].value


def string_to_token(string: str) -> int or str:
    return (
        TOKENS[TOKEN_VALUES[TOKEN_KEYS.index(string)]]
        if string in TOKEN_KEYS
        else string
    )


def error(statement, line_number=None) -> NoReturn:
    """
    Show error statement if there are any, including
    the line number in which the error happened
    """

    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}", end="")
    exit(EX_SOFTWARE)


def search(
    program_buffer: str,
    pos: int,
    line_number: int,
    token_class: Bracket or Punctuation or Keyword,
) -> Tuple[int, int] or NoReturn:
    parsed_buffer = ""

    for cur_pos, char in enumerate(program_buffer[pos:]):
        parsed_buffer += char

        if parsed_buffer in TOKEN_KEYS:
            token = string_to_token(parsed_buffer)
            if (
                token != TOKENS[Punctuation.SPACE]
                or TOKENS[token_class] == TOKENS[Punctuation.SPACE]
            ) and token != TOKENS[token_class]:
                error(
                    f"Expecting '{token_class.value}' but got '{token_to_string(token)}'",
                    line_number,
                )
            elif token == TOKENS[token_class]:
                return (pos + cur_pos + 1, line_number)

            parsed_buffer = ""

        if char == "\n":
            line_number += 1
            parsed_buffer = ""

    # Token string could not be found, should error
    error(f"Expecting '{token_class.value}' but have reached the End Of File")


def get_first_token_before(
    program_buffer: str, pos: int, other_than: list = [Punctuation.SPACE]
) -> int or str or None:
    parsed_buffer = ""
    token = -1

    for char in enumerate(program_buffer[:pos][::-1]):
        parsed_buffer += char

        if parsed_buffer in TOKEN_KEYS:
            token = string_to_token(parsed_buffer)

            for token_whitelist in other_than:
                if token != TOKENS[token_whitelist]:
                    return token

        if char == "\n":
            parsed_buffer = ""

        if char == " " and len(parsed_buffer) > 0:
            parsed_buffer = ""

    return None


def get_first_token_after(
    program_buffer: str, pos: int, other_than: list = [Punctuation.SPACE]
) -> int or str or None:
    parsed_buffer = ""
    token = -1

    for char in enumerate(program_buffer[pos:]):
        parsed_buffer += char

        if parsed_buffer in TOKEN_KEYS:
            token = string_to_token(parsed_buffer)

            for token_whitelist in other_than:
                if token != TOKENS[token_whitelist]:
                    return token

        if char == "\n":
            parsed_buffer = ""

        if char == " " and len(parsed_buffer) > 0:
            parsed_buffer = ""

    return None


def check_legal_identifier(
    identfier: str, line_number: int, is_function_identifier: bool
) -> NoReturn:
    global RESERVED_KEYWORD

    is_legal = identfier[0] not in digits

    for char in identfier:
        is_legal &= char in [*ascii_letters, *digits, "_"]

    if not is_function_identifier:
        is_legal &= identfier not in RESERVED_KEYWORD

    if not is_legal:
        error(f"Illegal identifier name: {identfier}", line_number)


def parse_parameters(token_list: list) -> list:
    parameters = []

    for pos, token in enumerate(token_list):
        if (
            token == TOKENS[Punctuation.DOUBLEQUOTE]
            and len(
                [x for x in token_list[pos:] if x == TOKENS[Punctuation.DOUBLEQUOTE]]
            )
            % 2
            != 0
        ):
            parameters.append(token_list[pos - 1])

        if (
            token == TOKENS[Punctuation.SINGLEQUOTE]
            and len(
                [x for x in token_list[pos:] if x == TOKENS[Punctuation.SINGLEQUOTE]]
            )
            % 2
            != 0
        ):
            parameters.append(token_list[pos - 1])

    return parameters


def parse_program(program_buffer: str) -> Tuple[list, list[CodeType]]:
    is_entrypoint_exist = False

    token_list = []
    declared_functions = []
    parsed_params = []

    parsed_buffer = ""
    line_number = 1

    context_stack = []

    program_bytecodes = []
    function_bytecodes = []
    header_bytecodes = []
    content_bytecodes = []

    program_codechunks = []

    for pos, char in enumerate(program_buffer[:-1]):
        parsed_buffer += char

        match char:
            case Bracket.OPENING_ROUND_BRACKET.value:
                # Start to parse function name backward
                function_name = parsed_buffer[:-1]
                if token_list[-2] == TOKENS[Keyword.FUNCTION]:
                    # Function definition
                    if function_name == "utama":
                        is_entrypoint_exist = True

                    if function_name in declared_functions:
                        error(
                            f"'{function_name}' function is already declared before",
                            line_number,
                        )

                    declared_functions.append(function_name)
                else:
                    # Function call
                    if function_name != "" and function_name not in declared_functions:
                        error(
                            f"'{parsed_buffer[:-1]}' function is not declared anywhere",
                            line_number,
                        )

                if function_name != "":
                    check_legal_identifier(function_name, line_number, True)
                    token_list.append(function_name)

                token_list.append(TOKENS[Bracket.OPENING_ROUND_BRACKET])
                context_stack.append(Context.ROUND_BRACKET)
                parsed_buffer = ""

            case Bracket.CLOSING_ROUND_BRACKET.value:
                if (
                    len(context_stack) == 0
                    or Context.ROUND_BRACKET not in context_stack
                ):
                    error("Unexpected ')'", line_number)

                # Start to parse function parameter backward
                opening_bracket_pos = (
                    len(token_list)
                    - 1
                    - token_list[::-1].index(TOKENS[Bracket.OPENING_ROUND_BRACKET])
                )
                parsed_params = parse_parameters(token_list[opening_bracket_pos:])

                if token_list[opening_bracket_pos - 3] == TOKENS[Keyword.FUNCTION]:
                    # Function definition
                    search(
                        program_buffer,
                        pos + 1,
                        line_number,
                        Bracket.OPENING_CURLY_BRACKET,
                    )
                else:
                    # Function call
                    cur_token = token_list[opening_bracket_pos - 1]
                    function_name = (
                        token_to_string(cur_token)
                        if cur_token in TOKENS.values()
                        else cur_token
                    )

                    if len(context_stack) == 0:
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

                    search(program_buffer, pos + 1, line_number, Punctuation.SEMICOLON)

                context_stack.pop()

            case Punctuation.DOUBLEQUOTE.value | Punctuation.SINGLEQUOTE.value:
                # Start to parse string inside double || single quote backward
                cur_quote = (
                    Punctuation.DOUBLEQUOTE
                    if char == Punctuation.DOUBLEQUOTE.value
                    else Punctuation.SINGLEQUOTE
                )
                if TOKENS[cur_quote] in token_list:
                    if (
                        len(
                            [
                                token
                                for token in token_list
                                if token == TOKENS[cur_quote]
                            ]
                        )
                        % 2
                        != 0
                    ):
                        # Closing double || single quote
                        token_list.append(parsed_buffer[:-1])
                        token_list.append(TOKENS[cur_quote])
                        context_stack.pop()

                        parsed_buffer = ""
                        continue

                # Opening double || single quote
                token_list.append(TOKENS[cur_quote])
                context_stack.append(
                    Context.DOUBLE_QUOTE
                    if cur_quote == Punctuation.DOUBLEQUOTE
                    else Context.SINGLE_QUOTE
                )

                parsed_buffer = ""

            case Bracket.OPENING_CURLY_BRACKET.value:
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

                context_stack.append(Context.CURLY_BRACKET)
                parsed_params = []

            case Bracket.CLOSING_CURLY_BRACKET.value:
                if len(declared_functions) == 0:
                    error("Unexpected '}'", line_number)

                if (
                    len(context_stack) == 0
                    or Context.CURLY_BRACKET not in context_stack
                ):
                    error("Unexpected '}'", line_number)

                bytecodes, codechunk = define_function_content(
                    declared_functions[-1],
                    {
                        "header": header_bytecodes,
                        "content": content_bytecodes,
                    },
                    declared_functions[-1] == "utama",
                    line_number,
                )

                if codechunk:
                    program_codechunks.append(codechunk)

                function_bytecodes.extend(bytecodes)
                program_bytecodes.extend(function_bytecodes)

                context_stack.pop()
                header_bytecodes = []
                content_bytecodes = []
                function_bytecodes = []

            case "\n":
                line_number += 1
                parsed_buffer = ""

        if (
            parsed_buffer in TOKEN_KEYS
            and Context.DOUBLE_QUOTE not in context_stack
            and Context.SINGLE_QUOTE not in context_stack
        ):
            token_list.append(string_to_token(parsed_buffer))
            parsed_buffer = ""

        if len(token_list) > 0:
            if token_list[-1] == TOKENS[Keyword.FUNCTION]:
                search(program_buffer, pos + 1, line_number, Punctuation.SPACE)

    token_list.append(TOKENS[Punctuation.EOF])

    if not is_entrypoint_exist:
        error(
            "Entrypoint is not exist, you should create it first using `utama()` function"
        )

    return (program_bytecodes, program_codechunks)
