import contextvars
import sys
import tempfile
import unittest
from pathlib import Path

from pyindo import runtime
from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled


class EntryPointTests(unittest.TestCase):
  def test_entry_signatures_are_zero_or_documented_two_parameters(self):
    for arguments in ("", "argv: himpunan<campuran>, argc: desimal",
                      "values: himpunan<apapun>, count: angka"):
      compile_source(f"fungsi utama({arguments}): kosong {{}}")
    for arguments in ("a: apapun", "a: apapun, b: apapun, c: apapun",
                      "a: desimal, b: desimal", "a: himpunan<desimal>, b: desimal",
                      "a: himpunan<campuran>, b: pecahan"):
      with self.subTest(arguments=arguments):
        with self.assertRaises(PyIndoError) as raised:
          compile_source(f"fungsi utama({arguments}): kosong {{}}")
        self.assertIsNotNone(raised.exception.span)
    with self.assertRaisesRegex(PyIndoError, "expects 2 arguments"):
      compile_source("fungsi utama(a: himpunan<campuran>, b: desimal): kosong { utama(); }")

  def test_argument_context_is_fresh_nested_and_exception_safe(self):
    def entrypoint(arguments, count):
      self.assertEqual(count, len(arguments))
      return arguments

    original = ["outer"]
    host_arguments = sys.argv[:]
    self.assertEqual(runtime.invoke_entrypoint(entrypoint, 2)[1:], [])
    with runtime.execution_arguments(original):
      first = runtime.invoke_entrypoint(entrypoint, 2)
      original.append("caller changed")
      first.append("program changed")
      self.assertEqual(runtime.invoke_entrypoint(entrypoint, 2)[1:], ["outer"])
      with self.assertRaisesRegex(ValueError, "inner failed"):
        with runtime.execution_arguments(["inner"]):
          self.assertEqual(runtime.invoke_entrypoint(entrypoint, 2)[1:], ["inner"])
          raise ValueError("inner failed")
      self.assertEqual(runtime.invoke_entrypoint(entrypoint, 2)[1:], ["outer"])
      self.assertEqual(contextvars.Context().run(runtime.invoke_entrypoint, entrypoint, 2)[1:], [])
    self.assertEqual(runtime.invoke_entrypoint(entrypoint, 2)[1:], [])
    self.assertEqual(sys.argv, host_arguments)
    with self.assertRaises(TypeError):
      with runtime.execution_arguments([1]):
        pass

  def test_library_results_and_default_arguments(self):
    source = "fungsi utama(): desimal { hasilkan 1337; }"
    assertions = """assert namespace['utama']() == 1337
assert namespace['<pyindo:entrypoint_result>'] is None
namespace['__name__'] = '__main__'
exec(code, namespace)
assert namespace['<pyindo:entrypoint_result>'] == 1337
namespace['__name__'] = 'inspection'
exec(code, namespace)
assert namespace['<pyindo:entrypoint_result>'] is None
"""
    assert_program_result(run_compiled(source, assertions), "")

  def test_argv_filename_survives_facades_and_marshal(self):
    source = """fungsi invoke_entrypoint(): desimal { hasilkan 7; }
fungsi utama(values: himpunan<campuran>, count: angka): apapun {
  hasilkan [values, count, invoke_entrypoint()];
}
"""
    script = """import dis, marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from pyindo.runtime import execution_arguments
""" + f"source = {source!r}\n" + """codes = [(compile_source(source), '<pyindo>')]
for sentinel in ('', '\\0'):
  instructions, chunks = parse_program(source + sentinel)
  codes.append((compile_bytecodes(instructions, filename='café source.pyind').to_code(), 'café source.pyind'))
for code, filename in codes:
  namespace = {'__name__': '__main__', '__file__': 'must not override filename'}
  with execution_arguments(['one']):
    exec(marshal.loads(marshal.dumps(code)), namespace)
  values, count, other = namespace['<pyindo:entrypoint_result>']
  assert list(values) == [filename, 'one'] and count == 2 and other == 7
  assert namespace['utama'].__code__.co_varnames == ('values', 'count')
  assert all(item.opname == 'LOAD_FAST_CHECK' for item in dis.get_instructions(namespace['utama']) if item.opname.startswith('LOAD_FAST'))
"""
    assert_program_result(run_python(script), "")

  def test_cli_separator_preserves_program_data(self):
    with tempfile.TemporaryDirectory(prefix="pyindo ruang ") as directory:
      source_path = Path(directory) / "bahasa é.pyind"
      source_path.write_text(
        "fungsi utama(argv: himpunan<campuran>, argc: desimal): kosong { tampilkan(argv, '|', argc); }",
        encoding="utf-8",
      )
      arguments = ("", "café ☕", "two words", "-D", "--")
      expected = repr([str(source_path.resolve()), *arguments]) + "|6"
      assert_program_result(run_program(source_path, program_arguments=arguments), expected)
      self.assertFalse(source_path.with_suffix(".dis").exists())
      for arguments in (None, ()):
        assert_program_result(
          run_program(source_path, ("-O",), program_arguments=arguments),
          repr([str(source_path.resolve())]) + "|1",
        )
      self.assertEqual(run_program(source_path, ("bare",)).returncode, 64)

  def test_cli_invocations_leave_host_and_caller_arguments_unchanged(self):
    source = "fungsi utama(argv: himpunan<campuran>, argc: desimal): kosong { argv[0] = 'changed'; hapus argv[1]; tampilkan(argc); }"
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "program.pyind"
      path.write_text(source, encoding="utf-8")
      script = "import sys\nfrom main import main\n" + f"arguments = [{str(path)!r}, '--', 'one']\n" + """original = arguments[:]
host = sys.argv[:]
assert main(arguments) == 0 and main(arguments) == 0
assert arguments == original and sys.argv == host
"""
      assert_program_result(run_python(script), "22")
    result = run_source("fungsi utama(argv: himpunan<campuran>, argc: desimal): kosong { argv[0] = 1; }")
    self.assertEqual(result.returncode, 1)
    self.assertIn("TypeError", result.stderr)

