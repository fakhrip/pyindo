from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import ascii_letters, digits
from types import CodeType
from enum import Enum
from typing import List, NoReturn, Tuple
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


class Operator(Enum):
    PLUS = "+"
    SELF_PLUS = "++"
    MINUS = "-"
    SELF_MINUS = "--"
    MULTIPLY = "*"
    POWER = "**"
    DIVIDE = "/"
    MODULO = "%"
    SAME = "=="
    AND = "&&"
    OR = "||"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    BIT_AND = "&"
    BIT_OR = "|"
    BIT_NOT = "!"
    BIT_SHIFT_LEFT = "<<"
    BIT_SHIFT_RIGHT = ">>"


class Punctuation(Enum):
    DOUBLEQUOTE = '"'
    SINGLEQUOTE = "'"
    SEMICOLON = ";"
    SPACE = " "
    COMMA = ","
    DOLLAR = "$"
    TRIPLEQUOTE = '"""'
    COLON = ":"
    EQUAL = "="
    SINGLELINE_COMMENT = "//"
    OPENING_MULTILINE_COMMENT = "/*"
    CLOSING_MULTILINE_COMMENT = "*/"
    EOF = "\0"


class Type(Enum):
    GENERIC = "apapun"
    STRING = "campuran"
    ARRAY = "himpunan"
    FLOAT = "pecahan"
    INT = "desimal"
    BOOLEAN = "boolean"
    CHARACTER = "karakter"
    DICTIONARY = "kamus"


class Keyword(Enum):
    FUNCTION = "fungsi"
    PRINT = "tampilkan"
    SAME = "adalah"
    NOT_SAME = "bukan"
    THEN = "maka"
    CONTINUE = "lewati"
    BREAK = "berhenti"
    IF = "jika"
    ELSE = "selainnya"
    SWITCH = "cocokkan"
    FOR = "untuk"
    WHILE = "selama"
    VARIABLE = "variabel"
    CONSTANT = "konstanta"
    NOT = "tidak"
    DELETE = "hapus"
    RETURN = "hasilkan"
    TRUE = "benar"
    FALSE = "salah"
    MAIN = "utama"


# TODO: Change this to automatic enum value when the development process
#       is done up to the time in which we can create compiler compilation pipeline
TOKENS = {
    Keyword.FUNCTION: 100,
    Keyword.PRINT: 101,
    Keyword.SAME: 102,
    Keyword.NOT_SAME: 103,
    Keyword.THEN: 104,
    Keyword.CONTINUE: 105,
    Keyword.BREAK: 106,
    Keyword.IF: 107,
    Keyword.ELSE: 108,
    Keyword.SWITCH: 109,
    Keyword.FOR: 110,
    Keyword.WHILE: 111,
    Keyword.VARIABLE: 112,
    Keyword.CONSTANT: 113,
    Keyword.NOT: 114,
    Keyword.DELETE: 115,
    Keyword.RETURN: 116,
    Keyword.TRUE: 117,
    Keyword.FALSE: 118,
    Keyword.MAIN: 119,
    Operator.PLUS: 300,
    Operator.SELF_PLUS: 301,
    Operator.MINUS: 302,
    Operator.SELF_MINUS: 303,
    Operator.MULTIPLY: 304,
    Operator.POWER: 305,
    Operator.DIVIDE: 306,
    Operator.MODULO: 307,
    Operator.SAME: 308,
    Operator.AND: 309,
    Operator.OR: 310,
    Operator.GREATER_THAN: 311,
    Operator.LESS_THAN: 312,
    Operator.BIT_AND: 313,
    Operator.BIT_OR: 314,
    Operator.BIT_NOT: 315,
    Operator.BIT_SHIFT_LEFT: 316,
    Operator.BIT_SHIFT_RIGHT: 317,
    Type.GENERIC: 400,
    Type.STRING: 401,
    Type.ARRAY: 402,
    Type.FLOAT: 403,
    Type.INT: 404,
    Type.BOOLEAN: 405,
    Type.CHARACTER: 406,
    Type.DICTIONARY: 407,
    Bracket.OPENING_ROUND_BRACKET: 500,
    Bracket.CLOSING_ROUND_BRACKET: 501,
    Bracket.OPENING_CURLY_BRACKET: 502,
    Bracket.CLOSING_CURLY_BRACKET: 503,
    Bracket.OPENING_ANGLE_BRACKET: 504,
    Bracket.CLOSING_ANGLE_BRACKET: 505,
    Bracket.OPENING_SQUARE_BRACKET: 506,
    Bracket.CLOSING_SQUARE_BRACKET: 507,
    Punctuation.DOUBLEQUOTE: 700,
    Punctuation.SEMICOLON: 701,
    Punctuation.SPACE: 702,
    Punctuation.COMMA: 703,
    Punctuation.DOLLAR: 704,
    Punctuation.SINGLEQUOTE: 705,
    Punctuation.TRIPLEQUOTE: 706,
    Punctuation.COLON: 707,
    Punctuation.EQUAL: 708,
    Punctuation.SINGLELINE_COMMENT: 709,
    Punctuation.OPENING_MULTILINE_COMMENT: 710,
    Punctuation.CLOSING_MULTILINE_COMMENT: 711,
    Punctuation.EOF: 999,
}

