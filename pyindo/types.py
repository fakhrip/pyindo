from pyindo.diagnostics import PyIndoError
from pyindo.nodes import TypeAnnotation


class LiteralString(str):
    def __init__(self):
        pass


type TypeSpec = str | tuple[str, TypeSpec]

SCALAR_TYPES = {
  "desimal": int,
  "pecahan": float,
  "campuran": str,
  "logika": bool,
  "kosong": type(None),
}


def format_type(type_spec: TypeSpec) -> str:
  """
  Render a normalized descriptor without recursing through nested list types.
  """

  depth = 0

  while isinstance(type_spec, tuple):
    depth += 1
    type_spec = type_spec[1]

  return "himpunan<" * depth + type_spec + ">" * depth


def allows_none(type_spec: TypeSpec) -> bool:
  """
  Identify the two contracts that permit a function to fall through.
  """

  return type_spec in ("apapun", "kosong")


def resolve_type(annotation: TypeAnnotation) -> TypeSpec:
  """
  Validate source annotations and produce only marshal-safe normalized values.
  """

  if annotation.name == "himpunan":
    if len(annotation.arguments) != 1:
      raise PyIndoError("Type 'himpunan' requires one type argument", annotation.span)
    return ("himpunan", resolve_type(annotation.arguments[0]))

  name = "desimal" if annotation.name == "angka" else annotation.name
  if name not in SCALAR_TYPES and name != "apapun":
    raise PyIndoError(f"Unknown type: {annotation.name}", annotation.span)
  if annotation.arguments:
    raise PyIndoError(f"Type '{annotation.name}' does not take type arguments", annotation.span)
  return name
