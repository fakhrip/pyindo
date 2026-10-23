import tempfile
import textwrap
import unittest
from pathlib import Path

from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError, format_error
from tests.fixture_runner import assert_program_result, run_python


def write_project(root: Path, files: dict[str, str | bytes]) -> Path:
  """
  Write isolated project sources; the caller owns the temporary directory.
  """

  for filename, content in files.items():
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
      path.write_bytes(content)
    else:
      path.write_text(content, encoding="utf-8")
  return root / "main.pyind"


def run_project(files: dict[str, str], assertions: str = "", *, module_name="inspection"):
  """
  Compile and execute all module bytecode in a bounded disposable interpreter.
  """

  script = """import tempfile
from pathlib import Path
from pyindo.compiler import compile_source
from tests.test_modules import write_project
with tempfile.TemporaryDirectory(prefix='pyindo modules café ') as directory:
  root = Path(directory)
""" + f"  entry = write_project(root, {files!r})\n" + """  source = entry.read_text(encoding='utf-8')
  code = compile_source(source, filename=str(entry))
""" + f"  namespace = {{'__name__': {module_name!r}}}\n" + "  exec(code, namespace)\n" + textwrap.indent(assertions, "  ")
  return run_python(script)


class ModuleExecutionTests(unittest.TestCase):
  def test_named_namespace_and_entry_aliases_keep_typed_calls(self):
    files = {
      "hitung.pyind": '''fungsi jumlah(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi kali(a: desimal, b: desimal): desimal { hasilkan a * b; }
fungsi utama(value: desimal): desimal { hasilkan value + 10; }''',
      "main.pyind": '''dari "hitung.pyind" impor jumlah sebagai total, utama sebagai library_entry;
impor "hitung.pyind" sebagai hitung;
fungsi utama(): kosong { tampilkan(total(2, 3), "|", hitung.kali(3, 4), "|", library_entry(1)); }''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "5|12|11")

  def test_same_named_helpers_stay_in_the_defining_module(self):
    files = {
      "left.pyind": "fungsi helper(): desimal { hasilkan 1; } fungsi value(n: desimal): desimal { hasilkan n + helper(); }",
      "right.pyind": "fungsi helper(): desimal { hasilkan 2; } fungsi value(n: desimal): desimal { hasilkan n + helper(); }",
      "main.pyind": '''impor "left.pyind" sebagai left;
impor "right.pyind" sebagai right;
fungsi helper(): desimal { hasilkan 99; }
fungsi utama(): kosong { tampilkan(left.value(10), "|", right.value(10), "|", helper()); }''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "11|12|99")

  def test_transitive_diamond_modules_share_only_within_one_execution(self):
    files = {
      "common.pyind": "fungsi value(): desimal { hasilkan 1; }",
      "left.pyind": 'impor "./common.pyind" sebagai shared; fungsi value(): desimal { hasilkan shared.value(); }',
      "right.pyind": 'dari "common.pyind" impor value sebagai shared; fungsi value(): desimal { hasilkan shared(); }',
      "main.pyind": 'impor "left.pyind" sebagai left; impor "right.pyind" sebagai right; impor "common.pyind" sebagai common; fungsi utama(): kosong {}',
    }
    assertions = '''import sys
left, right, common = namespace['left'], namespace['right'], namespace['common']
assert left.value.__globals__['shared'] is common
assert right.value.__globals__['shared'] is common.value
before = set(sys.modules)
again = {'__name__': 'inspection'}
exec(code, again)
assert again['common'] is not common and again['common'].value is not common.value
assert again['left'].value.__globals__['shared'] is again['common']
assert set(sys.modules) == before
assert str(root / 'common.pyind') not in sys.modules
'''
    assert_program_result(run_project(files, assertions), "")

  def test_type_checked_copies_and_constant_snapshots_cross_module_boundaries(self):
    files = {
      "values.pyind": '''fungsi checked(value: himpunan<desimal>): himpunan<desimal> { hasilkan value; }
fungsi frozen(value: apapun): apapun { konstanta copy: himpunan<himpunan<desimal>> = value; hasilkan copy; }
fungsi number(value: desimal): desimal { hasilkan value; }''',
      "main.pyind": 'impor "values.pyind" sebagai values; fungsi utama(): kosong {}',
    }
    assertions = '''module = namespace['values']
raw = [1, 2]
checked = module.checked(raw)
checked[0] = 9
assert raw == [1, 2] and list(checked) == [9, 2]
for action in (lambda: checked.__setitem__(0, 'bad'), lambda: module.number(True)):
  try:
    action()
  except TypeError:
    pass
  else:
    raise AssertionError('imported contract bypassed')
raw = [[1]]
frozen = module.frozen(raw)
raw[0][0] = 9
assert frozen[0][0] == 1
try:
  frozen[0][0] = 2
except TypeError:
  pass
else:
  raise AssertionError('mutable imported constant')
'''
    assert_program_result(run_project(files, assertions), "")

  def test_dependency_sources_are_snapshotted_and_recompilation_is_fresh(self):
    files = {
      "library.pyind": "fungsi value(): desimal { hasilkan 1; }",
      "main.pyind": 'impor "library.pyind" sebagai library; fungsi utama(): kosong {}',
    }
    assertions = '''(root / 'library.pyind').write_text('fungsi value(): desimal { hasilkan 9; }', encoding='utf-8')
fresh = {'__name__': 'inspection'}
exec(compile_source(source, filename=str(entry)), fresh)
old = {'__name__': 'inspection'}
exec(code, old)
assert namespace['library'].value() == old['library'].value() == 1
assert fresh['library'].value() == 9
'''
    assert_program_result(run_project(files, assertions), "")

  def test_supplied_root_text_is_authoritative_and_synthetic_sources_use_cwd(self):
    files = {
      "library.pyind": "fungsi value(): desimal { hasilkan 7; }",
      "main.pyind": 'dari "library.pyind" impor value; fungsi utama(): kosong {}',
    }
    assertions = '''import os
entry.write_text('invalid disk contents', encoding='utf-8')
loaded = {'__name__': 'inspection'}
exec(compile_source(source, filename=str(entry)), loaded)
assert loaded['value']() == 7
previous = Path.cwd()
try:
  os.chdir(root)
  synthetic = {'__name__': 'inspection'}
  exec(compile_source(source), synthetic)
  assert synthetic['value']() == 7
  assert synthetic['utama'].__code__.co_filename == '<pyindo>'
finally:
  os.chdir(previous)
'''
    assert_program_result(run_project(files, assertions), "")

  def test_all_dependencies_are_validated_before_any_entrypoint_runs(self):
    files = {
      "good.pyind": 'fungsi utama(): kosong { tampilkan("BAD LIBRARY ENTRY"); }',
      "bad.pyind": 'fungsi invalid(): desimal {}',
      "main.pyind": 'impor "good.pyind" sebagai good; impor "bad.pyind" sebagai bad; fungsi utama(): kosong { tampilkan("BAD ROOT ENTRY"); }',
    }
    script = """import tempfile
from pathlib import Path
from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
from tests.test_modules import write_project
with tempfile.TemporaryDirectory() as directory:
""" + f"  entry = write_project(Path(directory), {files!r})\n" + """  try:
    compile_source(entry.read_text(encoding='utf-8'), filename=str(entry))
  except PyIndoError as error:
    assert 'bad.pyind' in error.filename
  else:
    raise AssertionError('invalid dependency accepted')
"""
    assert_program_result(run_python(script), "")

  def test_facades_marshal_and_filename_override_preserve_dependency_metadata(self):
    files = {
      "café library.pyind": "fungsi twice(n: desimal): desimal { hasilkan n * 2; }",
      "main.pyind": '''dari "café library.pyind" impor twice;
fungsi own(): desimal { hasilkan twice(3); }
fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal { hasilkan 0; }''',
    }
    assertions = '''import marshal
from pyindo.parser import parse_program
from pyindo.compiler import compile_bytecodes
for sentinel in ('', '\\0'):
  instructions, chunks = parse_program(source + sentinel, filename=str(entry))
  assert [chunk.co_name for chunk in chunks] == ['own', 'utama']
  rewritten = compile_bytecodes(instructions, filename='renamed root.pyind').to_code()
  for path in root.glob('*.pyind'):
    path.unlink()
  loaded = {'__name__': 'inspection'}
  exec(marshal.loads(marshal.dumps(rewritten)), loaded)
  assert loaded['own']() == 6
  assert loaded['own'].__code__.co_filename == 'renamed root.pyind'
  assert loaded['twice'].__code__.co_filename == str(root / 'café library.pyind')
  # Restore only for the next compile; execution itself used the bundled code.
  write_project(root, files)
'''
    # The child keeps its original file mapping available for the second facade.
    assertions = f"files = {files!r}\n" + assertions
    assert_program_result(run_project(files, assertions), "")

  def test_relative_paths_use_each_importer_and_runtime_errors_keep_their_file(self):
    files = {
      "sub/base.pyind": "fungsi crash(): desimal { hasilkan 1 / 0; }",
      "sub/library.pyind": 'dari "base.pyind" impor crash; fungsi wrapper(): desimal { hasilkan crash(); }',
      "main.pyind": 'dari "sub/library.pyind" impor wrapper; fungsi utama(): kosong {}',
    }
    assertions = '''try:
  namespace['wrapper']()
except ZeroDivisionError as error:
  frame = error.__traceback__
  filenames = []
  while frame:
    filenames.append(frame.tb_frame.f_code.co_filename)
    frame = frame.tb_next
  assert str(root / 'sub/base.pyind') in filenames
  assert str(root / 'sub/library.pyind') in filenames
else:
  raise AssertionError('dependency error swallowed')
'''
    assert_program_result(run_project(files, assertions), "")

  def test_imported_calls_work_in_recursion_interpolation_and_iterator_bodies(self):
    files = {
      "math.pyind": '''fungsi fact(n: desimal): desimal { jika (n <= 1) maka hasilkan 1; hasilkan n * fact(n - 1); }
fungsi values(): himpunan<desimal> { hasilkan [1, 2, 3]; }''',
      "main.pyind": '''impor "math.pyind" sebagai math;
fungsi utama(): kosong {
  untuk (variabel n: desimal didalam math.values()) {
    tampilkan("${math.fact(n) jika n > 1 selainnya 1}|");
  }
}''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "1|2|6|")


class ModuleErrorTests(unittest.TestCase):
  def error_for(self, files):
    """
    Inspect structured compilation failures without executing assembled code.
    """

    with tempfile.TemporaryDirectory(prefix="pyindo module errors é ") as directory:
      entry = write_project(Path(directory), files)
      with self.assertRaises(PyIndoError) as raised:
        compile_source(entry.read_text(encoding="utf-8"), filename=str(entry))
      return raised.exception

  def test_missing_invalid_and_undecodable_paths_are_located_import_errors(self):
    for path, extra in (("missing.pyind", {}), ("bad.py", {"bad.py": ""}),
                        ("bad.pyind", {"bad.pyind": b"\xff"})):
      with self.subTest(path=path):
        error = self.error_for({"main.pyind": f'dari "{path}" impor f; fungsi utama(): kosong {{}}', **extra})
        self.assertIsNotNone(error.span)
        self.assertIn("main.pyind", error.filename)
        self.assertIn(path, error.message)

  def test_dependency_syntax_and_type_errors_identify_the_defining_file(self):
    for library in ("fungsi broken(: desimal {}", "fungsi broken(): desimal {}",
                    "fungsi broken(value: mystery): kosong {}"):
      with self.subTest(library=library):
        error = self.error_for({"main.pyind": 'impor "bad.pyind" sebagai bad; fungsi utama(): kosong {}',
                                "bad.pyind": library})
        self.assertIn("bad.pyind", error.filename)
        self.assertIsNotNone(error.span)
        self.assertIn("bad.pyind", format_error(error))

  def test_exports_aliases_namespaces_and_entrypoint_conflicts_are_checked(self):
    library = "fungsi value(n: desimal): desimal { hasilkan n; }"
    for imports, body in (
      ('dari "library.pyind" impor missing;', ""),
      ('dari "library.pyind" impor value, value;', ""),
      ('impor "library.pyind" sebagai x; dari "library.pyind" impor value sebagai x;', ""),
      ('impor "library.pyind" sebagai print;', ""),
      ('dari "library.pyind" impor value sebagai utama;', ""),
      ('dari "library.pyind" impor value;', "value();"),
      ('impor "library.pyind" sebagai x;', "x.value();"),
      ('impor "library.pyind" sebagai x;', "variabel x: desimal = 0;"),
    ):
      with self.subTest(imports=imports, body=body):
        self.error_for({"library.pyind": library,
                        "main.pyind": f"{imports} fungsi utama(): kosong {{ {body} }}"})
    error = self.error_for({"library.pyind": library, "main.pyind": 'dari "library.pyind" impor value;'})
    self.assertIn("Entrypoint", error.message)

  def test_cycles_use_canonical_paths_and_reexports_require_wrappers(self):
    error = self.error_for({
      "main.pyind": 'impor "a.pyind" sebagai a; fungsi utama(): kosong {}',
      "a.pyind": 'impor "./b.pyind" sebagai b;',
      "b.pyind": 'impor "./a.pyind" sebagai a;',
    })
    self.assertIn("Cyclic import", error.message)
    self.assertIn("a.pyind", error.message)
    self.assertIn("b.pyind", error.message)
    error = self.error_for({
      "main.pyind": 'dari "a.pyind" impor value; fungsi utama(): kosong {}',
      "a.pyind": 'dari "b.pyind" impor value;',
      "b.pyind": 'fungsi value(): desimal { hasilkan 1; }',
    })
    self.assertIn("export", error.message)
