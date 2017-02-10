# python simple file collection parsing framework (parsyfiles)
A declarative framework that combines many popular python parsers (json, jprops, yaml, pickle...) with your user-defined parsers and type converters, in order to easily read objects from files. It is able to read an object even if the object's content comes from several files requiring several parsers: this is typically useful to read test data where you want to combine datasets, parameters, expected results and what not. 

This library provides a *framework*, not a specific parser for a specific file format. By default several classic parsers from the python world are already registered, but it is also extremely easy to add more if your favourite parser is missing. Even better: if you just need to parse a derived type of a type that can already be parsed, you may simply need to register a *type converter*, the framework will link it to any compliant parser for you. 


**Intended audience:**

* developers looking for an easy way to parse dictionaries and simple objects from various formats (json, properties, cfg, csv...) using standard python libraries. They can combine this library with [classtools_autocode](https://github.com/smarie/python-classtools-autocode) to preserve compact, readable and content-validated classes.

* developers who already know how to parse their various files independently, but looking for a higher-level tool to read complex objects made of several files/folders and potentially requiring to combine several parsers.


**Typical use cases:**

* **read collections of test cases** on the file system - each test case being composed of several files (for example 2 'test inputs' .csv files, 1 'test configuration' .cfg file, and one 'reference test results' json or yaml file)
* more generally, **read complex objects that for some reason are not represented by a single file representation**, for example objects made of several csv files (timeseries + descriptive data), combinations of csv and xml/json files, configuration files, pickle files, etc.


*Note on the Intelligence/Speed tradeoff:*
This framework contains a bit of nontrivial logic in order to transparently infer which parser and conversion chain to use, and even in some cases to try several alternatives in order to guess what was your intent. This makes it quite powerful but will certainly be slower and more memory-consuming than writing a dedicated parser tailored for your specific case. However if you are looking for a tool to speedup your development so that you may focus on what's important (your business logic, algorithm implementation, test logic, etc) then have a try, it might do the job.


## Main features

* **Declarative (class-based)**: you *first* define the objects to parse - by creating or importing their class -, *then* you use `parse_item` or `parse_collection` on the appropriate folder or file path. 
* **Simple objects out-of-the-box**: if you're interested in parsing singlefile objects only requiring simple types in their constructor, then the framework is *already* able to parse them, for many singlefile formats (json, properties, txt, csv, yaml and more.).
* **Multifile collections out-of-the-box**: the framework is able to parse collections of objects, each represented by a file. Parsing may be done in a lazy fashion (each item is only read if needed) or in the background (in a separate thread).
* **Serialization**: pickle files (.pyc) are supported too. Base64-encoded pickle objects can also be included in any simple file content.
* **Multiparser**: the library will use the best parser adapted to each file format and desired type. At the time of writing the library:
    * knows **41** ways to parse a file
    * is able to parse **11** object types (including *'Any'* for generic parsers)
    * from **13** file extensions
* **Multifile+Multiparser objects**: You may therefore parse complex objects requiring a combination of several parsers to be built from several files. The framework will introspect the object constructor in order to know the list of required attributes to parse as well as their their type, and if they are mandatory or optional.
* **Recursive**: attributes may themselves be collections or complex types.
* Supports **two main file mapping flavours for Multifile objects**: the library comes with two ways to organize multifile objects such as collections: *wrapped* (each multifile object is a folder), or *flat* (all files are in the same folder, files belonging to the same multifile object have the same prefix)

In addition the library is

* **Extensible**. You may register any number of additional file parsers, or type converters, or both. When registering a parser you just have to declare the object types that it can parse, *and* the file extensions it can read. The same goes for converters: you declare the object type it can read, and the object type it can convert to. 
* **Intelligent** Since several parsers may be registered for the same file extension, and more generally several parsing chains (parser + converters) may be eligible to a given task, the library has a built-in set of rules to select the relevant parsing chains and test them in most plausible order. This provides you with several ways to parse the same object. This might be useful for example if some of your data comes from nominal tests, some other from field tests, some other from web service calls, etc. You don't need anymore to convert all of these to the same format before using it.
* **No annotations required**: as opposed to some data binding frameworks, this library is meant to parse object types that may already exist, and potentially only for tests. Therefore the framework does not require annotations on the type if there is there is a registered way to parse it. However if you wish to build higher-level objects encapsulating the result of several parsers, then PEP484 type hints are required. But that's probably less a problem since these objects are yours (they are part of your tests for example) 


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

### 1- Collections of known types : a list of DataFrame

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
./test_data/demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_dataframe_from_csv(stream mode)>
./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using [Try '<read_dataframe_from_csv(stream mode)>' then '$<read_dict_from_properties(stream mode)> => <dict_to_object>$' then '$<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$]
./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_dataframe_from_csv(stream mode)>
./test_data/demo/simple_collection\c (singlefile, .xls) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
./test_data/demo/simple_collection\d (singlefile, .xlsx) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
./test_data/demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
Parsing Plan created successfully

Executing Parsing Plan for ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./test_data/demo/simple_collection\a (singlefile, .csv) > DataFrame ------- using <read_dataframe_from_csv(stream mode)>
--> Successfully parsed a DataFrame from ./test_data/demo/simple_collection\a
Parsing ./test_data/demo/simple_collection\b (singlefile, .txt) > DataFrame ------- using <read_dataframe_from_csv(stream mode)>
--> Successfully parsed a DataFrame from ./test_data/demo/simple_collection\b
Parsing ./test_data/demo/simple_collection\c (singlefile, .xls) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
--> Successfully parsed a DataFrame from ./test_data/demo/simple_collection\c
Parsing ./test_data/demo/simple_collection\d (singlefile, .xlsx) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
--> Successfully parsed a DataFrame from ./test_data/demo/simple_collection\d
Parsing ./test_data/demo/simple_collection\e (singlefile, .xlsm) > DataFrame ------- using <read_dataframe_from_xls(file mode)>
--> Successfully parsed a DataFrame from ./test_data/demo/simple_collection\e
Assembling all parsed child items into a Dict[str, DataFrame] to build ./test_data/demo/simple_collection (multifile)
--> Successfully parsed a Dict[str, DataFrame] from ./test_data/demo/simple_collection
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

* first it recursively **checks your folder** to check that it is entirely compliant with the file mapping format. That is the log section beginning with "`Checking all files under ./test_data/demo/simple_collection`". If the same item appears twice (e.g. `a.csv` and `a.txt`)  it will throw an error at this stage (an `ObjectPresentMultipleTimesOnFileSystemError`).

* then it recursively **creates a parsing plan** that is able to produce an object the required type. That's the section beginning with "`Building a parsing plan to parse ./test_data/demo/simple_collection (multifile) into a Dict[str, DataFrame]`". Here you may note that by default, a collection of items is actually parsed as an object of type dictionary, where the key is the name of the file without extension, and the value is the object that is parsed from the file. If at this stage it does not find a way to parse a given file into the required object type, it will fail. For example if you add a file in the folder, named `unknown_ext_for_dataframe.ukn`, you will get an error (a `NoParserFoundForObjectExt`).

* finally it **executes the parsing plan**. That's the section beginning with "`Executing Parsing Plan for ./test_data/demo/simple_collection (multifile) > Dict[str, DataFrame] (...)`".

It is important to understand these 3 log sections, since the main issue with complex frameworks is debugging when something unexpected happens :-).

#### Note: parsing a single file

The following code may be used to parse a single file explicitly:

```python
from pprint import pprint
from parsyfiles import parse_item
from pandas import DataFrame

df = parse_item('./demo/simple_collection/c', DataFrame)
pprint(df)
```

Important : note that the file extension does not appear in the argument of the `parse_item` function. 


### 2- Simple user-defined types

Suppose that you want to test the following function, and you want to read your test datasets from a bunch of files.

```python
def exec_op(x: float, y: float, op: str) -> float:
    if op is '+':
        return x+y
    elif op is '-':
        return x-y
    else:
        raise ValueError('Unsupported operation : \'' + op + '\'')
```

Each test dataset could be represented as an object, containing the inputs and expected outputs. For example with this class:

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

Obviously this class is not known by the `parsyfiles` framework: there is no registered parser for the specific type `ExecOpTest`. However the type is fairly simple, so it can actually fit into a dictionary easily. `parsyfiles` knows a couple ways to parse dictionaries, using python standard libraries:

* From a `.cfg` or `.ini` file using the `configparser` module
* From a `.json` file using the `json` module
* From a `.properties` or `.txt` file using the `jprops` module
* From a `.yaml` or `.yml` file using the `yaml` module
* From a `.csv`, `.txt`, `.xls`, `.xlsx`, `.xlsm` file using the `pandas` module
* ...

It also knows how to convert a dictionary into an object, as long as the object constructor contains the right information about expected types. For example in the example above, the constructor has explicit PEP484 annotations `x: float, y: float, op: str, expected_result: float`.

So let's give it a try. Our test data folder looks like this:

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

e = parse_collection('./test_data/demo/simple_objects', ExecOpTest)
pprint(e)
```

Here is the result:

```
**** Starting to parse  collection of <ExecOpTest> at location ./test_data/demo/simple_objects ****
Checking all files under ./test_data/demo/simple_objects
(... removed for readability ...)
File checks done

Building a parsing plan to parse ./test_data/demo/simple_objects (multifile) into a Dict[str, ExecOpTest]
(... removed for readability ...)
Parsing Plan created successfully

Executing Parsing Plan for ./test_data/demo/simple_objects (multifile) > Dict[str, ExecOpTest] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)
Parsing ./test_data/demo/simple_objects (multifile) > Dict[str, ExecOpTest] ------- using Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item)

