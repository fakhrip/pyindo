import sys


EX_USAGE = 64
EX_NOINPUT = 66
EX_SOFTWARE = 70


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
