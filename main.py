from sys import argv
from bytecode import Instr, Bytecode


def help():
    print(
        """\rUsage: python main.py [input file]
        \r
        \rwhere `input file` is a program written in pyindo language"""
    )


if __name__ == "__main__":
    # Get the first argument to the program as a file input
    try:
        f_input = argv[1]
    except:
        help()
        exit()

    # Read the file input given in the first argument
    with open(f_input, "r") as f:
        f_buffer = f.read().split("\n")

        is_entrypoint_exist = False
        bytecode = []

        for line in f_buffer:
            if "utama() {" in line:
                is_entrypoint_exist = True

            if "tampilkan(" in (stripped_line := line.strip()):
                bytecode.append(Instr("LOAD_NAME", "print"))

                argument = stripped_line.replace("tampilkan(\"", "")
                argument = argument.replace("\");", "")
                argument = argument.strip()

                bytecode.append(Instr("LOAD_CONST", argument))
                bytecode.append(Instr("CALL_FUNCTION", 1))

        bytecode.extend([
            Instr("POP_TOP"), 
            Instr("LOAD_CONST", None), 
            Instr("RETURN_VALUE")
        ])

        compiled_bytecode = Bytecode(bytecode)
        code = compiled_bytecode.to_code()
        exec(code)