(... removed for readability ...)

Parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_dict_from_properties(stream mode)> => <dict_to_object>$
!!!! Caught error during execution : 
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\support_for_objects.py", line 266, in dict_to_object
    attr_name)
  ParsingException : Error while parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_dict_from_properties(stream mode)> => <dict_to_object>$' using args=(()) and kwargs=({}) : caught 
  InvalidAttributeNameForConstructorError : Cannot parse object of type <ExecOpTest> using the provided configuration file: configuration contains a property name ('x,y,op,expected_result')that is not an attribute of the object constructor. <ExecOpTest> constructor attributes are : ['op', 'expected_result', 'y', 'x']
----- Rebuilding local parsing plan with next candidate parser:
./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$
Parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$
!!!! Caught error during execution : 
  File "C:\Anaconda3\envs\azuremlbricks\lib\base64.py", line 88, in b64decode
    return binascii.a2b_base64(s)
  ParsingException : Error while parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$' using args=(()) and kwargs=({}) : caught 
  Error : Incorrect padding
----- Rebuilding local parsing plan with next candidate parser:
./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt(stream mode)> => <construct_from_str>$
Parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_str_from_txt(stream mode)> => <construct_from_str>$
!!!! Caught error during execution : 
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\support_for_primitive_types.py", line 23, in primitive_to_anything_by_constructor_call
    return desired_type(source)
  ParsingException : Error while parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) as a ExecOpTest with parser '$<read_str_from_txt(stream mode)> => <construct_from_str>$' using args=(()) and kwargs=({}) : caught 
  TypeError : __init__() missing 3 required positional arguments: 'y', 'op', and 'expected_result'
