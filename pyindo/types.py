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
