from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import ascii_letters, digits
from types import CodeType
from enum import Enum
from typing import Any, List, NoReturn, Tuple
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
    MINUS = "-"
    MULTIPLY = "*"
    POWER = "**"
    DIVIDE = "/"
    MODULO = "%"
    EQUAL = "=="
    AND = "&&"
    OR = "||"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    BIT_AND = "&"
    BIT_OR = "|"
    BIT_NOT = "!"
    BIT_SHIFT_LEFT = "<<"
    BIT_SHIFT_RIGHT = ">>"
    GREATER_THAN_EQUAL = ">="
    LESS_THAN_EQUAL = ">="
    NOT_EQUAL = "!="


class SelfOperator(Enum):
    SELF_PLUS = "+="
    SELF_MINUS = "-="
    SELF_MULTIPLY = "*="
    SELF_DIVIDE = "/="
    SELF_MODULO = "%="
    SELF_POWER = "**="
    SELF_PLUS_ONE = "++"
    SELF_MINUS_ONE = "--"
    SELF_BIT_AND = "&="
    SELF_BIT_OR = "|="
    SELF_BIT_SHIFT_LEFT = "<<="
    SELF_BIT_SHIFT_RIGHT = ">>="


class Punctuation(Enum):
    DOUBLEQUOTE = '"'
    SINGLEQUOTE = "'"
    SEMICOLON = ";"
    SPACE = " "
    COMMA = ","
    DOLLAR = "$"
    TRIPLEQUOTE = '"""'
    COLON = ":"
    ASSIGN = "="
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
    EQUAL = "adalah"
    NOT_EQUAL = "bukan"
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
    DELETE = "hapus"
    RETURN = "hasilkan"
    MAIN = "utama"


# TODO: Change this to automatic enum value when the development process
#       is done up to the time in which we can create compiler compilation pipeline
TOKENS = {
    Keyword.FUNCTION: 100,
    Keyword.PRINT: 101,
    Keyword.EQUAL: 102,
    Keyword.NOT_EQUAL: 103,
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
    Keyword.DELETE: 114,
    Keyword.RETURN: 115,
    Keyword.MAIN: 116,
    SelfOperator.SELF_PLUS: 200,
    SelfOperator.SELF_MINUS: 201,
    SelfOperator.SELF_MULTIPLY: 202,
    SelfOperator.SELF_DIVIDE: 203,
    SelfOperator.SELF_MODULO: 204,
    SelfOperator.SELF_POWER: 205,
    SelfOperator.SELF_PLUS_ONE: 206,
    SelfOperator.SELF_MINUS_ONE: 207,
    SelfOperator.SELF_BIT_AND: 208,
    SelfOperator.SELF_BIT_OR: 209,
    SelfOperator.SELF_BIT_SHIFT_LEFT: 210,
    SelfOperator.SELF_BIT_SHIFT_RIGHT: 211,
    Operator.PLUS: 300,
    Operator.MINUS: 301,
    Operator.MULTIPLY: 302,
    Operator.POWER: 303,
    Operator.DIVIDE: 304,
    Operator.MODULO: 305,
    Operator.EQUAL: 306,
    Operator.AND: 307,
    Operator.OR: 308,
    Operator.GREATER_THAN: 309,
    Operator.LESS_THAN: 310,
    Operator.BIT_AND: 311,
    Operator.BIT_OR: 312,
    Operator.BIT_NOT: 313,
    Operator.BIT_SHIFT_LEFT: 314,
    Operator.BIT_SHIFT_RIGHT: 315,
    Operator.GREATER_THAN_EQUAL: 316,
    Operator.LESS_THAN_EQUAL: 317,
    Operator.NOT_EQUAL: 318,
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
    Punctuation.ASSIGN: 708,
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
    *[e.value for e in SelfOperator],
    *[e.value for e in Type],
]

