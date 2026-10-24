import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from types import ModuleType


EX_USAGE = 64
EX_NOINPUT = 66
EX_SOFTWARE = 70
_USER_ARGUMENTS: ContextVar[tuple[str, ...]] = ContextVar("pyindo_user_arguments", default=())
_UNINITIALIZED_MODULE_VALUE = object()
MODULE_VALUE_NAMES = "<pyindo:module_value_names>"


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


def read_module_value(value: object, name: str) -> object:
  """
  Reject an owned slot until its declaration has successfully published a value.

  Slots are seeded on each execution so Python builtins and a reused host
  namespace cannot accidentally satisfy an indirect early initializer read.
  """

  if value is _UNINITIALIZED_MODULE_VALUE:
    raise NameError(f"Module binding '{name}' is not initialized")
  return value


def module_export(module: ModuleType, name: str) -> object:
  """
  Read an owned export without invoking ModuleType's attribute special cases.

  Explicit base lookup also avoids specialized attribute loads treating a
  function named __dict__ as the namespace mapping after repeated execution.
  """

  return read_module_value(object.__getattribute__(module, "__dict__")[name], name)


def _module_bindings(modules: list[ModuleType], bindings: tuple) -> dict[str, object]:
  """
  Bind an exported function or namespace from an already initialized dependency.
  """

  return {
    alias: modules[index] if name is None else module_export(modules[index], name)
    for alias, index, name in bindings
  }


def load_module_imports(bundle: tuple, bindings: tuple) -> dict[str, object]:
  """
  Instantiate one isolated module graph for this execution, without a global cache.

  Dependencies precede importers. Library code only defines functions, so all
  bindings exist before any PyIndo entrypoint or ordinary function can execute.
  """

  modules = []
  for filename, code, dependency_bindings in bundle:
    module = ModuleType(filename)
    module.__file__ = filename
    namespace = object.__getattribute__(module, "__dict__")
    namespace.update(_module_bindings(modules, dependency_bindings))
    exec(code, namespace)
    modules.append(module)

  return _module_bindings(modules, bindings)
