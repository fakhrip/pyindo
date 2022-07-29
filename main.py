from os import (
    EX_USAGE,  # Exit code that means that some kind of configuration error occurred.
    EX_NOINPUT,  # Exit code that means an input file did not exist or was not readable.
)
from os.path import isfile
from sys import argv, exit
from compiler import compile


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
    f_input = argv.pop(0)
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
    if len(argv) < 2:
        help()

    # Get the first argument to the program as a file input
    f_input = parse_argument()

    # Read the file input given in the first argument
    with open(f_input, "r") as f:
        f_buffer = f.read().split("\n")

        compiled_bytecode = compile(f_buffer)
        exec(compiled_bytecode.to_code())
