import sys
import unittest
from pathlib import Path


def main(test_directory: Path | None = None) -> int:
  """
  Discover and run the regression suite, returning a failing process status
  when any test fails. An optional directory supports isolated runner tests.
  """

  if test_directory is None:
    test_directory = Path(__file__).resolve().parent / "tests"

  test_suite = unittest.defaultTestLoader.discover(
    str(test_directory), pattern="test_*.py"
  )
  test_result = unittest.TextTestRunner(verbosity=2).run(test_suite)

  return 0 if test_result.wasSuccessful() else 1


if __name__ == "__main__":
  sys.exit(main())
