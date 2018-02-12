### 2.7.1 - Bugfix + Log warnings improvements

 * Fixed sub-subclass detection [#21](https://github.com/smarie/python-parsyfiles/issues/21)
 * Some log warnings were hidden, in particular those explaining why instances of a given class could not be instantiated from constructor.

### 2.7.0 - Added support for PEP484 forward references in type hints

 * Added support for Forward References in PEP484 annotations. Fixes [#20](https://github.com/smarie/python-parsyfiles/issues/20). This unlocks parsing infinitely-nested collections: you just have to create a collection type that contains a union to itself such as in `InfiniteRecursiveDictOfA = Dict[str, Union[A, 'InfiniteRecursiveDictOfA']]`. Note that infinite unions are detected and handled correctly (such as `Foo = Union[str, 'Foo']`)
 * Fixed a bug with type inspection for attrs classes

### 2.6.1 - bugfixes for unions, typevars and generics and log/warnings improvements

 * fixed `__init__` file: `__all__` contained a wrong entry
 * the central logger `default_logger` is now independent from the `RootParser` class
 * fixed a conversion bug for `Union` types (or `TypeVar`s with union constraints): now all alternate conversion paths are tried even in case of an exception in a converter.
 * The `<dict_to_object>` converter and the `Multifile object parser` now both support generic types when looking for subclasses (although strong compliance of the subclasses with the `TypeVar` constraints are not further checked). The method to list these subclasses is in a central place to ensure consistency
 * Now there are two error types for invalid type hints : `TypeInformationRequiredError` (no type hint) and `InvalidPEP484TypeHint` (invalid type hint). This PEP484-compliance check is also now done in a central place to ensure consistency.
 * The `<dict_to_object>` converter and the `Multifile object parser` now benefit from a cache in order to know if a given class can be built from its constructor, or its subclasses. This leads to much less log warning messages

### 2.6.0 - support for TypeVars and better support for Unions and subclasses

 * `TypeVars` are now supported. This fixes [#17](https://github.com/smarie/python-parsyfiles/issues/17)
 * `Union` are now better supported too, in particular when there is a union inside a typevar or conversely.
 * Instead of using `_args__` we now use `get_args(t, evaluate=True)` from [`typing_inspect`](https://github.com/ilevkivskyi/typing_inspect) everywhere, so as to be compliant with any complex PEP484 construct.
 * The `<dict_to_object>` converter and the `Multifile object parser` now both check if a subtype can be built from the `dict`/`files` present before giving up. There is a macimum limit to the number of subclasses tried, in global configuration `parsyfiles_global_config(dict_to_object_subclass_limit=x)`. Default is 50. Fixes [#18](https://github.com/smarie/python-parsyfiles/issues/18)
 * better 'nonability' check in all parsers/converters that rely on the constructor signature's PEP484 type hints
 * Improved log messages for Try/Catch parser (CascadingParser)

### 2.5.0 - support for Union types

 * Union types are now supported. This fixes [#16](https://github.com/smarie/python-parsyfiles/issues/16)

### 2.4.8 - various improvements

 * Removed annoying warnings for DataFrame objects in <dict_to_object>
 * Final log newline is now only present in debug mode
 * Handling of Tuple in nested conversion process now works correctly

### 2.4.7 - log and yaml parsing improvements 2

 * Fixed [#14](https://github.com/smarie/python-parsyfiles/issues/14): nested dictionary types now appear correctly in log messages
 * Fixed [#15](https://github.com/smarie/python-parsyfiles/issues/15): collections of custom collection types now benefit from automatic conversion too.
 * Unit tests updated to work with latest version of dependencies

### 2.4.6 - yaml parsing improvements

 * Fixed [#13](https://github.com/smarie/python-parsyfiles/issues/13): yaml collections now benefit from the conversion framework, meaning that if an inner object inside the collection has not the expected type it is converted.

### 2.4.5 - <dict_to_object> and log improvements

 * Added a warning in <dict_to_object> converter when some desired type can not be converted because of its constructor signature. Fixes [#10](https://github.com/smarie/python-parsyfiles/issues/10**)
 * Added support for `typing.Optional` in <dict_to_object> converter. This Fixes [#11](https://github.com/smarie/python-parsyfiles/issues/11)
 * Improved log messages to display information about the parsing chain used, and many other things. Fixes [#12](https://github.com/smarie/python-parsyfiles/issues/12)
 * New global configuration option `full_paths_in_logs`

### 2.4.4 - global traceback size option

 * Added a global configuration that can be changed by calling `parsyfiles_global_config(...)`. The only option available for now is controlling the traceback size in case of several parsers exceptions. This fixes [#9](https://github.com/smarie/python-parsyfiles/issues/9)

### 2.4.3 - logger customization fix

 * logger customization was not taken into account - fixed [#7](https://github.com/smarie/python-parsyfiles/issues/7)

### 2.4.2 - typing_inspect dependency
 * does not use internals from `typing` anymore but relies on `typing_inspect` API to guarantee the stability, see https://github.com/smarie/python-parsyfiles/issues/4
 * minor travis configuration

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