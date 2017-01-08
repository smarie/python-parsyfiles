import logging
from copy import deepcopy
from inspect import getmembers, signature, Parameter
from io import TextIOBase
from os.path import isfile, isdir
from threading import RLock
from typing import Tuple, Any, Dict, Callable, Type, List, Set, Union, TypeVar, Generic

from sficopaf.parsing_filemapping import FileMappingConfiguration, _find_collectionobject_file_prefixes, \
    MandatoryFileNotFoundError, check_complex_object_on_filesystem, \
    _get_attribute_item_file_prefix, FolderAndFilesStructureError, MultipleFilesError

from .dict_parsers import get_default_dict_parsers, convert_dict_to_simple_object
from .var_checker import check_var

S = TypeVar('S')  # Can be anything - used for "source object"
T = TypeVar('T')  # Can be anything - used for all other objects


class UnsupportedObjectTypeError(Exception):
    """
    Raised whenever the provided object type is unknown and therefore cannot be parsed from a file
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(UnsupportedObjectTypeError, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any]): # -> UnsupportedObjectTypeError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return UnsupportedObjectTypeError('No unitary file parser available for item type : ' + str(item_type) + '.')

    @staticmethod
    def create_with_details(item_name_for_log: str, item_file_prefix: str, item_type: Type[Any]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name_for_log:
        :param item_file_prefix:
        :param item_type:
        :return:
        """
        return UnsupportedObjectTypeError('Error while reading item ' + item_name_for_log + ' at ' + item_file_prefix
                                          + '. No unitary file parser available for item type requested : ' + str(item_type)
                                          + '. If this is a complex type, then you probably need to create one file or '
                                            ' folder for each of its fields.')


class ParsingChain(Generic[T]):
    """
    Represents a parsing chain, with a mandatory initial parser function and a list of converters.
    """
    def __init__(self, item_type: Type[T], parser_function:Callable[[TextIOBase], T]):
        self._item_type = item_type
        self._parser_func = parser_function
        self._converters_list = []

    def __str__(self):
        return 'ParsingChain[' + self._parser_func.__name__ + ' ' + \
                   ' '.join(['> ' + converter_fun.__name__ for converter_fun in self._converters_list])\
               + ']'

    def __repr__(self):
        # should we rather use the full canonical names ? yes, but pprint uses __repr__ so we'd like users to see
        # the small and readable version, really
        return self.__str__()

    def add_conversion_step(self, source_item_type: Type[S], dest_item_type: Type[T], converter_fun:Callable[[S], T]):
        if source_item_type is self._item_type:
            self._item_type = dest_item_type
            self._converters_list.append(converter_fun)
            return self
        else:
            raise TypeError('Cannnot register a converter on this conversion chain : source type \'' + source_item_type
                            + '\' is not compliant with current destination type of the chain : \'' + self._item_type)

    def parse_with_chain(self, file_object: TextIOBase) -> T:
        """
        Utility method to parse using the parser and all converters in order
        :return:
        """
        res = self._parser_func(file_object)
        for converter_func in self._converters_list:
            res = converter_func(res)
        return res


