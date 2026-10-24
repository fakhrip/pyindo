import unittest

from tests.fixture_runner import assert_program_result, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project


class KeywordExecutionTests(unittest.TestCase):
  def test_keyword_calls_bind_without_reordering_value_effects(self):
    source = '''fungsi mark(label: campuran, value: desimal): desimal { tampilkan(label); hasilkan value; }
fungsi show(a: desimal, b: desimal): kosong { tampilkan(a, b); }
fungsi add(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi factorial(n: desimal): desimal { jika (n < 2) { hasilkan 1; } hasilkan n * factorial(n=n - 1); }
fungsi utama(): kosong {
  show(b=mark("B", 2), a=mark("A", 1));
  tampilkan("|", add(3, b=add(b=2, a=1)), "|", factorial(n=5));
}'''
    assert_program_result(run_source(source), "BA12|6|120")
    assert_program_result(run_compiled(source, "assert namespace['add'](b=2, a=1) == 3"), "")

  def test_keyword_values_finish_before_declaration_order_type_guards(self):
    definition = '''fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi target(a: desimal, b: desimal): kosong { tampilkan("C"); }'''
    completed = run_source(definition + ' fungsi utama(): kosong { target(b=mark("B", 2), a=mark("A", "bad")); }')
    self.assertEqual(completed.returncode, 1)
    self.assertEqual(completed.stdout, "BA")
    self.assertIn("parameter 'a'", completed.stderr)
    for declaration, callee in (('dari "lib.pyind" impor target sebagai renamed;', "renamed"),
                                ('impor "lib.pyind" sebagai state;', "state.target")):
      source = declaration + f' fungsi utama(): kosong {{ {callee}(b=mark("B", 2), a=mark("A", "bad")); }}'
      # Only the owner supplies target; the caller's marks retain caller order.
      files = {"lib.pyind": definition, "main.pyind": definition.split("fungsi target")[0] + source}
      completed = run_project(files, module_name="__main__")
      self.assertEqual(completed.returncode, 1)
      self.assertEqual(completed.stdout, "BA")
      self.assertIn("parameter 'a'", completed.stderr)

  def test_keyword_calls_preserve_native_frames_and_stack_prefixes(self):
    source = '''fungsi pick(a: apapun, b: apapun): apapun { hasilkan a; }
fungsi add(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi probe(values: himpunan<apapun>): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [0, 1, 2]) {
      jika (add(b=0, a=inner) == 0) { lewati; }
      cocokkan (add(b=0, a=inner)) { kasus 1 { hasilkan pick(b=0, a=item); } selainnya { berhenti; } }
    }
  }
  hasilkan;
}
fungsi main_value(): campuran {
  variabel values: himpunan<desimal> = [add(b=2, a=1), 0];
  values[add(b=0, a=1)] = add(b=3, a=1);
  hasilkan "${values}|${0 < add(b=1, a=1) < 3}|${salah atau add(b=1, a=2)}";
}
fungsi utama(): kosong {}'''
    assertions = '''import inspect
marker = object()
assert namespace['probe']([marker]) is marker and namespace['probe']([]) is None
assert namespace['main_value']() == '[3, 4]|True|3'
function = namespace['add']
assert function.__code__.co_argcount == 2
assert function.__code__.co_posonlyargcount == function.__code__.co_kwonlyargcount == 0
assert function.__code__.co_varnames == ('a', 'b')
assert function.__code__.co_flags & (inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS) == 3
assert namespace['probe'].__code__.co_varnames == ('values', 'item', 'inner')
'''
    assert_program_result(run_compiled(source, assertions), "")
