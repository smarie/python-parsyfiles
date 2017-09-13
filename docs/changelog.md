### 2.4.0 - typing_inspect dependency
 * does not use internals from `typing` anymore but relies on `typing_inspect` API to guarantee the stability, see https://github.com/smarie/python-parsyfiles/issues/4

### 2.3.1 - Documentation and tests improvements + bug fix

 * Important bug fix for 2.3.0: custom parsers/converters were appearing in the capabilities but not used. Added a test to prevent this kind of regression to happen again.
 * Improved 'usage' documentation page
 * Reorganized tests and documented them for better readability, and improved some of them (primitive types, default parsers)
 * Test failure do not make travis builds fail anymore
 * Fixed file system mappings: now '.' is not mandatory for relative paths

### 2.3.0 - Several major improvements and Travis integration

Improved verbosity, quality of parser and converter combinations, performance, sorted collections

**PARSER/CONVERTER COMBINATION ENGINE**

 * replaced `None` with an explicit `JOKER` for all 'find' parsers/converters methods. Added sanity check at parser registration time: check that parser handles `JOKER` properly
 * split `is_able_to_parse` and `is_able_to_parse_detailed` (and the same for convert) so that the first returns a single boolean while the second returns a tuple. This fixed a number of bugs with parser/converter chain generation
 * fixed bug with generic parsers by now using the same piece of code than others for registration
 * generic parsers and converters are now allowed to chain with other converters. `is_able_to_convert` is therefore now called at runtime on the value generated because it could not fit the required input of the next element
 * fixed a few errors in the plugins so that their chaining is correct

**API**

 * better error message when the provided location has an extension
 * better separation of logging messages between info and debug
 * created a true base `ConversionException`
 * added package-level methods to access capabilities easily
 * `get_capabilities...` methods now do not return some keys when they are empty: the result is more compact to read
 * Added `OrderedDict` so that parsing collections now returns a sorted `list/set/dict/tuple`

**PERFORMANCE**

 * Big performance improvement for `_get_constructor_signature`, thanks to profiling
 * Big performance improvement for `var_checker`, thanks to profiling
 * added singleton cached instance for `RootParser` with default plugins so as not to pay the registration costs several times

**TRAVIS INTEGRATION**
 * tests, code coverage, doc generation, and releases deployment on PyPI are now automated

### 2.2.0 - New chaining capabilities and bugfixes

 * added new behaviour : genaric parsers can chain with converters. In some cases this may unlock new capabilities (for example parsing object A from its constructor then converting A to B might sometimes be interesting, rather than parsing B from its constructor)
 * fixed bug in is_able_to_convert: when from_type was any, the result was False > this was preventing the above use case to execute
 * fixed bug with automatic type conversion in collections

### 2.1.0 - Minor improvements

 * improved support for collections by supporting Mappings, Sequences, and AbstractSets instead of Dict, List, and Set
 * added automatic conversion of string to numbers and booleans in jprops properties reader
 * replaced dict_to_single_row_or_col_df with dict_to_df, able to handle both single-level and multi-level dictionaries
 * fixed filesystem mappings : now supporting multifile objects without children (=empty folder or file without extension)
 * fixed code for detecting a typing List or Set (was relying on typing.Collection that is not always available)

### 2.0.2 - Minor setup.py and doc edits


### 2.0.1 - Minor setup.py and doc edits


### 2.0.0 - New name 'parsyfiles', Major refactoring, Support for converters, Support for simple objects

 * Two new main functions `parse_item` and `parse_collection` at module level
 * Custom parsers for MULTIFILE may now be registered (since a multifile parser is now a parser like all others)
 * Added the concept of converters and conversion chains. A converter registry has an "intelligent" logic to infer what type of converters to chain in order to create value (preventing useless conversion chains, cycles, etc.)
 * Added support for primitive types, yaml and numpy primitives
 * Parsers and converters are defined according to the new object model for collections, objects, dataframes, configparser. (addded/fixed support for json, jprops, pickle, ...). There are now two ways to parse config files: as dictionary of dictionaries, or as a dictionary
 * Added the ability to parse collections in 'lazy' mode
 * Added support for Tuple and Set for collections
 * added automatic conversion of item values for all dict, list, tuple and set parsers/converters
 * added a system to pass options to the parsers/converters
 * Improved Logging and Error handling to ease debug
 * added support for classes written with `attrs` package
 * Major code refactoring :
    * split into several files to separate the concerns : file system / parsing chains / framework / typing and PEP484
    * object model for persisted objects, converters, parsers, and parsers/converters registries
    * All parsers and converters shipping with the framework are now plugins just as the custom ones : no hardcoded difference. This made the plugin mechanism quite "strange case-proof".
    * Added a test file specifically for parser registry

 
### 1.0.1 - First public working version of 'sficopaf' (Simple File Collections Parsing Framework)

This first version was mostly function-based and did not provide a way to parse simple objects from dictionaries.