TOKEN_KEYS = [
    *[e.value for e in Bracket],
    *[e.value for e in Punctuation],
    *[e.value for e in Keyword],
    *[e.value for e in Operator],
    *[e.value for e in Type],
]

TOKEN_VALUES = [
    *[e for e in Bracket],
    *[e for e in Punctuation],
    *[e for e in Keyword],
    *[e for e in Operator],
    *[e for e in Type],
]

FUNCTION_KEYWORD_TOKENS = [
    TOKENS[e]
    for e in [
        Keyword.MAIN,
        Keyword.IF,
        Keyword.ELSE,
        Keyword.SWITCH,
        Keyword.FOR,
        Keyword.WHILE,
    ]
]


class FunctionBytecode:
    def __init__(self):
        self._params = []
        self._header = []
        self._content = []
        self._function_bytecodes = []
        self._function_codechunk = None

    def set_function_params(self, parameters: list) -> None:
        self._params = parameters

    def set_header_bytecodes(self, line_number: int, function_name: str = None) -> None:
        self._header = define_function_header(
            function_name,
            self._params,
            function_name == Keyword.MAIN.value,
            line_number,
        )

    def add_content_bytecodes(self, bytecodes: list) -> None:
        self._content.extend(bytecodes)

    def create_function_bytecodes(
        self, line_number: int, function_name: str = None
    ) -> None:
        bytecodes, function_codechunk = define_function_content(
            function_name,
            {
                "header": self._header,
                "content": self._content,
            },
            function_name == Keyword.MAIN.value,
            line_number,
        )

        self._function_bytecodes = bytecodes

        if function_name:
            self._function_codechunk = function_codechunk

    def get_function_bytecodes(self) -> Tuple[list, CodeType or None]:
        return (self._function_bytecodes, self._function_codechunk)


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


def get_first_token(
    token_list: List[int],
    is_forward: bool,
    from_pos: int = None,
    other_than: list = [Punctuation.SPACE],
) -> int or None:
    token = None

    from_pos = from_pos if from_pos else len(token_list)
    token_list = token_list[from_pos:] if is_forward else token_list[:from_pos][::-1]
    for token in token_list:
        is_in_whitelist = False
        for token_whitelist in other_than:
            is_in_whitelist |= token == TOKENS[token_whitelist]

        if not is_in_whitelist:
            return token

    return token


