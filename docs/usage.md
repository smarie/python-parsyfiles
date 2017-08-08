# Usage

## Basic

### Parsing one file

Let's parse a single file containing a string: [hello_world.txt](./demo/a_helloworld/hello_world.txt). First right-click on this link and select 'save as' to save the file in your current working directory. Then

```python
from parsyfiles import parse_item

result = parse_item('hello_world', str)
print(result)
```

yields:

```bash
--> Successfully parsed a str from hello_world

hello
```

### Never include the file extension !

Note that the file extension should never be included when referencing a file with parsyfiles. This is because objects may be parsed from files or folders:

```python
result = parse_item('hello_world.txt', str)  # ObjectNotFoundOnFileSystemError
```

### Unsupported extensions

Lets rename our file `hello_world.ukn` and run the script again. We get a different exception:

```bash
parsyfiles.parsing_registries.NoParserFoundForObjectExt: hello_world (singlefile, .ukn) cannot be parsed as a str because no parser supporting that extension (singlefile, .ukn) is registered.
 If you wish to parse this fileobject in that type, you may replace the file with any of the following extensions currently supported :{'.yml', '.yaml', '<multifile>', '.txt', '.pyc'} (see get_capabilities_for_type(str, strict_type_matching=False) for details).
Otherwise, please register a new parser for type str and extension singlefile, .ukn
```

This is pretty explicit: the framework is not able to parse our file, because there is currently no registered parser for this extension `.ukn` and this desired type `str`. This example is a good introduction to the way `parsyfiles` parser registry works: parsers are registered for a combination of *supported file extensions* and *supported destination types*. Everytime you wish to parse some file into some type, the framework checks if there are any capable parsers, and tries them all in the most logical order. We'll see that in more details below.


### Log levels

By default the library uses a `Logger` that has an additional handler to print to `stdout`. The default level is `INFO`. This is how you change the module default logging level:

```python
import logging
logging.getLogger('parsyfiles').setLevel(logging.DEBUG)
```

Running the same example again yieds a much more verbose output:

```bash
**** Starting to parse single object  of type <str> at location hello_world ****
Checking all files under hello_world
hello_world (singlefile, .txt)
File checks done

Building a parsing plan to parse hello_world (singlefile, .txt) into a str
hello_world (singlefile, .txt) > str ------- using <read_str_from_txt>
Parsing Plan created successfully

Executing Parsing Plan for hello_world (singlefile, .txt) > str ------- using <read_str_from_txt>
Parsing hello_world (singlefile, .txt) > str ------- using <read_str_from_txt>
--> Successfully parsed a str from hello_world
Completed parsing successfully
```

### Understanding the debug-level Log messages

In the log output above you see a couple hints on how the parsing framework works:

* first it **checks your files**. That is the log section beginning with "`Checking all files ...`". If there is a missing file issue it will appear at this stage as an `ObjectNotFoundOnFileSystemError`.

* then it **creates a parsing plan** that is able to produce an object the required type. That's the section beginning with "`Building a parsing plan ...`". The parsing plan is the most important concept in the library, and the most complex. A parsing plan describes what the framework *will* try to perform when it will actually execute the parsing step (next step, below). If a parsing plan cannot be built at this stage you get a `NoParserFoundForObjectExt` error like the one we saw [previously](#unsupported_extensions). In this example we see that the parsing plan is straightforward: the framework will use a single parser, named `<read_str_from_txt>`.

* finally it **executes the parsing plan**. That's the section beginning with "`Executing Parsing Plan...`". Sometimes you will see in this section that the original plan gets updated as a consequence of parsing errors. For example a 'plan A' will be replaced by a 'plan B'. We will see some examples later on.

It is important to understand these 3 log sections, since the main issue with complex frameworks is debugging when something unexpected happens :-).

### Custom logger

You may also wish to provide your own logger:

```python
from logging import FileHandler
my_logger = logging.getLogger('mine')
my_logger.addHandler(FileHandler('hello.log'))
my_logger.setLevel(logging.INFO)
result = parse_item('hello_world', str, logger = my_logger)
```


# TODO refresh remaining sections


## Part 1 - Parsing collections of known types

### (a) Example: parsing a list of DataFrame

The most simple case of all: you wish to parse a collection of files that all have the same type, and for which a parser is already registered. For example your wish to parse a list of `DataFrame` for a data folder that looks like this:

