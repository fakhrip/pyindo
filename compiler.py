from bytecode import Compare, Instr, Bytecode, Label
import bytecode


def format_print(string_args: list, line_number: int, is_global_scope: bool) -> list:
    bytecodes = []

    bytecodes.append(
        Instr(
            "LOAD_NAME" if is_global_scope else "LOAD_GLOBAL",
            "print",
            lineno=line_number,
        )
    )

    for pos, string in enumerate(string_args):
        bytecodes.append(Instr("LOAD_CONST", string))

        if (pos + 1) % 2 == 0:
            bytecodes.append(Instr("FORMAT_VALUE", 0))

    bytecodes.extend(
        [
            Instr("BUILD_STRING", len(string_args)),
            Instr("CALL_FUNCTION", 1),
            Instr("POP_TOP"),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ]
    )

    return bytecodes


def call_function(
    function_name: str, function_param: list, line_number: int, is_global_scope: bool
) -> list:
    bytecodes = []

    match function_name:
        case "tampilkan":
            bytecodes = format_print(function_param, line_number, is_global_scope)

    return bytecodes


def define_function_content(
    function_name: str,
    function_bytecodes: dict,
    is_entrypoint_function: bool,
    line_number: int,
) -> list:
    bytecodes = []

    if is_entrypoint_function:
        # Function content definition for entrypoint
        label_else = Label()
        bytecodes.extend(
            [
                *function_bytecodes["header"],
                Instr("POP_JUMP_IF_FALSE", label_else),
                *function_bytecodes["content"],
                label_else,
                Instr("LOAD_CONST", None),
                Instr("RETURN_VALUE"),
            ]
        )
    else:
        # Function header definition for other functions
        # TODO: handle function header definition for other functions
        print("TODO (handle function content definition for other functions)")

    return bytecodes


def define_function_header(
    function_name: str,
    function_param: list,
    is_entrypoint_function: bool,
    line_number: int,
) -> list:
    bytecodes = []

    if is_entrypoint_function:
        # Function header definition for entrypoint
        bytecodes.extend(
            [
                Instr("LOAD_NAME", "__name__", lineno=line_number),
                Instr("LOAD_CONST", "__main__"),
                Instr("COMPARE_OP", Compare.EQ),
            ]
        )
    else:
        # Function header definition for other functions
        # TODO: handle function header definition for other functions
        print("TODO (handle function header definition for other functions)")

    return bytecodes


def compile_bytecodes(bytecodes: list) -> Bytecode:
    return Bytecode(bytecodes)
