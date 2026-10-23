import operator
import unittest

from pyindo.type_checks import prepare_typed_constant, prepare_typed_value
from pyindo.values import freeze_constant_value


INTS = ("himpunan", "desimal")
ROWS = ("himpunan", INTS)
ANY_ITEMS = ("himpunan", "apapun")
CONTEXT = "binding 'items' of 'main' on line 3"


class TypeChecksTests(unittest.TestCase):
  def test_exact_scalars_and_any(self):
    for value, spec in ((1, "desimal"), (1.5, "pecahan"), ("x", "campuran"),
                        (True, "logika"), (None, "kosong")):
      self.assertIs(prepare_typed_value(value, spec, CONTEXT), value)

    class Foreign(int):
      pass

    class NoRepr:
      def __repr__(self):
        raise AssertionError("error formatting called repr")

    arbitrary = NoRepr()
    self.assertIs(prepare_typed_value(arbitrary, "apapun", CONTEXT), arbitrary)
    for value, spec in ((True, "desimal"), (1, "pecahan"), (1, "campuran"),
                        (0, "logika"), (0, "kosong"), (Foreign(1), "desimal"),
                        (arbitrary, "desimal")):
      with self.subTest(spec=spec, actual=type(value).__name__):
        with self.assertRaisesRegex(TypeError, spec) as raised:
          prepare_typed_value(value, spec, CONTEXT)
        self.assertIn(CONTEXT, str(raised.exception))
        self.assertIn(type(value).__name__, str(raised.exception))

  def test_checked_aliases_and_descriptor_equivalence(self):
    original = [[1], [2]]
    checked = prepare_typed_value(original, ROWS, CONTEXT)
    original[0][0] = 9
    self.assertEqual(checked, [[1], [2]])
    equivalent = tuple(["himpunan", tuple(["himpunan", "desimal"])])
    self.assertIs(prepare_typed_value(checked, equivalent, CONTEXT), checked)
    self.assertIs(prepare_typed_value(checked, "apapun", CONTEXT), checked)
    with self.assertRaisesRegex(TypeError, r"\[0\]"):
      checked[0][0] = "bad"
    for values in (checked, prepare_typed_value([], ROWS, CONTEXT)):
      with self.assertRaises(TypeError):
        prepare_typed_value(values, ANY_ITEMS, CONTEXT)

  def test_copy_memo_and_any_edges(self):
    child = [1]
    original = [child, child]
    checked = prepare_typed_value(original, ROWS, CONTEXT)
    self.assertIs(checked[0], checked[1])
    self.assertIsNot(checked[0], prepare_typed_value(original, ROWS, CONTEXT)[0])
    unrestricted = prepare_typed_value(original, ANY_ITEMS, CONTEXT)
    self.assertIs(unrestricted[0], child)
    child[0] = "allowed"
    self.assertEqual(unrestricted, [["allowed"], ["allowed"]])

    class ForeignList(list):
      def __iter__(self):
        raise AssertionError("must not adapt foreign collection")

    for value in ((), {}, ForeignList([1]), object()):
      with self.assertRaises(TypeError):
        prepare_typed_value(value, INTS, CONTEXT)

  def test_checked_list_protocols(self):
    checked = prepare_typed_value([1, 2], INTS, CONTEXT)
    frozen = freeze_constant_value([1, 2])
    for other in ([1, 2], frozen, prepare_typed_value([1, 2], INTS, CONTEXT)):
      for operation in (operator.eq, operator.ne, operator.lt, operator.le,
                        operator.gt, operator.ge):
        self.assertEqual(operation(checked, other), operation([1, 2], [1, 2]))
        self.assertEqual(operation(other, checked), operation([1, 2], [1, 2]))
      self.assertEqual(checked + other, [1, 2, 1, 2])
      self.assertEqual(other + checked, [1, 2, 1, 2])
    self.assertEqual(repr(checked), "[1, 2]")
    self.assertEqual(list(reversed(checked)), [2, 1])
    self.assertEqual(checked[-1], 2)
    self.assertEqual(checked[True], 2)
    self.assertIn(2, checked)
    self.assertTrue(checked)
    self.assertFalse(prepare_typed_value([], INTS, CONTEXT))
    with self.assertRaises(TypeError):
      hash(checked)
    for result in (checked[:], checked.copy(), checked * 2, 2 * checked):
      self.assertIs(type(result), list)
    self.assertEqual(checked.count(1), 1)
    self.assertEqual(checked.index(2), 1)
    checked.insert(0, 3)
    checked.append(4)
    checked.extend([5, 6])
    checked += [7]
    checked *= 1
    checked.reverse()
    checked.sort()
    checked.remove(1)
    self.assertEqual(checked.pop(), 7)
    del checked[0]
    checked.clear()
    self.assertEqual(checked, [])
    nan = float("nan")
    values = prepare_typed_value([nan], ANY_ITEMS, CONTEXT)
    self.assertIn(nan, values)
    self.assertEqual(values, [nan])

  def test_checked_mutations_are_atomic(self):
    def failing_iterator():
      yield 3
      raise ValueError("iterator failed")

    mutations = (
      lambda values: values.append("bad"),
      lambda values: values.insert(0, "bad"),
      lambda values: values.extend([3, "bad"]),
      lambda values: values.__iadd__([3, "bad"]),
      lambda values: values.__setitem__(slice(None), [3, "bad"]),
      lambda values: values.extend(failing_iterator()),
    )
    for mutation in mutations:
      checked = prepare_typed_value([1, 2], INTS, CONTEXT)
      with self.assertRaises((TypeError, ValueError)):
        mutation(checked)
      self.assertEqual(checked, [1, 2])
    rows = prepare_typed_value([], ROWS, CONTEXT)
    child = [1]
    rows.extend([child, child])
    self.assertIs(rows[0], rows[1])
    child[0] = 9
    self.assertEqual(rows, [[1], [1]])

  def test_index_failure_precedes_value_check_once(self):
    class Index:
      def __init__(self, value):
        self.value = value
        self.calls = 0

      def __index__(self):
        self.calls += 1
        return self.value

    values = prepare_typed_value([1], INTS, CONTEXT)
    for number, error in ((0, TypeError), (5, IndexError)):
      index = Index(number)
      with self.assertRaises(error):
        values[index] = "bad"
      self.assertEqual(index.calls, 1)
      self.assertEqual(values, [1])
    trace = []

    class SliceIndex:
      def __init__(self, label, number):
        self.label = label
        self.number = number

      def __index__(self):
        trace.append(self.label)
        return self.number

    key = slice(SliceIndex("start", 0), SliceIndex("stop", 1), SliceIndex("step", 1))
    native = [1]
    native[key] = [2]
    expected = trace[:]
    trace.clear()
    values[key] = [2]
    self.assertEqual(trace, expected)
    self.assertEqual(values, native)

  def test_insert_rejects_oversized_indices_before_values(self):
    values = prepare_typed_value([1], INTS, CONTEXT)
    for index in (10 ** 100, -(10 ** 100)):
      with self.assertRaises(OverflowError):
        values.insert(index, "bad")
      self.assertEqual(values, [1])

  def test_typed_frozen_values_and_checked_snapshots(self):
    checked = prepare_typed_value([[1]], ROWS, CONTEXT)
    frozen = prepare_typed_constant(checked, ROWS, CONTEXT)
    checked[0][0] = 9
    self.assertEqual(frozen, [[1]])
    self.assertIs(prepare_typed_value(frozen, ROWS, CONTEXT), frozen)
    with self.assertRaises(TypeError):
      frozen[0][0] = 2
    for value in (object(), {}, (), [object()]):
      with self.assertRaisesRegex(TypeError, "Unsupported value"):
        prepare_typed_constant(value, "apapun", CONTEXT)

  def test_slice_callbacks_keep_their_storage_side_effects(self):
    def mutate(values, use_index):
      class Index:
        def __index__(self):
          values.append(3)
          return 0

      class Incoming:
        def __iter__(self):
          values.append(4)
          yield 9

      values[slice(Index() if use_index else 0, 1)] = Incoming()
      return list(values)

    for use_index in (False, True):
      with self.subTest(use_index=use_index):
        self.assertEqual(
          mutate(prepare_typed_value([1, 2], INTS, CONTEXT), use_index),
          mutate([1, 2], use_index),
        )

    checked = prepare_typed_value([0, 1, 2], INTS, CONTEXT)

    def incoming():
      checked.extend([3, 4])
      yield 9
      yield 8

    with self.assertRaises(ValueError):
      checked[::2] = incoming()
    self.assertEqual(checked, [0, 1, 2, 3, 4])

  def test_slice_iterator_hints_follow_native_protocol(self):
    def assign(values):
      trace = []

      class Iterator:
        def __iter__(self):
          trace.append("iterator.iter")
          return self

        def __length_hint__(self):
          trace.append("iterator.hint")
          return 0

        def __next__(self):
          trace.append("next")
          raise StopIteration

      class Incoming:
        def __iter__(self):
          trace.append("incoming.iter")
          return Iterator()

        def __len__(self):
          raise AssertionError("slice must use the iterator's length hint")

      values[:] = Incoming()
      return trace

    self.assertEqual(assign(prepare_typed_value([1], INTS, CONTEXT)), assign([1]))

  def test_any_cycles_and_shared_deep_graphs(self):
    checked = prepare_typed_value([0], ANY_ITEMS, CONTEXT)
    checked[0] = checked
    self.assertIn("...", repr(checked))
    with self.assertRaisesRegex(TypeError, "cyclic collection"):
      prepare_typed_constant(checked, "apapun", CONTEXT)
    raw = [0]
    mixed = prepare_typed_value([raw], ANY_ITEMS, CONTEXT)
    raw[0] = mixed
    with self.assertRaisesRegex(TypeError, "cyclic collection"):
      freeze_constant_value(mixed)
    deep = [1]
    for _ in range(1201):
      deep = prepare_typed_value([deep], ANY_ITEMS, CONTEXT)
    snapshot = freeze_constant_value(deep)
    for _ in range(1201):
      snapshot = snapshot[0]
    self.assertEqual(snapshot, [1])
