import dis
import sys
from pathlib import Path
from types import CodeType
from typing import Sequence

from pyindo.runtime import (
  EX_USAGE,
  EX_NOINPUT,
  EX_SOFTWARE,
  ensure_supported_runtime,
  execution_arguments,
  entrypoint_exit_status,
)


def help(exit_code: int = EX_USAGE) -> None:
  """
  Show compiler usage and terminate argument parsing with the given status.
  """

  print(
    "Usage: python main.py [input file] [options] [-- program arguments]\n"
    "\n"
    "Compile and run a program written in the PyIndo language.\n"
    "\n"
    "Available options:\n"
    "  -O      Accepted for compatibility; no optimizer is enabled.\n"
    "  -D      Also write bytecode disassembly to [input stem].dis.\n"
    "  --      Pass remaining arguments verbatim to the program."
  )

  raise SystemExit(exit_code)


def parse_argument(arguments: Sequence[str] | None = None) -> tuple[Path, dict, tuple[str, ...]]:
  """
  Parse a source path and trailing options without changing sys.argv.

  Return the resolved source path, enabled options, and user arguments after --.
  Invalid usage exits 64; a missing or non-file input exits 66 with a diagnostic.
  """

  if arguments is None:
    arguments = sys.argv[1:]

  if not arguments or arguments[0].startswith("-"):
    help()

  source_path = Path(arguments[0])
  enabled_options = {}
  user_arguments = ()

  for index, argument in enumerate(arguments[1:], start=1):
    if argument == "--":
      user_arguments = tuple(arguments[index + 1:])
      break

    match argument:
      case "-O":
        enabled_options["optimization"] = True
      case "-D":
        enabled_options["debug_output"] = True
      case _:
        help()

  if not source_path.is_file():
    print(f"Could not open file: {source_path}")
    raise SystemExit(EX_NOINPUT)

  return (source_path.resolve(), enabled_options, user_arguments)


def bundled_module_codes(code: CodeType) -> list[CodeType]:
  """
  Find library code inside tuple bundles that dis.dis does not visit itself.

  Normal nested functions are already handled by dis.dis. Traverse only tuple
  containers here, retaining graph order without comparing distinct code objects.
  """

  pending = [value for value in reversed(code.co_consts) if isinstance(value, tuple)]
  modules = []
  while pending:
    value = pending.pop()
    if isinstance(value, CodeType):
      modules.append(value)
    elif isinstance(value, tuple):
      pending.extend(reversed(value))
  return modules


def write_disassembly(code: CodeType, source_path: Path) -> None:
  """
  Write UTF-8 module and nested-function disassembly beside the input.

  Use a .dis suffix, appending it when replacement would overwrite the
  source itself. Propagate filesystem errors to the CLI's input/output handler.
  """

  disassembly_path = source_path.with_suffix(".dis")
  library_codes = bundled_module_codes(code)
  source_paths = [source_path, *(Path(library.co_filename) for library in library_codes)]

  def refers_to_source(path: Path) -> bool:
    """
    Protect every source in the graph, including output hardlinks and symlinks.
    """

    return path in source_paths or path.exists() and any(
      source.exists() and path.samefile(source) for source in source_paths
    )

  # A source or link can occupy either output name; validate both before opening.
  if refers_to_source(disassembly_path):
    disassembly_path = source_path.with_name(source_path.name + ".dis")

  if refers_to_source(disassembly_path):
    raise OSError("Disassembly output refers to a source file")

  with disassembly_path.open("w", encoding="utf-8") as output_file:
    dis.dis(code, file=output_file)
    for library_code in library_codes:
      print(f"\nImported module {library_code.co_filename}:\n", file=output_file)
      dis.dis(library_code, file=output_file)


def main(argv: Sequence[str] | None = None) -> int:
  """
  Compile and execute one source file, returning a portable process status.

  Check the interpreter before loading the assembler. Execute in a fresh
  module namespace so repeated calls do not share program definitions.
  """

  try:
    ensure_supported_runtime()
  except RuntimeError as runtime_error:
    print(runtime_error, file=sys.stderr)
    return EX_USAGE

  try:
    source_path, enabled_options, user_arguments = parse_argument(argv)
  except SystemExit as usage_exit:
    return usage_exit.code

  # Keep dependency loading behind the runtime and command-line checks.
  from pyindo.compiler import compile_source
  from pyindo.diagnostics import PyIndoError, format_error
  from pyindo.emitter import ENTRYPOINT_RESULT_NAME

  try:
    source_text = source_path.read_text(encoding="utf-8")
  except (OSError, UnicodeError) as input_error:
    print(f"Could not open file: {source_path}: {input_error}")
    return EX_NOINPUT

  try:
    code = compile_source(source_text, filename=str(source_path))
  except PyIndoError as compilation_error:
    print(format_error(compilation_error), end="")
    return EX_SOFTWARE
  except Exception as compilation_error:
    # Unexpected assembly/compiler failures stay separate from execution.
    # Ordinary syntax/name errors use the structured diagnostic above.
    print(f"Compiler Error: {compilation_error}")
    return EX_SOFTWARE

  execution_namespace = {
    "__name__": "__main__",
    "__file__": str(source_path),
  }

  # -O remains accepted but cannot change module scope or name lookup.
  with execution_arguments(user_arguments):
    exec(code, execution_namespace)

  # Process status is a CLI boundary, after argument cleanup and before debug I/O.
  exit_status = entrypoint_exit_status(execution_namespace[ENTRYPOINT_RESULT_NAME])

  if enabled_options.get("debug_output"):
    try:
      write_disassembly(code, source_path)
    except OSError as output_error:
      print(f"Could not write disassembly: {output_error}", file=sys.stderr)
      return EX_SOFTWARE

  return exit_status


if __name__ == "__main__":
  sys.exit(main())
