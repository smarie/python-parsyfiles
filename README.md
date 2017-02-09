# python simple file collection parsing framework (parsyfiles)
A declarative framework that combines many popular python parsers (json, jprops, yaml, pickle...) with your user-defined parsers and type converters, in order to easily read objects from files. It is able to read an object even if the object's content comes from several files requiring several parsers: this is typically useful to read test data where you want to combine datasets, parameters, expected results and what not. 

This library provides a *framework*, not a specific parser for a specific file format. By default several classic parsers from the python world are already registered, but it is also extremely easy to add more if your favourite parser is missing. Even better: if you just need to parse a derived type of a type that can already be parsed, you may simply need to register a *type converter*, the framework will link it to any compliant parser for you. 


## Intended audience

* developers looking for an easy way to parse dictionaries and simple objects from various formats (json, properties, cfg, csv...) using standard python libraries. They can combine this library with [classtools_autocode](https://github.com/smarie/python-classtools-autocode) to preserve compact, readable and content-validated classes.

* developers who already know how to parse their various files independently, but looking for a higher-level tool to read complex objects made of several files/folders and potentially requiring to combine several parsers.


## Typical use cases

* **read collections of test cases** on the file system - each test case being composed of several files (for example 2 'test inputs' .csv files, 1 'test configuration' .cfg file, and one 'reference test results' json or yaml file)
* more generally, **read complex objects that for some reason are not represented by a single file representation**, for example objects made of several csv files (timeseries + descriptive data), combinations of csv and xml/json files, configuration files, pickle files, etc.


### Note on the Intelligence/Speed tradeoff
This framework contains a bit of nontrivial logic in order to transparently infer which parser and conversion chain to use, and even in some cases to try several alternatives in order to guess what was your intent. This makes it quite powerful but will certainly be slower and more memory-consuming than writing a dedicated parser tailored for your specific case. However if you are looking for a tool to speedup your development so that you may focus on what's important (your business logic, algorithm implementation, test logic, etc) then it might do the job.


## Main features

* **Declarative (class-based)**: you *first* define the objects to parse - by creating or importing their class -, *then* you use `parse_item` or `parse_collection` on the appropriate folder or file path. 
* **Simple objects out of the box**: if you're interested in parsing singlefile objects only requiring simple types in their constructor, then the framework is probably already able to parse them, for many singlefile formats (json, properties, txt, csv, yaml and more.). 
* **Serialization out of the box**: pickle files (.pyc) are supported too. Base64-encoded pickle objects can also be included in any simple file content.
* **Multifile objects out of the box**: the library comes with two ways to organize multifile objects: *wrapped* (each object is a folder), or *flat* (all files are in the same folder, files belonging to the same object have the same prefix)

* **Extensible**. You may register any number of additional file parsers, or type converters, or both. When registering a parser you just have to declare the object types that it can parse, *and* the file extensions it can read. The same goes for converters: you declare the object type it can read, and the object type it can convert to. 
* **Intelligent** Since several parsers may be registered for the same file extension, and more generally several parsing chains (parser + converters) may be eligible to a given task, the library has a built-in set of rules to select the relevant parsing chains and test them in most plausible order. This provides you with several ways to parse the same object. This might be useful for example if some of your data comes from nominal tests, some other from field tests, some other from web service calls, etc. You don't need anymore to convert all of these to the same format before using it.
* **No annotations required**: as opposed to some data binding frameworks, this library is meant to parse object types that may already exist, and potentially only for tests. Therefore the framework does not require annotations on the type if there is there is a registered way to parse it. However if you wish to build higher-level objects encapsulating the result of several parsers, then PEP484 type hints are required. But that's probably less a problem since these objects are yours (they are part of your tests for example) 


**TODO**
 
 
* **Supports complex classes** : the main interest of this framework is its ability to define complex classes that spans across several files. For example, a `MyTestCase` class that would have two fields `input: DataFrame` and `expected_output: str`. The class constructor is introspected in order to find the *required* and *optional* fields and their names. Fields may be objects or collections (that should be declared with the `typing` module such as `Dict[str, Foo]`) in order for the framework to keep track of the underlying collection types) 
* **Recursive**: fields may themselves be collections or complex types. In which case they are represented by several files.
* Supports **two main file mapping flavours**: 
    * *flat*, where all items are represented as files in the same folder (even fields and collection elements)
    * *wrapped*, where all items that represent collections or complex types are represented by folders, and all ready-to-parse items are represented by files.
* **Safe**: files are opened and finally closed by the framework, your parsing function may exit without closing
* **Lazy-parsing** : TODO, a later version will allow to only trigger parsing when objects are read, in the case of collections 
* Last but not least, you may change the *encoding* used to parse the files (but as of today all files are open with the same global encoding)


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
> pip install parsyfiles
```

### Uninstalling

As usual : 

```bash
> pip uninstall parsyfiles
```

## Usage

### 1- Collections of known types

The most simple case of all: you wish to parse a collection of files that all have the same type, and for which a parser is already registered. For example your data folder looks like this (you may find this example data folder in the [project sources](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/test_data)):

```bash
demo/simple_collection
├── a.csv
├── b.txt
├── c.xls
├── d.xlsx
└── e.xlsm
```

Parsing all of these dataframes is straightforward:

```python
from pprint import pprint
from parsyfiles import parse_collection
from pandas import DataFrame

