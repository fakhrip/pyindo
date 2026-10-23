import operator
from collections.abc import Sequence
from reprlib import recursive_repr

from pyindo.types import SCALAR_TYPES, TypeSpec, format_type
from pyindo.values import _FrozenList, _list_operand, freeze_constant_value


def _mismatch(value: object, type_spec: TypeSpec, context: str, path: str) -> TypeError:
  """
  Describe a failed contract without invoking an arbitrary value's repr.
  """

  return TypeError(
    f"Expected {format_type(type_spec)}, got {type(value).__name__} for {context}{path}"
  )


def _prepare(value, type_spec, context, path, completed):
  """
  Prepare governed list nodes iteratively, sharing results within this conversion.

  Any edges deliberately stop traversal. Checked objects retain their invariant
  contracts; frozen objects need structural validation but never become mutable.
  """

  pending = [(value, type_spec, path, False)]
  results = []

  while pending:
    current, spec, current_path, children_ready = pending.pop()

    if spec == "apapun":
      results.append(current)
      continue

    if isinstance(spec, str):
      if type(current) is not SCALAR_TYPES[spec]:
        raise _mismatch(current, spec, context, current_path)
      results.append(current)
      continue

    if type(current) is _CheckedList:
      if current._element_type != spec[1]:
        raise _mismatch(current, spec, context, current_path)
      results.append(current)
      continue

    if type(current) not in (list, _FrozenList):
      raise _mismatch(current, spec, context, current_path)

    key = (id(current), spec)
    items = current if type(current) is list else current._items

    if children_ready:
      count = len(items)
      prepared = results[-count:] if count else []
      if count:
        del results[-count:]
      result = _CheckedList(prepared, spec[1], context + current_path) if type(current) is list else current
      completed[key] = result
      results.append(result)
    elif key in completed:
      results.append(completed[key])
    else:
      pending.append((current, spec, current_path, True))
      pending.extend(
        (items[index], spec[1], f"{current_path}[{index}]", False)
        for index in range(len(items) - 1, -1, -1)
      )

  return results[0]


def prepare_typed_value(value: object, type_spec: TypeSpec, context: str) -> object:
  """
  Check a scalar or create an owned checked copy along explicitly typed paths.
  """

  return _prepare(value, type_spec, context, "", {})


def prepare_typed_constant(value: object, type_spec: TypeSpec, context: str) -> object:
  """
  Freeze first so Any never weakens constant eligibility or cycle detection.
  """

  return prepare_typed_value(freeze_constant_value(value), type_spec, context)


class _CheckedList(Sequence):
  """
  Own mutable list storage whose incoming elements obey one invariant contract.

  Composition prevents native list methods from bypassing validation. Conversions
  and batch writes share a local memo, never a registry retaining raw originals.
  """

  __slots__ = ("_items", "_element_type", "_context")
  __hash__ = None

  def __init__(self, items, element_type, context):
    self._items = items
    self._element_type = element_type
    self._context = context

  def __len__(self):
    return len(self._items)

  def __iter__(self):
    return iter(self._items)

  def __reversed__(self):
    return reversed(self._items)

  def __contains__(self, value):
    return value in self._items

  def __getitem__(self, index):
    return self._items[index]

  @recursive_repr(fillvalue="[...]")
  def __repr__(self):
    return repr(self._items)

  def _prepare_batch(self, values):
    """
    Materialize and check the entire incoming batch before changing storage.
    """

    incoming = list(values)
    completed = {}
    return [
      _prepare(value, self._element_type, self._context, f"[{index}]", completed)
      for index, value in enumerate(incoming)
    ]

  def __setitem__(self, index, value):
    """
    Resolve index errors once before checking values, then commit atomically.
    """

    if isinstance(index, slice):
      # Mark inserted slots so native slice validation runs exactly once.
      candidate = self._items.copy()
      incoming = []
      markers = []

      def marked_values():
        for item in value:
          marker = object()
          incoming.append(item)
          markers.append(marker)
          yield marker

      candidate[index] = marked_values()
      prepared = self._prepare_batch(incoming)
      replacements = {id(marker): item for marker, item in zip(markers, prepared)}
      self._items[:] = [replacements.get(id(item), item) for item in candidate]
      return

    normalized = operator.index(index)
    # Reading storage validates bounds without running the user's index again.
    self._items[normalized]
    prepared = _prepare(value, self._element_type, self._context, f"[{normalized}]", {})
    self._items[normalized] = prepared

  def __delitem__(self, index):
    del self._items[index]

  def append(self, value):
    self._items.extend(self._prepare_batch([value]))

  def insert(self, index, value):
    normalized = operator.index(index)
    prepared = self._prepare_batch([value])[0]
    self._items.insert(normalized, prepared)

  def extend(self, values):
    self._items.extend(self._prepare_batch(values))

  def pop(self, index=-1):
    return self._items.pop(index)

  def remove(self, value):
    self._items.remove(value)

  def clear(self):
    self._items.clear()

  def reverse(self):
    self._items.reverse()

  def sort(self, *, key=None, reverse=False):
    self._items.sort(key=key, reverse=reverse)

  def copy(self):
    return self._items.copy()

  def count(self, value):
    return self._items.count(value)

  def index(self, value, *bounds):
    return self._items.index(value, *bounds)

  def __iadd__(self, values):
    self.extend(values)
    return self

  def __imul__(self, count):
    self._items *= count
    return self

  def _compare(self, other, operation):
    other = _list_operand(other)
    return NotImplemented if other is NotImplemented else operation(self._items, other)

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
    other = _list_operand(other)
    return NotImplemented if other is NotImplemented else self._items + other

  def __radd__(self, other):
    other = _list_operand(other)
    return NotImplemented if other is NotImplemented else list.__add__(other, self._items)

  def __mul__(self, count):
    return self._items * count

  def __rmul__(self, count):
    return list.__rmul__(self._items, count)
