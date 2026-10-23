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

Milestone 5 requires type annotations and enforces scalar, function, and collection
contracts on CPython 3.15. The larger v1 example below still includes roadmap features.

| Available and tested | Still planned or incomplete |
| --- | --- |
| Function-local `variabel`, `konstanta`, and mutable reassignment | Module variables, closures, and nested functions |
| Typed positional parameters, nested calls, forward calls, and recursion | Default/keyword/variadic parameters and first-class functions |
| Real `hasilkan` values, early returns, and implicit `None` on fallthrough | Program arguments and entrypoint-selected process exit status |
| Integers, decimals, unary signs, arithmetic/bitwise precedence, and comparisons | Chained comparisons and collection in-place arithmetic |
| Lazy `dan`/`&&`, `atau`/`||`, and logical `tidak`/`!` | Assignment expressions and conditional expressions |
| Nested conditions and single-statement `maka` arms | Unbraced compound arms and optional statement semicolons |
| Braced `selama` and C-style `untuk`, `berhenti`, and `lewati` | Iterator/range loops and loop-else |
| Name-only augmented assignments and postfix `++`/`--` statements | Prefix/expression-valued updates and augmented attribute/index targets |
| Fresh nested list literals, indexed reads/writes, and indexed `hapus` | Slices, dictionaries/sets, comprehensions, methods, and unpacking |
| Deeply immutable detached constant snapshots | Freezing arbitrary foreign Python objects |
| `didalam` membership and contextual `tidak kosong` predicates | Infix `tidak didalam` and chained predicates |
| Mandatory annotations, checked list copies, and runtime type contracts | General static expression inference and user-defined types |
| Unicode strings, escapes, `${expression}`, and outside-string comments | Multiline strings and imports |

```pyindo
fungsi utama(): kosong {
  konstanta batas: desimal = 10;
  variabel total: desimal = jumlah(2, 3);
  total = total + batas;

  jika (total >= 10) {
    tampilkan("hasil: ${total}");
  } selainnya {
    tampilkan("hasil kecil");
  }
}

fungsi jumlah(angka_pertama: desimal, angka_kedua: desimal): desimal {
  hasilkan angka_pertama + angka_kedua;
}
```

This prints `hasil: 15`. All functions are defined before `utama` is called,
so helpers may appear later in the file. Every program requires exactly one
zero-argument `utama`. It runs once under the normal CLI; its returned value
is discarded and a successful run exits 0. `hasilkan;` and falling through a
function return `None` when its return type is `kosong` or `apapun`.

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

### Control flow

```pyindo
fungsi utama(): kosong {
  variabel total: desimal = 0;

  untuk (variabel angka: desimal = 0; angka < 6; angka++) {
    jika (angka adalah 2) maka lewati;
    jika (angka adalah 5) maka berhenti;
    total += angka;
  }

  variabel sisa: desimal = 2;

  selama (sisa > 0 dan total > 0) {
    sisa -= 1;
  }

  cetak(total);
}

fungsi cetak(nilai: desimal): kosong {
  tampilkan(nilai);
}
```

This prints `8`. `selama (condition) { ... }` checks its condition before each
iteration. `untuk (initializer; condition; update) { ... }` executes its
initializer once, checks the condition before each iteration, and executes the
update after each completed body. Each header slot can be omitted; an omitted
condition means true. Both header semicolons and loop-body braces are required.
New header bindings need `variabel` or `konstanta`; bare assignments update an
existing initialized name. Initializers can also be updates, calls, or indexed
deletions; update slots permit assignments, updates, calls, or indexed deletions,
with one statement per slot.

`berhenti;` exits the innermost loop. `lewati;` rechecks a while condition, or
runs a for update exactly once before the next condition. Break and function
return skip that update. Loop controls outside a loop are compile errors.

`dan`/`&&` and `atau`/`||` evaluate left to right and skip unnecessary RHS
effects. They return the selected operand: `0 dan 7` is `0`, `1 dan 7` is `7`,
and `"" atau "cadangan"` is `"cadangan"`. `tidak`/`!` return exact Booleans.
From low to high, precedence is `atau`, `dan`, `tidak`, comparisons, then the
existing bitwise/arithmetic operators. Aliases share precedence: `!a == b`
means `!(a == b)`. Parenthesize negation in arithmetic/comparison operands,
such as `1 == (!salah)`. Both logical operands still receive static name,
arity, and initialization checks even when one would be skipped at runtime.

`+= -= *= /= %= **= &= |= <<= >>=` read an initialized mutable name, evaluate
the RHS once, perform ordinary arithmetic/bitwise rebinding, and store the
result. `name++;` and `name--;` are statement-only updates by 1. Constants
cannot be targets. Updates are not expressions or implicit declarations.