dfs = parse_collection('./test_data/simple_collection', DataFrame)
print(dfs)
```

Here is the result
```bash
**** Starting to parse  collection of <DataFrame> at location ./test_data/demo/simple_collection ****
Checking all files under ./test_data/demo/simple_collection
./test_data/demo/simple_collection (multifile)
./test_data/demo/simple_collection\a (singlefile, .csv)
./test_data/demo/simple_collection\b (singlefile, .txt)
./test_data/demo/simple_collection\c (singlefile, .xls)
./test_data/demo/simple_collection\d (singlefile, .xlsx)
./test_data/demo/simple_collection\e (singlefile, .xlsm)
File checks done

Building a parsing plan to parse ./test_data/demo/simple_collection (multifile) into a Dict[str, DataFrame]
./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
./test_data/demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_simpledf_from_csv(stream mode)>
./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using [Try '<read_simpledf_from_csv(stream mode)>' then '$<read_dict_from_properties(stream mode)> => <dict_to_object>$' then '$<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$]
./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_simpledf_from_csv(stream mode)>
./test_data/demo/simple_collection\c (singlefile, .xls) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
./test_data/demo/simple_collection\d (singlefile, .xlsx) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
./test_data/demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
Parsing Plan created successfully

Executing Parsing Plan for ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./test_data/demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_simpledf_from_csv(stream mode)>
Parsing ./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_simpledf_from_csv(stream mode)>
Parsing ./test_data/demo/simple_collection\c (singlefile, .xls) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
Parsing ./test_data/demo/simple_collection\d (singlefile, .xlsx) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
Parsing ./test_data/demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_simpledf_from_xls(file mode)>
--> Assembling all parsed child items into a Dict[str, DataFrame] to build ./test_data/demo/simple_collection (multifile)
Completed parsing successfully

{'a':    a  b  c  d
      0  1  2  3  4,
 'b':    a  b  c  d
      0  1  2  3  4,
 'c':    c   5
      0  d   8
      1  e  12
      2  f   3,
 'd':    c   5
      0  d   8
      1  e  12
      2  f   3,
 'e':    c   5
      0  d   8
      1  e  12
      2  f   3}
```

*Note: the above capture was slightly 'improved' for readability, because unfortunately pprint does not display dictionaries of dataframes as nicely as this.*

In this output you see a couple hints on how the parsing framework works:

* first it recursively checks your folder to check that it is entirely compliant with the file mapping format. That is the log section beginning with `Checking all files under ./test_data/demo/simple_collection`. If the same item appears twice (e.g. `a.csv` and `a.txt`)  it will throw an error at this stage (an `ObjectPresentMultipleTimesOnFileSystemError`).

* then it recursively creates a parsing plan that is able to produce an object the required type. That's the section beginning with `Building a parsing plan to parse ./test_data/demo/simple_collection (multifile) into a Dict[str, DataFrame]`. Here you may note that by default, a collection of items is actually parsed as an object of type dictionary, where the key is the name of the file without extension, and the value is the object that is parsed from the file. If at this stage it does not find a way to parse a given file into the required object type, it will fail. For example if you add a file in the folder, named `unknown_ext_for_dataframe.ukn`, you will get an error (a `NoParserFoundForObjectExt`).

* finally it executes the parsing plan. That's the section beginning with `Executing Parsing Plan for ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)`.

It is important to understand these 3 log sections, since the main issue with complex framework is debugging when something unexpected.


### 2- Simple objects

Simple objects are objects that can be read from a single file. We will see complex objects spanning across several files in [section 2](#2--complex-objects).

#### a - Getting started

Suppose that we want to test the following function.

```python
def exec_op(x: float, y: float, op: str) -> float:
    if op is '+':
        return x+y
    elif op is '-':
        return x-y
    else:
        raise ValueError('Unsupported operation : \'' + op + '\'')
```

We would like each test configuration to be represented as an object, containing the inputs and expected outputs. So we define this class:

```python
class ExecOpTest(object):

    def __init__(self, x: float, y: float, op: str, expected_result: float):
        self.x = x
        self.y = y
        self.op = op
        self.expected_result = expected_result
```

#### b - Parsing simple objects

Simple objects such as instances of `ExecOpTest` may be represented by dictionaries. The following 3 "default" file formats are provided for convenience, relying on python standard libraries to parse a dictionary from a file:

* `.cfg` or `.ini`
* `.json`
* `.properties` or `.txt`

Our test data folder looks like this:

```bash
demo_simple
├── test_diff_1.cfg
├── test_diff_2.ini
├── test_sum_1.json
├── test_sum_2.properties
└── test_sum_3.txt
```

Note that the variety of file formats is not very realistic here - you will probably use one or two - but it is used to demonstrate all formats supported out of the box. You may find this example data folder in the [project sources](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/test_data) by the way.

```python
from parsyfiles import get_simple_object_parser
simple_parser = get_simple_object_parser(ExecOpTest)
```

To read a single object from a single file, for example `test_sum_1.json`, simply use




### 2- Complex objects


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
import parsyfiles as sf
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

*Do you like this library ? You might also like [these](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python)* 



## Combining parsyfiles and classtools_autocode (combo!)

Users may wish to use [classtools_autocode](https://github.com/smarie/python-classtools-autocode) in order to create very compact classes representing their objects *and* ensuring that parsed data is valid.

```python
from classtools_autocode import autoprops, autoargs
from contracts import contract, new_contract

new_contract('allowed_op', lambda x: x in {'+', '-'})

@autoprops
class ExecOpTest(object):
    @autoargs
    @contract
    def __init__(self, x: float, y: float, op: str, expected_result: float):
        pass
```


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