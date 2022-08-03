from bytecode import Instr, Bytecode


def print_function(string_args: list) -> list:
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


def compile(bytecodes: list) -> Bytecode:
    return Bytecode(bytecodes)
