from os import (
    EX_USAGE,  # Exit code that means that some kind of configuration error occurred.
    EX_NOINPUT,  # Exit code that means an input file did not exist or was not readable.
    EX_SOFTWARE,  # Exit code that means an internal software error was detected.
)
from os.path import isfile
from sys import argv, argc, exit
from bytecode import Instr, Bytecode


def help(exit_code=EX_USAGE) -> None:
    """
    Show usage of the program
    """
    
    print(
        """\rUsage: python main.py [input file] [options]
        \r
        \rWhere `input file` is a file with program written 
        \rin pyindo language inside.
        \r
        \rAvailable options: 
        \r  -O      Enable program optimizations 
        \r  -D      Output python bytecode result
        \r          filename: [input file name].pyc"""
    )
    exit(exit_code)


def error(statement, line_number=None) -> None:
    """
    Show error statement if there are any, including
    the line number in which the error happened
    """

    line_number_str = f" (on line number {line_number})" if line_number else ""
    print(f"\rError: {statement}{line_number_str}")
    exit(EX_SOFTWARE)


def parse_argument() -> tuple[str, dict]:
    """
    Parse the argument to the command line
    compiler application.

    Return a tuple of (
        str of -> file input of the program to be compiled
        dict of -> the enabled options and the value given
                    to each of them (if any)
    )
    """

    # We dont care about the first argument
    # which is this file itself
    del argv[0]

    # Get the second argument and check if
    # the file actually exist or not
    f_input = argv.pop(1)
    if not isfile(f_input):
        help(EX_NOINPUT)

    # Track which options are enabled
    # and what value is given to each of them
    enabled_options = []
    for arg in argv:
        match arg:
            case "-O":
                enabled_options["optimization"] = True
            case "-D":
                enabled_options["debug_output"] = True
            case _:
                help()

    return f_input


if __name__ == "__main__":
    if argc < 2:
        help()

    # Get the first argument to the program as a file input
    f_input = parse_argument()

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
                    error("Return value should be integer", line_number=line_num)

        if not is_entrypoint_exist:
            error(
                "Entrypoint is not exist, you should create it first using `utama()` function"
            )

        bytecode.extend(
            [Instr("POP_TOP"), Instr("LOAD_CONST", return_value), Instr("RETURN_VALUE")]
        )

        compiled_bytecode = Bytecode(bytecode)
        code = compiled_bytecode.to_code()
        exec(code)