----- Rebuilding local parsing plan with next candidate parser:
./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_dataframe_from_csv(stream mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$
Parsing ./test_data/demo/simple_objects\test_diff_3_csv_format (singlefile, .txt) > ExecOpTest ------- using $<read_dataframe_from_csv(stream mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$
--> Successfully parsed a ExecOpTest from ./test_data/demo/simple_objects\test_diff_3_csv_format

(... removed for readability ...)

Parsing ./test_data/demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using <read_object_from_yaml(stream mode)>
!!!! Caught error during execution : 
  File "C:\W_dev\_pycharm_workspace\python-parsyfiles\parsyfiles\parsing_core_api.py", line 365, in execute
    res, *args, **kwargs)
  ParsingException : Error while parsing ./test_data/demo/simple_objects\test_sum_4 (singlefile, .yaml) as a <class 'test_parsyfiles.DemoTests.test_simple_objects.<locals>.ExecOpTest'> with parser '<read_object_from_yaml(stream mode)>' using args=(()) and kwargs=({}) : parser returned {'y': 5, 'x': 2, 'op': '+', 'expected_result': 7} of type <class 'dict'> which is not an instance of <class 'test_parsyfiles.DemoTests.test_simple_objects.<locals>.ExecOpTest'>
----- Rebuilding local parsing plan with next candidate parser:
./test_data/demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using $<read_collection_from_yaml> => <dict_to_object>$
Parsing ./test_data/demo/simple_objects\test_sum_4 (singlefile, .yaml) > ExecOpTest ------- using $<read_collection_from_yaml> => <dict_to_object>$
--> Successfully parsed a ExecOpTest from ./test_data/demo/simple_objects\test_sum_4

(... removed for readability ...)

Assembling all parsed child items into a Dict[str, ExecOpTest] to build ./test_data/demo/simple_objects (multifile)
--> Successfully parsed a Dict[str, ExecOpTest] from ./test_data/demo/simple_objects
Completed parsing successfully

{'test_diff_1': 1.0 - 1.0 =? 0.0,
 'test_diff_2': 0.0 - 1.0 =? -1.0,
 'test_diff_3_csv_format': 5.0 - 4.0 =? 1.0,
 'test_sum_1': 1.0 + 2.0 =? 3.0,
 'test_sum_2': 0.0 + 1.0 =? 1.0,
 'test_sum_3_properties_format': 1.0 + 1.0 =? 2.0,
 'test_sum_4': 2.0 + 5.0 =? 7.0,
 'test_sum_5': 56.0 + 12.0 =? 68.0,
 'test_sum_6': 56.0 + 13.0 =? 69.0,
 'test_sum_7': 56.0 + 14.0 =? 70.0}
```

This time the parser is a little bit more verbose. This is because two files were quite difficult to parse: `test_diff_3_csv_format.txt` and `test_sum_4.yaml`.

* For `test_diff_3_csv_format.txt` is a txt file that contains csv-format data. The issue is that txt files may also contain many other formats. You can see from the logs that the framework successively tries several ways to parse this file :

    * `$<read_dict_from_properties(stream mode)> => <dict_to_object>$`: the txt file is read in the 'properties' format (using `jprops`) into a dictionary, and then the dictionary is converted to a `ExecOpTest` object. This fails.
    * `$<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$` : the txt file is read as a string, and then the string is interpreted as a base64-encoded pickle `ExecOpTest` object (!). This fails.
    * `$<read_str_from_txt(stream mode)> => <construct_from_str>$`: the txt file is read as a string, and then the constructor of `ExecOpTest` is called with that string as unique argument. This fails again.
    * `$<read_dataframe_from_csv(stream mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$`: the txt file is read as a csv into a DataFrame, then the DataFrame is converted to a dictionary, and finally the dictionary is converted into a `ExecOpTest` object. **This finally succeeds**.
    
* For `test_sum_4.yaml`, the difficulty is that yaml format may contain a dictionary or a collection directly, but is also able to contain any object thanks to the object directive. You can see from the logs that the framework successively tries several ways to parse this file :

    * `<read_object_from_yaml(stream mode)>`: the file is read according to the yaml format, as a `ExecOpTest` object directly. This fails.
    
    * `$<read_collection_from_yaml> => <dict_to_object>$`: the file is read according to the yaml format, as a dictionary. Then this dictionary is converted into a `ExecOpTest` object. **This succeeds**



This example shows how `parsyfiles` intelligently combines all registered parsers and converters to create parsing chains that make sense. These parsing chains are tried in order until a solution is found. Note that the order is deterministic:

* First all **exact match** parsers. This includes combinations of {parser + converter chain} that lead to an exact match, sorted by converter chain size: first the small conversion chains, last the large conversion chains.

* Then all **approximative match** parsers. This is similar to the "exact match" except that these are parsers able to parse a **subclass** of what you're asking for.

* Finally all **generic** parsers. This includes combinations of {parser + converter chain} that end with a generic converter (for example the "dict to object" converter seen in the example above)


In order to know in advance which file extensions and formats the framework will be able to parse, you may wish to use the following command:

```python
from parsyfiles import RootParser
RootParser().print_capabilities_for_type(typ=ExecOpTest)
```

The result is a dictionary where each entry is a file extension:
```
{'.cfg': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_config(stream mode)> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$,
                        $<read_config(stream mode)> => <config_to_dict_of_dict> -> <dict_of_dict_to_object>$,
                        $<read_config(stream mode)> => <config_to_dict_of_dict> -> <dict_to_object>$]},
 '.csv': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_simpledf_from_csv(stream mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.ini': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_config(stream mode)> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$,
                        $<read_config(stream mode)> => <config_to_dict_of_dict> -> <dict_of_dict_to_object>$,
                        $<read_config(stream mode)> => <config_to_dict_of_dict> -> <dict_to_object>$]},
 '.json': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_dict_or_list_from_json(stream mode)> => <dict_to_object>$]},
 '.properties': {'1_exact_match': [],
                 '2_approx_match': [],
                 '3_generic': [$<read_dict_from_properties(stream mode)> => <dict_to_object>$]},
 '.pyc': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [<read_object_from_pickle(stream mode)>]},
 '.txt': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_dict_from_properties(stream mode)> => <dict_to_object>$,
                        $<read_str_from_txt(stream mode)> => <base64_ascii_str_pickle_to_object>$,
                        $<read_str_from_txt(stream mode)> => <construct_from_str>$,
                        $<read_simpledf_from_csv(stream mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xls': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [$<read_simpledf_from_xls(file mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xlsm': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_simpledf_from_xls(file mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.xlsx': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [$<read_simpledf_from_xls(file mode)> => <single_row_or_col_df_to_dict> -> <dict_to_object>$]},
 '.yaml': {'1_exact_match': [],
           '2_approx_match': [],
           '3_generic': [<read_object_from_yaml(stream mode)>,
                         $<read_collection_from_yaml> => <dict_to_object>$]},
 '.yml': {'1_exact_match': [],
          '2_approx_match': [],
          '3_generic': [<read_object_from_yaml(stream mode)>,
                        $<read_collection_from_yaml> => <dict_to_object>$]},
 '<multifile>': {'1_exact_match': [],
                 '2_approx_match': [],
                 '3_generic': [Generic MF Object parser (based on 'parsyfiles defaults' to find the parser for each attribute),
                               $Multifile Dict parser (based on 'parsyfiles defaults' to find the parser for each item) => <dict_to_object>$]}}
```
Looking at the entries for `.txt` and `.yaml`, we can find back the ordered list of parsers tried in the above example

### 4- Dataframes - revisited

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
{'a':    a  b  c  d
      0  1  2  3  4,
 'b':    a  b  c  d
      0  1  2  3  4,
 'c': Empty DataFrame
Columns: []
Index: [],
 'd': Empty DataFrame
Columns: []
Index: [],
 's_b64_pickle': Empty DataFrame
Columns: [gANjcGFuZGFzLmNvcmUuZnJhbWUKRGF0YUZyYW1lCnEAKYFxAX1xAihYCQAAAF9tZXRhZGF0YXEDXXEEWAQAAABfdHlwcQVYCQAAAGRhdGFmcmFtZXEGWAUAAABfZGF0YXEHY3BhbmRhcy5jb3JlLmludGVybmFscwpCbG9ja01hbmFnZXIKcQgpgXEJKF1xCihjcGFuZGFzLmluZGV4ZXMuYmFzZQpfbmV3X0luZGV4CnELY3BhbmRhcy5pbmRleGVzLmJhc2UKSW5kZXgKcQx9cQ0oWAQAAABkYXRhcQ5jbnVtcHkuY29yZS5tdWx0aWFycmF5Cl9yZWNvbnN0cnVjdApxD2NudW1weQpuZGFycmF5CnEQSwCFcRFDAWJxEodxE1JxFChLAUsChXEVY251bXB5CmR0eXBlCnEWWAIAAABPOHEXSwBLAYdxGFJxGShLA1gBAAAAfHEaTk5OSv////9K/////0s/dHEbYoldcRwoWAEAAABjcR1LBWV0cR5iWAQAAABuYW1lcR9OdYZxIFJxIWgLY3BhbmRhcy5pbmRleGVzLnJhbmdlClJhbmdlSW5kZXgKcSJ9cSMoWAUAAABzdGFydHEkSwBYBAAAAHN0ZXBxJUsBWAQAAABzdG9wcSZLA2gfTnWGcSdScShlXXEpKGgPaBBLAIVxKmgSh3ErUnEsKEsBSwFLA4ZxLWgWWAIAAABpOHEuSwBLAYdxL1JxMChLA1gBAAAAPHExTk5OSv////9K/////0sAdHEyYolDGAgAAAAAAAAADAAAAAAAAAADAAAAAAAAAHEzdHE0YmgPaBBLAIVxNWgSh3E2UnE3KEsBSwFLA4ZxOGgZiV1xOShYAQAAAGRxOlgBAAAAZXE7WAEAAABmcTxldHE9YmVdcT4oaAtoDH1xPyhoDmgPaBBLAIVxQGgSh3FBUnFCKEsBSwGFcUNoGYldcURLBWF0cUViaB9OdYZxRlJxR2gLaAx9cUgoaA5oD2gQSwCFcUloEodxSlJxSyhLAUsBhXFMaBmJXXFNaB1hdHFOYmgfTnWGcU9ScVBlfXFRWAYAAAAwLjE0LjFxUn1xUyhYBAAAAGF4ZXNxVGgKWAYAAABibG9ja3NxVV1xVih9cVcoWAYAAAB2YWx1ZXNxWGgsWAgAAABtZ3JfbG9jc3FZY2J1aWx0aW5zCnNsaWNlCnFaSwFLAksBh3FbUnFcdX1xXShoWGg3aFloWksASwFLAYdxXlJxX3VldXN0cWBidWIu]
Index: [],
 't_pickle':    c   5
             0  d   8
             1  e  12
             2  f   3,
 'u':    a  b  c  d
      0  1  2  +  3,
 'v_properties':    a = 1
                 0  b = 1
                 1  c = +
                 2  d = 2,
 'w':    a  b  c  d
      0  0  1  +  1,
 'x':    r  t  u  x
      0  7  +  5  2,
 'y':    d  r  s  t
      0  0  1  1  -,
 'z':     d  r  s  t
      0  -1  0  1  -
}
```


### 5- Complex and multifile types

We have seen in both examples above that the framework is able to read multifile collection types: an object of type `Dict`, `List`, `Set`, and `Tuple` may be read from a folder.

```python
from pprint import pprint
from parsyfiles import parse_collection
from pandas import DataFrame

dfs = parse_collection('./demo/simple_collection', DataFrame)
pprint(dfs)
```



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