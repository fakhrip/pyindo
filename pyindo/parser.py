from types import CodeType

from bytecode import Instr

from pyindo.diagnostics import PyIndoError, format_error
from pyindo.emitter import compile_program
from pyindo.runtime import EX_SOFTWARE, ensure_supported_runtime
from pyindo.syntax import parse_module


def parse_program(program_buffer: str) -> tuple[list, list[CodeType]]:
  """
  Preserve the original parser API while using the structured compiler pipeline.

  A single final NUL is a legacy caller sentinel. All other NULs remain source
  errors. New APIs raise PyIndoError; this facade retains its print/exit contract.
  """

  ensure_supported_runtime()

  if program_buffer.endswith("\0"):
    program_buffer = program_buffer[:-1]

  try:
    bytecode = compile_program(parse_module(program_buffer))
  except PyIndoError as compilation_error:
    print(format_error(compilation_error), end="")
    raise SystemExit(EX_SOFTWARE) from compilation_error

  instructions = list(bytecode)
  function_chunks = [
    instruction.arg for instruction in instructions
    if isinstance(instruction, Instr) and isinstance(instruction.arg, CodeType)
  ]

  return instructions, function_chunks
