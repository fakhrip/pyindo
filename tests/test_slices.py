import unittest

from pyindo import runtime


class InclusiveSliceKeyTests(unittest.TestCase):
  def setUp(self):
    self.assertTrue(hasattr(runtime, "make_inclusive_slice"), "inclusive slice key constructor is missing")
    self.key = runtime.make_inclusive_slice

  def test_inclusive_keys_require_both_forward_bounds(self):
    values = [0, 1, 2, 3, 4]
    for start, stop, expected in ((1, 3, [1, 2, 3]), (0, -1, values),
                                  (-3, -1, [2, 3, 4]), (3, 1, []), (2, 2, [2])):
      with self.subTest(start=start, stop=stop):
        self.assertEqual(values[self.key(start, stop)], expected)
    self.assertEqual("café ☕"[self.key(3, 5)], "é ☕")

  def test_inclusive_key_matrix_matches_closed_interval_model(self):
    for length in range(7):
      values = list(range(length))
      bounds = [*range(-10, 11), -(10 ** 100), 10 ** 100]
      for start in bounds:
        for stop in bounds:
          # Walk valid indices against the inclusive end, independently of the
          # runtime helper's conversion to an exclusive Python slice stop.
          first = start + length if start < 0 else start
          last = stop + length if stop < 0 else stop
          first = min(max(first, 0), length)
          expected = [index for index in range(first, length) if index <= last]
          self.assertEqual(values[self.key(start, stop)], expected, (length, start, stop))

  def test_key_protocols_run_once_in_start_stop_order(self):
    events = []
    values = [0, 1, 2]

    class Bound:
      def __init__(self, label, value, fails=False):
        self.label, self.value, self.fails = label, value, fails

      def __index__(self):
        events.append(self.label)
        values.append(3)
        if self.fails:
          raise RuntimeError(self.label)
        return self.value

      def __eq__(self, other):
        raise AssertionError("bound equality was used")

      def __bool__(self):
        raise AssertionError("bound truth was used")

    self.assertEqual(values[self.key(Bound("start", 1), Bound("stop", -1))], [1, 2, 3, 3])
    self.assertEqual(events, ["start", "stop"])
    for first_fails, expected in ((True, ["start"]), (False, ["start", "stop"])):
      events.clear()
      with self.assertRaisesRegex(RuntimeError, expected[-1]):
        self.key(Bound("start", 0, first_fails), Bound("stop", 1, True))
      self.assertEqual(events, expected)

  def test_key_native_types_and_extreme_values_preserve_errors(self):
    self.assertEqual([0, 1, 2][self.key(False, True)], [0, 1])
    self.assertEqual([0, 1, 2][self.key(-(10 ** 100), 10 ** 100)], [0, 1, 2])
    for invalid in (None, 1.5, "1", object()):
      for bounds in ((invalid, 1), (0, invalid)):
        with self.subTest(bounds=bounds), self.assertRaises(TypeError):
          self.key(*bounds)
    for arguments in ((), (0,), (0, 1, 2)):
      with self.assertRaises(TypeError):
        self.key(*arguments)
