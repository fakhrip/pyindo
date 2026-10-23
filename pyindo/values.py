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
    if isinstance(other, _FrozenList):
      other = list(other._items)
    elif not isinstance(other, list):
      return NotImplemented

    # Native concatenation copies list storage, without invoking its iterator.
    return list(self._items) + other

  def __radd__(self, other):
    if isinstance(other, _FrozenList):
      other = list(other._items)
    elif not isinstance(other, list):
      return NotImplemented

    return list.__add__(other, list(self._items))

  def __mul__(self, count):
    return list(self._items) * count

  def __rmul__(self, count):
    # The left operand already declined multiplication; do not reflect it again.
    return list.__rmul__(list(self._items), count)


def _freeze_value(value: object, completed: dict[int, _FrozenList], active: set[int]) -> object:
  """
  Visit a supported graph without depending on Python's call-stack limit.

  Exit frames build parents only after their children. Active identities mark
  the current path; completed identities reuse shared acyclic snapshots.
  """

  pending = [(value, False)]

  while pending:
    current, children_ready = pending.pop()

    if type(current) in (type(None), bool, int, float, complex, str, _FrozenList):
      continue

    if type(current) is not list:
      raise TypeError(f"Unsupported value in constant snapshot: {type(current).__name__}")

    identity = id(current)

    if children_ready:
      frozen_items = tuple(
        completed[id(item)] if type(item) is list else item for item in current
      )
      completed[identity] = _FrozenList(frozen_items)
      active.remove(identity)
    elif identity in active:
      raise TypeError("Cannot freeze a cyclic collection")
    elif identity not in completed:
      active.add(identity)
      pending.append((current, True))
      # Reverse the work stack to validate children in their original order.
      pending.extend((item, False) for item in reversed(current))

  return completed[id(value)] if type(value) is list else value


def freeze_constant_value(value: object) -> object:
  """
  Return a deeply immutable snapshot, leaving mutable originals independent.

  Memoization belongs to this conversion only. No registry retains originals
  after the snapshot is built, and a failed conversion cannot poison another.
  """

  return _freeze_value(value, {}, set())