Loops retain function scope. A header initializer can initialize a name used
after the loop, including after zero iterations. Body declarations cannot
establish post-loop initialization; analysis does not assume an iteration even
for a literal-true or omitted condition. A body-local used by a for update must
be initialized on every fallthrough/continue route reaching that update.
Breaking/returning routes are excluded. One declaration may run its initializer
on repeated iterations, including a constant declaration; separate duplicate
source declarations and explicit writes to constants remain errors.

`maka` replaces braces around exactly one simple semicolon-terminated
conditional-arm statement: a declaration, assignment/update, indexed deletion,
call, return, break, or continue. It also works for `selainnya jika` and
`selainnya maka`. Compound if/loop arms and all loop bodies require braces.
Multiline strings and conditional expressions remain future work.

### Mandatory types

Every variable, constant, parameter, and function return needs an annotation.
Reassignments retain the binding's declared type. The old unannotated syntax is
rejected; existing examples and regression programs have been migrated in place.

| Type | Values |
| --- | --- |
| `desimal`, `angka` | Exact Python integer; `angka` is an alias |
| `pecahan` | Exact Python float |
| `campuran` | Exact Python string |
| `logika` | Exact Python Boolean |
| `kosong` | `None`, including `tampilkan`'s result |
| `apapun` | Any value, including `None` and foreign Python objects |
| `himpunan<T>` | Lists whose elements satisfy `T`, including nested list types |

Scalar checks are exact: `benar` is not a `desimal`, integer `1` is not a
`pecahan`, and there are no implicit numeric conversions. Type names are
contextual, so `angka` and `kosong` remain legal function/local names.

Annotation structure, known type names, and return coverage are checked during
compilation. A nonnullable function needs a value-return on every continuing
path; an exhaustive returning if/else qualifies, while loops are conservatively
possibly zero-iteration even with a true or omitted condition. `kosong` and
`apapun` allow bare returns and fallthrough. Types do not establish initialization.

Value contracts run at binding stores, after an augmented/postfix update computes
its result, at parameter entry, and at returns. All caller arguments evaluate
left to right before parameter checks; a mismatch prevents body execution.
External Python callers receive the same checks. Failed assignments leave the
previous binding unchanged. Mismatches raise native `TypeError` tracebacks with
the expected/actual type, function/binding, source line, and nested element path.
They exit 1 in the CLI; source annotation errors use the existing compile-error
status 70. There is no general static expression inference: a wrong value in a
statement that never executes does not cause a runtime error.

