from os import (
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from bytecode import Instr, Bytecode


def error(statement, line_number=None) -> None:
    """
    Show error statement if there are any, including
    the line number in which the error happened
    """

    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}")
    exit(EX_SOFTWARE)


def compile(program_buffer) -> Bytecode:
    is_entrypoint_exist = False
    return_value = 0
    bytecode = []

    for line_num, line in enumerate(program_buffer):
        if "utama() {" in line:
            is_entrypoint_exist = True

        if "tampilkan(" in (stripped_line := line.strip()):
            bytecode.append(Instr("LOAD_NAME", "print"))

            argument = stripped_line.replace('tampilkan("', "")
            argument = argument.replace('");', "")
            argument = argument.strip()

            bytecode.append(Instr("LOAD_CONST", argument))
            bytecode.append(Instr("CALL_FUNCTION", 1))

        if "return" in line:
            try:
                return_value = line.replace("return", "")
                return_value = return_value.replace(";", "")
                return_value = int(return_value)
            except:
                error("Return value should be integer", line_number=line_num)

    if not is_entrypoint_exist:
        error(
            "Entrypoint is not exist, you should create it first using `utama()` function"
        )

    bytecode.extend(
        [Instr("POP_TOP"), Instr("LOAD_CONST", return_value), Instr("RETURN_VALUE")]
    )

    return Bytecode(bytecode)
