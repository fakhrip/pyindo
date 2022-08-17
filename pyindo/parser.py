from __future__ import annotations
from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from string import ascii_letters, digits
from types import CodeType
from enum import Enum
from typing import Any, List, NoReturn, Tuple, Union
from pyindo.compiler import (
    condition,
    math_operation,
    bool_operation,
    call_function,
    comparison,
    define_function_content,
    define_function_wrapper,
)
from pyindo.types import LiteralString
from bytecode import Label


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
    # Dont tokenize this as this just act as a
    # marker throughout the whole parser process
    ELIF = "selainnya jika"


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


# TODO: Create LoopBytecode


class ConditionBytecode:
    def __init__(self, c_type: str):
        self._condition_type = c_type
        self._conditional_expression = []
        self._conditional_statements = []
        self._other_coditional_statements = []

    @property
    def condition_type(self) -> str:
        return self._condition_type

    def set_conditional_expression(self, expressions: list) -> None:
        self._conditional_expression = expressions

    def add_conditional_statement(self, statements: list) -> None:
        self._conditional_statements.extend(statements)

    def add_other_conditional_statement(self, statements: list) -> None:
        other_condition_label = Label()
        self._other_coditional_statements.extend([other_condition_label, *statements])

        return other_condition_label

    def create_condition_bytecodes(
        self,
        jump_label: Union[Label, None] = None,
        condition_label: Union[Label, None] = None,
    ) -> list:
        return condition(
            self._conditional_expression,
            self._conditional_statements,
            self._other_coditional_statements,
            self._condition_type,
            jump_label,
            condition_label,
        )


class FunctionBytecode:
    def __init__(self, function_name: Union[str, None] = None):
        self._params: list = []
        self._header: list = []
        self._tail: Tuple[list, Label] = ()
        self._content: list = []
        self._function_name: Union[str, None] = function_name
        self._identifiers: dict = {}
        self._function_bytecodes: list = []
        self._function_codechunk: Union[CodeType, None] = None

    @property
    def function_tail(self) -> Tuple[list, Label]:
        return self._tail

    @property
    def function_name(self) -> Union[str, None]:
        return self._function_name

    def set_function_params(self, parameters: list) -> None:
        self._params = parameters

    def set_header_bytecodes(self, line_number: int) -> None:
        if self._function_name == Keyword.MAIN.value:
            self._header, self._tail = define_function_wrapper(
                self.function_name,
                self._params,
                self._function_name == Keyword.MAIN.value,
                line_number,
            )
        else:
            self._header, self._tail = define_function_wrapper(
                self._function_name,
                self._params,
                self._function_name == Keyword.MAIN.value,
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

    def create_function_bytecodes(self, line_number: int) -> None:
        bytecodes, function_codechunk = define_function_content(
            self._function_name,
            {
                "header": self._header,
                "tail": self._tail,
                "content": self._content,
            },
            self._function_name == Keyword.MAIN.value,
            line_number,
        )

        self._function_bytecodes = bytecodes

        if self._function_name:
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


def compiler_error(statement) -> NoReturn:
    """
    Show compiler error statement if there are any
    """

    print(
        f"\r[!] Compiler Error: {statement}\n\n--+--(Please file an issue in the github repository if you found this)\n--+--",
        end="",
    )
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
) -> Tuple[int or None, int or None]:
    token = None

    from_pos = from_pos if from_pos else len(token_list)
    token_list = token_list[from_pos:] if is_forward else token_list[:from_pos][::-1]
    for pos, token in enumerate(token_list):
        is_in_whitelist = False
        for token_whitelist in other_than:
            is_in_whitelist |= token == TOKENS[token_whitelist]

        if not is_in_whitelist:
            return token, pos

    return token, len(token_list)


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
    if len(postfix_token_list) == 1:
        if isinstance(postfix_token_list[0], tuple) or isinstance(
            postfix_token_list[0], str
        ):
            return [postfix_token_list[0]]
        else:
            compiler_error(
                f"Orphan '{token_to_string(postfix_token_list[0])}' token without any expression in bytecode expression evaluator"
            )

    stack = []
    bytecodes = []
    for token in postfix_token_list:
        if isinstance(token, tuple) or isinstance(token, str):
            if isinstance(token, tuple) and token[1] == LiteralString:
                bytecodes.append(token)
            else:
                stack.append(token)
        else:
            if len(stack) > 1:
                r_operand = stack.pop()
                l_operand = stack.pop()
            else:
                r_operand = stack.pop()
                l_operand = bytecodes[-1]

            match token_to_string(token):
                case _ as token_string if token_string in [
                    Operator.EQUAL.value,
                    Operator.NOT_EQUAL.value,
                    Operator.GREATER_THAN.value,
                    Operator.LESS_THAN.value,
                    Operator.GREATER_THAN_EQUAL.value,
                    Operator.LESS_THAN_EQUAL.value,
                ]:
                    if len(stack) > 1:
                        bytecodes = comparison(l_operand, r_operand, token_string)
                    else:
                        bytecodes.append(comparison(l_operand, r_operand, token_string))

                case _ as token_string if token_string in [
                    Operator.BIT_AND.value,
                    Operator.BIT_OR.value,
                    Operator.BIT_NOT.value,
                    Operator.BIT_SHIFT_LEFT.value,
                    Operator.BIT_SHIFT_RIGHT.value,
                    Operator.PLUS.value,
                    Operator.MINUS.value,
                    Operator.MULTIPLY.value,
                    Operator.DIVIDE.value,
                    Operator.MODULO.value,
                    Operator.POWER.value,
                ]:
                    if len(stack) > 1:
                        bytecodes = math_operation(l_operand, r_operand, token_string)
                    else:
                        bytecodes.append(
                            math_operation(l_operand, r_operand, token_string)
                        )

                case _ as token_string if token_string in [
                    Operator.AND.value,
                    Operator.OR.value,
                ]:
                    if len(stack) > 1:
                        bytecodes = bool_operation(l_operand, r_operand, token_string)
                    else:
                        bytecodes.append(
                            bool_operation(l_operand, r_operand, token_string)
                        )

    return bytecodes


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
                    TOKENS[Punctuation.COMMA],
                    TOKENS[Punctuation.DOLLAR],
                    TOKENS[Bracket.OPENING_CURLY_BRACKET],
                    TOKENS[Bracket.CLOSING_CURLY_BRACKET],
                ]:
                    error(f"Illegal token '{token_string}'", line_number)
        else:
            parsed_tokens.append(token)

    if len(bracket_stack) > 0:
        error("Expecting ')'", line_number)

    if len(parsed_tokens) == 0:
        error("Expression not found", line_number)

    return evaluate_to_bytecode(convert_to_postfix(parsed_tokens))


