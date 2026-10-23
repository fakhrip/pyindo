import unittest

from tests.fixture_runner import (
  REPOSITORY_PATH,
  assert_program_result,
  discover_pairs,
  run_program,
)


class OriginalFixtureTests(unittest.TestCase):
  def test_all_original_inputs_and_outputs_are_paired(self):
    success_pairs = discover_pairs(REPOSITORY_PATH / "tests" / "success")
    error_pairs = discover_pairs(REPOSITORY_PATH / "tests" / "error")

    self.assertEqual(len(success_pairs), 11)
    self.assertEqual(len(error_pairs), 8)

  def test_implemented_success_fixtures(self):
    fixture_directory = REPOSITORY_PATH / "tests" / "success"

    for source_path, output_path in discover_pairs(fixture_directory):
      with self.subTest(fixture=source_path.name):
        expected_output = output_path.read_text(encoding="utf-8")

        assert_program_result(run_program(source_path), expected_output)

  def test_error_fixtures(self):
    fixture_directory = REPOSITORY_PATH / "tests" / "error"

    for source_path, output_path in discover_pairs(fixture_directory):
      with self.subTest(fixture=source_path.name):
        expected_output = output_path.read_text(encoding="utf-8")

        assert_program_result(run_program(source_path), expected_output, 70)
