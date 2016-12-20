# python simple file collection parsing framework (sficopaf)
A declarative framework to read complex objects made of several files, using a user-provided library of unitary file parsers. 

This library provides a *framework*, not a specific parser ! Although it comes with a couple unitary file parsers as an example, it is intended for users that already know how to parse their various files independently, but who are looking for a higher-level tool to read complex objects made of several files/folders and potentially requiring to combine several parsers.

Typical use cases of this library :
* read collections of test cases on the file system - each test case being composed of several files (for example 2 'test inputs' .csv files, 1 'test configuration' .cfg file, and one 'reference test results' json file)
* more generally, read complex objects, for example made of several csv files (timeseries + descriptive data), combinations of csv and xml/json files, configuration files, etc.


## Main features

* **Declarative**: you *first* define the type of objects to parse - by creating a class -, then you use `parse_collection` or `parse_item` on the appropriate folder or file path.
* **Supports concurrent unitary file parsers** for the same object type. Thanks to a combined *{Type+Extension}* registration, you register unitary file parsers for a given object type *and* for a given file extension (for example `str` + `.txt`). This allows users to register several parsers for the same object type, supporting various formats represented by the extensions.
* **Supports complex classes** : the main interest of this framework is its ability to define complex classes that spans across several files. For example, a `MyTestCase` class that would have two fields `input: DataFrame` and `expected_output: str`. The class constructor is introspected in order to find the *required* and *optional* fields and their names. Fields may be objects or collections (that should be declared with the `typing` module such as `Dict[str, Foo]`) in order for the framework to keep track of the underlying collection types) 
* **Recursive**: fields may themselves be collections or complex types. In which case they are represented by several files.
* Supports **two main file mapping flavours**: 
    * *flat*, where all items are represented as files in the same folder (even fields and collection elements)
    * *wrapped*, where all items that represent collections or complex types are represented by folders, and all ready-to-parse items are represented by files.
* **Lazy-parsing** : TODO, a later version will allow to only trigger parsing when objects are read, in the case of collections 


## Installation

### Recommended : create a clean virtual environment