class ParsingException(Exception):
    """
    Raised whenever parsing fails
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(ParsingException, self).__init__(contents)

    @staticmethod
    def create(file_path: str, parsing_chain: ParsingChain[T], encoding: str, fun_args: list, fun_kwargs: dict, cause):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return ParsingException('Error while parsing file at path \'' + file_path + '\' with encoding \'' + encoding
                                + '\' and parser function \'' + str(parsing_chain)+ '\' '
                                + 'with args : ' + str(fun_args) + 'and kwargs : ' + str(fun_kwargs) + '.\n'
                                + str(cause))


class RootParser(object):
    """
    The root parser
    """

    logger = logging.getLogger(__name__)

    def __init__(self, initial_parsers: Dict[Type[T], Dict[str, Callable[[TextIOBase], T]]] = None,
                 register_dict_parsers: bool = True):
        """
        Constructor. Initializes the dictionary of parsers with the optionally provided initial_parsers, and
        inits the lock that will be used for access in multithreading context.

        :param initial_parsers:
        """
        self.__types_lock = RLock() # lock for self.__parsers
        self.__parsers = {} # Dict[DestinationType > Dict[ext > parser]]
        self.__converters = {} # Dict[DestinationType > Dict[SourceType > converter]]

        if initial_parsers is not None:
            self.register_parsers(initial_parsers)
        if register_dict_parsers:
            self.register_parsers({dict: get_default_dict_parsers()})

        return

    def register_converter(self, from_type: Type[S], to_type: Type[T], converter: Callable[[S], T]):
        """
        To register a single converter from one object type to another.

        :param from_type:
        :param to_type:
        :param converter:
        :return:
        """
        check_var(from_type, var_types=type)
        check_var(to_type, var_types=type)
        check_var(converter, var_types=Callable)

        self.__types_lock.acquire()
        try:
            if to_type in self.__converters.keys():
                if from_type in self.__converters[to_type]:
                    RootParser.logger.warning('Warning : overriding existing converter from type '
                                              + str(from_type) + ' to type ' + str(to_type))
                self.__converters[to_type][from_type] = converter
            else:
                self.__converters[to_type] = {from_type: converter}
        finally:
            self.__types_lock.release()
        return


    def register_converters(self, converters:Dict[Type[T], Dict[Type[S], Callable[[S], T]]]):
        """
        Registers the provided converters (a dictionary)
        :param converters:
        :return:
        """
        check_var(converters, var_types=dict)

        # don't use dict.update because we want to perform sanity checks here
        for to_type, converters_to_this_type in converters.items():
            for from_type, converter in converters_to_this_type.items():
                self.register_converter(from_type, to_type, converter)
        return


    def get_converters_copy(self) -> Dict[Type[T], Dict[S, Dict[str, Callable[[S], T]]]]:
        """
        Returns a deep copy of the converters dictionary
        :return:
        """
        return deepcopy(self.__converters)


    def register_unitary_parser(self, object_type: Type[T], extension: str,
                                extension_parser: Callable[[TextIOBase], T]):
        """
        To register a single parsing function, for a single file extension, for a given object type

        :param object_type:
        :param extension:
        :param extension_parser:
        :return:
        """
        check_var(object_type, var_types=type)
        check_var(extension, var_types=str, min_len=1)
        check_var(extension_parser, var_types=Callable)

        self.__types_lock.acquire()
        try:
            if object_type in self.__parsers.keys():
                if extension in self.__parsers[object_type]:
                    RootParser.logger.warning('Warning : overriding existing extension parser for type '
                                              + str(object_type) + ' and extension ' + extension)
                self.__parsers[object_type][extension] = extension_parser
            else:
                self.__parsers[object_type] = {extension: extension_parser}
        finally:
            self.__types_lock.release()
        return


    def register_parsers_for_type(self, object_type:Type[T], extension_parsers:Dict[str, Callable[[TextIOBase], T]]):
        """
        Registers a new type, with associated extension parsers

        :param object_type:
        :param extension_parsers:
        :return:
        """
        check_var(object_type, var_types=type)
        check_var(extension_parsers, var_types=dict, min_len=1)

        # don't use dict.update because we want to perform sanity checks here
        for extension, extension_parser in extension_parsers.items():
            self.register_unitary_parser(object_type, extension, extension_parser)
        return


    def register_parsers(self, parsers:Dict[Type[T], Dict[str, Callable[[TextIOBase], T]]]):
        """
        Registers the provided parsers
        :param parsers:
        :return:
        """
        check_var(parsers, var_types=dict)

        # don't use dict.update because we want to perform sanity checks here
        for object_type, extension_parsers in parsers.items():
            self.register_parsers_for_type(object_type, extension_parsers)
        return


    def get_parsers_copy(self) -> Dict[Type[T], Dict[str, Dict[str, Callable[[TextIOBase], T]]]]:
        """
        Returns a deep copy of the parsers dictionary
        :return:
        """
        return deepcopy(self.__parsers)


    def get_parsers_for_type(self, item_type: Type[T]) -> Dict[str, Callable[[TextIOBase], T]]:
        """
        Utility method to return the parsers associated to a given type (a dictionary extension > parser)
        Throws an UnsupportedObjectTypeError if not found

        :param item_type:
        :return: the dictionary of (extension, parsers) for the given type
        """
        check_var(item_type, var_types=type, var_name='item_type')
        try:
            # get exact match - throws KeyError if not found
            return self.__parsers[item_type]
        except KeyError as e:
            raise UnsupportedObjectTypeError.create(item_type) from e

            # DISABLED -  This automatic behavior may lead to confusion.
            # # find a parser able to parse a parent type, but only if the desired type is not a reserved collection
            # # (this is to prevent dict parsers (used for simple objects) to be used for Dict[str, Any]
            # # (used for complex objects).
            # if _is_multifile_collection(item_type):
            #     raise UnsupportedObjectTypeError.create(item_type)
            # else:
            #     .
            #     return RootParser._find_dict_entry_for_which_key_is_a_parent_class(item_type, self.__parsers)


    def get_parsing_chains_for_type(self, item_type: Type[T], error_if_not_found: bool=True) \
            -> Dict[str, ParsingChain[T]]:
        """
        Utility method to return the parsing_chain associated to a given type. A dictionary extension > parsing_chain
        Throws an UnsupportedObjectTypeError if no valid converter found

        :param item_type:
        :return: the dictionary of (source_type, converter) for the given type
        """

        # First collect all basic parsers
        try:
            parsing_chains = {ext: ParsingChain(item_type, parser_fun) for ext, parser_fun in self.__parsers[item_type].items()}
        except KeyError as e:
            parsing_chains = {}

        # Then add all converters
        try:
            converters_to_type = self.__converters[item_type]
            for source_type, converter in converters_to_type.items():
                subchains = self.get_parsing_chains_for_type(source_type, error_if_not_found=False)
                for ext, subchain in subchains.items():
                    if ext not in parsing_chains:
                        # add the chain to the result set (dont forget to add the converter)
                        parsing_chains[ext] = subchain.add_conversion_step(source_type, item_type, converter)
                    else:
                        # we already know how to parse item_type from this extension. Is the new solution better ?
                        if parsing_chains[ext].chain_length() > (subchain.chain_length() + 1):
                            # we found a shorter conversion chain to get the same result ! Use it
                            parsing_chains[ext] = subchain.add_conversion_step(source_type, item_type, converter)
        except KeyError as e:
            pass

        # throw error if empty, if requested
        if error_if_not_found and len(parsing_chains) == 0:
            raise UnsupportedObjectTypeError.create(item_type)
        else:
            return parsing_chains


    def get_all_known_parsing_chains(self):
        """
        Utility method to return all known parsing chains (obtained by assembling converters and parsers)

        :return:
        """
        return {type: self.get_parsing_chains_for_type(type)
                for type in list(self.__parsers.keys()) + list(self.__converters.keys())}


    # @staticmethod
    # def _find_dict_entry_for_which_key_is_a_parent_class(item_type: Type[Any], candidates_dict: Dict[Type[Any], Any]) \
    #         -> Any:
    #     """
    #     Utility method to find a unique approximative match for a given item_type in a dictionary that contains types as
    #     keys. A match will be a parent class of item_type. If several matches are found, an error will be raised
    #
    #     :param item_type:
    #     :param candidates_dict:
    #     :return:
    #     """
    #     compliant_types = [supported_type for supported_type in candidates_dict.keys() if
    #                        issubclass(item_type, supported_type)]
    #     if len(compliant_types) == 1:
    #         return candidates_dict[compliant_types[0]]
    #     elif len(compliant_types) > 1:
    #         raise TypeError('No exact match found, but several registered parsers/converters exist that would '
    #                         'fit requested type ' + str(item_type) + ' because they work for one of its parent '
    #                                                                  'class. Unknown behaviour, exiting.')
    #     else:
    #         raise UnsupportedObjectTypeError.create(item_type)


    @staticmethod
    def _check_common_vars(item_file_prefix, item_type, file_mapping_conf, item_name_for_log, indent_str_for_log,
                           lazy_parsing):
        """
        Utility method to check common vars and init default values

        :param item_file_prefix:
        :param item_type:
        :param file_mapping_conf:
        :param item_name_for_log:
        :param indent_str_for_log:
        :param lazy_parsing:
        :return:
        """
        indent_str_for_log, item_name_for_log = _check_common_vars_core(item_file_prefix, item_type,
                                                                                   item_name_for_log,
                                                                                   indent_str_for_log)

        file_mapping_conf = file_mapping_conf or FileMappingConfiguration()
        check_var(file_mapping_conf, var_types=FileMappingConfiguration, var_name='file_mapping_conf')

        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')

        return file_mapping_conf, indent_str_for_log, item_name_for_log



    def parse_collection(self, item_file_prefix: str, collection_or_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                         indent_str_for_log: str = None) -> Union[T, Dict[str, T], List[T], Set[T], Tuple[T]]:
        """
        Method to start parsing a collection of items under the given folder path.
        * If flat_mode = False, each item is a folder.
        * If flat_mode = True, each item is a set of files with the same prefix separated from the attribute name by
        the character sequence <sep_for_flat>

        :param item_file_prefix: the path of the parent item. it may be a folder or an absolute file prefix
        :param collection_or_item_type: the type of objects to parse in this collection. It should be a class from the typing
        package (PEP484), either List, Set, or Dict. If a different type T is provided, it is assumed that the desired
        result is Dict[T]
        :param item_name_for_log: the optional item name, just for logging information
        :param file_mapping_conf:
        :param lazy_parsing: if True, the method will return without parsing all the contents. Instead, the returned
        dictionary will perform the parsing only the first time an item is required.
        :return: a dictionary of named items and content
        """

        # 0. check inputs/params
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(item_file_prefix,
                                                                                          collection_or_item_type,
                                                                                          file_mapping_conf,
                                                                                          item_name_for_log,
                                                                                          indent_str_for_log,
                                                                                          lazy_parsing)
        item_name_for_main_log = ('<collection>' if item_name_for_log is '<item>' else item_name_for_log)

        # 1. Check the collection type and extract the base item type
        base_collection_type = _find_typing_collection_class_or_none(collection_or_item_type)
        if base_collection_type is None:
            # default behaviour when a non-collection type is provided : return a dictionary
            item_type = collection_or_item_type
            collection_or_item_type = Dict[str, item_type]
        else:
            # it is a collection. find the base type of objects in that collection ?
            item_type = _extract_collection_base_type(collection_or_item_type, base_collection_type,
                                                      item_name_for_main_log)


        # 2. Parse the collection
        RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_main_log + ' as a ' +
                               str(collection_or_item_type) + ' collection at path ' + item_file_prefix)

        # list all items in the collection and get their paths
        item_paths = _find_collectionobject_file_prefixes(item_file_prefix,
                                                          flat_mode=file_mapping_conf.flat_mode,
                                                          sep_for_flat=file_mapping_conf.sep_for_flat,
                                                          item_name_for_log=item_name_for_main_log)

        # create a dictionary item > content to store the results
        if lazy_parsing:
            # TODO make a lazy dictionary
            raise ValueError('Lazy parsing is unsupported at the moment')
        else:
            # parse them right now
            results = {}
            for item, item_path in item_paths.items():
                results[item] = self.parse_item(item_path, item_type,
                                                item_name_for_log=(item_name_for_log or '') + '[' + item + ']',
                                                file_mapping_conf=file_mapping_conf,
                                                indent_str_for_log=indent_str_for_log + '--')

        # format output if needed
        if issubclass(collection_or_item_type, List):
            results = list(results.values())
        elif issubclass(collection_or_item_type, Set):
            results = set(results.values())
        elif issubclass(item_type, Tuple):
            raise TypeError('Tuple attributes are not supported yet')

        return results


    def parse_item(self, item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                   file_mapping_conf: FileMappingConfiguration = None,
                   lazy_parsing: bool = False, indent_str_for_log: str = None) -> T:
        """
        Method to parse an item at the given parent path. Note that the type of this item may be a collection,
        this method will silently redirect to parse_collection.
        * If flat_mode = False, each item is a folder.
        * If flat_mode = True, each item is a set of files with the same prefix separated from the attribute name by
        the character sequence <sep_for_flat>

        The parser uses the following algorithm to perform the parsing:
        * First check if there is at least a registered parser for `item_type`. If so, try to parse the file at path
        `item_file_prefix` with the parser corresponding to its file extension
        * If the above did not succeed, check if there is at least a registered converter for `item_type`. If so, for
        each converter available, get its source type, and try to parse the file at path `item_file_prefix` as this
        source type using a registered parser if any.
        * If the above did not succeed, use either the multi-file collection parser (if `item_type` is a collection)
        or the multi-file complex object parser (if `item_type` is not a collection)

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :param indent_str_for_log:
        :return:
        """

        # 0. check all inputs and apply defaults
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(item_file_prefix, item_type,
                                                                                          file_mapping_conf,
                                                                                          item_name_for_log,
                                                                                          indent_str_for_log,
                                                                                          lazy_parsing)

        try:
            # 1. Try to parse with a registered parser and an optional parsing chain, if any
            return self._parse_simple_item_with_registered_parsers(item_file_prefix, item_type, file_mapping_conf,
                                                                   item_name_for_log, indent_str_for_log)

        except (UnsupportedObjectTypeError, MandatoryFileNotFoundError) as e:
            # this means that
            # * no parser may be found for this type,
            # * or that the file extensions required by the parsers were not found > we can fallback to default behaviour
            try:
                # 2. Try to find a conversion path, then
                # TODO this function should return one parsing_chain per extension, only
                conversion_chain = self.get_parsing_chains_for_type(item_type)
                # if we are here that means that there is at least a converter registered.
                return parse_simple_item_with_parsing_chains(
                    item_file_prefix,
                    item_type,
                    conversion_chain,
                    item_name_for_log=item_name_for_log,
                    indent_str_for_log=indent_str_for_log,
                    encoding=file_mapping_conf.encoding)
            except (UnsupportedObjectTypeError, MandatoryFileNotFoundError) as e:
                # 3. Check if the item has a collection type. If so, redirects on the collection method.
                if _is_multifile_collection(item_type):
                    # parse collection
                    return self.parse_collection(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                 file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                 indent_str_for_log=indent_str_for_log)
                else:
                    # parse single item using constructor inference
                    return self._parse_complex_item(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                    file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                    indent_str_for_log=indent_str_for_log)


    def _parse_simple_item_with_registered_parsers(self, item_file_prefix: str, item_type: Type[T],
                                                   file_mapping_conf: FileMappingConfiguration = None,
                                                   item_name_for_log: str = None, indent_str_for_log: str = None):
        """
        Utility method to parse a simple item of type "item_type" using the registered parsers of this RootParser.
        Exact match will be used first, otherwise a parser that is able to parse a parent class will be used, but only
        if only one is available.

        :param item_file_prefix:
        :param item_type:
        :param file_mapping_conf:
        :param item_name_for_log:
        :param indent_str_for_log:
        :return:
        """
        matching_parsers = self.get_parsers_for_type(item_type)  # throws an error if no parser found
        return parse_simple_item_with_parsers(item_file_prefix, item_type, matching_parsers, item_name_for_log,
                                              indent_str_for_log,
                                              file_mapping_conf.encoding)  # throws an error if supported file extension not found


    def _parse_complex_item(self, item_file_prefix:str, item_type:Type[T], item_name_for_log=None,
                            file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                            indent_str_for_log: str = None) -> T:
        """
        Helper method to read an object of type "item_type" from a file path, as a complex (multi-file) object.
        The constructor of the provided item_type is used to check the names and types of the attributes of the object,
        as well as if they are collections and/or optional.

        * If wrap_items_in_folders = True, the object is a folder containing as files named after its attribute names:
            item1/
            |-attribute1.<ext>
            |-attribute2.<ext>

        * If wrap_items_in_folders = False, the object is a set of files with the same prefix, and with a suffix that
        is the attribute name:
            .
            |-item1<sep>attribute1.<ext>
            |-item1<sep>attribute2.<ext>

        :param item_file_prefix: the path of the object to read. if flat_mode is False , this path should be the path of a
        folder. Otherwise it should be an absolute file prefix.
        :param item_type: the type of the object to read.
        :param file_mapping_conf:
        :return:
        """

        # 0. check all inputs and perform defaults
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(item_file_prefix, item_type,
                                                                                          file_mapping_conf,
                                                                                          item_name_for_log,
                                                                                          indent_str_for_log,
                                                                                          lazy_parsing)

        # 1. Check if the item has a collection type. If so, raise an error.
        if _is_multifile_collection(item_type):
            raise TypeError('Item ' + item_name_for_log + ' is a Collection-like object cannot be parsed with '
                            'parse_single_item(). Found type ' + str(item_type))



        # 2. Parse according to the mode.
        # -- (a) first check that the file structure is correct
        RootParser.logger.info(indent_str_for_log + 'Parsing multifile object ' + str(item_name_for_log) + ' of type '
                               + str(item_type) + ' at ' + item_file_prefix)
        check_complex_object_on_filesystem(item_file_prefix, file_mapping_conf, item_name_for_log)

        # -- (b) extract the schema from the class constructor
        constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
        if len(constructors) is not 1:
            raise ValueError('Several constructors were found for class ' + str(item_type))
        # extract constructor
        constructor = constructors[0]
        s = signature(constructor)


        # -- (c) parse each attribute required by the constructor
        parsed_object = {} # results will be put in this object
        for attribute_name, param in s.parameters.items():

            attribute_is_mandatory = param.default is Parameter.empty       # - is it a mandatory attribute ?
            attribute_type = param.annotation                               # - get the object class

            if attribute_name is 'self':
                pass # nothing to do, this is not an attribute
            else:
                attribute_file_prefix = _get_attribute_item_file_prefix(item_file_prefix, attribute_name,
                                                                             flat_mode=file_mapping_conf.flat_mode,
                                                                             sep_for_flat=file_mapping_conf.sep_for_flat)
                att_item_name_for_log = item_name_for_log + '.' + attribute_name
                try:
                    parsed_object[attribute_name] = self.parse_item(attribute_file_prefix, attribute_type,
                                                                    item_name_for_log=att_item_name_for_log,
                                                                    file_mapping_conf=file_mapping_conf,
                                                                    indent_str_for_log=indent_str_for_log + '--')
                except MandatoryFileNotFoundError as e:
                    if attribute_is_mandatory:
                        # raise the error only if the attribute was mandatory
                        raise e

        # -- (d) finally create the object and return it
        return item_type(**parsed_object)



