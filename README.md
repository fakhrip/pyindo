# pyindo 

This is a (python bytecode + indonesian language) based toy programming language.  

## How to use

Run this command to install all dependencies for the whole things :  
```bash
make
```  

Run the compiler against a pyindo program inside a file like this:  
(you can change `tests/hello_world.pyind` with any file you want to compile and run)
```bash
python3 main.py tests/hello_world.pyind
```

Oh and please note that you need at least **python version `3.10`** to run and use this compiler and also the official extension for this language is `.pyind`.

If you are curious as to how this works, please go to [how it works](#how-it-works) section.

## Examples

You can find all program examples of pyindo language in the [`tests/`](./tests/) directory

## Language specificaton

Entrypoint should be available for the compiler to run properly, it could be made like this:
```pyindo
fungsi utama() {
    // Apapun isinya
}
```

There are several features that are available and will be available (already plan to develop) for this language, which expressed in this one example as a full test throughout all features:  
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

### Ternary Operator

There are no ternary operator in this language, and instead, we follow the pythonic syntax for this one which is to create one line if statement like this:  
```pyindo
tampilkan("apakah 1 sama dengan 1 ? ${'ya' jika 1 adalah 1 selainnya 'tidak'}")
```

### Syntatic Sugar

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

1. Parse the pyindo code using a handwritten parser  
2. Convert it into python bytecode using the help of [bytecode](https://github.com/MatthieuDartiailh/bytecode) (we have a plan on replacing this with our custom implementation later on)

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
