import os
from dataclasses import dataclass
from pathlib import Path

from bytecode import Bytecode

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, PyIndoError
from pyindo.emitter import compile_program
from pyindo.nodes import Import, Program
from pyindo.resolver import RESERVED_FUNCTION_NAMES, FunctionSignature, ValueBinding, analyze_program
from pyindo.syntax import parse_module


@dataclass(frozen=True)
class CompiledModule:
  index: int
  exports: dict[str, FunctionSignature | ValueBinding]


class ModuleGraph:
  """
  Resolve a local dependency graph for one compilation, never executing its code.
  """

  def __init__(self):
    self.bundle = []
    self.completed: dict[str, CompiledModule] = {}
    self.active: dict[str, str] = {}

  def dependency(self, declaration: Import, filename: str) -> CompiledModule:
    """
    Canonicalize a path, detect active cycles, and compile a library exactly once.
    """

    try:
      base = Path.cwd() if filename.startswith("<") and filename.endswith(">") else Path(filename).resolve().parent
      path = (base / declaration.path).resolve()
      if path.suffix != ".pyind":
        raise ValueError("Module path requires the .pyind extension")
      key = os.path.normcase(str(path))
    except (OSError, ValueError, RuntimeError) as path_error:
      raise PyIndoError(
        f"Could not import {declaration.path!r}: {path_error}", declaration.path_span, filename=filename,
      ) from path_error

    if key in self.active:
      chain = " -> ".join([*self.active.values(), str(path)])
      raise PyIndoError(f"Cyclic import: {chain}", declaration.path_span, filename=filename)
    if key in self.completed:
      return self.completed[key]

    try:
      source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as input_error:
      raise PyIndoError(
        f"Could not import {declaration.path!r}: {input_error}", declaration.path_span, filename=filename,
      ) from input_error

    self.active[key] = str(path)
    try:
      program = parse_module(source)
      bytecode, exports, bindings = self.build(program, str(path), is_library=True)
      compiled = CompiledModule(len(self.bundle), exports)
      self.bundle.append((str(path), bytecode.to_code(), bindings))
      self.completed[key] = compiled
      return compiled
    except PyIndoError as error:
      if error.filename is None:
        error.filename = str(path)
      raise
    finally:
      self.active.pop(key)

  def build(self, program: Program, filename: str, *, is_library: bool):
    """
    Classify owned exports before checking calls, live value reads and bindings.
    """

    signatures = {}
    imported_values = {}
    namespaces = set()
    aliases = set()
    bindings = []
    local_names = {function.name for function in program.functions} | {
      declaration.name for declaration in program.declarations
    }

    def claim(alias, span):
      """
      Reject ambiguity before an imported binding can enter a module's globals.
      """

      if alias in aliases or alias in local_names or alias in RESERVED_FUNCTION_NAMES | {"utama"}:
        raise PyIndoError(f"Import alias {alias!r} conflicts with an existing or reserved name", span, filename=filename)
      aliases.add(alias)

    for declaration in program.imports:
      dependency = self.dependency(declaration, filename)
      if declaration.namespace is not None:
        alias = declaration.namespace
        claim(alias, declaration.span)
        namespaces.add(alias)
        bindings.append((alias, dependency.index, None))
        for name, exported in dependency.exports.items():
          target = imported_values if isinstance(exported, ValueBinding) else signatures
          target[f"{alias}.{name}"] = exported
      else:
        for binding in declaration.bindings:
          claim(binding.alias, binding.span)
          if binding.name not in dependency.exports:
            raise PyIndoError(
              f"Module {declaration.path!r} does not export {binding.name!r}",
              binding.span, filename=filename,
            )
          exported = dependency.exports[binding.name]
          target = imported_values if isinstance(exported, ValueBinding) else signatures
          target[binding.alias] = exported
          bindings.append((binding.alias, dependency.index, binding.name))

    symbols = analyze_program(
      program, imported_signatures=signatures, namespace_names=namespaces,
      require_entrypoint=not is_library,
      imported_values=imported_values,
    )
    bytecode = compile_program(
      program, filename=filename, symbols=symbols, is_library=is_library,
      module_bundle=tuple(self.bundle) if not is_library else (),
      import_bindings=tuple(bindings) if not is_library else (),
    )
    exports = {function.name: symbols.signatures[function.name] for function in program.functions}
    exports.update(symbols.module_values)
    return bytecode, exports, tuple(bindings)


def compile_module_graph(source_text: str, *, filename: str = "<pyindo>") -> Bytecode:
  """
  Bundle local imports with isolated globals while preserving the single-file API.
  """

  program = parse_module(source_text)
  if not program.imports:
    return compile_program(program, filename=filename)

  graph = ModuleGraph()
  try:
    if not (filename.startswith("<") and filename.endswith(">")):
      graph.active[os.path.normcase(str(Path(filename).resolve()))] = filename
    return graph.build(program, filename, is_library=False)[0]
  except PyIndoError as error:
    if error.filename is None:
      error.filename = filename
    raise
  except (RecursionError, OSError, ValueError) as graph_error:
    message = COMPLEXITY_ERROR_MESSAGE if isinstance(graph_error, RecursionError) else str(graph_error)
    raise PyIndoError(message, program.imports[0].span, filename=filename) from graph_error
