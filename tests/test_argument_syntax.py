import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Binary, Call
from pyindo.resolver import FunctionSignature, analyze_program
from pyindo.syntax import parse_module


class KeywordSyntaxTests(unittest.TestCase):
  def expression(self, text):
    """
    Inspect argument syntax without assembling or running new call bytecode.
    """

    return parse_module(f"fungsi utama(): apapun {{ hasilkan {text}; }}").functions[0].body[0].value

  def test_keyword_nodes_preserve_positional_and_written_named_order(self):
    call = self.expression("f(1, c=mark(3), b=mark(2))")
    self.assertEqual([value.value for value in call.arguments], [1])
    self.assertEqual([keyword.name for keyword in call.keywords], ["c", "b"])
    self.assertEqual(call.keywords[0].value.callee, "mark")
    self.assertIsInstance(self.expression("f(a == b)").arguments[0], Binary)
    self.assertEqual(self.expression("f(kosong=1, kasus=2)").keywords[0].name, "kosong")
    first, second = Call("f", [], call.span), Call("f", [], call.span)
    first.keywords.append(call.keywords[0])
    self.assertEqual(second.keywords, [])

  def test_keyword_values_keep_expression_boundaries_and_spans(self):
    source = 'fungsi utama(): apapun { hasilkan "café ☕ ${state.f(value=1 < 2 < 3, other=[g(x=1) jika benar selainnya 0][0])}"; }'.replace("; }", ";\r\n}")
    call = parse_module(source).functions[0].body[0].value.parts[1]
    self.assertEqual(call.callee, "state.f")
    self.assertEqual(source[call.keywords[0].span.start:call.keywords[0].span.end], "value=1 < 2 < 3")
    self.assertEqual(source[call.keywords[0].value.span.start:call.keywords[0].value.span.end], "1 < 2 < 3")
    self.assertTrue(source[call.span.start:call.span.end].endswith("][0])"))
    for text in ("f(a=)", "f(a=1, 2)", "f(a=1, a=2)", "f(a=1,)", "f(1,)",
                 'f("a"=1)', "f(state.a=1)", "f(*items)", "f(**items)", "f((a=1))"):
      with self.subTest(text=text), self.assertRaises(PyIndoError) as raised:
        self.expression(text)
      self.assertIsNotNone(raised.exception.span)
    for suffix in ("f(a=", "f(a=1,", "f(a=1"):
      source = "fungsi utama(): apapun { hasilkan " + suffix
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError) as raised:
        parse_module(source)
      self.assertEqual(raised.exception.span.start, len(source))

  def test_keyword_binding_rejects_unknown_duplicate_missing_and_excess_slots(self):
    definition = "fungsi f(a: apapun, b: apapun): apapun {} "
    for text in ("f(a=1)", "f(a=1, unknown=2)", "f(1, a=2, b=3)", "f(1, 2, 3, b=4)", "tampilkan(end=1)"):
      with self.subTest(text=text), self.assertRaises(PyIndoError):
        analyze_program(parse_module(definition + f"fungsi utama(): apapun {{ hasilkan {text}; }}"))
    program = parse_module(definition + "fungsi utama(): apapun { hasilkan f(b=2, a=1); }")
    analyze_program(program)
    call = program.functions[1].body[0].value
    call.keywords.append(call.keywords[0])
    with self.assertRaises(PyIndoError):
      analyze_program(program)
    for callee in ("renamed", "state.f"):
      program = parse_module(f"fungsi utama(): apapun {{ hasilkan {callee}(b=2, a=1); }}")
      signature = FunctionSignature("original", ["a", "b"], program.span)
      analyze_program(program, imported_signatures={callee: signature}, namespace_names={"state"})
      program.functions[0].body[0].value.keywords[0] = self.expression("f(wrong=2)").keywords[0]
      with self.assertRaises(PyIndoError):
        analyze_program(program, imported_signatures={callee: signature}, namespace_names={"state"})

  def test_keyword_values_keep_static_source_order_and_old_arity_contract(self):
    definition = "fungsi f(a: apapun, b: apapun): apapun {} "
    for text, message in (("f(missing_first, b=missing_second)", "missing_first"),
                          ("f(b=missing_first, a=missing_second)", "missing_first"),
                          ("benar atau f(a=1, b=unknown())", "Unknown function"),
                          ("f(a=1, b=later)", "not initialized"),
                          ("f(a=1, b=f())", "expects 2 arguments"),
                          ("f()", "expects 2 arguments")):
      source = definition + f"fungsi utama(): apapun {{ hasilkan {text}; variabel later: desimal = 1; }}"
      with self.subTest(text=text), self.assertRaisesRegex(PyIndoError, message):
        analyze_program(parse_module(source))
