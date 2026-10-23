import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar


EX_USAGE = 64
EX_NOINPUT = 66
EX_SOFTWARE = 70
_USER_ARGUMENTS: ContextVar[tuple[str, ...]] = ContextVar("pyindo_user_arguments", default=())


def ensure_supported_runtime() -> None:
  """
  Require CPython 3.15 before assembling version-specific instructions.

  Raise RuntimeError with the required and actual interpreter versions
  when a different Python implementation or minor release is used.
  """

  implementation_name = sys.implementation.name
  python_version = sys.version_info[:2]

  if implementation_name != "cpython" or python_version != (3, 15):
    actual_version = ".".join(str(part) for part in sys.version_info[:3])

    raise RuntimeError(
      "PyIndo requires CPython 3.15.x; "
      f"running {implementation_name} {actual_version}."
    )


@contextmanager
def execution_arguments(user_arguments: Sequence[str]) -> Iterator[None]:
  """
  Scope immutable user arguments to one execution, restoring nested callers.

  Copy before entering the context so caller mutations cannot affect a program.
  Reset the token even when compilation, execution or a nested call raises.
  """

  arguments = tuple(user_arguments)
  if any(type(argument) is not str for argument in arguments):
    raise TypeError("Program arguments must be exact strings")

  token = _USER_ARGUMENTS.set(arguments)
  try:
    yield
  finally:
    _USER_ARGUMENTS.reset(token)


def invoke_entrypoint(entrypoint: Callable[..., object], parameter_count: int) -> object:
  """
  Invoke a compiled entrypoint without selecting a host process exit status.

  Derive the program name from current code metadata, including legacy filename
  overrides. Each invocation owns a fresh list before normal parameter guards.
  """

  if parameter_count == 0:
    return entrypoint()
  if parameter_count != 2:
    raise ValueError("Entrypoint requires zero or two parameters")

  arguments = [entrypoint.__code__.co_filename, *_USER_ARGUMENTS.get()]
  return entrypoint(arguments, len(arguments))


def entrypoint_exit_status(result: object) -> int:
  """
  Map an entrypoint result to a portable process status without coercing values.

  This boundary belongs to the CLI. Library execution and ordinary function
  calls keep their raw return values, including values outside the status range.
  """

  if result is None:
    return 0
  if type(result) is not int:
    raise TypeError(
      f"Entrypoint exit status must be an integer or None, got {type(result).__name__}"
    )
  if not 0 <= result <= 255:
    raise ValueError("Entrypoint exit status must be between 0 and 255")
  return result
