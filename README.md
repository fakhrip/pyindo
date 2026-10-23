# pyindo 

This is a (python bytecode + indonesian language) based toy programming language.  

## How to use

Use **CPython 3.15.x**. The reference runtime for this port is **3.15.1**,
with **bytecode 0.19.1** pinned in `requirements.txt`. Other Python minor
versions and implementations are rejected because their bytecode can differ.

From the repository root, create a local environment and install dependencies.
The `.venv/` directory stays local and is ignored by Git.

Windows (with Python 3.15 installed):

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py tests/success/hello_world.pyind
.\.venv\Scripts\python.exe test.py
```

Linux or macOS:

```bash
python3.15 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py tests/success/hello_world.pyind
.venv/bin/python test.py
```

With that environment active, the shorter commands are:

```bash
python main.py tests/success/hello_world.pyind
python test.py
```

The official source extension is `.pyind`. `make` and `make test` are optional
shortcuts; use `make PYTHON=.venv/bin/python` (or the Windows environment's
Python path) to select the intended interpreter explicitly.

Options go after the input path:

- `-D` runs the program and writes readable disassembly to a sibling `.dis`
  file, including helper functions. This is text, not an executable `.pyc`.
- `-O` is retained for compatibility and currently does nothing. It does not
  change code-object scope flags or enable a language optimizer.

Successful runs exit 0. Usage or unsupported-runtime errors exit 64, unreadable
inputs exit 66, and compiler/syntax errors exit 70.

If you are curious as to how this works, please go to [how it works](#how-it-works) section.

## Examples

You can find all program examples of pyindo language in the [`tests/`](./tests/) directory

## Current implementation status

Milestone 2 implements the core language on CPython 3.15. The larger typed v1
example below remains a roadmap. The supported subset is untyped:

| Available and tested | Still planned or incomplete |
| --- | --- |
| Function-local `variabel`, `konstanta`, and mutable reassignment | Module variables, closures, and nested functions |
| Positional parameters, nested call expressions, forward calls, and recursion | Typed/default/keyword/variadic parameters and first-class functions |
| Real `hasilkan` values, early returns, and implicit `None` on fallthrough | Program arguments and entrypoint-selected process exit status |
| Integers, decimals, unary signs, arithmetic/bitwise precedence, and comparisons | Chained comparisons, short-circuit Boolean operators, and logical negation |
| Nested braced `jika` / `selainnya jika` / `selainnya` chains | `maka` shorthand, loops, break/continue, and conditional expressions |
| Unicode strings, escapes, `${expression}`, and outside-string comments | Multiline strings, collections/indexing/deletion, imports, and type checking |

```pyindo
fungsi utama() {
  konstanta batas = 10;
  variabel total = jumlah(2, 3);
  total = total + batas;

  jika (total >= 10) {
    tampilkan("hasil: ${total}");
  } selainnya {
    tampilkan("hasil kecil");
  }
}