def parse_parameters(token_list: list, line_number: int) -> list:
    parameters = []

    cur_tokens = []
    for pos, token in enumerate(token_list):
        if token == TOKENS[Punctuation.COMMA]:
            parameters.extend(parse_expression(cur_tokens, line_number))
            cur_tokens = []

        cur_tokens.append(token)

        if pos == len(token_list) - 1 and len(cur_tokens) > 0:
            parameters.extend(parse_expression(cur_tokens, line_number))

    return parameters


def parse_program(program_buffer: str) -> Tuple[list, list[CodeType]]:
    is_entrypoint_exist = False

    token_list = []
    parsed_params = []
    declared_functions = []
    global_identifiers = {}

    context_stack: List[Context] = []
    bytecode_stack: List[Union[FunctionBytecode, ConditionBytecode]] = []
    function_context_stack: List[str] = []

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
                last_token, _ = get_first_token(token_list, False)
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
                    line_number,
                )

                second_last_token, _ = get_first_token(
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
                    last_token, _ = get_first_token(
                        token_list, False, opening_bracket_pos
                    )
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
                        bytecodes = call_function(
                            function_name,
                            parsed_params,
                            line_number,
                            False,
                        )

                        if isinstance(bytecode_stack[-1], FunctionBytecode):
                            bytecode_stack[-1].add_content_bytecodes(bytecodes)
                        elif isinstance(bytecode_stack[-1], ConditionBytecode):
                            bytecode_stack[-1].add_conditional_statement(bytecodes)

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
                        if parsed_buffer[:-1] != Bracket.CLOSING_CURLY_BRACKET.value:
                            token_list.append((parsed_buffer[:-1], LiteralString))

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

                bytecode_class = None

                if (
                    Context.DOUBLE_QUOTE in context_stack
                    or Context.SINGLE_QUOTE in context_stack
                ):
                    if program_buffer[pos - 1] == Punctuation.DOLLAR.value:
                        token_list.append((parsed_buffer[:-2], LiteralString))
                        token_list.append(
                            TOKENS[
                                Punctuation.DOUBLEQUOTE
                                if Context.DOUBLE_QUOTE in context_stack
                                else Punctuation.SINGLE_QUOTE
                            ]
                        )
                        token_list.extend(
                            [
                                TOKENS[Punctuation.DOLLAR],
                                TOKENS[Bracket.OPENING_CURLY_BRACKET],
                            ]
                        )

                        parsed_buffer = ""
                elif (
                    Keyword.IF.value in function_context_stack
                    or Keyword.ELIF.value in function_context_stack
                    or Keyword.ELSE.value in function_context_stack
                ):
                    last_branch_context = None
                    for context in function_context_stack[::-1]:
                        if context in [
                            Keyword.IF.value,
                            Keyword.ELIF.value,
                            Keyword.ELSE.value,
                        ]:
                            last_branch_context = context
                            break

                    match last_branch_context:
                        case Keyword.IF.value:
                            condition_bytecode = ConditionBytecode(Keyword.IF.value)
                            condition_bytecode.set_conditional_expression(
                                parsed_params[0]
                            )
                            bytecode_class = condition_bytecode

                        case Keyword.ELIF.value:
                            condition_bytecode = ConditionBytecode(Keyword.ELIF.value)
                            condition_bytecode.set_conditional_expression(
                                parsed_params[0]
                            )
                            bytecode_class = condition_bytecode

                    match token_to_string(get_first_token(token_list, False)[0]):
                        case Keyword.ELSE.value:
                            condition_bytecode = ConditionBytecode(Keyword.ELSE.value)
                            bytecode_class = condition_bytecode

                else:
                    function_bytecode = FunctionBytecode(declared_functions[-1])
                    function_bytecode.set_function_params(parsed_params)
                    function_bytecode.set_header_bytecodes(line_number)
                    bytecode_class = function_bytecode

                if bytecode_class:
                    bytecode_stack.append(bytecode_class)

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
                        token_list.extend(
                            [
                                TOKENS[Bracket.CLOSING_CURLY_BRACKET],
                                TOKENS[
                                    Punctuation.DOUBLEQUOTE
                                    if Context.DOUBLE_QUOTE in context_stack
                                    else Punctuation.SINGLEQUOTE
                                ],
                            ]
                        )
                elif isinstance(bytecode_stack[-1], ConditionBytecode):
                    # TODO: implement parse ahead
                    is_else_ahead = False

                    cur_parsed_buffer = ""
                    for cur_char in program_buffer[pos + 1 :]:
                        if cur_char != Punctuation.SPACE.value:
                            cur_parsed_buffer += cur_char
                        elif cur_char in [
                            *[e.value for e in Bracket],
                            *[e.value for e in Punctuation],
                            *[e.value for e in Operator],
                            *[e.value for e in SelfOperator],
                            " " "\n",
                        ]:
                            if cur_parsed_buffer != "":
                                is_else_ahead = cur_parsed_buffer == Keyword.ELSE.value
                                break
                            elif cur_char in [" ", "\n"]:
                                cur_parsed_buffer = ""
                                continue
                            else:
                                is_else_ahead = False
                                break

                    if not is_else_ahead:
                        condition_stack: List[ConditionBytecode] = []
                        while isinstance(bytecode_stack[-1], ConditionBytecode):
                            condition_stack.append(bytecode_stack.pop())

                        target_label = Label()

                        condition_temp = None
                        condition_label = None
                        for condition in condition_stack:
                            if not condition_temp:
                                condition_temp = condition
                            else:
                                condition_temp = (
                                    condition_temp.create_condition_bytecodes(
                                        condition_label
                                    )
                                )
                                condition_label = (
                                    condition.add_other_conditional_statement(
                                        condition_temp
                                    )
                                )
                                condition_temp = condition

                        bytecode_stack[-1].add_content_bytecodes(
                            [
                                *condition_temp.create_condition_bytecodes(
                                    target_label,
                                    condition_label
                                    if condition_label
                                    else target_label,
                                ),
                                target_label,
                            ]
                        )
                    else:
                        # There are another condition, so keep on parsing...
                        pass
                else:
                    bytecode_stack[-1].create_function_bytecodes(line_number)

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
                if context_stack[-1] == Context.CURLY_BRACKET:
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
            should_parse = True

            if (
                Context.DOUBLE_QUOTE in context_stack
                or Context.SINGLE_QUOTE in context_stack
            ):
                if context_stack[-1] == Context.CURLY_BRACKET:
                    should_parse = True
                else:
                    should_parse = False

            if (
                program_buffer[pos + 1]
                in [
                    *[e.value for e in Bracket],
                    *[e.value for e in Punctuation],
                    *[e.value for e in Operator],
                    *[e.value for e in SelfOperator],
                    "\n",
                ]
                or char == "\n"
            ) and should_parse:
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
                # Space have to exist after all those checked tokens
                search(program_buffer, pos + 1, line_number, Punctuation.SPACE)

            if token_list[-1] in [
                TOKENS[SelfOperator.SELF_PLUS_ONE],
                TOKENS[SelfOperator.SELF_MINUS_ONE],
            ]:
                # Semicolon have to exist after those self operators
                search(program_buffer, pos + 1, line_number, Punctuation.SEMICOLON)

            if token_list[-1] in [TOKENS[Keyword.IF], TOKENS[Keyword.ELSE]]:
                if (
                    token_list[-1] == TOKENS[Keyword.IF]
                    and get_first_token(token_list, False)[0] == TOKENS[Keyword.ELSE]
                ):
                    function_context_stack.append(Keyword.ELIF.value)
                else:
                    function_context_stack.append(token_to_string(token_list[-1]))

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
