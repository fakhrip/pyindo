from bytecode import Instr, Bytecode


def format_print(string_args: list) -> list:
    bytecodes = []

    bytecodes.append(Instr("LOAD_NAME", "print"))

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


def define_function(
    function_name: str, function_param: list, is_entrypoint_function: bool
) -> list:
    bytecodes = []

    if is_entrypoint_function:
        # Function definition for entrypoint
        # TODO: handle function definition for entrypoint
        print("TODO (handle function definition for entrypoint)")
    else:
        # Function definition for other functions
        # TODO: handle function definition for other functions
        print("TODO (handle function definition for other functions)")

    return bytecodes


def compile_bytecodes(bytecodes: list) -> Bytecode:
    return Bytecode(bytecodes)
