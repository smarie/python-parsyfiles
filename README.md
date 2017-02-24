# python simple file collection parsing framework (parsyfiles)
A declarative framework that combines many popular python parsers (json, jprops, yaml, pickle, pandas...) with your user-defined parsers and type converters, in order to easily read objects from files. It is able to read an object even if the object's content comes from several files requiring several parsers. This is typically useful to read test data where you want to combine datasets, parameters, expected results and what not. 

This library provides a *framework*, not a specific parser for a specific file format. By default several classic parsers from the python world are already registered, but it is also extremely easy to add more if your favourite parser is missing. Even better: if you just need to parse a derived type of a type that can already be parsed, you may simply need to register a *type converter*, the framework will link it to any compliant parser for you. 

## Contents
 * [Overview](#overview)
    * [1- Intended audience](#1--intended-audience)
    * [2- Typical use cases](#2--typical-use-cases)
    * [3- Main features](#3--main-features)
 * [Installation](#installation)
    * [1- Recommended : create a clean virtual environment](#1--recommended--create-a-clean-virtual-environment)
    * [2- Installation steps](#2--installation-steps)
    * [3- Uninstalling](#3--uninstalling)
 * [Usage](#usage)
    * [1- Collections of known types : a list of DataFrame](#1--collections-of-known-types--a-list-of-dataframe)
       * [(a) Example](#a-example)
       * [(b) Understanding the log output](#b-understanding-the-log-output)
       * [(c) Parsing a single file only](#c-parsing-a-single-file-only)
       * [(d) Default collection type and other supported types](#d-default-collection-type-and-other-supported-types)
    * [2- Simple user-defined types](#2--simple-user-defined-types)
       * [(a) Example](#a-example-1)
       * [(b) Under the hood : why does it work, even on ambiguous files?](#b-under-the-hood--why-does-it-work-even-on-ambiguous-files)
          * [Solved Difficulty 1 - Several formats/parsers for the same file extension](#solved-difficulty-1---several-formatsparsers-for-the-same-file-extension)
          * [Solved Difficulty 2 - Generic parsers](#solved-difficulty-2---generic-parsers)
          * [Understanding the inference logic - in which order are the parsers tried ?](#understanding-the-inference-logic---in-which-order-are-the-parsers-tried-)
    * [3- Multifile objects: combining several parsers](#3--multifile-objects-combining-several-parsers)
    * [5- Advanced topics](#5--advanced-topics)
       * [(a) Lazy parsing](#a-lazy-parsing)
       * [(b) Parsing wrappers of existing types - writing proxy classes](#b-parsing-wrappers-of-existing-types---writing-proxy-classes)
       * [(c) Contract validation for parsed objects : combo with classtools-autocode](#c-contract-validation-for-parsed-objects--combo-with-classtools-autocode)
       * [(d) File mappings: Wrapped/Flat and encoding](#d-file-mappings-wrappedflat-and-encoding)
       * [(e) Recursivity: Multifile children of Multifile objects](#e-recursivity-multifile-children-of-multifile-objects)
          * [Example recursivity in flat mode](#example-recursivity-in-flat-mode)
          * [Example recursivity in wrapped mode](#example-recursivity-in-wrapped-mode)
       * [(f) Diversity of formats supported: DataFrames - revisited](#f-diversity-of-formats-supported-dataframes---revisited)
 * [See Also](#see-also)
 * [Developers](#developers)
    * [Packaging](#packaging)
    * [Releasing memo](#releasing-memo)

*ToC created by [gh-md-toc](https://github.com/ekalinin/github-markdown-toc)*

## Overview

### 1- Intended audience

* developers looking for an easy way to parse dictionaries and simple objects from various formats (json, properties, cfg, csv...) using standard python libraries. They can combine this library with [classtools_autocode](https://github.com/smarie/python-classtools-autocode) to preserve compact, readable and content-validated classes.

* developers who already know how to parse their various files independently, but looking for a higher-level tool to read complex objects made of several files/folders and potentially requiring to combine several parsers.


### 2- Typical use cases

* **read collections of test cases** on the file system - each test case being composed of several files (for example 2 'test inputs' .csv files, 1 'test configuration' .cfg file, and one 'reference test results' json or yaml file)
* more generally, **read complex objects that for some reason are not represented by a single file representation**, for example objects made of several csv files (timeseries + descriptive data), combinations of csv and xml/json files, configuration files, pickle files, etc.


*Note on the Intelligence/Speed tradeoff:*
This framework contains a bit of nontrivial logic in order to transparently infer which parser and conversion chain to use, and even in some cases to try several alternatives in order to guess what was your intent. This makes it quite powerful but will certainly be slower and more memory-consuming than writing a dedicated parser tailored for your specific case. However if you are looking for a tool to speedup your development so that you may focus on what's important (your business logic, algorithm implementation, test logic, etc) then have a try, it might do the job.


### 3- Main features

* **Declarative (class-based)**: you *first* define the objects to parse - by creating or importing their class -, *then* you use `parse_item` or `parse_collection` on the appropriate folder or file path. 
* **Simple objects out-of-the-box**: if you're interested in parsing singlefile objects only requiring simple types in their constructor, then the framework is *already* able to parse them, for many singlefile formats (json, properties, txt, csv, yaml and more.).
* **Multifile collections out-of-the-box**: the framework is able to parse collections of objects, each represented by a file. Parsing may optionally be done in a lazy fashion (each item is only read if needed).
* **Serialization**: pickle files (.pyc) are supported too. Base64-encoded pickle objects can also be included in any simple file content.
* **Multiparser**: the library will use the best parser adapted to each file format and desired type. At the time of writing the library:
    * knows **44** ways to parse a file
    * is able to parse **15** object types (including *'Any'* for generic parsers)
    * from **13** file extensions
* **Multifile+Multiparser objects**: You may therefore parse complex objects requiring a combination of several parsers to be built from several files. The framework will introspect the object constructor in order to know the list of required attributes to parse as well as their their type, and if they are mandatory or optional.
* **Recursive**: attributes may themselves be collections or complex types.
* Supports **two main file mapping flavours for Multifile objects**: the library comes with two ways to organize multifile objects such as collections: *wrapped* (each multifile object is a folder), or *flat* (all files are in the same folder, files belonging to the same multifile object have the same prefix)

In addition the library is

* **Extensible**. You may register any number of additional file parsers, or type converters, or both. When registering a parser you just have to declare the object types that it can parse, *and* the file extensions it can read. The same goes for converters: you declare the object type it can read, and the object type it can convert to. 
* **Intelligent** Since several parsers may be registered for the same file extension, and more generally several parsing chains (parser + converters) may be eligible to a given task, the library has a built-in set of rules to select the relevant parsing chains and test them in most plausible order. This provides you with several ways to parse the same object. This might be useful for example if some of your data comes from nominal tests, some other from field tests, some other from web service calls, etc. You don't need anymore to convert all of these to the same format before using it.
* **No annotations required**: as opposed to some data binding frameworks, this library is meant to parse object types that may already exist, and potentially only for tests. Therefore the framework does not require annotations on the type if there is there is a registered way to parse it. However if you wish to build higher-level objects encapsulating the result of several parsers, then PEP484 type hints are required. But that's probably less a problem since these objects are yours (they are part of your tests for example) 


## Installation

### 1- Recommended : create a clean virtual environment

We strongly recommend that you use conda *environment* or pip *virtualenv*/*venv* in order to better manage packages. Once you are in your virtual environment, open a terminal and check that the python interpreter is correct:

```bash
(Windows)>  where python
(Linux)  >  which python
```

The first executable that should show up should be the one from the virtual environment.


### 2- Installation steps

This package is available on `PyPI`. You may therefore use `pip` to install from a release

```bash
> pip install parsyfiles
```

### 3- Uninstalling

As usual : 

```bash
> pip uninstall parsyfiles
```

## Usage

### 1- Collections of known types : a list of DataFrame

#### (a) Example

The most simple case of all: you wish to parse a collection of files that all have the same type, and for which a parser is already registered. For example your wish to parse a list of `DataFrame` for a data folder that looks like this:

```bash
./demo/simple_collection
├── a.csv
├── b.txt
├── c.xls
├── d.xlsx
└── e.xlsm
```
*Note: you may find this example data folder in the [project sources](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/test_data)*

Parsing all of these dataframes is straightforward:

```python
from pprint import pprint
from parsyfiles import parse_collection
from pandas import DataFrame

dfs = parse_collection('./demo/simple_collection', DataFrame)
pprint(dfs)
```

Here is the result
```
**** Starting to parse  collection of <DataFrame> at location ./demo/simple_collection ****
Checking all files under ./demo/simple_collection
./demo/simple_collection (multifile)
./demo/simple_collection\a (singlefile, .csv)
(...)
./demo/simple_collection\e (singlefile, .xlsm)
File checks done

Building a parsing plan to parse ./demo/simple_collection (multifile) into a Dict[str, DataFrame]
./demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
./demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_df_or_series_from_csv(stream mode)>
(...)
./demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
Parsing Plan created successfully

Executing Parsing Plan for ./demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_df_or_series_from_csv(stream mode)>
--> Successfully parsed a DataFrame from ./demo/simple_collection\a
(...)
Parsing ./demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
--> Successfully parsed a DataFrame from ./demo/simple_collection\e
Assembling all parsed child items into a Dict[str, DataFrame] to build ./demo/simple_collection (multifile)
--> Successfully parsed a Dict[str, DataFrame] from ./demo/simple_collection
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


#### (b) Understanding the log output

By default the library uses a `Logger` that has an additional handler to print to `stdout`. If you do not want to see all these messages printed to the console, or if you want to use a different logging configuration, you may provide a custom logger to the function:

```python
from logging import getLogger
dfs = parse_collection('./demo/simple_collection', DataFrame, logger=getLogger('my_logger'))
```

In the log output you see a couple hints on how the parsing framework works:

* first it recursively **checks your folder** to check that it is entirely compliant with the file mapping format. That is the log section beginning with "`Checking all files under ./demo/simple_collection`". If the same item appears twice (e.g. `a.csv` and `a.txt`)  it will throw an error at this stage (an `ObjectPresentMultipleTimesOnFileSystemError`).

* then it recursively **creates a parsing plan** that is able to produce an object the required type. That's the section beginning with "`Building a parsing plan to parse ./demo/simple_collection (multifile) into a Dict[str, DataFrame]`". Here you may note that by default, a collection of items is actually parsed as an object of type dictionary, where the key is the name of the file without extension, and the value is the object that is parsed from the file. If at this stage it does not find a way to parse a given file into the required object type, it will fail. For example if you add a file in the folder, named `unknown_ext_for_dataframe.ukn`, you will get an error (a `NoParserFoundForObjectExt`).

* finally it **executes the parsing plan**. That's the section beginning with "`Executing Parsing Plan for ./demo/simple_collection (multifile) > Dict[str, DataFrame] (...)`".

It is important to understand these 3 log sections, since the main issue with complex frameworks is debugging when something unexpected happens :-).


#### (c) Parsing a single file only

The following code may be used to parse a single file explicitly:

```python
from pprint import pprint
from parsyfiles import parse_item
from pandas import DataFrame

df = parse_item('./demo/simple_collection/c', DataFrame)
pprint(df)
```

Important : note that the file extension does not appear in the argument of the `parse_item` function. 


#### (d) Default collection type and other supported types 

You might have noticed that the demonstrated collection example returned a `dict` of dataframes, not a `list`. This is the default behaviour of the `parse_collection` method - it has the advantage of not making any assumption on the sorting order. 

Behind the scenes, `parse_collection` redirects to the `parse_item` command. So the following code leads to the exact same results:

```python
from parsyfiles import parse_item
from pandas import DataFrame
from typing import Dict

df = parse_item('./demo/simple_collection/c', Dict[str, DataFrame])
```

The `typing` module is used here to entirely specify the type of item that you want to parse (`Dict[str, DataFrame]`). The parsed item will  be a dictionary with string keys (the file names) and DataFrame values (the parsed file contents).

You may parse a `list`, a `set`, or a `tuple` exactly the same way, using the corresponding `typing` class: 

```python
from parsyfiles import parse_item
from pandas import DataFrame
from typing import List, Set, Tuple

dfl = parse_item('./demo/simple_collection', List[DataFrame])
# dfs = parse_item('./demo/simple_collection', Set[DataFrame])
dft = parse_item('./demo/simple_collection', Tuple[DataFrame, DataFrame, DataFrame, DataFrame, DataFrame])
```

For `List` and `Tuple` the implied order is alphabetical on the file names (similar to using `sorted()` on the items of the dictionary).
Note that `DataFrame` objects are not mutable, so in this particular case the collection cannot be parsed as a `Set`.


Finally, note that it is not possible to mix collection and non-collection items together (for example, `Union[int, List[int]]` is not supported).


### 2- Simple user-defined types

#### (a) Example

Suppose that you want to test the following `exec_op` function, and you want to read your test datasets from a bunch of files.

```python
def exec_op(x: float, y: float, op: str) -> float:
    if op is '+':
        return x+y
    elif op is '-':
        return x-y
    else:
        raise ValueError('Unsupported operation : \'' + op + '\'')
```

Each test dataset could be represented as an object, containing the inputs and expected outputs for `exec_op`. For example:

```python
class ExecOpTest(object):

    def __init__(self, x: float, y: float, op: str, expected_result: float):
        self.x = x
        self.y = y
        self.op = op
        self.expected_result = expected_result
    
    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)
```

Obviously this class is not known by the `parsyfiles` framework: there is no registered parser for the `ExecOpTest` type. However the type is fairly simple, so it can actually fit into a dictionary containing the values for `x`, `y`, `op`, and `expected_results`. `parsyfiles` knows a couple ways to parse dictionaries, using python standard libraries:

* From a `.cfg` or `.ini` file using the `configparser` module
* From a `.json` file using the `json` module
* From a `.properties` or `.txt` file using the `jprops` module
* From a `.yaml` or `.yml` file using the `yaml` module
* From a `.csv`, `.txt`, `.xls`, `.xlsx`, `.xlsm` file using the `pandas` module
* ...

It also knows how to convert a dictionary into an object, as long as the object constructor contains the right information about expected types. For example in the example above, the constructor has explicit PEP484 annotations `x: float, y: float, op: str, expected_result: float`.

So let's try to parse instances of `ExecOpTest` from various files. Our test data folder looks like this (available in the [project sources](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/test_data)):

```bash
./demo/simple_objects
├── test_diff_1.cfg
├── test_diff_2.ini
├── test_diff_3_csv_format.txt
├── test_sum_1.json
├── test_sum_2.properties
├── test_sum_3_properties_format.txt
├── test_sum_4.yaml
├── test_sum_5.xls
├── test_sum_6.xlsx
└── test_sum_7.xlsm
```

As usual, we tell the framework that we want to parse a collection of objects of type `ExecOpTest`:

```python
from pprint import pprint
from parsyfiles import parse_collection

sf_tests = parse_collection('./demo/simple_objects', ExecOpTest)
pprint(sf_tests)
```

Here is the result:

```
**** Starting to parse  collection of <ExecOpTest> at location ./demo/simple_objects ****
Checking all files under ./demo/simple_objects
(...)
File checks done

Building a parsing plan to parse ./demo/simple_objects (multifile) into a Dict[str, ExecOpTest]
(...)
Parsing Plan created successfully

Executing Parsing Plan for ./demo/simple_objects (multifile) > Dict[str, ExecOpTest] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
(...)
--> Successfully parsed a Dict[str, ExecOpTest] from ./demo/simple_objects
Completed parsing successfully

{'test_diff_1': 1.0 - 1.0 =? 0.0,
 'test_diff_2': 0.0 - 1.0 =? -1.0,
 'test_diff_3_csv_format': 5.0 - 4.0 =? 1.0,
 'test_diff_4_csv_format2': 4.0 - 4.0 =? 0.0,
 'test_sum_1': 1.0 + 2.0 =? 3.0,
 'test_sum_2': 0.0 + 1.0 =? 1.0,
 'test_sum_3_properties_format': 1.0 + 1.0 =? 2.0,
 'test_sum_4': 2.0 + 5.0 =? 7.0,
 'test_sum_5': 56.0 + 12.0 =? 68.0,
 'test_sum_6': 56.0 + 13.0 =? 69.0,
 'test_sum_7': 56.0 + 14.0 =? 70.0}
```


#### (b) Under the hood : why does it work, even on ambiguous files? 

In the example above, three files were actually quite difficult to parse into a `dict` before being converted to an `ExecOpTest`: `test_diff_3_csv_format.txt`, `test_diff_4_csv_format2.txt` and `test_sum_4.yaml`. Let's look at both cases in details.

##### Solved Difficulty 1 - Several formats/parsers for the same file extension

`test_diff_3_csv_format.txt` and `test_diff_4_csv_format2.txt` are both  .txt file that contains csv-format data. But 

* there are several way to write a dictionary in a csv format (one row of header + one row of values, or one column of names + one column of values).
* .txt files may also contain many other formats such as for example, the 'properties' format. 

How does the framework manage to parse these files ? Lets look at the log output for `test_diff_3_csv_format.txt`:

```
Parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_dict_from_properties> => <dict_to_object>$
  !! Caught error during execution !!
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\support_for_objects.py", line 273, in dict_to_object
    attr_name)
  ParsingException : Error while parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_dict_from_properties> => <dict_to_object>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
  InvalidAttributeNameForConstructorError : Cannot parse object of type <ExecOpTest> using the provided configuration file: configuration contains a property name ('5,4,-,1')that is not an attribute of the object constructor. <ExecOpTest> constructor attributes are : ['y', 'x', 'expected_result', 'op']

Rebuilding local parsing plan with next candidate parser: $<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$
./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$
Parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$
  !! Caught error during execution !!
  File "C:\Anaconda3\envs\azuremlbricks\lib\base64.py", line 88, in b64decode
    return binascii.a2b_base64(s)
  ParsingException : Error while parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
  Error : Incorrect padding

Rebuilding local parsing plan with next candidate parser: $<read_str_from_txt> => <constructor_with_str_arg>$
./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt> => <constructor_with_str_arg>$
Parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt> => <constructor_with_str_arg>$
  !! Caught error during execution !!
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\support_for_primitive_types.py", line 98, in constructor_with_str_arg
    return desired_type(source)
  ParsingException : Error while parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_str_from_txt> => <constructor_with_str_arg>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
  CaughtTypeError : Caught TypeError while calling conversion function 'constructor_with_str_arg'. Note that the conversion function signature should be 'def my_convert_fun(desired_type: Type[T], source: S, logger: Logger, **kwargs) -> T' (unpacked options mode - default) or def my_convert_fun(desired_type: Type[T], source: S, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T (unpack_options = False).Caught error message is : TypeError : __init__() missing 3 required positional arguments: 'y', 'op', and 'expected_result'

Rebuilding local parsing plan with next candidate parser: $<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$
./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$
Parsing ./demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$
--> Successfully parsed a ExecOpTest from ./demo/simple_objects\test_diff_3_csv_format
```

You can see from the logs that the framework successively tries several ways to parse this file :

 * `$<read_dict_from_properties> => <dict_to_object>$`: the txt file is read in the 'properties' format (using `jprops`) into a dictionary, and then the dictionary is converted to a `ExecOpTest` object. *This fails.*
 * `$<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$` : the txt file is read as a string, and then the string is interpreted as a base64-encoded pickle `ExecOpTest` object (!). *This fails.*
 * `$<read_str_from_txt> => <constructor_with_str_arg>$`: the txt file is read as a string, and then the constructor of `ExecOpTest` is called with that string as unique argument. *This fails again.*
 * `$<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$`: the txt file is read as a csv into a DataFrame, then the DataFrame is converted to a dictionary, and finally the dictionary is converted into a `ExecOpTest` object. *This finally succeeds*.

The same goes for the other file `test_diff_4_csv_format2.txt`. 
    
    
##### Solved Difficulty 2 - Generic parsers

For `test_sum_4.yaml`, the difficulty is that yaml format may contain a dictionary directly, but is also able to contain any typed object thanks to the YAML `object` directive. Therefore it could contain a `ExecOpTest`.

The parsing logs are the following:

```
Parsing ./demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using <read_object_from_yaml>
  !! Caught error during execution !!
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\parsing_core_api.py", line 403, in execute
    res, options)
  ParsingException : Error while parsing ./demo/simple_objects\test_sum_4 (singlefile, .yaml) as a <class 'test_parsyfiles.DemoTests.test_simple_objects.<locals>.ExecOpTest'> with parser '<read_object_from_yaml>' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : 
      parser returned {'y': 5, 'x': 2, 'op': '+', 'expected_result': 7} of type <class 'dict'> which is not an instance of <class 'test_parsyfiles.DemoTests.test_simple_objects.<locals>.ExecOpTest'>

Rebuilding local parsing plan with next candidate parser: $<read_collection_from_yaml> => <dict_to_object>$
./demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using $<read_collection_from_yaml> => <dict_to_object>$
Parsing ./demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using $<read_collection_from_yaml> => <dict_to_object>$
--> Successfully parsed a ExecOpTest from ./demo/simple_objects\test_sum_4
```

You can see from the logs that the framework successively tries several ways to parse this file :

 * `<read_object_from_yaml>`: the file is read according to the yaml format, as an `ExecOpTest` object directly. This fails.
    
 * `$<read_collection_from_yaml> => <dict_to_object>$`: the file is read according to the yaml format, as a dictionary. Then this dictionary is converted into a `ExecOpTest` object. **This succeeds**


##### Understanding the inference logic - in which order are the parsers tried ?

These example show how `parsyfiles` intelligently combines all registered parsers and converters to create parsing chains that make sense. These parsing chains are tried **in order** until a solution is found. Note that the order is deterministic:

* First all **exact match** parsers. This includes combinations of {parser + converter chain} that lead to an exact match, sorted by converter chain size: first the small conversion chains, last the large conversion chains.

* Then all **approximative match** parsers. This is similar to the "exact match" except that these are parsers able to parse a **subclass** of what you're asking for.

* Finally all **generic** parsers. This includes combinations of {parser + converter chain} that end with a generic converter (for example the "dict to object" converter seen in the example above)


In order to know in advance which file extensions and formats the framework will be able to parse, you may wish to use the following command to ask the framework:

```python
from parsyfiles import RootParser
RootParser().print_capabilities_for_type(typ=ExecOpTest)
```

The result is a dictionary where each entry is a file extension:
```
{'.cfg': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_config> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$,
                        $<read_config> => <config_to_dict_of_dict> -> <dict_of_dict_to_object>$,
                        $<read_config> => <config_to_dict_of_dict> -> <dict_to_object>$]},
 '.csv': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.ini': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_config> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$,
                        $<read_config> => <config_to_dict_of_dict> -> <dict_of_dict_to_object>$,
                        $<read_config> => <config_to_dict_of_dict> -> <dict_to_object>$]},
 '.json': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_dict_or_list_from_json> => <dict_to_object>$]},
 '.properties': {'1_exact_match': [],
                 '2_approx_match': [],
                 '3_generic': [$<read_dict_from_properties> => <dict_to_object>$]},
 '.pyc': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [<read_object_from_pickle>]},
 '.txt': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_dict_from_properties> => <dict_to_object>$,
                        $<read_str_from_txt> => <base64_ascii_str_pickle_to_object>$,
                        $<read_str_from_txt> => <constructor_with_str_arg>$,
                        $<read_df_or_series_from_csv> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xls': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_dataframe_from_xls> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xlsm': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_dataframe_from_xls> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xlsx': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_dataframe_from_xls> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.yaml': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [<read_object_from_yaml>,
                         $<read_collection_from_yaml> => <dict_to_object>$]},
 '.yml': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [<read_object_from_yaml>,
                        $<read_collection_from_yaml> => <dict_to_object>$]},
 '<multifile>': {'1_exact_match': [],
                 '2_approx_match': [],
                 '3_generic': [Multifile Object parser (parsyfiles defaults)]}}
```
Looking at the entries for `.txt` and `.yaml`, we can find back the ordered list of parsers that were automatically tried in the above examples.


### 3- Multifile objects: combining several parsers

This **'the'** typical use case for this library. Suppose that you want to test the following `exec_op_series` function, that uses complex types `Series` and `AlgoConf` as inputs and `AlgoResults` as output:

```python
class AlgoConf(object):
    def __init__(self, foo_param: str, bar_param: int):
        self.foo_param = foo_param
        self.bar_param = bar_param

class AlgoResults(object):
    def __init__(self, score: float, perf: float):
        self.score = score
        self.perf = perf

from pandas import Series
def exec_op_series(x: Series, y: AlgoConf) -> AlgoResults:
    # ... intelligent stuff here...
    pass
```

Similar to what we've done in previous chapter, each test dataset can be represented as an object, containing the inputs and expected outputs. For example with this class:

```python
class ExecOpSeriesTest(object):

    def __init__(self, x: Series, y: AlgoConf, expected_results: AlgoResults):
        self.x = x
        self.y = y
        self.expected_results = expected_results
```

Our test data folder look like this : 
```
./demo/complex_objects
├── case1
│   ├── expected_results.txt
│   ├── x.csv
│   └── y.txt
└── case2
    ├── expected_results.txt
    ├── x.csv
    └── y.txt
```

You may notice that in this case, we chose to represent each instance of `ExecOpSeriesTest` as a folder. This makes them 'multifile'. The default multifile object parser in the framework will try to parse each attribute of the constructor as an independent file in the folder. 

The code for parsing remains the same - we tell the framework that we want to parse a collection of objects of type `ExecOpSeriesTest`. The rest is handled automatically by the framework:

```python
from pprint import pprint
from parsyfiles import parse_collection

mf_tests = parse_collection('./demo/complex_objects', ExecOpSeriesTest)
pprint(mf_tests)
```

Here are the results :

```
**** Starting to parse  collection of <ExecOpSeriesTest> at location ./demo/complex_objects ****
Checking all files under ./demo/complex_objects
./demo/complex_objects (multifile)
(...)
File checks done

Building a parsing plan to parse ./demo/complex_objects (multifile) into a Dict[str, ExecOpSeriesTest]
(...)
Parsing Plan created successfully

Executing Parsing Plan for ./demo/complex_objects (multifile) > Dict[str, ExecOpSeriesTest] ------- using Multifile Collection parser (parsyfiles defaults)
(...)
--> Successfully parsed a Dict[str, ExecOpSeriesTest] from ./demo/complex_objects
Completed parsing successfully

{'case1': <ExecOpSeriesTest object at 0x00000000087DDF98>,
 'case2': <ExecOpSeriesTest object at 0x000000000737FBE0>}
```

Note that multifile objects and singlefile objects may coexist in the same folder, and that parsing is recursive - meaning that multifile objects or collections may contain multifile children as well.


### 5- Advanced topics

#### (a) Lazy parsing

The multifile collection parser included in the library provides an option to return a lazy collection instead of a standard `set`, `list`, `dict` or `tuple`. This collection will trigger parsing of each element only when that element is required. In addition to better controlling the parsing time, this feature is especially useful if you want to parse the most items possible, even if one item in the list fails parsing. 

```python
from pprint import pprint
from parsyfiles import parse_collection
from pandas import DataFrame

dfs = parse_collection('./demo/simple_collection', DataFrame, lazy_mfcollection_parsing=True)
print('dfs length : ' + str(len(dfs)))
print('dfs keys : ' + str(dfs.keys()))
print('Is b in dfs : ' + str('b' in dfs))
pprint(dfs.get('b'))
```

The result log shows that `parse_collection` returned without parsing, and that parsing is executed when item `'b'` is read from the dictionary:
 
 ```
Executing Parsing Plan for ./demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Collection parser (parsyfiles defaults)
Parsing ./demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Collection parser (parsyfiles defaults)
Assembling a Dict[str, DataFrame] from all children of ./demo/simple_collection (multifile) (lazy parsing: children will be parsed when used) 
--> Successfully parsed a Dict[str, DataFrame] from ./demo/simple_collection
Completed parsing successfully

dfs length : 5
dfs keys : {'a', 'e', 'd', 'c', 'b'}
Is b in dfs : True
Executing Parsing Plan for ./demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_df_or_series_from_csv>
Parsing ./demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_df_or_series_from_csv>
--> Successfully parsed a DataFrame from ./demo/simple_collection\b
Completed parsing successfully
   a  b  c  d
0  1  2  3  4
```

#### (b) Parsing wrappers of existing types - writing proxy classes

**TODO** : show how to parse a `TimeSeries` class that extends `DataFrame`, by registering a custom converter between the two types

**TODO** old comments to reuse in the explanation : 

This is named a dynamic proxy. The `OpConfig` class extends the `dict` class, but delegates everything to the underlying `dict` implementation provided in the constructor.

*Note: this pattern is very useful to use this library, even if the underlying class is not an 'item collection' type. Indeed, this is a good way to create specialized versions of generic objects created by your favourite parsers. For example two `pandas.DataFrame` might represent a training set, and a prediction table. Both objects, although similar (both are tables with rows and columns), might have very different contents (column names, column types, number of rows, etc.). We can make this fundamental difference appear at the parsing level, by creating two classes.*


#### (c) Contract validation for parsed objects : combo with classtools-autocode

Users may wish to use [classtools_autocode](https://github.com/smarie/python-classtools-autocode) in order to create very compact classes representing their objects while at the same time ensuring that parsed data is valid according to some contract. Parsyfiles is totally compliant with such classes:

```python
from classtools_autocode import autoprops, autoargs
from contracts import contract, new_contract

# custom contract used in the class
new_contract('allowed_op', lambda x: x in {'+','*'})

@autoprops
class ExecOpTest(object):
    @autoargs
    @contract(x='int|float', y='int|float', op='str,allowed_op', expected_result='int|float')
    def __init__(self, x: float, y: float, op: str, expected_result: float):
        pass

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)

sf_tests = parse_collection('./demo/simple_objects', ExecOpTest)
```

The above code has a contract associated to `allowed_op` that checks that it must be in `{'+','*'}`. When `'-'` is found in a test file, it fails:

```
  ParsingException : Error while parsing ./demo/simple_objects\test_diff_1 (singlefile, .cfg) as a ExecOpTest with parser '$<read_config> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
  ObjectInstantiationException : Error while building object of type <ExecOpTest> using its constructor and parsed contents : {'y': 1.0, 'x': 1.0, 'expected_result': 0.0, 'op': '-'} : 
<class 'contracts.interface.ContractNotRespected'> Breach for argument 'op' to ExecOpTest:generated_setter_fun().
Value does not pass criteria of <lambda>()() (module: test_parsyfiles).
checking: callable()       for value: Instance of <class 'str'>: '-'   
checking: allowed_op       for value: Instance of <class 'str'>: '-'   
checking: str,allowed_op   for value: Instance of <class 'str'>: '-'   
```

#### (d) File mappings: Wrapped/Flat and encoding

In [3- Multifile objects: combining several parsers](#3--multifile-objects-combining-several-parsers) we used folders to encapsulate objects. In previous examples we also used the root folder to encapsulate the main item collection. This default setting is known as 'Wrapped' mode and correspond behind the scenes to a `WrappedFileMappingConfiguration` being used, with default python encoding. 

Alternatively you may wish to use flat mode. In this case the folder structure should be flat, as shown below. Item names and field names are separated by a configurable character string. For example to parse the same example as in [3- Multifile objects: combining several parsers](#3--multifile-objects-combining-several-parsers) but with the following flat tree structure:

```bash
.
├── case1--expected_results.txt
├── case1--x.csv
├── case1--y.txt
├── case2--expected_results.txt
├── case2--x.csv
└── case2--y.txt
```

you'll need to call

```python
from parsyfiles import FlatFileMappingConfiguration
dfs = parse_collection('./demo/complex_objects_flat', DataFrame, file_mapping_conf=FlatFileMappingConfiguration())
```

Note that `FlatFileMappingConfiguration` may be configured to use another separator sequence than `'--'` by passing it to the constructor: e.g. `FlatFileMappingConfiguration(separator='_')`. A dot `'.'` may be safely used as a separator too.

Finally you may change the file encoding used by both file mapping configurations : `WrappedFileMappingConfiguration(encoding='utf-16')` `FlatFileMappingConfiguration(encoding='utf-16')`.


#### (e) Recursivity: Multifile children of Multifile objects

As said earlier in this tutorial, parsyfiles is able to parse multifile recursively, for example multifile collections of multifile objects, multifile objects containing attributes, etc.


##### Example recursivity in flat mode
 
```
./custom_old_demo_flat_coll
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

##### Example recursivity in wrapped mode

```
./custom_old_demo_coll
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


#### (f) Diversity of formats supported: DataFrames - revisited

Now that we've seen that parsyfiles is able to combine parsers and converters, we can try to parse `DataFrame` objects from many more sources:

```
./demo/simple_collection_dataframe_inference
├── a.csv
├── b.txt
├── c.xls
├── d.xlsx
├── s_b64_pickle.txt
├── t_pickle.pyc
├── u.json
├── v_properties.txt
├── w.properties
├── x.yaml
├── y.cfg
└── z.ini
```

*Note: once again you may find this example data folder in the [project sources](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/test_data)*

The code is the same:

```python
from pprint import pprint
from parsyfiles import parse_collection
from pandas import DataFrame

dfs = parse_collection('./demo/simple_collection_dataframe_inference', DataFrame)
pprint(dfs)
```

And here is the result

```
TODO
```


## See Also

* Check [here](https://github.com/webmaven/python-parsing-tools) for other parsers in Python, that you might wish to register as unitary parsers to perform specific file format parsing (binary, json, custom...) for some of your objects.

* Do you like this library ? You might also like [these](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python)* 

* This [cattrs](https://cattrs.readthedocs.io/en/latest/readme.html) project seems to have related interests, to check. 


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