def _extract_collection_base_type(object_type, base_collection_type, item_name_for_errors):
    """
    Utility method to extract the base item type from a collection/iterable item type. R
    eturns None if the item type is not a collection, and throws an error if it is a collection but it uses the
    base types instead of relying on the typing module (typing.List, etc.).

    :param object_type:
    :param base_collection_type:
    :param item_name_for_errors:
    :return:
    """
    # default value, if no wrapper collection type is found
    item_type = None

    if base_collection_type is None:
        return None

    elif issubclass(object_type, Dict):
        # Dictionary
        # noinspection PyUnresolvedReferences
        key_type, item_type = object_type.__args__
        if key_type is not str:
            raise TypeError(
                'Item ' + item_name_for_errors + ' has type Dict, but the keys are of type ' + key_type + ' which '
                                                                                                       'is not supported. Only str keys are supported')
    elif issubclass(object_type, List) or issubclass(object_type, Set):
        # List or Set
        # noinspection PyUnresolvedReferences
        item_type = object_type.__args__[0]

    elif issubclass(object_type, Tuple):
        # Tuple
        # noinspection PyUnresolvedReferences
        item_type = object_type.__args__[0]
        raise TypeError('Tuple attributes are not supported yet')

    elif issubclass(object_type, dict) or issubclass(object_type, list) \
            or issubclass(object_type, tuple) or issubclass(object_type, set):
        # unsupported collection types
        raise TypeError('Found attribute type \'' + str(object_type) + '\'. Please use one of '
                        'typing.Dict, typing.Set, typing.List, or typing.Tuple instead, in order to enable '
                        'type discovery for collection items')
    return item_type


