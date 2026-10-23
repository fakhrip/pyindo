import re
import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import REPOSITORY_PATH, assert_program_result, run_program, run_python, run_source


V1_PROGRAM = '''fungsi jumlah(angka1: desimal, angka2: desimal): desimal {
  hasilkan angka1 + angka2;
}

fungsi utama(argv: himpunan<apapun>, argc: desimal): desimal {
  konstanta b: angka = 100;

  tampilkan("Halo dunia, ini adalah contoh program menggunakan bahasa pyindo.");
  tampilkan("""
    Bahasa ini ditujukan untuk memudahkan para manusia di indonesia untuk bisa
    mempelajari bahasa pemrograman tanpa terhalang oleh kesulitan dalam bahasa
    inggris atau syntax yang terlalu cryptic (aneh bagi manusia).
  """);

  untuk(variabel c: desimal = 0; c bukan 20; c++) {
    jika(c adalah 0 atau c adalah 21) {
      tampilkan("=========================");
      tampilkan("=========================");
    }

    jika(c adalah 0) maka lewati;
    jika(c adalah 20) maka berhenti;

    jika(c <= 10) maka
      tampilkan("${'#' * 25}");
    selainnya {
      tampilkan("#${' ' * 23}#");
    }
  }

  tampilkan("Apakah angka 1 ada didalam himpunan [1, 2, 3, 4, 5] ? ${'ya' jika 1 didalam [1, 2, 3, 4, 5] selainnya 'tidak'}");

  tampilkan("Proses penghapusan angka pada himpunan diatas:");
  variabel beberapa_angka: himpunan<angka> = [1, 2, 3, 4, 5];
  selama(beberapa_angka tidak kosong) {
    hapus beberapa_angka[0];
    tampilkan(beberapa_angka);
  }

  hasilkan 0;
}
'''

# This oracle spells the intended sections independently of compiler execution.
# Literal indentation/newlines and the final empty-list display are significant.
V1_EXPECTED_OUTPUT = (
  "Halo dunia, ini adalah contoh program menggunakan bahasa pyindo."
  "\n    Bahasa ini ditujukan untuk memudahkan para manusia di indonesia untuk bisa"
  "\n    mempelajari bahasa pemrograman tanpa terhalang oleh kesulitan dalam bahasa"
  "\n    inggris atau syntax yang terlalu cryptic (aneh bagi manusia).\n  "
  + "=" * 50 + "#" * 250 + ("#" + " " * 23 + "#") * 9
  + "Apakah angka 1 ada didalam himpunan [1, 2, 3, 4, 5] ? ya"
  "Proses penghapusan angka pada himpunan diatas:"
  "[2, 3, 4, 5][3, 4, 5][4, 5][5][]"
)


class V1AcceptanceTests(unittest.TestCase):
  def test_readme_contains_the_exact_runnable_program(self):
    readme = (REPOSITORY_PATH / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```pyindo\n(.*?)```", readme, re.S)
    self.assertIn(V1_PROGRAM, blocks)

  def test_complete_readme_v1(self):
    with tempfile.TemporaryDirectory(prefix="pyindo v1 é ") as directory:
      source_path = Path(directory) / "complete example.pyind"
      source_path.write_text(V1_PROGRAM, encoding="utf-8")
      original = source_path.read_bytes()
      for options in ((), ("-O",), ("-D",)):
        for arguments in (None, ("one", "two words")):
          assert_program_result(
            run_program(source_path, options, program_arguments=arguments), V1_EXPECTED_OUTPUT,
          )
      listing = source_path.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn("utama", listing)
      self.assertIn("jumlah", listing)
      self.assertEqual(source_path.read_bytes(), original)

  def test_complete_program_through_facades_and_marshal(self):
    script = """import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from pyindo.runtime import execution_arguments
""" + f"source = {V1_PROGRAM!r}\n" + """codes = [compile_source(source, filename='complete é.pyind')]
for sentinel in ('', '\\0'):
  instructions, chunks = parse_program(source + sentinel)
  codes.append(compile_bytecodes(instructions, filename='complete é.pyind').to_code())
for code in codes:
  namespace = {'__name__': '__main__'}
  with execution_arguments(['one']):
    exec(marshal.loads(marshal.dumps(code)), namespace)
  assert namespace['<pyindo:entrypoint_result>'] == 0
  assert namespace['jumlah'](2, 3) == 5
"""
    assert_program_result(run_python(script), V1_EXPECTED_OUTPUT * 3)

  def test_multiline_conditional_arguments_and_nonzero_status(self):
    source = '''fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal {
  konstanta saved: himpunan<campuran> = argv;
  tampilkan("""café ☕
${saved[1] jika argc > 1 selainnya 'empty'}|${argc}
""");
  hasilkan 7;
}
'''
    assert_program_result(run_source(source), "café ☕\nempty|1\n", 7)
    assert_program_result(run_source(source, program_arguments=("argument",)), "café ☕\nargument|2\n", 7)