fungsi jumlah(angka_pertama, angka_kedua) {
  hasilkan angka_pertama + angka_kedua;
}
```

This prints `hasil: 15`. All functions are defined before `utama` is called,
so helpers may appear later in the file. Every program requires exactly one
zero-argument `utama`. It runs once under the normal CLI; its returned value
is discarded and a successful run exits 0. `hasilkan;` and falling through a
function return `None`.

Variables and constants need initializers. Parameters start initialized;
other names may be read only after initialization on every path that reaches
the read. Braces do not create a separate scope. Duplicate declarations within
a function and reassigning a constant are errors. A branch that returns does
not need to initialize a variable used only by the other, continuing branch.

`tampilkan` formats its arguments left to right, concatenating them without
separators or a final newline. It returns `None`; Booleans print as `True` and
`False`. Interpolation accepts expressions and nested calls. `\${` produces a
literal `${`; other supported escapes include `\n`, `\t`, `\\`, and Unicode
escapes. Comments (`//` and non-nested `/* ... */`) apply outside string text.

Arithmetic follows Python precedence: `2 ** 3 ** 2` is 512, `-2 ** 2` is -4,
and `/` is true division. Identifiers use ASCII letters, digits, and underscores,
starting with a letter or underscore; strings can contain Unicode. Keywords
are complete words. Functions cannot be named `tampilkan`, `print`, `__name__`,
`__file__`, or `__builtins__`, which are reserved for printing/module execution.

`python test.py` uses standard-library `unittest`. It fails on mismatched output,
unexpected exit status/stderr, orphaned fixtures, or a subprocess timeout.
Expected output retains significant whitespace.

All 19 original fixtures are checked: 11 success examples and eight expected
syntax errors. `simple_math.pyind` now prints its complete message ending in
`180.0`, reflecting true division. Additional tests cover actual return values,
early exits, local scopes, initialization, recursion, nested conditions, source
positions, and malformed input. Newly assembled bytecode executes in test
subprocesses so a backend failure cannot terminate the test runner itself.

## Language specificaton

Entrypoint should be available for the compiler to run properly, it could be made like this:
```pyindo
fungsi utama() {
  // Apapun isinya
}
```

The following example combines existing syntax with planned features and is
the intended v1 acceptance goal. See the status table above before trying it:
```pyindo
fungsi jumlah(angka1: desimal, angka2: desimal): desimal {
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

    untuk(c: desimal = 0; c bukan 20; c++) {
        jika(c adalah 0 atau c adalah 21) {
            tampilkan("=========================");
            tampilkan("=========================");
        }

        jika(c adalah 0) maka lewati;
        jika(c adalah 20) maka berhenti;

        jika(c <= 10) maka
            tampilkan("${'#' * 25}")
        selainnya {
            tampilkan("#${' ' * 23}#")
        }
    }

    tampilkan("Apakah angka 1 ada didalam himpunan [1, 2, 3, 4, 5] ? ${'ya' jika 1 didalam [1, 2, 3, 4, 5] selainnya 'tidak'}")

    tampilkan("Proses penghapusan angka pada himpunan diatas:")
    variabel beberapa_angka: himpunan<angka> = [1, 2, 3, 4, 5];
    selama(beberapa_angka tidak kosong) {
        hapus beberapa_angka[0];
        tampilkan(beberapa_angka);
    }

    hasilkan 0;
}
```

That example program also functioned as our current main goal to develop the language (in other words, v1 of the language will be out whenever that program [and other test programs] can be run successfully without any trouble).

## Language quirks

For all coders that have been using many kinds of programming languages might get confused to the keywords used in this language so these are the equality of each keyword to other general programming language:  
```
apapun == any || generic type
campuran == string
himpunan == array
pecahan == float
desimal == int
konstanta == const
variabel == var || let
fungsi == function || def || fun
jika == if
cocokkan == switch
selainnya == else
untuk == for
selama == while
berhenti == break
lewati == continue
hapus || hilangkan == del || delete
tidak == not || !
```

Also note that we introduced new keyword in this language that are unique just to this language such as `maka`, so in order for you to understand the whole language syntax, you can see some of examples exist inside the [`tests/`](./tests/) directory.

### Planned conditional expressions

There are no ternary operator in this language, and instead, we follow the pythonic syntax for this one which is to create one line if statement like this:  
```pyindo
tampilkan("apakah 1 sama dengan 1 ? ${'ya' jika 1 adalah 1 selainnya 'tidak'}")
```

### Planned syntactic sugar

There are some of syntatic sugar which one can use to be able to use this language in a more comfortable way such as:

- Dont have to use curly braces when an if syntax will only have one statement inside.
    For example you can do this one  
    ```pyindo
    jika(1 adalah 1) maka tampilkan("satu adalah satu :D");
    ```

    Instead of this one  
    ```pyindo
    jika(1 adalah 1) {
        tampilkan("satu adalah satu :D")
    }
    ```

---

### Why tho ?

The main reason behind this creation is just to learn and explore how to build a working compiler from the ground up and to also understand what is happening inside python under the hood (which is all about its bytecode and how to assemble, and interpret it).

### How it works

These are the steps of the compilation process:

1. Tokenize the source with character-based locations, then parse a small AST.
2. Resolve function signatures and local bindings; check arity, constants, and initialization paths.
3. Emit CPython 3.15 instructions and assemble them with [bytecode](https://github.com/MatthieuDartiailh/bytecode).

The compiler generates bytecode directly. Source locations are converted to
UTF-8 byte columns when attached to executable instructions.

For embedding, `pyindo.compiler.compile_source(source_text, filename=...)`
returns a Python code object and raises `PyIndoError` for source errors.
Exceptionally deep nesting or expressions that exceed the compiler's recursive
traversal capacity receive a located complexity-limit diagnostic.

`pyindo.parser.parse_program(source_text)` is the compatibility interface:
it returns `(module_instructions, function_code_objects)` and accepts one
optional final NUL sentinel. Its error contract remains printing a diagnostic
and raising `SystemExit(70)`. New callers should use `compile_source`.

And then we can execute the compiled bytecode using python [exec](https://docs.python.org/3/library/functions.html#exec) function (maybe we can also create a custom interpreter (as a replacement of CPython) of our own later when we have enough guts to work on that part :D).

So in this case the python bytecode could be called as the IR (Intermediate Representation) of this language.

### Streaming Notes

You can check for any usefull links throughout the development stream in the [notes.txt](./notes.txt).  

You can also check for the streaming session recording in [daskom1337 youtube channel](https://www.youtube.com/channel/UCl51jsRs074Ve1cyXxrbhxA) (which will be made available for public consumption at some point, and please bear in mind that it will all be in indonesian language, im sorry for all of you non indonesia speaker).

### FAQ

Q: Any plan on continuing this project ?  
A: Yes, currently this is one of the main project in the streaming session of daskom1337.

Q: Are there any plan on self hosting the compiler ?  
A: We are aware of the complexity to do this, so it might be included in the future plan, but we dont know about it yet as we have to figure out the bootstrapping process first.

Q: Can i contribute to this project ?  
A: Absolutely, you are all more than welcome to contribute to this project, but please follow the contributing process in the [CONTRIBUTING.md](./CONTRIBUTING.md) file.

Q: Can i join daskom1337 community ?  
A: Unfortunately our community is currently only open for daskom laboratory assistant or ex-assistant of Telkom University, but this could change later.

### License

```
Copyright (C) 2022  Daskom1337 Community

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