def check_legal_identifier(identfier: str, line_number: int) -> None or NoReturn:
    is_legal = identfier[0] not in digits

    for char in identfier:
        is_legal &= char in [*ascii_letters, *digits, "_"]

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
    parsed_params = []
    declared_functions = []

    context_stack: List[Context] = []
    bytecode_stack: List[FunctionBytecode] = []

    program_bytecodes = []
    program_codechunks = []

    parsed_buffer = ""
    line_number = 1

    for pos, char in enumerate(program_buffer[:-1]):
        parsed_buffer += char

        match char:
            case Bracket.OPENING_ROUND_BRACKET.value:
                # Start to parse function name backward
                function_name = parsed_buffer[:-1].strip()
                last_token = get_first_token(token_list, False)
                if last_token and (
                    last_token == TOKENS[Keyword.FUNCTION]
                    or last_token in FUNCTION_KEYWORD_TOKENS
                ):
                    # Function definition
                    if last_token in FUNCTION_KEYWORD_TOKENS:
                        function_name = token_to_string(last_token)
                        is_entrypoint_exist = True

                    if (
                        function_name == Keyword.MAIN.value
                        or last_token not in FUNCTION_KEYWORD_TOKENS
                    ):
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
                    check_legal_identifier(function_name, line_number)
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

                second_last_token = get_first_token(
                    token_list, False, opening_bracket_pos - 1
                )
                if (
                    second_last_token == TOKENS[Keyword.FUNCTION]
                    or second_last_token in FUNCTION_KEYWORD_TOKENS
                ):
                    # Function definition
                    search(
                        program_buffer,
                        pos + 1,
                        line_number,
                        Bracket.OPENING_CURLY_BRACKET,
                    )
                else:
                    # Function call
                    last_token = get_first_token(token_list, False, opening_bracket_pos)
                    function_name = (
                        token_to_string(last_token)
                        if last_token in TOKENS.values()
                        else last_token
                    )

                    if Context.CURLY_BRACKET not in context_stack:
                        program_bytecodes.extend(
                            call_function(
                                function_name,
                                parsed_params,
                                line_number,
                                True,
                            )
                        )
                    else:
                        bytecode_stack[-1].add_content_bytecodes(
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

                if (
                    Context.DOUBLE_QUOTE in context_stack
                    or Context.SINGLE_QUOTE in context_stack
                ):
                    if program_buffer[pos - 1] == Punctuation.DOLLAR.value:
                        print(
                            "TODO: Implement anonymous function definition for block of codes inside curly braces inside quotes"
                        )
                else:
                    function_bytecode = FunctionBytecode()
                    function_bytecode.set_function_params(parsed_params)
                    function_bytecode.set_header_bytecodes(
                        line_number, declared_functions[-1]
                    )
                    bytecode_stack.append(function_bytecode)

                context_stack.append(Context.CURLY_BRACKET)
                parsed_params = []

            case Bracket.CLOSING_CURLY_BRACKET.value:
                if (
                    len(declared_functions) == 0
                    or len(context_stack) == 0
                    or Context.CURLY_BRACKET not in context_stack
                ):
                    error("Unexpected '}'", line_number)

                if (
                    Context.DOUBLE_QUOTE in context_stack
                    or Context.SINGLE_QUOTE in context_stack
                ):
                    if context_stack[-1] == Context.CURLY_BRACKET:
                        print(
                            "TODO: Implement anonymous function inside curly braces inside quotes"
                        )
                else:
                    bytecode_stack[-1].create_function_bytecodes(
                        line_number, declared_functions[-1]
                    )

                    (
                        bytecodes,
                        function_codechunk,
                    ) = bytecode_stack.pop().get_function_bytecodes()

                    if function_codechunk:
                        program_codechunks.append(function_codechunk)

                    program_bytecodes.extend(bytecodes)

                context_stack.pop()

            case "\n":
                line_number += 1
                parsed_buffer = ""

        if parsed_buffer in TOKEN_KEYS:
            should_parse = True

            if (
                Context.DOUBLE_QUOTE in context_stack
                or Context.SINGLE_QUOTE in context_stack
            ):
                if (
                    (
                        char == Punctuation.DOLLAR.value
                        and program_buffer[pos + 1] == Bracket.OPENING_CURLY_BRACKET
                    )
                    or (
                        program_buffer[pos - 1] == Punctuation.DOLLAR.value
                        and char == Bracket.OPENING_CURLY_BRACKET
                    )
                    or context_stack[-1] == Context.CURLY_BRACKET
                ):
                    should_parse = True
                else:
                    should_parse = False

            if should_parse:
                token_list.append(string_to_token(parsed_buffer))
                parsed_buffer = ""

        if len(token_list) > 0:
            if token_list[-1] == TOKENS[Keyword.FUNCTION]:
                search(program_buffer, pos + 1, line_number, Punctuation.SPACE)

    if len(context_stack) > 0:
        error(
            f"Expecting '{context_stack[-1].value[-1]}' but have reached the End Of File",
            line_number,
        )

    token_list.append(TOKENS[Punctuation.EOF])

    if not is_entrypoint_exist:
        error(
            "Entrypoint is not exist, you should create it first using `utama` function"
        )

    return (program_bytecodes, program_codechunks)