TOKEN_VALUES = [
    *[e for e in Bracket],
    *[e for e in Punctuation],
    *[e for e in Keyword],
    *[e for e in Operator],
    *[e for e in SelfOperator],
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
        self._identifiers = {}
        self._function_bytecodes = []
        self._function_codechunk = None

    def set_function_params(self, parameters: list) -> None:
        self._params = parameters

    def set_header_bytecodes(self, line_number: int, function_name: str) -> None:
        self._header = define_function_header(
            function_name,
            self._params,
            function_name == Keyword.MAIN.value,
            line_number,
        )

    def is_identifier_exist(self, identifier_name: str) -> bool:
        return identifier_name in self._identifiers.keys()

    def add_identifier(self, identifier_name: str) -> None:
        # TODO: add some bytecodes here to set identifier to local name
        self._identifiers[identifier_name] = None

    def set_identifier_value(
        self, line_number: int, identifier_name: str, value: Any
    ) -> None:
        self._identifiers[identifier_name] = value
        # TODO: add some bytecodes here to add value to the identifier
        self._content.extend()

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


def check_legal_identifier(identifier: str, line_number: int) -> None or NoReturn:
    is_legal = identifier[0] not in digits

    for char in identifier:
        is_legal &= char in [*ascii_letters, *digits, "_"]

    if not is_legal:
        error(f"Illegal identifier name: {identifier}", line_number)


def clean_identifier(identifier: str) -> str:
    clean_str = ""

    for char in identifier:
        if char in [*ascii_letters, *digits, "_"]:
            clean_str += char

    return clean_str


def parse_format_string(string: str) -> list:
    formatted_string = []

    while "${" in string:
        starting_point = string.index("${")
        ending_point = string.index("}")

        formatted_string.append(string[:starting_point])
        string = string[ending_point + 1 :]

    return formatted_string


def convert_to_postfix(token_list: list) -> list:
    stack = []
    postfix = []

    OPERATORS = {
        TOKENS[Operator.BIT_AND]: 0,
        TOKENS[Operator.BIT_OR]: 0,
        TOKENS[Operator.BIT_NOT]: 0,
        TOKENS[Operator.BIT_SHIFT_LEFT]: 0,
        TOKENS[Operator.BIT_SHIFT_RIGHT]: 0,
        TOKENS[Operator.PLUS]: 1,
        TOKENS[Operator.MINUS]: 1,
        TOKENS[Operator.MULTIPLY]: 2,
        TOKENS[Operator.DIVIDE]: 2,
        TOKENS[Operator.MODULO]: 2,
        TOKENS[Operator.POWER]: 3,
        TOKENS[Operator.EQUAL]: 4,
        TOKENS[Operator.NOT_EQUAL]: 4,
        TOKENS[Operator.GREATER_THAN]: 4,
        TOKENS[Operator.LESS_THAN]: 4,
        TOKENS[Operator.GREATER_THAN_EQUAL]: 4,
        TOKENS[Operator.LESS_THAN_EQUAL]: 4,
        TOKENS[Operator.AND]: 4,
        TOKENS[Operator.OR]: 4,
    }

    for pos, token in enumerate(token_list):
        if isinstance(token, tuple) or isinstance(token, str):
            postfix.append(token)
        elif token == TOKENS[Bracket.OPENING_ROUND_BRACKET]:
            stack.append(token)
        elif token == TOKENS[Bracket.CLOSING_ROUND_BRACKET]:
            while stack[-1] != TOKENS[Bracket.OPENING_ROUND_BRACKET]:
                postfix.append(stack.pop())
            stack.pop()
        else:
            while (
                len(stack) > 0
                and stack[-1] != TOKENS[Bracket.OPENING_ROUND_BRACKET]
                and OPERATORS[stack[-1]] >= OPERATORS[token]
            ):
                postfix.append(stack.pop())
            stack.append(token)

        if pos == len(token_list) - 1 and len(stack) > 0:
            while len(stack) != 0:
                postfix.append(stack.pop())

    return postfix


def evaluate_to_bytecode(postfix_token_list: list) -> list:
    print("TODO: Implement the postfix evaluator to convert to bytecode")
    return []


def parse_expression(token_list: list, line_number: int) -> list:
    parsed_tokens = []
    bracket_stack = []
    for token in token_list:
        if isinstance(token, int):
            match token_to_string(token):
                case Keyword.EQUAL.value:
                    parsed_tokens.append(TOKENS[Operator.EQUAL])

                case Keyword.NOT_EQUAL.value:
                    parsed_tokens.append(TOKENS[Operator.NOT_EQUAL])

                case Bracket.OPENING_ROUND_BRACKET.value:
                    parsed_tokens.append(token)
                    bracket_stack.append(token)

                case Bracket.CLOSING_ROUND_BRACKET.value:
                    parsed_tokens.append(token)
                    bracket_stack.pop()

                case _ as token_string if token in [*[TOKENS[e] for e in Operator]]:
                    if parsed_tokens[-1] in [*[TOKENS[e] for e in Operator]]:
                        error(f"Illegal token '{token_string}'", line_number)

                    parsed_tokens.append(token)

                case _ as token_string if token not in [
                    TOKENS[Punctuation.SPACE],
                    TOKENS[Punctuation.SINGLEQUOTE],
                    TOKENS[Punctuation.DOUBLEQUOTE],
                    TOKENS[Punctuation.OPENING_MULTILINE_COMMENT],
                    TOKENS[Punctuation.CLOSING_MULTILINE_COMMENT],
                ]:
                    error(f"Illegal token '{token_string}'", line_number)
        else:
            parsed_tokens.append(token)

    if len(bracket_stack) > 0:
        error("Expecting ')'", line_number)

    if len(parsed_tokens) == 0:
        error("Expression not found", line_number)

    return evaluate_to_bytecode(convert_to_postfix(parsed_tokens))


def parse_parameters(
    token_list: list, anonymous_functions: list, line_number: int
) -> list:
    parameters = []

    cur_tokens = []
    for pos, token in enumerate(token_list):
        if token == TOKENS[Punctuation.COMMA]:
            parameters.extend(parse_expression(cur_tokens, line_number))
            cur_tokens = []

        cur_tokens.append(token)

        if pos == len(token_list) - 1 and len(cur_tokens) > 0:
            parameters.extend(parse_expression(cur_tokens, line_number))

    final_parameters = []
    for param in parameters:
        # Parse it as a format string if anonymous functions exist
        if isinstance(param[1], str) and len(anonymous_functions) > 0:
            for string in parse_format_string(param):
                final_parameters.append((string, str))
                final_parameters.append(anonymous_functions.pop())
            continue

        final_parameters.append(param)

    return final_parameters


def parse_program(program_buffer: str) -> Tuple[list, list[CodeType]]:
    is_entrypoint_exist = False

    token_list = []
    parsed_params = []
    declared_functions = []
    global_identifiers = {}

    context_stack: List[Context] = []
    bytecode_stack: List[FunctionBytecode] = []

    anonymous_functions = []

    program_bytecodes = []
    program_codechunks = []

    parsed_buffer = ""
    line_number = 1

    pos = 0
    while program_buffer[pos] != Punctuation.EOF.value:
        char = program_buffer[pos]
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
                        if not is_entrypoint_exist:
                            is_entrypoint_exist = last_token == TOKENS[Keyword.MAIN]

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

                if function_name != "" and last_token not in FUNCTION_KEYWORD_TOKENS:
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
                parsed_params = parse_parameters(
                    token_list[opening_bracket_pos + 1 :],
                    anonymous_functions,
                    line_number,
                )

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

                    if len(bytecode_stack) == 0:
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
                        token_list.append((parsed_buffer[:-1], str))
                        token_list.append(TOKENS[cur_quote])
                        context_stack.pop()

                        parsed_buffer = ""
                        pos += 1
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
                        function_bytecode = FunctionBytecode()
                        bytecode_stack.append(function_bytecode)
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

                bytecodes = None

                if (
                    Context.DOUBLE_QUOTE in context_stack
                    or Context.SINGLE_QUOTE in context_stack
                ):
                    if context_stack[-1] == Context.CURLY_BRACKET:
                        bytecode_stack[-1].create_function_bytecodes(line_number)
                        (
                            bytecodes,
                            _,
                        ) = bytecode_stack.pop().get_function_bytecodes()

                        anonymous_functions.append(bytecodes)
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

                    if len(bytecode_stack) == 0:
                        program_bytecodes.extend(bytecodes)
                    else:
                        bytecode_stack[-1].add_content_bytecodes(bytecodes)

                context_stack.pop()

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
                # Parse token with the longest char possible first
                token = (
                    three_char
                    if isinstance(
                        three_char := string_to_token(program_buffer[pos : pos + 3]),
                        int,
                    )
                    else (
                        two_char
                        if isinstance(
                            two_char := string_to_token(program_buffer[pos : pos + 2]),
                            int,
                        )
                        else string_to_token(parsed_buffer)
                    )
                )

                pos += (
                    2
                    if isinstance(three_char, int)
                    else (1 if isinstance(two_char, int) else 0)
                )

                token_list.append(token)
                parsed_buffer = ""
        else:
            if (
                (
                    program_buffer[pos + 1]
                    in [
                        *[e.value for e in Bracket],
                        *[e.value for e in Punctuation],
                        *[e.value for e in Operator],
                        *[e.value for e in SelfOperator],
                        "\n",
                    ]
                    or char == "\n"
                )
                and Context.DOUBLE_QUOTE not in context_stack
                and Context.SINGLE_QUOTE not in context_stack
            ):
                match clean_string := clean_identifier(parsed_buffer):
                    case "benar" | "BENAR" | "salah" | "SALAH" as v_boolean:
                        token_list.append((v_boolean, bool))
                    case _ as v_integer if clean_string.isdigit():
                        token_list.append((v_integer, int))
                    case _ as v_float if clean_string.replace(
                        ".", ""
                    ).isdigit() and "." in clean_string:
                        token_list.append((v_float, float))
                    case _ as identifier if clean_string != "":
                        if program_buffer[pos + 1] not in [
                            Bracket.OPENING_ROUND_BRACKET.value,
                            Bracket.OPENING_CURLY_BRACKET.value,
                        ]:
                            if len(bytecode_stack) == 0:
                                # GLobal identifiers
                                if identifier not in global_identifiers.keys():
                                    error(
                                        f"Identifier '{identifier}' has not declared yet",
                                        line_number,
                                    )
                            else:
                                # Local identifiers
                                if not bytecode_stack[-1].is_identifier_exist(
                                    identifier
                                ):
                                    error(
                                        f"Identifier '{identifier}' has not declared yet",
                                        line_number,
                                    )
                        else:
                            pos += 1
                            continue

                parsed_buffer = ""
                if char == "\n":
                    line_number += 1

        if len(token_list) > 0:
            if token_list[-1] in [
                TOKENS[Keyword.FUNCTION],
                TOKENS[Keyword.THEN],
                TOKENS[Keyword.RETURN],
                TOKENS[Keyword.VARIABLE],
                TOKENS[Keyword.CONSTANT],
            ]:
                # Space have to exist after all these checked tokens
                search(program_buffer, pos + 1, line_number, Punctuation.SPACE)

            if token_list[-1] == TOKENS[Punctuation.SINGLELINE_COMMENT]:
                # Jump to next line if single line comment is found
                if "\n" in program_buffer[pos:]:
                    pos += program_buffer[pos:].index("\n")
                    line_number += 1

            if token_list[-1] == TOKENS[Punctuation.OPENING_MULTILINE_COMMENT]:
                # Jump to closing of multiline comment if any
                if Punctuation.CLOSING_MULTILINE_COMMENT.value in program_buffer[pos:]:
                    closing_position = program_buffer[pos:].index(
                        Punctuation.CLOSING_MULTILINE_COMMENT.value
                    )
                    line_number += program_buffer[pos : pos + closing_position].count(
                        "\n"
                    )

                    pos += closing_position
                    token_list.append(Punctuation.CLOSING_MULTILINE_COMMENT)
                else:
                    # End the parsing process directly if no closing multiline comment found
                    break

        pos += 1

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