```bash
./demo/simple_collection
├── a.csv
├── b.txt
├── c.xls
├── d.xlsx
└── e.xlsm
```
*Note: you may find this example data folder in the [project sources](https://minhaskamal.github.io/DownGit/#/home?url=https://github.com/smarie/python-parsyfiles/tree/master/parsyfiles/test_data/demo/simple_collection)*

Parsing all of these dataframes is straightforward:

```python
from parsyfiles import parse_collection, pprint_out
from pandas import DataFrame

dfs = parse_collection('./data/simple_collection', DataFrame)
pprint_out(dfs)
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


### (b) Understanding the log output


In the log output you see a couple hints on how the parsing framework works:

* first it recursively **checks your folder** to check that it is entirely compliant with the file mapping format. That is the log section beginning with "`Checking all files under ./demo/simple_collection`". If the same item appears twice (e.g. `a.csv` and `a.txt`)  it will throw an error at this stage (an `ObjectPresentMultipleTimesOnFileSystemError`).

* then it recursively **creates a parsing plan** that is able to produce an object the required type. That's the section beginning with "`Building a parsing plan to parse ./demo/simple_collection (multifile) into a Dict[str, DataFrame]`". Here you may note that by default, a collection of items is actually parsed as an object of type dictionary, where the key is the name of the file without extension, and the value is the object that is parsed from the file. If at this stage it does not find a way to parse a given file into the required object type, it will fail. For example if you add a file in the folder, named `unknown_ext_for_dataframe.ukn`, you will get an error (a `NoParserFoundForObjectExt`).

* finally it **executes the parsing plan**. That's the section beginning with "`Executing Parsing Plan for ./demo/simple_collection (multifile) > Dict[str, DataFrame] (...)`".

It is important to understand these 3 log sections, since the main issue with complex frameworks is debugging when something unexpected happens :-).


### (c) Parsing a single file only

The following code may be used to parse a single file explicitly:

```python
from pprint import pprint
from parsyfiles import parse_item
from pandas import DataFrame

df = parse_item('./demo/simple_collection/c', DataFrame)
pprint(df)
```

Important : note that the file extension does not appear in the argument of the `parse_item` function. 


### (d) Default collection type and other supported types 

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


## Part 2 - Simple user-defined types

### (a) Example: parsing a collection of test cases

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
* etc.

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


### (b) Under the hood : why does it work, even on ambiguous files? 

In the example above, three files were actually quite difficult to parse into a `dict` before being converted to an `ExecOpTest`: `test_diff_3_csv_format.txt`, `test_diff_4_csv_format2.txt` and `test_sum_4.yaml`. Let's look at both cases in details.

#### Solved Difficulty 1 - Several formats/parsers for the same file extension

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
    
    
#### Solved Difficulty 2 - Generic parsers

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


#### Understanding the inference logic - in which order are the parsers tried ?

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


## Part 3 - Multifile objects: combining several parsers

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


## Part 4 - Advanced topics

The `parse_collection` and `parse_item` that we have used in most examples are actually just helper methods to build a parser registry (`RootParser()`) and use it. Most of the advanced topics below use this object directly.


### (a) Lazy parsing

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

### (b) Passing options to existing parsers

Parsers and converters support options. In order to know which options are available for a specific parser, the best is to identify it and ask it. For example if you want to know what are the options available for the parsers reading `DataFrame` objects :

```python
from pandas import DataFrame
from parsyfiles import RootParser

# create a root parser
parser = RootParser()

# retrieve the parsers of interest
parsers = parser.get_capabilities_for_type(DataFrame, strict_type_matching=False)
df_csv_parser = parsers['.csv']['1_exact_match'][0]
p_id_csv = df_csv_parser.get_id_for_options()
print('Parser id for csv is : ' + p_id_csv + ', implementing function is ' + repr(df_csv_parser._parser_func))
print(' * ' + df_csv_parser.options_hints())
df_xls_parser = parsers['.xls']['1_exact_match'][0]
p_id_xls = df_xls_parser.get_id_for_options()
print('Parser id for csv is : ' + p_id_xls + ', implementing function is ' + repr(df_xls_parser._parser_func))
print(' * ' + df_xls_parser.options_hints())
```

The result is:

```
Parser id for csv is : read_df_or_series_from_csv, implementing function is <function read_df_or_series_from_csv at 0x0000000007391378>
 * read_df_or_series_from_csv: all options from read_csv are supported, see http://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html
Parser id for csv is : read_dataframe_from_xls, implementing function is <function read_dataframe_from_xls at 0x0000000007391158>
 * read_dataframe_from_xls: all options from read_excel are supported, see http://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_excel.html
```

Then you may set the options accordingly on the root parser before calling it

```python
from parsyfiles import create_parser_options, add_parser_options

# configure the DataFrame parsers to automatically parse dates and use the first column as index
opts = create_parser_options()
opts = add_parser_options(opts, 'read_df_or_series_from_csv', {'parse_dates': True, 'index_col': 0})
opts = add_parser_options(opts, 'read_dataframe_from_xls', {'index_col': 0})

dfs = parser.parse_collection('./test_data/demo/ts_collection', DataFrame, options=opts)
print(dfs)
```

Results:

```
{'a':                    a  b  c  d
	time                           
	2015-08-28 23:30:00  1  2  3  4
	2015-08-29 00:00:00  1  2  3  5, 
 'c':           a  b
	date            
	2015-01-01  1  2
	2015-01-02  4  3, 
 'b':                    a  b  c  d
	time                           
	2015-08-28 23:30:00  1  2  3  4
	2015-08-29 00:00:00  1  2  3  5}
```

### (c) Parsing subclasses of existing types - registering converters

Imagine that you want to parse a subtype of something the framework already knows to parse. For example a `TimeSeries` class of your own, that extends `DataFrame`:

```python
from pandas import DataFrame, DatetimeIndex

class TimeSeries(DataFrame):
    """
    A dummy timeseries class that extends DataFrame
    """

    def __init__(self, df: DataFrame):
        """
        Constructor from a DataFrame. The DataFrame index should be an instance of DatetimeIndex
        :param df:
        """
        if isinstance(df, DataFrame) and isinstance(df.index, DatetimeIndex):
            if df.index.tz is None:
                df.index = df.index.tz_localize(tz='UTC')# use the UTC hypothesis in absence of other hints
            self._df = df
        else:
            raise ValueError('Error creating TimeSeries from DataFrame: provided DataFrame does not have a '
                             'valid DatetimeIndex')

    def __getattr__(self, item):
        # Redirects anything that is not implemented here to the base dataframe.
        # this is called only if the attribute was not found the usual way

        # easy version of the dynamic proxy just to save time :)
        # see http://code.activestate.com/recipes/496741-object-proxying/ for "the answer"
        df = object.__getattribute__(self, '_df')
        if hasattr(df, item):
            return getattr(df, item)
        else:
            raise AttributeError('\'' + self.__class__.__name__ + '\' object has no attribute \'' + item + '\'')

    def update(self, other, join='left', overwrite=True, filter_func=None, raise_conflict=False):
        """ For some reason this method was abstract in DataFrame so we have to implement it """
        return self._df.update(other, join=join, overwrite=overwrite, filter_func=filter_func,
                               raise_conflict=raise_conflict)
```

It is relatively easy to write a converter between a `DataFrame` and a `TimeSeries`. `parsyfiles` provides classes that you should use to define your converters, for example here `ConverterFunction`, that takes as argument a conversion method with a specific signature - hence the extra unused arguments in `df_to_ts`:

```python
from typing import Type
from logging import Logger
from parsyfiles.converting_core import ConverterFunction

def df_to_ts(desired_type: Type[TimeSeries], df: DataFrame, logger: Logger) -> TimeSeries:
    """ Converter from DataFrame to TimeSeries """
    return TimeSeries(df)

my_converter = ConverterFunction(from_type=DataFrame, to_type=TimeSeries, conversion_method=df_to_ts)
```

You have to create the parser manually in order to register your converter:

```python
from parsyfiles import RootParser, create_parser_options, add_parser_options

# create a parser
parser = RootParser('parsyfiles with timeseries')
parser.register_converter(my_converter)
```

In some cases you may wish to change the underlying parsers options. This is possible provided that you know the identifier of the parser you wish to configure (typically it is the one appearing in the logs):

```python
# configure the DataFrame parsers to read the first column as an datetime index
opts = create_parser_options()
opts = add_parser_options(opts, 'read_df_or_series_from_csv', {'parse_dates': True, 'index_col': 0})
opts = add_parser_options(opts, 'read_dataframe_from_xls', {'index_col': 0})
```

Finally, parsing is done the same way than before:

```python
dfs = parser.parse_collection('./test_data/demo/ts_collection', TimeSeries, options=opts)
```

*Note: you might have noticed that `TimeSeries` is a dynamic proxy. The `TimeSeries` class extends the `DataFrame` class, but delegates everything to the underlying `DataFrame` implementation provided in the constructor. This pattern is a good way to create specialized versions of generic objects created by your favourite parsers. For example two `DataFrame` might represent a training set, and a prediction table. Both objects, although similar (both are tables with rows and columns), might have very different contents (column names, column types, number of rows, etc.). We can make this fundamental difference appear at parsing level, by creating two classes.*


### (d) Registering a new parser

Parsyfiles offers several ways to register a parser. Here is a simple example, where we register a basic 'singlefile' xml parser:

```python
from typing import Type
from parsyfiles import RootParser
from parsyfiles.parsing_core import SingleFileParserFunction, T
from logging import Logger
from xml.etree.ElementTree import ElementTree, parse, tostring

def read_xml(desired_type: Type[T], file_path: str, encoding: str,
             logger: Logger, **kwargs):
    """
    Opens an XML file and returns the tree parsed from it as an ElementTree.

    :param desired_type:
    :param file_path:
    :param encoding:
    :param logger:
    :param kwargs:
    :return:
    """
    return parse(file_path)

my_parser = SingleFileParserFunction(parser_function=read_xml,
                                     streaming_mode=False,
                                     supported_exts={'.xml'},
                                     supported_types={ElementTree})

parser = RootParser('parsyfiles with timeseries')
parser.register_parser(my_parser)
xmls = parser.parse_collection('./test_data/demo/xml_collection', ElementTree)
print({name: tostring(x.getroot()) for name, x in xmls.items()})
```

For more examples on how the parser API can be used, please have a look at the [core](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/plugins_base) and [optional](https://github.com/smarie/python-simple-file-collection-parsing-framework/tree/master/parsyfiles/plugins_optional) plugins.

### (e) Contract validation for parsed objects : combo with classtools-autocode and attrs

Users may wish to use [classtools_autocode](https://github.com/smarie/python-classtools-autocode) or [attrs](https://attrs.readthedocs.io/en/stable/) in order to create very compact classes representing their objects while at the same time ensuring that parsed data is valid according to some contract. Parsyfiles is totally compliant with such classes, as shown in the examples below

#### classtools-autocode example

```python
from classtools_autocode import autoprops, autoargs
from contracts import contract, new_contract

# custom PyContract used in the class
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

```bash
ParsingException : Error while parsing ./demo/simple_objects\test_diff_1 (singlefile, .cfg) as a ExecOpTest with parser '$<read_config> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
ObjectInstantiationException : Error while building object of type <ExecOpTest> using its constructor and parsed contents : {'y': 1.0, 'x': 1.0, 'expected_result': 0.0, 'op': '-'} : 
<class 'contracts.interface.ContractNotRespected'> Breach for argument 'op' to ExecOpTest:generated_setter_fun().
Value does not pass criteria of <lambda>()() (module: test_parsyfiles).
checking: callable()       for value: Instance of <class 'str'>: '-'   
checking: allowed_op       for value: Instance of <class 'str'>: '-'   
checking: str,allowed_op   for value: Instance of <class 'str'>: '-'   
```

#### attrs example

In order for parsyfiles to find the required type for each attribute declared using `attrs`, you will have to use `attr.validators.instance_of`. However, since you may wish to also implement some custom validation logic, we provide (until it is offically added in `attrs`) a chaining operator. The code below shows how to create a similar example than the previous one:

```python
import attr
from attr.validators import instance_of
from parsyfiles.plugins_optional.support_for_attrs import chain

# custom contract used in the class
def validate_op(instance, attribute, value):
    allowed = {'+','*'}
    if value not in allowed:
        raise ValueError('\'op\' has to be a string, in ' + str(allowed) + '!')

@attr.s
class ExecOpTest(object):
    x = attr.ib(convert=float, validator=instance_of(float))
    y = attr.ib(convert=float, validator=instance_of(float))
    # we use the 'chain' validator here to keep using instance_of
    op = attr.ib(convert=str, validator=chain(instance_of(str), validate_op))
    expected_result = attr.ib(convert=float, validator=instance_of(float))

# with self.assertRaises(ParsingException):
sf_tests = parse_collection('./test_data/demo/simple_objects', ExecOpTest)
```

When `'-'` is found in a test file, it also fails with a nice error message:

```bash
ParsingException : Error while parsing ./test_data/demo/simple_objects\test_diff_1 (singlefile, .cfg) as a ExecOpTest with parser '$<read_config> => <merge_all_config_sections_into_a_single_dict> -> <dict_to_object>$' using options=({'MultifileCollectionParser': {'lazy_parsing': False}}) : caught 
ObjectInstantiationException : Error while building object of type <ExecOpTest> using its constructor and parsed contents : {'y': 1.0, 'x': 1.0, 'expected_result': 0.0, 'op': '-'} : 
<class 'ValueError'> 'op' has to be a string, in {'*', '+'}!
```

Note: unfortunately, as of today (version 16.3), `attrs` does not validate attribute contents when fields are later modified on the object directly. A pull request is ongoing.


### (e) File mappings: Wrapped/Flat and encoding

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


### (f) Recursivity: Multifile children of Multifile objects

As said earlier in this tutorial, parsyfiles is able to parse multifile recursively, for example multifile collections of multifile objects, multifile objects containing attributes, etc.


#### Example recursivity in flat mode
 
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

#### Example recursivity in wrapped mode

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


### (g) Diversity of formats supported: DataFrames - revisited

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
