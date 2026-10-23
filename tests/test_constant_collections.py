import operator
import unittest

from pyindo.values import freeze_constant_value
from tests.fixture_runner import assert_program_result, run_python, run_source


class ConstantCollectionTests(unittest.TestCase):
  def test_compiled_constant_snapshots_are_detached_and_protected(self):
    source = """fungsi snapshot(value) { konstanta saved = value; hasilkan saved; }
fungsi __pyindo_freeze_constant__() { hasilkan 22; }
fungsi utama() { tampilkan(__pyindo_freeze_constant__()); }
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "original = [[1]]\n"
      "saved = namespace['snapshot'](original)\n"
      "original[0][0] = 9\n"
      "assert saved == [[1]] and original == [[9]]\n"
      "try:\n"
      "  saved[0][0] = 7\n"
      "except TypeError:\n"
      "  pass\n"
      "else:\n"
      "  raise AssertionError('mutable nested constant')\n"
      "assert namespace['snapshot'](2 + 3j) == 2 + 3j\n"
    )
    assert_program_result(run_python(script), "")
    assert_program_result(run_source(source), "22")

  def test_snapshot_import_works_in_facade_and_marshal_round_trips(self):
    source = "fungsi make() { konstanta saved = [[1]]; hasilkan saved; } fungsi utama() {}"
    script = (
      "import marshal\n"
      "from pyindo.compiler import compile_source, compile_bytecodes\n"
      "from pyindo.parser import parse_program\n"
      f"source = {source!r}\n"
      "codes = [compile_source(source, filename='café.pyind')]\n"
      "for sentinel in ('', '\\0'):\n"
      "  instructions, chunks = parse_program(source + sentinel)\n"
      "  assert [chunk.co_name for chunk in chunks] == ['make', 'utama']\n"
      "  codes.append(compile_bytecodes(instructions, filename='café.pyind').to_code())\n"
      "for code in codes:\n"
      "  namespace = {'__name__': 'inspection'}\n"
      "  exec(marshal.loads(marshal.dumps(code)), namespace)\n"
      "  assert namespace['make']() == [[1]]\n"
      "  assert namespace['make'].__code__.co_filename == 'café.pyind'\n"
    )
    assert_program_result(run_python(script), "")

  def test_repeated_constant_declarations_take_new_snapshots(self):
    source = """fungsi utama() {
  untuk (variabel index = 0; index < 2; index++) {
    konstanta saved = [index];
    tampilkan(saved);
  }
}
"""
    assert_program_result(run_source(source), "[0][1]")

  def test_snapshot_is_deep_and_detached(self):
    original = [[1]]
    snapshot = freeze_constant_value(original)
    original[0][0] = 9

    self.assertEqual(str(snapshot), "[[1]]")
    self.assertEqual(original, [[9]])
    self.assertEqual(snapshot, [[1]])
    self.assertEqual([[1]], snapshot)
    with self.assertRaises(TypeError):
      snapshot[0][0] = 7
    with self.assertRaises(TypeError):
      del snapshot[0][0]
    with self.assertRaises(TypeError):
      snapshot[0] = [7]
    with self.assertRaises(TypeError):
      del snapshot[0]

  def test_supported_scalars_and_frozen_values_are_reused(self):
    for value in (None, False, True, 0, 123456789, 1.25, 2 + 3j, "café"):
      with self.subTest(value=value):
        self.assertIs(freeze_constant_value(value), value)

    snapshot = freeze_constant_value([1, [2]])
    self.assertIs(freeze_constant_value(snapshot), snapshot)

  def test_shared_lists_are_valid_but_cycles_are_rejected(self):
    shared = [1]
    snapshot = freeze_constant_value([shared, shared])

    self.assertIs(snapshot[0], snapshot[1])
    shared[0] = 9
    self.assertEqual(snapshot, [[1], [1]])

    cyclic = [None]
    cyclic[0] = cyclic
    with self.assertRaisesRegex(TypeError, "Cannot freeze a cyclic collection"):
      freeze_constant_value(cyclic)
    self.assertIs(cyclic[0], cyclic)
    self.assertEqual(freeze_constant_value([2]), [2])

  def test_unsupported_foreign_values_are_rejected(self):
    class MutableInteger(int):
      pass

    for value in ({}, set(), (), object(), MutableInteger(1)):
      with self.subTest(value=value):
        with self.assertRaises(TypeError):
          freeze_constant_value(value)
        with self.assertRaises(TypeError):
          freeze_constant_value([value])

  def test_reads_truth_membership_and_unhashability_match_lists(self):
    empty = freeze_constant_value([])
    snapshot = freeze_constant_value([3, [4], "é"])

    self.assertFalse(empty)
    self.assertTrue(snapshot)
    self.assertEqual(snapshot[-1], "é")
    self.assertEqual(snapshot[True], [4])
    self.assertIn([4], snapshot)
    self.assertNotIn(7, snapshot)
    with self.assertRaises(IndexError):
      _ = snapshot[3]
    with self.assertRaises(TypeError):
      _ = snapshot[1.5]
    with self.assertRaises(TypeError):
      hash(snapshot)

  def test_comparisons_match_mutable_lists_in_both_directions(self):
    operations = (operator.eq, operator.ne, operator.lt, operator.le, operator.gt, operator.ge)
    cases = ([], [1], [1, [2]], [1, [3]], [2])

    for left in cases:
      for right in cases:
        for operation in operations:
          with self.subTest(left=left, right=right, operation=operation.__name__):
            expected = operation(left, right)
            self.assertEqual(operation(freeze_constant_value(left), right), expected)
            self.assertEqual(operation(left, freeze_constant_value(right)), expected)
            self.assertEqual(operation(freeze_constant_value(left), freeze_constant_value(right)), expected)

    snapshot = freeze_constant_value([1])
    self.assertNotEqual(snapshot, (1,))
    self.assertNotEqual((1,), snapshot)
    with self.assertRaises(TypeError):
      _ = snapshot < 1
    with self.assertRaises(TypeError):
      _ = 1 < snapshot
    with self.assertRaises(TypeError):
      _ = freeze_constant_value([1]) < ["a"]

  def test_concatenation_and_repetition_produce_mutable_outer_lists(self):
    snapshot = freeze_constant_value([[1]])
    results = (snapshot + [2], [2] + snapshot, snapshot + snapshot, snapshot * 2, 2 * snapshot)

    for result in results:
      with self.subTest(result=result):
        self.assertIs(type(result), list)
        result.append(9)
        child = next(item for item in result if not isinstance(item, int))
        with self.assertRaises(TypeError):
          child[0] = 7

    self.assertEqual(snapshot, [[1]])
    self.assertEqual(snapshot * 0, [])
    self.assertEqual(snapshot * -2, [])
    with self.assertRaises(TypeError):
      _ = snapshot + (2,)
    with self.assertRaises(TypeError):
      _ = snapshot * 1.5

  def test_comparisons_keep_native_identity_and_complex_prefix_rules(self):
    nan = float("nan")
    snapshot = freeze_constant_value([nan])

    self.assertEqual(snapshot, [nan])
    self.assertLessEqual(snapshot, [nan])
    self.assertGreaterEqual(snapshot, [nan])
    self.assertNotEqual(snapshot, [float("nan")])
    self.assertLess(freeze_constant_value([1j, 0]), [1j, 1])
    with self.assertRaises(TypeError):
      _ = freeze_constant_value([1j]) < [2j]
