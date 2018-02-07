## Foreword

The following list is valid as of version 2.2.0 ; it will become obsolete when new parsers and converters are registered. Since one of the main goals of `parsyfiles` is to provide you with an easy way to register your own parsers and converters, you would better query your root parser for its *actual* capabilities, using one of the following commands:

```python
from pprint import pprint
parser = RootParser()

# all registered parsers (actually, all parsing chains made of parsers+converters)
all_parsers = parser.get_all_parsers()
print('\n' + str(len(all_parsers)) + ' parsing chains:')
pprint(all_parsers)

# by extension
extensions = parser.get_all_supported_exts()
print('\n' + str(len(extensions)) + ' supported file extensions:')
pprint(extensions)

txt_parsers = parser.get_capabilities_for_ext('.txt')
print('\n' + str(len(txt_parsers)) + ' parsers for .txt files:')
pprint(txt_parsers)

# by type
types = parser.get_all_supported_types_pretty_str()
print('\n' + str(len(extensions)) + ' supported types:')
pprint(types)

df_parsers = parser.get_capabilities_for_type(DataFrame)
print('\n' + str(len(txt_parsers)) + ' DataFrame parsers:')
pprint(df_parsers)

# alternate methods to print capabilities:
parser.print_capabilities_by_ext()
parser.print_capabilities_by_type()
```

Note that all the methods are also available for convenience for the default settings, from the package directly :

```python
from pprint import pprint
from parsyfiles import get_capabilities_for_type
pprint(get_capabilities_for_type(bool))
```

## By Type

### primitive types: bool, float, int, str

The following files

```bash
.pyc              .txt              .txt         .txt
---------------   ---------------   ----------   ----------
\x80\x03\x88.     Yes               gAOILg==     1.0                                               
```

 may all be parsed into a `bool` using 
 
```python
bl = parse_item('<file_path_without_ext>', bool)
```

Any primitive can be converted from another one (above, the string 'Yes' and the float '1.0'). The above also demonstrates the ability of parsyfiles to chain parsers and converters where appropriate: the binary pickle object in the .pyc file is extracted correctly, and so is the base64-encoded pickle object in the .txt.


### ConfigParser


### Dict

(note about `dict`)



### DictOfDict

### list
### List

### Series
### DataFrame

### Set
### Tuple


### Generic (Any Object)

#### parsers without restrictions

Any object may be read from 
 * `.pyc` (binary pickle format), 
 * `.txt` (base64-encoded pickle format), 
 * `.yaml`/`.yml` (yaml object)

#### parsers with restrictions

If your object class constructor is entirely defined with PEP484, such as in:

```python
class ExecOpTest(object):
    def __init__(self, x: float, y: float, op: str, 
                 expected_result: float = True):
        self.x = x
        self.y = y
        self.op = op
        self.expected_result = expected_result
```

##### from dict-compliant format

You may parse it from all supported [Dict formats](#dict) as long as there is one dict key per attribute name (here, `x`, `y`, `op`, `expected_result`). Note that attributes with default values in the constructor (here, `expected_result`) are optional in the dict. The `typing.Optional` type is not yet supported. 

Note that the types don't need to be simple types, as long as there is a registered converter available between the parsed dict's entry and the constructor required type

###### from dict of dict-compliant format

You may parse it from any [DictOfDict formats](#dictofdict). Each attribute will be constructed from the corresponding sub-dict, and then the main constructor will be called. Note that this is quite a rare use-case but it might be convenient if you want to parse a quite complex object from a single `.ini` file

##### from multifile format

You may parse it from multiple files, where each file represents an attribute. These files may have any extension, as long as there is a registered parser between this extension and the required type in the constructor signature. Here again, optional constructor arguments lead to optional files

```bash
./folder
|-x.*
|-y.*
|-op.*
```








## By Extension

TODO