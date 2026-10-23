import operator
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, eq=False)
class _FrozenList(Sequence):
  """
  Hold a deeply frozen list snapshot without exposing mutable backing storage.

  Native list operations retain their identity/equality and ordering rules.
  Only the outer operands are converted; nested frozen elements stay protected.
  """

  _items: tuple
  __hash__ = None

  def __len__(self):
    return len(self._items)

  def __iter__(self):
    return iter(self._items)

  def __getitem__(self, index):
    if isinstance(index, slice):
      return _FrozenList(self._items[index])

    return self._items[index]

  def __repr__(self):
    return "[" + ", ".join(repr(item) for item in self._items) + "]"

  def __setitem__(self, index, value):
    raise TypeError("Cannot mutate a frozen collection")

  def __delitem__(self, index):
    raise TypeError("Cannot mutate a frozen collection")

  def _compare(self, other, operation):
    """
    Delegate comparisons to lists without accepting unrelated sequence types.
    """

    if isinstance(other, _FrozenList):
      other = list(other._items)
    elif not isinstance(other, list):
      return NotImplemented

    return operation(list(self._items), other)

  def __eq__(self, other):
    return self._compare(other, operator.eq)

  def __ne__(self, other):
    return self._compare(other, operator.ne)

  def __lt__(self, other):
    return self._compare(other, operator.lt)

  def __le__(self, other):
    return self._compare(other, operator.le)

  def __gt__(self, other):
    return self._compare(other, operator.gt)

  def __ge__(self, other):
    return self._compare(other, operator.ge)

  def __add__(self, other):
    if not isinstance(other, (list, _FrozenList)):
      return NotImplemented

    return list(self._items) + list(other)

  def __radd__(self, other):
    if not isinstance(other, (list, _FrozenList)):
      return NotImplemented

    return list(other) + list(self._items)

  def __mul__(self, count):
    return list(self._items) * count

  def __rmul__(self, count):
    return self * count


def _freeze_value(value: object, completed: dict[int, _FrozenList], active: set[int]) -> object:
  """
  Copy one supported value, distinguishing shared children from active cycles.
  """

  if type(value) in (type(None), bool, int, float, complex, str, _FrozenList):
    return value

  if type(value) is not list:
    raise TypeError(f"Unsupported value in constant snapshot: {type(value).__name__}")

  identity = id(value)

  if identity in active:
    raise TypeError("Cannot freeze a cyclic collection")

  if identity in completed:
    return completed[identity]

  active.add(identity)

  try:
    snapshot = _FrozenList(tuple(_freeze_value(item, completed, active) for item in value))
    completed[identity] = snapshot
    return snapshot
  finally:
    active.remove(identity)


def freeze_constant_value(value: object) -> object:
  """
  Return a deeply immutable snapshot, leaving mutable originals independent.

  Memoization belongs to this conversion only. No registry retains originals
  after the snapshot is built, and a failed conversion cannot poison another.
  """

  return _freeze_value(value, {}, set())

