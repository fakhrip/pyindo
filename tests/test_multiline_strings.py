import unittest

from pyindo.diagnostics import PyIndoError, SourceMap
from pyindo.lexer import StringExpression, StringText, tokenize
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_python, run_source
from tests.test_language import run_compiled


class MultilineStringTests(unittest.TestCase):
  def literal_text(self, source):
    return "".join(part.text for part in tokenize(source)[0].value if isinstance(part, StringText))

  def test_both_triple_delimiters_and_embedded_quotes(self):
    for quote in ('"', "'"):
      delimiter = quote * 3
      opposite = "'" if quote == '"' else '"'
      for text in ("", "plain", quote, quote * 2, opposite * 3, "a" + quote * 2 + "b"):
        # A quote run at the end needs separation from the closing delimiter.
        content = text + "!"
        self.assertEqual(self.literal_text(delimiter + content + delimiter), content)
      self.assertEqual(self.literal_text(delimiter * 2), "")
      self.assertEqual(self.literal_text(delimiter + "\\" + quote + quote * 2 + "!" + delimiter), delimiter + "!")

  def test_whitespace_and_physical_newlines_are_explicit(self):
    text = "\n  first\n\tsecond\n  "
    for newline in ("\n", "\r\n", "\r"):
      source = '"""' + text.replace("\n", newline) + '"""'
      token = tokenize(source)[0]
      self.assertEqual(self.literal_text(source), text)
      self.assertEqual(source[token.span.start:token.span.end], source)
      self.assertEqual(token.span.end_line, 4)
    self.assertEqual(self.literal_text(r'"""a\rb"""'), "a\rb")

  def test_nested_multiline_interpolation_and_escape_parity(self):
    source = '"""head\n${"""} /* text */\ninner"""}\ntail"""'
    parts = tokenize(source)[0].value
    expression = next(part for part in parts if isinstance(part, StringExpression))
    self.assertEqual(source[expression.span.start:expression.span.end], '"""} /* text */\ninner"""')
    program = 'fungsi utama(): kosong { tampilkan(' + source + '); }'
    assert_program_result(run_source(program), "head\n} /* text */\ninner\ntail")
    source = r'"""\n\u00e9\\n\q\${name}\\${1}"""'
    program = 'fungsi utama(): kosong { tampilkan(' + source + '); }'
    assert_program_result(run_source(program), "\né\\n\\q${name}\\1")

  def test_bounded_delimiters_and_ordered_errors(self):
    for source in ('"""missing', '"""raw\0text"""', '"""\\\n"""', "'raw\rline'"):
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError) as raised:
          tokenize(source)
        self.assertIsNotNone(raised.exception.span)
    for end in (3, 4, 5):
      with self.assertRaises(PyIndoError):
        tokenize('""""""', end=end)
    self.assertEqual(len(tokenize('"""', end=2)), 2)
    for suffix in (r' \xGG"""', " unfinished"):
      source = 'fungsi utama(): kosong { tampilkan("""${@}' + suffix + "); }"
      with self.assertRaises(PyIndoError) as raised:
        parse_module(source)
      self.assertEqual(source[raised.exception.span.start], "@")
    with self.assertRaisesRegex(PyIndoError, "Invalid string escape"):
      parse_module(r'fungsi utama(): kosong { tampilkan("""${1} \xGG"""); }')

  def test_newline_maps_and_utf8_positions(self):
    for newline in ("\n", "\r\n", "\r"):
      source = 'fungsi utama(): kosong {' + newline + '// comment' + newline + '  tampilkan("""café ☕' + newline + '${1 + 2}""");' + newline + '}'
      program = parse_module(source)
      expression = program.functions[0].body[0].call.arguments[0].parts[1]
      self.assertEqual(expression.span.line, 4)
      self.assertEqual(source[expression.span.start:expression.span.end], "1 + 2")
      self.assertEqual(SourceMap(source).span(source.index("tampilkan"), source.index("tampilkan") + 9).line, 3)
      assert_program_result(run_compiled(source, module_name="__main__"), "café ☕\n3")
    source = 'fungsi utama(): kosong { tampilkan("""a\u2028b${1}"""); }'
    self.assertEqual(parse_module(source).functions[0].body[0].span.line, 1)

  def test_interpolations_run_once_and_keep_multiline_byte_positions(self):
    source = 'fungsi mark(value: desimal): desimal { tampilkan(value); hasilkan value; }\nfungsi utama(): kosong { tampilkan("""\n  café ☕ ${mark(1)}\n${mark(2)}\n  """); }'
    assert_program_result(run_source(source), "12\n  café ☕ 1\n2\n  ")
    script = "import dis\nfrom pyindo.compiler import compile_source\n" + f"source = {source!r}\n" + """namespace = {'__name__': 'inspection'}
exec(compile_source(source), namespace)
positions = [item.positions for item in dis.get_instructions(namespace['utama']) if item.opname == 'LOAD_GLOBAL' and item.argval == 'mark']
line = source.splitlines()[2]
assert positions[0].lineno == 3
assert positions[0].col_offset == len(line[:line.index('mark')].encode('utf-8'))
assert positions[1].lineno == 4
"""
    assert_program_result(run_python(script), "")