def _is_multifile_collection(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}.

    :param object_type:
    :return:
    """
    return _find_typing_collection_class_or_none(object_type) is not None



def _find_typing_collection_class_or_none(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}. In that case returns the parent
     type, otherwise returns None. Note that '_find_typing_collection_or_none(dict)' will return None since dict is not
     Dict.
    :param object_type:
    :return: List, Dict, Set, Tuple, or None
    """
    if not hasattr(object_type, '__args__'):
        # this class does not extend any typing module class
        return None
    elif issubclass(object_type, Dict):
        return Dict
    elif issubclass(object_type, List):
        return List
    elif issubclass(object_type, Set):
        return Set
    elif issubclass(object_type, Tuple):
        return Tuple
    elif issubclass(object_type, dict) or issubclass(object_type, list) \
            or issubclass(object_type, tuple) or issubclass(object_type, set):
        # unsupported collection types - but anyway this should not happen since these classes dont have
        # a '__args__' attribute: the first if would trigger
        return None
    else:
        # a typing subclass that is not a collection.
        return None

def parse_simple_item_with_parsers(item_file_prefix, item_type, parsers: Dict[str, Callable[[TextIOBase], T]],
                                   item_name_for_log, indent_str_for_log, encoding):
    """
    Utility function to parse a simple item with a bunch of available parsers (a [extension > function] dictionary).
    It will look if the file is present with a SINGLE supported extension, and parse with the associated parser if it
    is the case.

    :param item_file_prefix:
    :param item_type:
    :param parsers:
    :param item_name_for_log:
    :param indent_str_for_log:
    :param encoding:
    :return:
    """

    # First transform all parser functions into parsing chains
    parsing_chains = {ext: ParsingChain(item_type, parser_function) for ext, parser_function in parsers.items()}

    # Then use the generic method with parsing chains
    return parse_simple_item_with_parsing_chains(item_file_prefix, item_type, parsing_chains, item_name_for_log,
                                                 indent_str_for_log, encoding)


