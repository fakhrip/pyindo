from os import popen
from glob import glob

if __name__ == "__main__":
    incorrect_programs, incorrect_programs_out = [
        sorted(glob("tests/error/*.pyind")),
        sorted(glob("tests/error/*.output")),
    ]
    correct_programs, correct_programs_out = [
        sorted(glob("tests/success/*.pyind")),
        sorted(glob("tests/success/*.output")),
    ]

    print("==============================")
    print("[+] Testing incorrect programs")
    print("==============================")

    # Test all incorrect programs
    for iteration, program, output in zip(
        range(len(incorrect_programs)), incorrect_programs, incorrect_programs_out
    ):
        program_out = popen(f"python3 main.py {program}").read().lstrip("\n")
        expected_out = open(output, "r").read()

        print(f"[{iteration + 1}] {program} ", end="")
        if program_out == expected_out:
            print("(PASSED)")
        else:
            print("(FAIL)")
            print(f"Expected: `{expected_out}`")
            print(f"Got: `{program_out}`", end="\n\n")

    print("\n============================")
    print("[+] Testing correct programs")
    print("============================")

    # Test all correct programs
    for iteration, program, output in zip(
        range(len(correct_programs)), correct_programs, correct_programs_out
    ):
        program_out = popen(f"python3 main.py {program}").read().lstrip("\n")
        expected_out = open(output, "r").read()

        print(f"[{iteration + 1}] {program} ", end="")
        if program_out == expected_out:
            print("(PASSED)")
        else:
            print("(FAIL)")
            print(f"Expected: `{expected_out}`")
            print(f"Got: `{program_out}`", end="\n\n")
