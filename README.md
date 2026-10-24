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
- `--` ends compiler options and passes the remaining tokens to the program.

The result of `utama` selects the process status: `None` means 0, and exact
integers from 0 through 255 select that code. Usage or unsupported-runtime errors
exit 64, unreadable inputs exit 66, and compiler/syntax errors exit 70.

If you are curious as to how this works, please go to [how it works](#how-it-works) section.

## Examples

You can find all program examples of pyindo language in the [`tests/`](./tests/) directory

## Current implementation status

Milestone 6 completes the README v1 example on CPython 3.15 with multiline
strings, conditional expressions, typed program arguments, and CLI exit codes.
Mandatory annotations and checked collection contracts remain enforced.
Milestone 7 adds typed iterator loops over strings, collections, and iterable
values supplied by an embedding Python program.
Milestone 8 adds local `.pyind` modules with named imports, aliases, and namespace
calls while retaining each file's own function globals and type contracts.
Milestone 9 adds typed module-level variables/constants, ordered initialization,
and live value imports with rebinding controlled by the declaring module.
Milestone 10 adds `cocokkan` switches with lazy expression cases and no fallthrough.
Milestone 11 adds lazy comparison chains and infix `tidak didalam` membership.

| Available and tested | Still planned or incomplete |
| --- | --- |
| Function-local and module-level typed variables/constants and reassignment | Closures and nested functions |
| Typed positional parameters, nested calls, forward calls, and recursion | Default/keyword/variadic parameters and first-class functions |
| Real returns, typed argv/argc, and entrypoint-selected process status | Default/keyword/variadic entrypoint arguments |
| Integers, decimals, unary signs, arithmetic/bitwise precedence, and comparison chains | Collection in-place arithmetic |
| Lazy logic, logical negation, and conditional expressions | Assignment expressions |
| Nested conditions and single-statement `maka` arms | Unbraced compound arms and optional statement semicolons |
| `cocokkan` with grouped expression cases and an optional fallback | Structural patterns, captures, guards, and switch expressions |
| Braced `selama`, C-style and iterator `untuk`, `berhenti`, and `lewati` | Range helpers, unpacked loop targets, and loop-else |
| Name-only augmented assignments and postfix `++`/`--` statements | Prefix/expression-valued updates and augmented attribute/index targets |
| Fresh nested list literals, indexed reads/writes, and indexed `hapus` | Slices, dictionaries/sets, comprehensions, methods, and unpacking |
| Deeply immutable detached constant snapshots | Freezing arbitrary foreign Python objects |
| `didalam`/`tidak didalam` membership and contextual `tidak kosong` predicates | Ungrouped chains with postfix `tidak kosong` predicates |
| Mandatory annotations, checked list copies, and runtime type contracts | General static expression inference and user-defined types |
| Unicode/multiline strings, escapes, `${expression}`, and comments | Raw/byte string prefixes |
| Local imports, live values, typed functions, aliases, and namespace reads/calls | Packages, reexports, wildcard/Python imports, and general attribute access |

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
`utama` with zero or two parameters. It runs once under the normal CLI; its result
selects the process status as described below. `hasilkan;` and falling through a
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

### Multiline strings

Both `"""..."""` and `'''...'''` allow physical newlines and preserve indentation,
tabs, blank lines, and leading/trailing whitespace. There is no automatic dedent
or removal of a newline after the opening quotes. Raw LF, CRLF, and CR line endings
decode to LF; an explicit `\r` escape remains a carriage return.

Only the first unescaped matching triple delimiter closes the literal. One or two
matching quotes and opposite quotes remain text. Escapes and `${expression}` work
as in ordinary strings, including nested multiline strings inside interpolation.
Comment markers in literal text remain text. Ordinary single-delimiter strings
still reject raw newlines, and backslash followed by a physical newline remains
unsupported. Adjacent literal concatenation and string prefixes are not enabled.

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

`berhenti;` exits the innermost loop. `lewati;` rechecks a while condition,
runs a C-style for update exactly once, or requests the next iterator item. Break and function
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
Statement semicolons remain required, including in single-statement maka arms.

### Iterator loops

Use `untuk (variabel item: Type didalam expression) { ... }` to visit each item.
Use `konstanta` for a protected iteration binding. Both forms require a fresh
name, a type annotation, parentheses, and a braced body.

```pyindo
fungsi utama(): kosong {
  variabel total: desimal = 0;

  untuk (variabel angka: desimal didalam [1, 2, 3, 4]) {
    jika (angka adalah 2) maka lewati;
    jika (angka adalah 4) maka berhenti;
    total += angka;
  }

  untuk (konstanta huruf: campuran didalam "café ☕") {
    tampilkan(huruf);
  }

  tampilkan("|", total);
}
```

This prints `café ☕|4`. The iterable expression runs once, then each item is
checked against the target's annotation before the body runs. Lists with an
explicit element type receive the usual checked-copy treatment at this binding;
constant collection items receive detached deeply immutable snapshots on every
iteration. Explicit reassignment or direct mutation of a constant target remains
an error. Mutable targets may be reassigned; the next item initializes them again.

Strings yield Unicode code points. Ordinary and checked lists use live iteration:
replacing a later element is visible, deleting elements can skip an item, and
appending can extend traversal. Constant snapshots retain their immutable data.
Rebinding the source variable or mutable target does not redirect an existing
iterator. These source-evaluation and iteration rules follow
[Python's for statement](https://docs.python.org/3.15/reference/compound_stmts.html#the-for-statement).

The target has function scope and follows existing duplicate-name checks.
It is initialized for the body, after evaluation of the iterable. Analysis always
allows zero iterations, so reading the target or a body-only declaration after
the loop is rejected, even for a visibly nonempty source. Existing initialized
variables updated by the body remain available after the loop.

The CLI treats noniterables, iterator failures, and item contract failures as
ordinary runtime errors. Embedding callers can supply other Python iterables
through `apapun`; their iterator protocol is preserved. Range
helpers, target unpacking, and loop-else remain future work.

### Modules and imports

Put reusable functions in a `.pyind` file. For example, save this as `hitung.pyind`:

```pyindo
fungsi jumlah(a: desimal, b: desimal): desimal {
  hasilkan a + b;
}

fungsi kali(a: desimal, b: desimal): desimal {
  hasilkan a * b;
}
```

Save this next to it as `main.pyind`, then run `python main.py main.pyind`:

```pyindo
dari "hitung.pyind" impor jumlah sebagai total;
impor "hitung.pyind" sebagai hitung;

fungsi utama(): kosong {
  tampilkan("jumlah: ", total(2, 3), "|", hitung.kali(3, 4));
}
```

This prints `jumlah: 5|12`. Named imports accept functions and values separated by
commas, each with an optional `sebagai` alias. Namespace imports require an alias
and allow calls such as `hitung.jumlah(2, 3)` and declared value reads such as
`state.total`. Qualified access supports one namespace/member pair, rather than
general Python attributes. Import words remain contextual identifiers.
Imports belong at module level and require literal paths and semicolons.

Paths resolve relative to the importing file, including imports inside libraries.
Use `/` for portable subdirectory paths. Missing/unreadable files, invalid UTF-8,
cycles, unknown exports, alias conflicts, and incorrect call arity are compiler
errors with source locations. Supplied root source text is authoritative.

A library may omit `utama`. If it declares one, that function remains an ordinary
typed function and runs only when explicitly called. The entry file must define
its own `utama`; imported functions cannot supply it implicitly. Every directly
declared library function or module value is available for explicit import,
including underscore names. Imported bindings are not automatically reexported;
define a function wrapper or a new owned value to expose composed behavior.
Import aliases cannot collide with functions, module values, local bindings,
reserved module names, or `utama`.

Imported functions keep their defining module's globals, annotations, checked-list
copies, and constant snapshots. Two libraries can have helpers with the same name.
All dependencies are compiled and validated before execution. Each canonical file
has one module instance per execution, shared by diamond imports. Executing the
compiled program again creates fresh modules; PyIndo does not use `sys.modules`
as a source-module cache.

Compiled code includes its dependencies, so marshal round trips can run after the
source files are removed. `-D` includes dependency functions and their original
filenames. Runtime errors still produce normal tracebacks/status 1; imported code
does not change the entry file's argv or selected process status.

### Module-level variables and constants

Declarations may appear outside functions. Save this as `state.pyind`:

```pyindo
variabel total: desimal = 0;
variabel angka: himpunan<desimal> = [1, 2];
konstanta awal: himpunan<desimal> = angka;

fungsi tambah(jumlah: desimal): kosong {
  total += jumlah;
}
```

Save this beside it as `main.pyind`, then run `python main.py main.pyind`:

```pyindo
dari "state.pyind" impor total sebagai jumlah_sekarang, tambah;
impor "state.pyind" sebagai state;

fungsi utama(): kosong {
  tampilkan(jumlah_sekarang, "|");
  tambah(2);
  state.angka[0] = 9;
  tampilkan(jumlah_sekarang, "|", state.total, "|", state.awal, "|", state.angka);
}
```

This prints `0|2|2|[1, 2]|[9, 2]`. Both import forms read the current owned value
each time. The owning module's functions can rebind its mutable variables without
an additional keyword. Other modules cannot assign to an imported name or a
namespace member; they call an owner function such as `tambah` to rebind it.
Imported mutable collections still permit checked indexed writes/deletions.
Constants remain detached, deeply immutable snapshots through either import form.

Ordinary aliases hold their current objects: a local assigned from `state.angka`
retains that list if the owner later replaces `angka`. A fresh import read sees
the replacement. A local constant made from an imported value takes a snapshot
at that declaration, with the same freezing and annotation rules as other constants.

Module declarations require an annotation, initializer and semicolon. Imports and
functions are available before declaration evaluation, even when written later
in the file. Dependencies initialize first, in depth-first import order; each
module's declarations then run once in source order, before the root's automatic
`utama`. Compilation validates the whole graph without running initializers.
A state-only library needs no functions or entrypoint. Standalone top-level
assignments, calls and control statements remain unsupported; calls are allowed
inside initializer expressions.

A direct initializer read of its own or a later declaration is a compile error.
If an initializer calls a function that reads or rebinds a later variable, the
runtime raises `NameError` identifying the uninitialized binding. It cannot use
a Python builtin or stale value from a previous execution instead. A failure
prevents importer initialization and the automatic entrypoint; earlier effects
are not rolled back. Runtime errors retain tracebacks/status 1. Executing the
code again rebuilds dependencies and resets owned state, even in the same host
namespace.

Module names cannot conflict with imports, functions, reserved runtime names or
`utama`; parameters and locals cannot shadow owned or imported module values.
Every owned store retains its declared type, and failed stores preserve the
previous binding. Functions and namespaces cannot be used as values, and declared
values cannot be called, including values annotated `apapun`.

Embedding callers can inspect owned globals as ordinary Python values. Named
value-import slots contain private live references used by the generated code;
reading a raw host dictionary slot is not a live-value API. Imported function
slots remain ordinary function objects. Direct host dictionary edits can bypass
language contracts; PyIndo source stores and checked collection mutations enforce them.

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

### Program arguments and exit codes

An entrypoint may take no parameters, or two parameters with types
`himpunan<campuran>`/`himpunan<apapun>` and `desimal` (alias `angka`). Parameter
names are arbitrary. The first value is a fresh checked argument list; `argv[0]`
is the resolved absolute source path under the CLI, and `argc` is its initial
length, including that path. Mutating argv does not change argc or host arguments.

```pyindo
fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal {
  tampilkan("jumlah: ", argc);
  jika (argc > 1) maka tampilkan("|", argv[1]);
  hasilkan 0;
}
```

Use `python main.py program.pyind -D -- halo` to print `jumlah: 2|halo` and write
disassembly. Compiler flags precede the first `--`; everything after it is program
data, including `-D`, spaces, empty strings and another `--`. With no user arguments
the example prints `jumlah: 1`. The source path must still be the first CLI argument.

For either entrypoint form, `None` selects exit 0 and an exact integer 0–255 selects
that status. Booleans and other types raise `TypeError`; out-of-range integers
raise `ValueError`. These are runtime failures with native tracebacks/status 1.
Ordinary return type contracts run first. A valid nonzero result still writes
requested -D output; a disassembly write failure retains status 70. -O remains a
compatibility no-op and preserves the selected status.

Embedding keeps the compiler APIs unchanged. Imported execution only defines
functions. `exec(code, {"__name__": "__main__"})` invokes the entrypoint and records
its raw result under `<pyindo:entrypoint_result>` without exiting Python or
validating process status. Ordinary function calls also retain raw return values.
For embedding arguments, scope execution with
`pyindo.runtime.execution_arguments(["hello"])`; nested/repeated executions restore
their caller's arguments, and host `sys.argv` is unchanged. The program name comes
from the entry function's current `co_filename`, including legacy filename overrides;
the default is `<pyindo>`, and an injected `__file__` does not override that metadata.

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
It supports list equality membership and string substring membership.
`item tidak didalam values` returns its inverse, with the same evaluation order
and native membership protocols. `tidak (item didalam values)` remains valid.
Both membership forms share comparison precedence and can join binary chains.

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

The following complete v1 example is runnable. Its exact source and output are
checked in `tests/test_v1_acceptance.py`:
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
```

This was the project's original v1 acceptance goal. The regression suite now checks
it through both compiler APIs, marshal round trips, and normal/-O/-D CLI execution.

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

### Chained comparisons

Comparison chains evaluate operands left to right, with each middle operand
evaluated once. A false intermediate comparison skips all remaining operands:

```pyindo
fungsi utama(): kosong {
  variabel nilai: desimal = 7;
  konstanta dilarang: himpunan<desimal> = [0, 13];

  tampilkan(0 < nilai < 10, "|", nilai tidak didalam dilarang, "|", 3 > 2 > 5);
}
```

This prints `True|True|False`. `a < b <= c` compares `a` with `b`, then `b`
with `c`. All existing binary comparison operators can mix, including `adalah`
for `==`, `bukan` for `!=`, and both membership forms. For example,
`1 < 2 didalam [2]` is true. The aliases retain value-comparison meanings.
Arithmetic binds above comparisons; `tidak`, `dan` and `atau` bind below them.
Parentheses keep separate comparisons: `(a < b) < c` compares a result with `c`.

Value contexts preserve native rich comparison results: a chain returns its
first false-tested result object, or its final untested result. Existing
`apapun` and `logika` contracts still apply; `logika` requires an exact Boolean.
Conditions consume each visited result with one truth test. Materializing a
chain before outer `dan`/`atau` or value-producing `tidak` can test its returned
object again, matching CPython even for an embedding object's changing truth
value. Membership results are always exact Booleans; comparison, membership
and truth errors propagate normally.

All operands are checked statically even when skipped at runtime. Later operands
read live module values when reached. Retaining a middle object preserves it
across owner rebinding; mutation of that object is visible to the next comparison.
Whitespace or comments can separate `tidak` and `didalam` without affecting
prefix negation or contextual names. The separate `tidak kosong` predicate
still needs grouping with comparisons: use `(values tidak kosong) == benar`
or `(a < b) tidak kosong`.

### Switch statements

Use `cocokkan` to compare one value against ordered expression cases:

```pyindo
konstanta berhasil: desimal = 200;

fungsi uraikan(kode: desimal): campuran {
  cocokkan (kode) {
    kasus berhasil, 201 {
      hasilkan "berhasil";
    }
    kasus 404 {
      hasilkan "tidak ditemukan";
    }
    selainnya {
      hasilkan "lainnya";
    }
  }
}

fungsi utama(): kosong {
  tampilkan(uraikan(201), "|", uraikan(404), "|", uraikan(500));
}
```

This prints `berhasil|tidak ditemukan|lainnya`. The subject runs once. Each
`kasus` accepts one or more expressions, including calls and imported constants,
separated by commas. Values are evaluated left to right, in case order, only
until the first equality match. That body's completion continues after the
switch; remaining values, later bodies and the fallback do not execute. Empty
matching bodies also win. There is no fallthrough or explicit case-ending break.

Comparisons use ordinary `subject == candidate` semantics, including Boolean/
numeric equality and checked/frozen list comparisons. A foreign comparison
result is truth-tested once, and comparison/truth errors propagate normally.
No identity shortcut or hash lookup is used. The captured subject is neither
copied nor frozen: owner rebinding does not replace it, while mutation of that
same object can affect later comparisons. Later candidate expressions still
read live imported values at their own evaluation time.

Require a parenthesized subject, at least one `kasus`, and braces around each
body. An optional `selainnya` must be last and unique. Without it, an unmatched
subject simply continues after the switch. Case lists do not accept a trailing
comma. `kasus` remains a valid identifier elsewhere; case expressions read
existing names rather than declaring pattern bindings. Switches cannot be
expressions, top-level statements or unbraced compound `maka` arms.

Bodies retain function scope, mandatory annotations, constant/ownership rules
and initialization checks. Every header/body is checked statically even when
it will be skipped. A nonnullable function whose only return paths are in a
switch needs a returning fallback as well; the compiler does not infer
exhaustiveness from literal cases. `berhenti` and `lewati` still target the
nearest loop and remain invalid outside a loop. `hasilkan` returns from the
function. Structural patterns, captures, guards and switch expressions remain
future work.

### Conditional expressions

Use `true_value jika condition selainnya false_value` to select a value:
```pyindo
tampilkan("apakah 1 sama dengan 1 ? ${'ya' jika 1 adalah 1 selainnya 'tidak'}");
```

The condition runs first and only the selected arm runs. The selected value keeps
its type and identity until an enclosing type contract prepares it. Static name,
arity and initialization checks still inspect both arms. The conditional binds
below `atau` and associates right in the false arm; group a nested conditional in
the condition or true arm. These rules follow
[Python's conditional expressions](https://docs.python.org/3.15/reference/expressions.html#conditional-expressions).
It is an expression inside calls, assignments, returns, list/index expressions and
interpolation; standalone conditional-expression statements remain unsupported.

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
2. Resolve the local import graph and typed signatures/bindings; check arity, constants, initialization, and return paths.
3. Emit CPython 3.15 instructions with runtime type contracts and assemble them with [bytecode](https://github.com/MatthieuDartiailh/bytecode).

The compiler generates bytecode directly. Source locations are converted to
UTF-8 byte columns when attached to executable instructions.

For embedding, `pyindo.compiler.compile_source(source_text, filename=...)`
returns a Python code object and raises `PyIndoError` for source errors.
Use a real source `filename` to anchor imports. Synthetic filenames such as
`<pyindo>` resolve imports from the current directory. Dependency code and source
metadata are bundled into the root code object, with fresh namespaces on execution.
Exceptionally deep nesting or expressions that exceed the compiler's recursive
traversal capacity receive a located complexity-limit diagnostic.

`pyindo.parser.parse_program(source_text, filename=...)` is the compatibility interface:
it returns `(module_instructions, function_code_objects)` and accepts one
optional final NUL sentinel. Its error contract remains printing a diagnostic
and raising `SystemExit(70)`. Its optional keyword-only filename anchors imports;
the returned function-code list contains only root functions. A subsequent
`compile_bytecodes(..., filename=...)` override changes root metadata while keeping
dependency filenames intact. New callers should use `compile_source`.

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
