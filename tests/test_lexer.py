import unittest

from pyindo.diagnostics import PyIndoError, format_error
from pyindo.lexer import StringExpression, StringText, tokenize


class LexerTests(unittest.TestCase):
  def test_keywords_require_word_boundaries(self):
    tokens = tokenize("fungsi makanan jumlahkan fungsiutama")

    self.assertEqual([token.text for token in tokens[:-1]], [
      "fungsi", "makanan", "jumlahkan", "fungsiutama",
    ])
    self.assertNotEqual(tokens[0].kind, tokens[1].kind)
    self.assertEqual(tokens[1].kind, tokens[3].kind)

  def test_numbers_keep_decimal_points(self):
    values = [token.value for token in tokenize("10 1.25 benar BENAR salah SALAH")[:-1]]

    self.assertEqual(values, [10, 1.25, True, True, False, False])

  def test_operators_use_longest_match(self):
    text = "<= >= == != ** << >> += ++ && ||"

    self.assertEqual([token.text for token in tokenize(text)[:-1]], text.split())

  def test_comments_do_not_consume_string_text(self):
    tokens = tokenize('/* ignored */ "// {} , /* text */" // end\n 12')

    self.assertEqual(tokens[0].value[0].text, "// {} , /* text */")
    self.assertEqual(tokens[1].value, 12)
    self.assertEqual(tokens[1].span.line, 2)

  def test_strings_decode_escapes_once(self):
    tokens = tokenize(r'''"\n\u00e9\\n\q\${name}" 'it\'s' "\\${value}"''')

    self.assertEqual(tokens[0].value[0].text, "\né\\n\\q${name}")
    self.assertEqual(tokens[1].value[0].text, "it's")
    self.assertEqual(tokens[2].value[0].text, "\\")
    self.assertIsInstance(tokens[2].value[1], StringExpression)

  def test_interpolation_spans_are_absolute(self):
    source = '\n"café ☕ ${value + 1}"'
    parts = tokenize(source)[0].value
    expression_span = parts[1].span

    self.assertIsInstance(parts[0], StringText)
    self.assertEqual(source[expression_span.start:expression_span.end], "value + 1")
    self.assertEqual(expression_span.line, 2)
    self.assertEqual(expression_span.column, source.splitlines()[1].index("value") + 1)
    inner_tokens = tokenize(source, start=expression_span.start, end=expression_span.end)
    self.assertEqual(inner_tokens[0].span.start, expression_span.start)
    self.assertEqual(inner_tokens[0].span.line, expression_span.line)
    self.assertEqual(inner_tokens[0].span.column, expression_span.column)
    self.assertEqual(inner_tokens[-1].span.start, expression_span.end)

  def test_invalid_input_has_a_located_error(self):
    for source in ("123tes", "1.2.3", "\0", '"unclosed', "/*", '"${name"', '"raw\nline"'):
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError) as raised:
          tokenize(source)

        self.assertIsNotNone(raised.exception.span)
        self.assertIn("(on line number", format_error(raised.exception))

  def test_interpolation_matching_respects_inner_strings_and_comments(self):
    source = '''"${call("}", /* } */ "//")}"'''
    expression_span = tokenize(source)[0].value[0].span

    self.assertEqual(source[expression_span.start:expression_span.end], 'call("}", /* } */ "//")')

  def test_comments_and_escapes_cannot_hide_nuls_or_raw_newlines(self):
    for source in ("// \0", "/* \0 */", '"\\\n"', '"\\\r"', '"\\\0"'):
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError):
          tokenize(source)

  def test_oversized_integer_conversion_is_a_located_user_error(self):
    with self.assertRaises(PyIndoError) as raised:
      tokenize("1" * 4500)

    self.assertEqual(raised.exception.span.start, 0)
