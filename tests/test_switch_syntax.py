import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import FunctionSignature, ValueBinding, analyze_program
from pyindo.syntax import parse_module


class SwitchSyntaxTests(unittest.TestCase):
  def analyze(self, body, *, return_type="kosong"):
    """
    Check a complete function without assembling or executing switch bytecode.
    """

    return analyze_program(parse_module(f"fungsi utama(): {return_type} {{ {body} }}"))

  def test_switch_nodes_keep_expression_order_and_spans(self):
    source = '''fungsi utama(): kosong {
  cocokkan ("café") {
    kasus "teh", "café" jika benar selainnya "air" {
      cocokkan (1) { kasus 1 {} }
    }
    selainnya {}
  }
}'''.replace("\n", "\r\n")
    program = parse_module(source)
    switch = program.functions[0].body[0]
    self.assertEqual(source[switch.subject.span.start:switch.subject.span.end], '"café"')
    self.assertEqual(len(switch.cases[0].values), 2)
    conditional = switch.cases[0].values[1]
    self.assertEqual(source[conditional.span.start:conditional.span.end], '"café" jika benar selainnya "air"')
    self.assertTrue(source[switch.cases[0].span.start:switch.cases[0].span.end].startswith('kasus "teh",'))
    self.assertTrue(source[switch.cases[0].span.start:switch.cases[0].span.end].endswith("\r\n    }"))
    self.assertTrue(source[switch.span.start:switch.span.end].endswith("\r\n  }"))
    self.assertEqual(switch.else_body, [])
    self.assertIsNone(switch.cases[0].body[0].else_body)
    analyze_program(program)

  def test_switch_grammar_requires_cases_and_braced_bodies(self):
    bodies = (
      "cocokkan () { kasus 1 {} }", "cocokkan 1 { kasus 1 {} }",
      "cocokkan (1) {}", "cocokkan (1) { selainnya {} }",
      "cocokkan (1) { kasus {} }", "cocokkan (1) { kasus 1, {} }",
      "cocokkan (1) { kasus 1: {} }", "cocokkan (1) { kasus 1 maka tampilkan(1); }",
      "cocokkan (1) { kasus 1 {} selainnya maka tampilkan(1); }",
      "cocokkan (1) { kasus 1 {} selainnya {} kasus 2 {} }",
      "cocokkan (1) { kasus 1 {} selainnya {} selainnya {} }",
      "jika (benar) maka cocokkan (1) { kasus 1 {} }",
      "variabel value: apapun = cocokkan (1) { kasus 1 {} };",
    )
    for body in bodies:
      with self.subTest(body=body), self.assertRaises(PyIndoError) as raised:
        parse_module(f"fungsi utama(): kosong {{ {body} }}")
      self.assertIsNotNone(raised.exception.span)
    with self.assertRaises(PyIndoError):
      parse_module("cocokkan (1) { kasus 1 {} } fungsi utama(): kosong {}")
    for suffix in ("cocokkan (1)", "cocokkan (1) { kasus 1 {", "cocokkan (1) { kasus 1 {}"):
      source = "fungsi utama(): kosong { " + suffix
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError) as raised:
        parse_module(source)
      self.assertEqual(raised.exception.span.start, len(source))

  def test_kasus_remains_a_contextual_identifier(self):
    sources = (
      "fungsi kasus(): desimal { hasilkan 1; } fungsi utama(): kosong { cocokkan (1) { kasus kasus() {} } }",
      "fungsi f(kasus: desimal): kosong { cocokkan (kasus) { kasus kasus {} } } fungsi utama(): kosong {}",
      "variabel kasus: desimal = 1; fungsi utama(): kosong { cocokkan (kasus) { kasus 1 {} } }",
      "fungsi utama(): kosong { variabel kasus: desimal = 1; cocokkan (kasus) { kasus kasus {} } }",
    )
    for source in sources:
      with self.subTest(source=source):
        analyze_program(parse_module(source))
    program = parse_module("fungsi utama(): kosong { cocokkan (1) { kasus kasus() {} } }")
    analyze_program(program, imported_signatures={"kasus": FunctionSignature("value", [], program.span, (), "desimal")})

  def test_all_headers_and_bodies_keep_static_checks_and_declaration_order(self):
    bodies = (
      "kasus 1 {} kasus missing() {}", "kasus 1 {} selainnya { tampilkan(missing); }",
      "kasus 1 { variabel value: desimal = 2; } kasus value {}",
      "kasus 1 { variabel value: desimal = 2; } selainnya { tampilkan(value); }",
      "kasus 1 { variabel value = 2; }", "kasus 1 { variabel value: desimal = 2; } selainnya { variabel value: desimal = 3; }",
      "kasus 1 { konstanta saved: apapun = [1]; saved[0] = 2; }",
    )
    for body in bodies:
      with self.subTest(body=body), self.assertRaises(PyIndoError):
        self.analyze(f"cocokkan (1) {{ {body} }}")
    symbols = self.analyze("cocokkan (1) { kasus 1 { variabel first: desimal = 1; } kasus 2 { variabel second: desimal = 2; } selainnya { variabel last: desimal = 3; } }")
    self.assertEqual(symbols.scopes["utama"].local_names, ["first", "second", "last"])
    program = parse_module("fungsi utama(): kosong { cocokkan (1) { kasus 1 {} kasus helper() {} } }")
    with self.assertRaisesRegex(PyIndoError, "expects 1 arguments"):
      analyze_program(program, imported_signatures={"helper": FunctionSignature("helper", ["value"], program.span)})
    program = parse_module("fungsi utama(): kosong { cocokkan (1) { kasus 1 {} selainnya { imported = 2; } } }")
    with self.assertRaisesRegex(PyIndoError, "imported value"):
      analyze_program(program, imported_values={"imported": ValueBinding("value", "desimal", False, program.span)})

  def test_fallback_controls_exhaustiveness_and_return_coverage(self):
    self.analyze("cocokkan (1) { kasus 1 { hasilkan 10; } selainnya { hasilkan 20; } }", return_type="desimal")
    self.analyze("cocokkan (1) { kasus 1 { hasilkan 10; } selainnya { variabel result: desimal = 20; } } hasilkan result;", return_type="desimal")
    for body in (
      "cocokkan (1) { kasus 1 { hasilkan 10; } }",
      "cocokkan (1) { kasus 1 { variabel result: desimal = 10; } } hasilkan result;",
      "cocokkan (1) { kasus 1 { hasilkan 10; } selainnya {} }",
    ):
      with self.subTest(body=body), self.assertRaises(PyIndoError):
        self.analyze(body, return_type="desimal")

  def test_switch_propagates_only_live_nearest_loop_exits(self):
    for control in ("berhenti", "lewati"):
      with self.subTest(control=control), self.assertRaisesRegex(PyIndoError, "inside a loop"):
        self.analyze(f"cocokkan (1) {{ kasus 1 {{ {control}; }} }}")
    template = "untuk (variabel index: desimal = 0; index < 2; index += amount) { cocokkan (index) { kasus 0 { variabel amount: desimal = 1; lewati; } %s } }"
    self.analyze(template % "selainnya { berhenti; lewati; }")
    self.analyze(template % "selainnya { hasilkan; }")
    for fallback in ("", "selainnya { lewati; }"):
      with self.subTest(fallback=fallback), self.assertRaisesRegex(PyIndoError, "not initialized"):
        self.analyze(template % fallback)
    self.analyze("untuk (;;) { cocokkan (1) { kasus 1 { selama (benar) { berhenti; } lewati; } selainnya { berhenti; } } }")
