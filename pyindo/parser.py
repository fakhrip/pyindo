from types import CodeType

from bytecode import Instr

from pyindo.diagnostics import PyIndoError, format_error
from pyindo.modules import compile_module_graph
from pyindo.runtime import EX_SOFTWARE, ensure_supported_runtime


def parse_program(program_buffer: str, *, filename: str = "<pyindo>") -> tuple[list, list[CodeType]]:
  """
  Preserve the original parser API while using the structured compiler pipeline.

  A single final NUL is a legacy caller sentinel. All other NULs remain source
  errors. New APIs raise PyIndoError; this facade retains its print/exit contract.
  Supply filename to anchor local imports and retain the root source identity.
  """

  ensure_supported_runtime()

  if program_buffer.endswith("\0"):
    program_buffer = program_buffer[:-1]

  try:
    bytecode = compile_module_graph(program_buffer, filename=filename)
  except PyIndoError as compilation_error:
    print(format_error(compilation_error), end="")
    raise SystemExit(EX_SOFTWARE) from compilation_error

  instructions = list(bytecode)
  function_chunks = [
    instruction.arg for instruction in instructions
    if isinstance(instruction, Instr) and isinstance(instruction.arg, CodeType)
  ]

  return instructions, function_chunks