We strongly recommend that you use conda *environment* or pip *virtualenv*/*venv* in order to better manage packages. Once you are in your virtual environment, open a terminal and check that the python interpreter is correct:

```bash
(Windows)>  where python
(Linux)  >  which python
```

The first executable that should show up should be the one from the virtual environment.


### Installation steps

This package is available on `PyPI`. You may therefore use `pip` to install from a release

```bash
> pip install sficopaf
```

### Uninstalling

As usual : 

```bash
> pip uninstall sficopaf
```

## Examples

### Basic: the `op_function` test cases

#### a - example overview
In this very simple example, we will parse 'test cases' for an imaginary function that performs operations : `op_function(a:int, b:int, operation:str = '+') -> output:int.`

Each of our 'test case' items will be made of several things:
 * mandatory input data (here, `a` and `b`)
 * optional configuration (here, `operation`)
 * mandatory expected result (here, `output`)

We would like these things stored in separate files. Typically the reason is that you will want to separate the various formats that you wish to use: *csv*, *xml*, *json*...

In this first example we decide to store all items in separate files. So our data folder structure looks like this:

```bash
test_cases
├── case1
│   ├── input_a.txt
│   ├── input_b.txt
│   └── output.txt
├── case2
│   ├── input_a.txt
│   ├── input_b.txt
│   ├── options.txt
│   └── output.txt
└── case3
    ├── input_a.txt
    ├── input_b.txt
    ├── options.cfg
    └── output.txt
```
(this data is available in the source code of this project, in folder `test_data/demo`)

Note that the configuration file is optional. Here, only `case2` and `case3` will have a non-default configuration.

You may also have noticed that the configuration file is present with two different extensions : `.txt` (in case2) and `.cfg` (in case3). This framework allows to register several file extensions for the same type of object to parse. Each extension may have its own parser function.

#### b - base types and parsers registration - simple

First import the package and create a root parser.

```python
import sficopaf as sf
root_parser = sf.RootParser()
```

Then register a parser function for all items that will be represented as **single** files. 

In this example, all inputs and outputs are `int` so we create a first function to parse an `int` from a text file:

```python
from io import TextIOBase
def parse_int_file(file_object: TextIOBase) -> int:
    integer_str = file_object.readline()
    return int(integer_str)
```

and we register it:

```python
root_parser.register_extension_parser(int, '.txt', parse_int_file)
```

Note that the parsing framework automatically opens and closes the file for you, even in case of exception.


#### c - base types and parsers registration - proxies and item collections

We also need to be able to read a `configuration`, that we would like to be a `Dict[str, str]` in order for it to later contain more configuration options. 

Unfortunately this type is an 'item collection' type (dict, list, set, tuple), so we have to create our own custom wrapper class, in order for the framework not to think that it has to read each `<key, value>` pair as a separate file. Indeed by default the framework considers that all 'item collection' types are collections of files.

```python
class OpConfig(dict):
"""
An OpConfig object is a Dict[str, str] object
"""
def __init__(self, config: Dict[str, str]):
    super(OpConfig, self).__init__()
    self.__wrapped_impl = config

    # here you may wish to perform additional checks on the wrapped object
    unrecognized = set(config.keys()) - set('operation')
    if len(unrecognized) > 0:
        raise ValueError('Unrecognized options : ' + unrecognized)

# Delegate all calls to the implementation:
def __getattr__(self, name):
    return getattr(self.__wrapped_impl, name)
```

This is named a dynamic proxy. The `OpConfig` class extends the `dict` class, but delegates everything to the underlying `dict` implementation provided in the constructor.

*Note: this pattern is very useful to use this library, even if the underlying class is not an 'item collection' type. Indeed, this is a good way to create specialized versions of generic objects created by your favourite parsers. For example two `pandas.DataFrame` might represent a training set, and a prediction table. Both objects, although similar (both are tables with rows and columns), might have very different contents (column names, column types, number of rows, etc.). We can make this fundamental difference appear at the parsing level, by creating two classes.*
 
Back to our example, we propose two formats for the `OpConfig`: 
* one `.txt` format where the first row will directly contain the value for the `operation`
* one `.cfg` format where the configuration will be available in a `configparser` format, and for which we want to reuse the existing parser.
    
```python
from typing import Dict
def parse_configuration_txt_file(file_object: TextIOBase) -> OpConfig:
    return {'operation': file_object.readline()}

def parse_configuration_cfg_file(file_object: TextIOBase) -> OpConfig:
    import configparser
    config = configparser.ConfigParser()
    config.read_file(file_object)
    return dict(config['main'].items())
```

Once again, we finally register the parsers:

```python
root_parser.register_extension_parser(OpConfig, '.txt', parse_configuration_txt_file)
root_parser.register_extension_parser(OpConfig, '.cfg', parse_configuration_cfg_file)
```

#### d - main complex type and final parsing execution

Finally, we define the `OpTestCase` object. Its constructor should reflect the way we want to dispatch the various 
pieces of information in separate files, as well as indicate the files the are optional: 

```python
class OpTestCase(object):
    def __init__(self, input_a: int, input_b: int, output: int, options: OpConfig = None):
        self.input_a, self.input_b, self.output = input_a, input_b, output
        if options is None:
            self.op = '+'
        else:
            self.op = options['operation']

        def __str__(self):
            return self.__repr__()

        def __repr__(self):
            return str(self.input_a) + ' ' + self.op + ' ' + str(self.input_b) + ' =? ' + str(self.output)
``` 

Parsing is then straightforward: simply provide the root folder, the object type, and the file mapping flavour.

```python
results = root_parser.parse_collection('./test_data/demo', OpTestCase)
```

The output shows the created test case objects:

```python
pprint(results)

{'case1': 1 + 2 =? 3, 'case2': 1 + 3 =? 4, 'case3': 1 - 2 =? -1}
```

### Advanced topics

#### Flat mode

In our example we used folders to encapsulate object fields and item collections. This is `flat_mode=False`. Alternatively you may wish to set `flat_mode=True`. In this case the folder structure should be flat, as shown below. Item names and field names are separated by a configurable character string. For example to parse the following tree structure:

```bash
.
├── case1--input_a.txt
├── case1--input_b.txt
├── case1--output.txt
├── case2--input_a.txt
├── case2--input_b.txt
├── case2--options.txt
├── case2--output.txt
├── case3--input_a.txt
├── case3--input_b.txt
├── case3--options.cfg
└── case3--output.txt
```

you'll need to call
```python
results = root_parser.parse_collection('./test_data/demo_flat', OpTestCase, flat_mode=True, sep_for_flat='--')
        pprint(results)
```
Note that the dot may be safely used as a separator too.


#### Item collections

The parsing framework automatically detects any object that is of a 'item collection' type (`dict`, `list`, `set`, and currently `tuple` is not supported). These types should be well  defined according to the `typing` module: for example let's imagine that we have an additional `input_c` in our example, with type `typing.Dict[str, typing.List[int]]`.

```python
class OpTestCaseColl(object):
    def __init__(self, input_a: int, input_b: int, output: int,
                 input_c: Dict[str, List[int]] = None, options: OpConfig = None):
        self.input_a, self.input_b, self.output = input_a, input_b, output
        if options is None:
            self.op = '+'
        else:
            self.op = options['operation']
        self.input_c = input_c or None

        def __str__(self):
            return self.__repr__()

        def __repr__(self):
            return str(self.input_a) + ' ' + self.op + ' ' + str(self.input_b) + ' =? ' + str(
                self.output) + ' ' + str(self.input_c)
``` 

For `flat_mode=True` :
 * dictionary keys are read from the text behind the separator after `input_c` (so below, `keyA` and `keyB` are the key names)
 * list items are indicated by any character sequence, but that sequence is not kept when creating the list object (below, `item1` and `item2` will not be kept in the output list) 
 
```bash
.
├── case1--input_a.txt
├── case1--input_b.txt
├── case1--output.txt
├── case2--input_a.txt
├── case2--input_b.txt
├── case2--options.txt
├── case2--output.txt
├── case3--input_a.txt
├── case3--input_b.txt
├── case3--input_c--keyA--item1.txt
├── case3--input_c--keyA--item2.txt
├── case3--input_c--keyB--item1.txt
├── case3--options.cfg
└── case3--output.txt
```

```python
results = root_parser.parse_collection('./test_data/demo_flat_coll', OpTestCaseColl, flat_mode=True, sep_for_flat='--')
pprint(results['case3'].input_c)
```
Results:
```python
{'keyA': [-1, -1], 'keyB': [-1]}
```

For `flat_mode=False` :
 * we already saw that complex objects are represented by folders (for example `case1`, `case2` and `case3`)
 * item collections are, too : `input_c` is a folder
    * dictionary keys are read from the files or folder names (so below, `keyA` and `keyB` are the key names, and since their content is a complex or collection object they are folders themselves)
    * list items are indicated by files or folders with any name, but that name is not kept when creating the list object (below, `item1` and `item2` are not kept in the output list, only their contents is) 
 
```bash
.
├── case1
│   ├── input_a.txt
│   ├── input_b.txt
│   └── output.txt
├── case2
│   ├── input_a.txt
│   ├── input_b.txt
│   ├── options.txt
│   └── output.txt
└── case3
    ├── input_a.txt
    ├── input_b.txt
    ├── input_c
    │   ├── keyA
    │   │   ├── item1.txt
    │   │   └── item2.txt
    │   └── keyB
    │       └── item1.txt
    ├── options.cfg
    └── output.txt
```

```python
results = root_parser.parse_collection('./test_data/demo_coll', OpTestCaseColl, flat_mode=False)
pprint(results['case3'].input_c)
```
Results:
```python
{'keyA': [-1, -1], 'keyB': [-1]}
```


Finally, note that it is not possible to mix collection and non-collection items together (for example, `Union[int, List[int]]` is not supported)


## See Also

Check [here](https://github.com/webmaven/python-parsing-tools) for other parsers in Python, that you might wish to register as unitary parsers to perform specific file format parsing (binary, json, custom...) for some of your objects.


## Developers

### Packaging

This project uses `setuptools_scm` to synchronise the version number. Therefore the following command should be used for development snapshots as well as official releases: 

```bash
python setup.py egg_info bdist_wheel rotate -m.whl -k3
```

### Releasing memo

```bash
twine upload dist/* -r pypitest
twine upload dist/*
```