def parse_simple_item_with_parsing_chains(item_file_prefix, item_type, parsers: Dict[str, ParsingChain[T]],
                                   item_name_for_log, indent_str_for_log, encoding):
    """
    Utility function to parse a simple item with a bunch of available parsing chains (a [extension > parsing_chain]
    dictionary). It will look if the file is present with a SINGLE supported extension, and parse with the associated
    parsing chain if it is the case.

    :param item_file_prefix:
    :param item_type:
    :param parsers:
    :param item_name_for_log:
    :param indent_str_for_log:
    :param encoding:
    :return:
    """

    # 0. check all vars
    indent_str_for_log, item_name_for_log = _check_common_vars_core(item_file_prefix, item_type,
                                                                    item_name_for_log,
                                                                    indent_str_for_log)

    # 1. Check that there is no folder with that name
    if isdir(item_file_prefix):
        raise FolderAndFilesStructureError('Error parsing item ' + item_name_for_log + ' with registered parsers. '
                                           'Item file prefix ' + item_file_prefix + ' is a folder !')

    # 2. Find files that can be parsed with one of the provided parsing chains
    #
    # -- list all possible file names that *could* be parsed, according to supported extensions
    possible_files = {item_file_prefix + ext: ext for ext in parsers.keys()}
    #
    # -- find all the ones that *actually* exist on the file system
    found_files = {file_path: ext for file_path, ext in possible_files.items() if
                   isfile(file_path)}

    # 2. Parse only if a *unique* file has been found, otherwise throw errors
    if len(found_files) is 1:
        # parse this file and add to the result
        file_path, file_ext = list(found_files.items())[0]
        parsing_chain = parsers[file_ext]
        RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_log + ' of type ' + str(item_type) +
                               ' at ' + file_path + ' with parsing chain ' + str(parsing_chain))
        return parse_file_as_simple_item_with_parsing_chain(file_path, parsing_chain, encoding=encoding)

    elif len(found_files) is 0:
        # item is mandatory and no compliant file was found : error
        raise MandatoryFileNotFoundError.create(item_name_for_log, item_file_prefix, list(parsers.keys()))

    else:
        # the file is present several times with various extensions
        raise MultipleFilesError.create(item_name_for_log, item_file_prefix, list(found_files.values()))


