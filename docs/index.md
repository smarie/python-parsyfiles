# python simple file collection parsing framework (parsyfiles)

*Read files as objects, even if several parsers and converters are needed.*

[![Build Status](https://travis-ci.org/smarie/python-parsyfiles.svg?branch=master)](https://travis-ci.org/smarie/python-parsyfiles) [![Tests Status](https://smarie.github.io/python-parsyfiles/junit/junit-badge.svg?dummy=8484744)](https://smarie.github.io/python-parsyfiles/junit/report.html) [![codecov](https://codecov.io/gh/smarie/python-parsyfiles/branch/master/graph/badge.svg)](https://codecov.io/gh/smarie/python-parsyfiles) [![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://smarie.github.io/python-parsyfiles/) [![PyPI](https://img.shields.io/badge/PyPI-parsyfiles-blue.svg)](https://pypi.python.org/pypi/parsyfiles/)

`parsyfiles` is a declarative framework able to combine many popular python parsers (`json`, `jprops`, `yaml`, `pickle`, `pandas`...) with  user-defined ones, in order to easily read objects from files. It is able to read an object even if the object's content comes from several files requiring several parsers. This is typically useful to read test data where you want to combine datasets, parameters, expected results and more. 

It is extremely easy to add a parser in `parsyfiles` if your favourite parser is missing. Even better: if you just need to parse a derived type of a type that can already be parsed, you may simply need to register a type `Converter`, the framework will automatically link it to all compliant parsers for you. 


## Main use cases

This is just a glance at what you could use parsyfiles for. Check the [Usage](./usage/) page for details.

### 1 - Parsing dictionaries and simple objects from various formats

The following files

```bash
.json             .properties       .cfg         .csv         .yaml
---------------   ---------------   ----------   ----------   ----------
{                                   [main]                    
  "age": 1         age=1            age=1        age, name    age: 1
  "name": "foo"    name=foo         name=foo     1, foo       name: foo
}                                                             
```

 may all be parsed into a `dict` using 
 
```python
dct = parse_item('<file_path_without_ext>', Dict)
```

and into a `MySimpleObject` with constructor `__init__(self, age: int, name: str)` using

```python
smpl = parse_item('<file_path_without_ext>', MySimpleObject)
```

Note that you might wish to use [autoclass](https://github.com/smarie/python-autoclass) and [enforce](https://github.com/RussBaz/enforce) to write compact but yet validated classes. `parsyfiles` is totally compliant with those:

```python
@runtime_validation
@autoprops
class MySimpleObject:
    @validate(age=gt(0), name=minlens(0))
    @autoargs
    def __init__(self, age: Integral, name: str):
        pass
```


### 2 - Parsing objects from multiple files: collections and complex objects

If you already know how to parse the various files you need one by one, you might still wish to define higher-lever container objects made of several files/folders and potentially requiring to combine several parsers. For example objects made of several `DataFrame` each stored in a `.csv` (timeseries + descriptive data), combinations of csv and xml/json files, configuration files, pickle files, etc.

Here is how you parse a collection of simple files into a dictionary of `MySimpleObject`:

```python
dct = parse_collection('<folder_path>', MySimpleObject)
# or
dct = parse_item('<folder_path>', Dict[str, MySimpleObject])
```

And here is how you parse a `MyComplexObject` with constructor `__init__(foo: Dict, bar: MySimpleObject)` from a folder containing `foo.json` and `bar.properties`:

```python
cplx = parse_item('<folder_path>', MyComplexObject)
```


### 3 - Parsing test cases

A typical use case for this library is to define your test cases as objects. These objects will typically contain fields such as test inputs and test expected outcomes. Here is an example with `py.test`:

```python
# The function that we want to test
def exec_op(x: float, y: float, op: str) -> float:
    return eval(str(x) + op + str(y))

# Define what is a test case for exec_op
class ExecOpTest(object):
    def __init__(self, x: float, y: float, op: str, expected_result: float):
        self.x = x
        self.y = y
        self.op = op
        self.expected_result = expected_result

# Parse the collection of tests, in lazy mode (parsing will happen at get)
cases = parse_collection('<folder_path>', ExecOpTest, 
                         lazy_mfcollection_parsing=True)

# Execute the test in py.test
@pytest.mark.parametrize("case_name", cases.keys())
def test_simple_objects(case_name: str):
    # lazy-load case data (so that one parsing error doesn't make all tests fail)
    case = cases[case_name]
    # test that exec_op works on that case
    assert exec_op(case.x, case.y, case.op) == case.expected_result
```

## Main features

* **Declarative (class-based)**: you *first* define the objects to parse - by creating or importing their class -, *then* you use `parse_item` or `parse_collection` on the appropriate folder or file path. 
* **Simple objects out-of-the-box**: if you're interested in parsing singlefile objects only requiring simple types in their constructor, then the framework is *already* able to parse them, for many singlefile formats (json, properties, txt, csv, yaml and more.).
* **Multifile collections out-of-the-box**: the framework is able to parse collections of objects, each represented by a file. Parsing may optionally be done in a lazy fashion (each item is only read if needed).
* **Serialization**: pickle files (.pyc) are supported too. Base64-encoded pickle objects can also be included in any simple file content.
* **Multiparser**: the library will use the best parser adapted to each file format and desired type. At the time of writing the library:
    * knows **44** ways to parse a file
    * is able to parse **15** object types (including *'AnyObject'* for generic parsers). See [Known Formats Reference](./known_formats_reference/) section.
    * from **13** file extensions
* **Multifile+Multiparser objects**: You may therefore parse complex objects requiring a combination of several parsers to be built from several files. The framework will introspect the object constructor in order to know the list of required attributes to parse as well as their their type, and if they are mandatory or optional.
* **Recursive**: attributes may themselves be collections or complex types.
* Supports **two main file mapping flavours for Multifile objects**: the library comes with two ways to organize multifile objects such as collections: *wrapped* (each multifile object is a folder), or *flat* (all files are in the same folder, files belonging to the same multifile object have the same prefix)

In addition the library is

* **Extensible**. You may register any number of additional file parsers, or type converters, or both. When registering a parser you just have to declare the object types that it can parse, *and* the file extensions it can read. The same goes for converters: you declare the object type it can read, and the object type it can convert to. 
* **Intelligent** Since several parsers may be registered for the same file extension, and more generally several parsing chains (parser + converters) may be eligible to a given task, the library has a built-in set of rules to select the relevant parsing chains and test them in most plausible order. This provides you with several ways to parse the same object. This might be useful for example if some of your data comes from nominal tests, some other from field tests, some other from web service calls, etc. You don't need anymore to convert all of these to the same format before using it.
* **No annotations required**: as opposed to some data binding frameworks, this library is meant to parse object types that may already exist, and potentially only for tests. Therefore the framework does not require annotations on the type if there is there is a registered way to parse it. However if you wish to build higher-level objects encapsulating the result of several parsers, then PEP484 type hints are required. But that's probably less a problem since these objects are yours (they are part of your tests for example) 

*Note on the Intelligence/Speed tradeoff:*
This framework contains a bit of nontrivial logic in order to transparently infer which parser and conversion chain to use, and even in some cases to try several alternatives in order to guess what was your intent. This makes it quite powerful but will certainly be slower and more memory-consuming than writing a dedicated parser tailored for your specific case. However if you are looking for a tool to speedup your development so that you may focus on what's important (your business logic, algorithm implementation, test logic, etc) then have a try, it might do the job.




## See Also

* Check [here](https://github.com/webmaven/python-parsing-tools) for other parsers in Python, that you might wish to register as unitary parsers to perform specific file format parsing (binary, json, custom...) for some of your objects.

* Do you like this library ? You might also like [my other python libraries](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python) 

* This [cattrs](https://cattrs.readthedocs.io/en/latest/readme.html) project seems to have related interests, to check. 
