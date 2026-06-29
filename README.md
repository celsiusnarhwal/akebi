# Akebi

Akebi allows Python programs to manage [Bun](https://bun.com) installations. It is intended for programs that need
to install or run Node.js packages but do not wish to depend on the end user having an appropriate runtime or package
manager installed.

![gif](vhs/gifs/demo.gif)

## Installation

```shell
pip install akebi
```

## Usage

First, create an `akebi.Bun` object:

```python
from akebi import Bun

bun = Bun()
bun = Bun(version="1.3.14")  # use a specific version of Bun
bun = Bun(version="latest")  # use the latest version of Bun
```

You can then invoke Bun by calling the `Bun` object you just created. A `Bun` object takes a `subprocess.run`-esque list or string
containing command-line arguments.

```python
from akebi import Bun

bun = Bun()

bun(["run", "./my-script.ts"])
bun(["add", "next"])
bun(["create", "docusaurus"])
```

Akebi will automatically install Bun as necessary, but you can also install it manually with `Bun.setup`:

```python
bun.setup()

# or, to forcibly overwrite existing installations of the same version:

bun.setup(force=True)  
```

Under the hood, Akebi uses `subprocess.run` to invoke Bun. Keyword arguments passed to `Bun` objects will be passed 
through to `subprocess.run`, e.g.:

```python
bun("update tailwindcss", shell=True, capture_output=True, text=True)
```

### Isolated installations

If you want to ensure the Bun installations used by your program aren't touched by anything else that uses
Akebi, you can set `Bun.app_name`:

```python
bun = Bun(app_name="com.example.myapp")
```

Bun installations created by your program will be located under an `app_name` subdirectory. You should choose
an app name that's consistent within your program and not likely be taken by other programs that use
Akebi.