from sys import argv


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

# open("")
