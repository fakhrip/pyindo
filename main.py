from sys import argv
from bytecode import Instr, Bytecode


def help():
    print(
        """\rUsage: python main.py [input file]
        \r
        \rwhere `input file` is a program written in pyindo language"""
    )
    exit()


def error(statement, line_number=None):
    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}")
    exit()


if __name__ == "__main__":
    # Get the first argument to the program as a file input
    try:
        f_input = argv[1]
    except:
        help()

    # Read the file input given in the first argument
    with open(f_input, "r") as f:
        f_buffer = f.read().split("\n")

        is_entrypoint_exist = False
        return_value = 0
        bytecode = []

        for line_num, line in enumerate(f_buffer):
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
                    error(
                        statement="Return value should be integer", 
                        line_number=line_num
                    )

        if not is_entrypoint_exist:
            error(
                statement="Entrypoint is not exist, you should create it first using `utama()` function"
            )

        bytecode.extend(
            [Instr("POP_TOP"), Instr("LOAD_CONST", return_value), Instr("RETURN_VALUE")]
        )

        compiled_bytecode = Bytecode(bytecode)
        code = compiled_bytecode.to_code()
        exec(code)
