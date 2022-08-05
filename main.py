from os import (
    EX_USAGE,  # Exit code that means that some kind of configuration error occurred.
    EX_NOINPUT,  # Exit code that means an input file did not exist or was not readable.
)
from os.path import isfile
from sys import argv, exit
from compiler import compile_bytecodes
from parser import parse_program
from bytecode import Bytecode, dump_bytecode
from contextlib import redirect_stdout
from io import StringIO


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
        \r  -D      Output python bytecode disassembly result
        \r          wiht filename: [input file name].pyc"""
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
        print(f"Could not open file: {f_input}")
        exit(EX_NOINPUT)

    # Track which options are enabled
    # and what value is given to each of them
    enabled_options = {}
    for arg in argv:
        match arg:
            case "-O":
                enabled_options["optimization"] = True
            case "-D":
                enabled_options["debug_output"] = True
            case _:
                help()

    return (f_input, enabled_options)


if __name__ == "__main__":
    if len(argv) < 2:
        help()

    # Get the first argument to the program as a file input
    f_input, enabled_options = parse_argument()

    # Read the file input given in the first argument
    with open(f_input, "r") as f:
        f_buffer = f.read() + "\0"

        bytecodes, codechunks = parse_program(f_buffer)
        compiled_bytecode = compile_bytecodes(bytecodes)
        exec(compiled_bytecode.to_code())

        if "debug_output" in enabled_options.keys():
            f = StringIO()
            with redirect_stdout(f):
                dump_bytecode(compiled_bytecode, lineno=True)

            disassembly = f.getvalue()

            for chunk in codechunks:
                f = StringIO()
                with redirect_stdout(f):
                    dump_bytecode(Bytecode.from_code(chunk), lineno=True)

                disassembly += f"Disassembly of {chunk}:\n" 
                disassembly += f.getvalue()

            open(f_input.replace(".pyind", ".pyc"), "w").write(disassembly)