`apapun` is an explicit dynamic escape hatch. Conditions retain Python truthiness,
logical operators return selected operands, and arithmetic keeps its native result
rules. Python itself does not enforce annotation metadata, so PyIndo emits its own
[runtime checks](https://docs.python.org/3.15/library/typing.html).

### Collections and constant snapshots

```pyindo
fungsi utama(): kosong {
  variabel angka: himpunan<desimal> = [1, 2, 3];
  konstanta awal: himpunan<desimal> = angka;

  angka[0] = 9;
  tampilkan(awal, "|", angka, "|", 2 didalam angka, "|");

  selama (angka tidak kosong) {
    tampilkan(angka[0]);
    hapus angka[0];
  }

  tampilkan(angka);
}
```

This prints `[1, 2, 3]|[9, 2, 3]|True|923[]`. Lists are ordered arrays, including
empty `[]`, mixed values, nested lists, and a trailing comma such as `[1,]`.
Every evaluation creates fresh lists; elements run once, from left to right.
An ordinary assignment such as `variabel alias: himpunan<desimal> = angka;` shares the same list.
The type spelling `himpunan` refers to arrays, rather than mathematical sets.

An exact ordinary Python list entering `himpunan<T>` becomes an owned checked
copy. Nested list nodes governed by `himpunan` are copied too; matching checked
children preserve sharing within the conversion. Existing checked lists with the
same normalized element type keep their identity across bindings, parameters,
returns, and `apapun` aliases. Their indexed writes and ordinary host mutator
methods reject incompatible incoming elements, including through those aliases.
Batch type failures do not partially insert values. Index type/bounds errors
precede element validation; each index protocol runs once.

Mutable list contracts are invariant: a checked `himpunan<desimal>` cannot be
passed as `himpunan<apapun>`, even when empty. A standalone `apapun` accepts it
unchanged. Under `himpunan<apapun>`, nested raw values remain shared/unrestricted;
only the typed outer node is copied. Separate conversions of the same raw list
are independent. This checked conversion differs from a constant's deep snapshot.

Checked values are private sequence objects, rather than Python `list` instances.
Host integrations can obtain a native shallow outer copy with `list(value)`.
Concatenation, repetition, host slicing, and `copy()` likewise yield native shallow
outer lists; nested checked/frozen children retain their contracts. Source methods
and slices remain unsupported. Source `+=` still adds/rebinds; host `+=` on a
checked sequence mutates that object in place.

Indexing binds above unary signs and power. Reads can be chained and can follow
calls, strings, or grouping: `buat()[1][0]`, `"café"[-1]`, and `([7, 8])[0]`.
Each bracket pair contains one index. Zero-based, negative, and Boolean indices
use Python subscription behavior. Invalid indices, bounds, and writes to
immutable strings retain runtime `TypeError`/`IndexError` tracebacks.

`angka[index] = value;` evaluates the RHS first, then the target base and indices
from left to right, each once. `hapus angka[index];` evaluates its target once
and removes that element; it does not delete the local binding. Both statements
work in `maka` arms and for-header statement slots. Indexed `+=`/`++`, slices,
multiple indices in one bracket pair, and variable deletion remain unsupported.

`konstanta saved: apapun = original;` takes a deeply immutable snapshot of every nested
list before binding `saved`. Later changes to `original` leave the snapshot
unchanged. Aliases, parameters, and returned nested values referring to `saved`
remain immutable. Direct writes/deletions through a known constant root are
compile errors; indirect attempts through aliases or function calls raise
runtime `TypeError`. Rebinding constants is still a compile error.

Snapshots display and compare like lists. Concatenation and repetition produce
fresh mutable outer lists; any nested frozen elements remain protected. Shared
acyclic children are supported. Each execution of a constant declaration makes
a new snapshot of its current initializer, including repeated loop iterations.

Constant snapshots support exact built-in `None`, Boolean, integer, float,
complex, and string values, lists, and already frozen values. Cyclic lists raise
`TypeError: Cannot freeze a cyclic collection`. When embedding the compiler,
other Python objects, scalar/list subclasses, dictionaries, sets, and tuples in
constant initializers also raise `TypeError`; ordinary variables retain their
existing Python interoperability through `apapun`. Checked lists are also valid
snapshot input. Freezing happens before annotation validation, so even `apapun`
constants reject cycles and unsupported objects. A frozen value accepted by a
`himpunan<T>` annotation remains immutable.

`item didalam values` returns an exact Boolean and evaluates item before values.
It supports list equality membership and string substring membership. Negate it
with `tidak (item didalam values)`. Membership has comparison precedence, and
mixed comparison chains still need explicit grouping.

`values tidak kosong` returns an exact Boolean using general truthiness: empty
lists/strings and zero are false. The contextual phrase keeps `kosong` available
as a variable or function name; `tidak kosong()` still negates that function's
result. The phrase wraps an arithmetic operand, so `a + b tidak kosong` tests
`a + b`. Parenthesize the predicate before further arithmetic or comparisons,
such as `(values tidak kosong) + 1`. Logical continuations are supported.

`python test.py` uses standard-library `unittest`. It fails on mismatched output,
unexpected exit status/stderr, orphaned fixtures, or a subprocess timeout.
Expected output retains significant whitespace.

All 19 original fixtures are checked: 11 success examples and eight expected
syntax errors. `simple_math.pyind` now prints its complete message ending in
`180.0`, reflecting true division. Additional tests cover actual return values,
early exits, local scopes, initialization, recursion, nested conditions, lazy
logic, loop/update order, immutable snapshots, collection evaluation order,
source positions, and malformed input. Newly assembled bytecode executes in
test subprocesses so a backend failure cannot terminate the test runner itself.

## Language specificaton

Entrypoint should be available for the compiler to run properly, it could be made like this:
```pyindo
fungsi utama(): kosong {
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

  untuk(variabel c: desimal = 0; c bukan 20; c++) {
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
angka == desimal
logika == bool
kosong == None
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

### Single-statement condition arms

There are some of syntatic sugar which one can use to be able to use this language in a more comfortable way such as:

- Dont have to use curly braces when an if syntax will only have one statement inside.
    For example you can do this one  
    ```pyindo
    jika(1 adalah 1) maka tampilkan("satu adalah satu :D");
    ```

    Instead of this one  
    ```pyindo
    jika(1 adalah 1) {
      tampilkan("satu adalah satu :D");
    }
    ```

---

### Why tho ?

The main reason behind this creation is just to learn and explore how to build a working compiler from the ground up and to also understand what is happening inside python under the hood (which is all about its bytecode and how to assemble, and interpret it).

### How it works

These are the steps of the compilation process:

1. Tokenize the source with character-based locations, then parse a small AST.
2. Resolve typed signatures and bindings; check arity, constants, initialization, and return paths.
3. Emit CPython 3.15 instructions with runtime type contracts and assemble them with [bytecode](https://github.com/MatthieuDartiailh/bytecode).

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
