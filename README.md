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

Oh and please note that you need at least **python version `3.10`** to run and use this compiler.

## Examples

You can find all program examples of pyindo language in the [`tests/`](./tests/) directory

## Language specificaton

Entrypoint should be available for the compiler to run properly, it could be made like this:
```pyindo
fungsi utama() {
    // Apapun isinya
}
```

## Language quirks

TBA

---

### Why tho ?

The main reason behind this creation is just to learn and explore how to build a working compiler from the ground up and to also understand what is happening inside python under the hood (which is all about its bytecode and how to assemble, and interpret it).

### How it works

These are the steps of the compilation process:

1. Parse the pyindo code using a handwritten parser  
2. Convert it into python bytecode using the help of [bytecode](https://github.com/MatthieuDartiailh/bytecode) (we have a plan on replacing this with our custom implementation later on)

And then we can execute the compiled bytecode using python [exec](https://docs.python.org/3/library/functions.html#exec) function (maybe we can also create a custom interpreter (as a replacement of CPython) of our own later when we have enough guts to work on that part :D).

### Streaming Notes

You can check for any usefull links throughout the stream in the [notes.txt](./notes.txt).  

You can also check for the streaming session recording in [daskom1337 youtube channel](https://www.youtube.com/channel/UCl51jsRs074Ve1cyXxrbhxA) (which will be made available for public consumption at some point, and please bear in mind that it will all be in indonesian language, im sorry for all of you non indonesia speaker).

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
