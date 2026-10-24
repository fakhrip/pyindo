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


class DefaultSyntaxTests(unittest.TestCase):
  def test_typed_default_signatures_keep_expressions_and_generic_closers(self):
    from dataclasses import replace
    from pyindo.nodes import Literal, Parameter

    source = '''fungsi f(a: desimal, b: desimal = a,
  rows: himpunan<himpunan<desimal>>=[[1]],
  value: apapun = helper(value=1 < 2 < 3 jika benar selainnya salah)): apapun {}
fungsi helper(value: apapun): apapun { hasilkan value; }
fungsi utama(): kosong {}'''
    program = parse_module(source)
    parameters = program.functions[0].parameters
    self.assertIsNone(parameters[0].default)
    self.assertEqual(parameters[1].default.identifier, "a")
    self.assertEqual(source[parameters[2].default.span.start:parameters[2].default.span.end], "[[1]]")
    self.assertEqual(parameters[3].default.callee, "helper")
    self.assertIsNone(Parameter("old", program.span).default)
    self.assertEqual(FunctionSignature("old", [], program.span).default_count, 0)
    self.assertEqual(FunctionSignature("old", [], program.span, (), "kosong").default_count, 0)
    embedded = parse_module("fungsi f(value: apapun): apapun { hasilkan value; } fungsi utama(): kosong {}")
    original = embedded.functions[0].parameters[0]
    embedded.functions[0].parameters[0] = replace(original, default=Literal(None, original.span))
    self.assertEqual(analyze_program(embedded).signatures["f"].default_count, 1)
    for signature in ("a = 1", "a: apapun =", "a: apapun = 1, b: apapun", "a: apapun = 1,",
                      "*a: apapun", "a: apapun, *, b: apapun", "a: apapun, /", "**a: apapun"):
      with self.subTest(signature=signature), self.assertRaises(PyIndoError):
        parse_module(f"fungsi f({signature}): apapun {{}} fungsi utama(): kosong {{}}")
    embedded = parse_module("fungsi f(a: apapun, b: apapun): apapun {} fungsi utama(): kosong {}")
    original = embedded.functions[0].parameters[0]
    embedded.functions[0].parameters[0] = replace(original, default=Literal(1, original.span))
    with self.assertRaisesRegex(PyIndoError, "default"):
      analyze_program(embedded)
    for suffix in ("fungsi f(a: apapun =", "fungsi f(a: apapun = helper(value="):
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError) as raised:
        parse_module(suffix)
      self.assertEqual(raised.exception.span.start, len(suffix))

  def test_defaults_validate_earlier_parameters_and_all_skipped_expressions(self):
    for default in ("value", "later", "local", "missing", "unknown()", "helper()",
                    "helper(wrong=1)", "1 jika benar selainnya missing"):
      source = f'''fungsi helper(value: apapun): apapun {{ hasilkan value; }}
fungsi f(value: apapun = {default}, later: apapun = 2): apapun {{ variabel local: apapun = 1; }}
fungsi utama(): kosong {{ f(value=1, later=2); }}'''
      with self.subTest(default=default), self.assertRaises(PyIndoError):
        analyze_program(parse_module(source))
    source = '''variabel global_value: desimal = 2;
fungsi f(first: desimal = global_value, second: desimal = first + 1): desimal { hasilkan second; }
fungsi utama(): kosong {}'''
    self.assertEqual(analyze_program(parse_module(source)).signatures["f"].default_count, 2)
    with self.assertRaisesRegex(PyIndoError, "missing_first"):
      analyze_program(parse_module("fungsi f(a: apapun = missing_first, b: apapun = missing_last): apapun {} fungsi utama(): kosong {}"))

  def test_default_count_binding_and_entrypoint_shapes(self):
    definition = "fungsi f(a: desimal, b: desimal = 2, c: desimal = 3): desimal { hasilkan a + b + c; } "
    for call in ("f(1)", "f(c=4, a=1)", "f(1, c=4)", "f(1, 2, 3)"):
      with self.subTest(call=call):
        self.assertEqual(analyze_program(parse_module(definition + f"fungsi utama(): kosong {{ tampilkan({call}); }}")).signatures["f"].default_count, 2)
    for call in ("f()", "f(c=1)", "f(1, 2, 3, 4)", "f(1, a=2)"):
      with self.subTest(call=call), self.assertRaises(PyIndoError):
        analyze_program(parse_module(definition + f"fungsi utama(): kosong {{ tampilkan({call}); }}"))
    for signature in ("value: apapun = 1", "args: himpunan<campuran> = [], count: campuran = ''"):
      with self.subTest(signature=signature), self.assertRaises(PyIndoError):
        analyze_program(parse_module(f"fungsi utama({signature}): kosong {{}}"))
    analyze_program(parse_module("fungsi utama(args: himpunan<campuran> = [], count: desimal = 0): kosong {}"))
    analyze_program(parse_module("fungsi utama(value: desimal = 1): desimal { hasilkan value; }"), require_entrypoint=False)