def parse_file_as_simple_item_with_parsing_chain(file_path: str, parsing_chain: ParsingChain[T],
                                                 encoding: str = 'utf-8', *args, **kwargs) -> T:
    """
    Utility function to parse a single file

    :param file_path:
    :param parsing_chain:
    :param encoding:
    :param args:
    :param kwargs:
    :return:
    """
    global f
    check_var(file_path, var_types=str, var_name='file_path')
    check_var(parsing_chain, var_types=ParsingChain, var_name='parsing_chain')

    try:
        # Open the file with the appropriate encoding
        f = open(file_path, 'r', encoding=encoding)

        # Apply the parsing function
        return parsing_chain.parse_with_chain(f, *args, **kwargs)
    except Exception as e:
        raise ParsingException.create(file_path, parsing_chain, encoding, args,
                                      kwargs, e) from e
    finally:
        f.close()


def parse_file_as_simple_item_with_parser_function(file_path:str, item_type: Type[T],
                                                   parser_function:Callable[[TextIOBase], T],
                                                   encoding:str= 'utf-8', *args, **kwargs) -> T:
    """
    A function to execute a given parsing function on a file path while handling the close() properly.
    Made public so that users may directly try with their parser functions on a single file.

    :param file_path:
    :param parser_function:
    :param encoding:
    :param args:
    :param kwargs:
    :return:
    """
    check_var(parser_function, var_types=Callable, var_name='parser_function')
    return parse_file_as_simple_item_with_parsing_chain(file_path, ParsingChain(item_type, parser_function),
                                                          encoding=encoding, *args, **kwargs)


def get_simple_object_parser(object_type: Type[T]) -> RootParser:
    """
    Convenience method to create a parser ready to parse the simple object type provided, from supported dict files

    :param object_type:
    :return:
    """
    rp = RootParser()

    def convert_dict_to_simple_typed_object(dict) -> T:
        return convert_dict_to_simple_object(dict, object_type=object_type)

    rp.register_converter(dict, object_type, convert_dict_to_simple_typed_object)
    return rp


def _check_common_vars_core(item_file_prefix, item_type, item_name_for_log, indent_str_for_log):
    """
    Utility method to check all these variables and apply defaults
    :param item_file_prefix:
    :param item_type:
    :param item_name_for_log:
    :param indent_str_for_log:
    :return:
    """
    check_var(item_file_prefix, var_types=str, var_name='item_path')
    check_var(item_type, var_types=type, var_name='item_type')
    item_name_for_log = item_name_for_log or '<item>'
    check_var(item_name_for_log, var_types=str, var_name='item_name')
    indent_str_for_log = indent_str_for_log or ''
    check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

    return indent_str_for_log, item_name_for_log