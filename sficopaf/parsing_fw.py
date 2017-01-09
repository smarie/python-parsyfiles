import logging
from copy import deepcopy
from inspect import getmembers, signature, Parameter
from io import TextIOBase
from threading import RLock
from typing import Tuple, Any, Dict, Callable, Type, List, Set, Union, TypeVar, Generic
from warnings import warn

from sficopaf.dict_parsers import get_default_dict_parsers, get_default_dict_of_dicts_parsers
from sficopaf.parsing_filemapping import FileMappingConfiguration, ObjectNotFoundOnFileSystemError, \
    ObjectPresentMultipleTimesOnFileSystemError, EXT_SEPARATOR, WrappedFileMappingConfiguration
from sficopaf.var_checker import check_var

S = TypeVar('S')  # Can be anything - used for "source object"
T = TypeVar('T')  # Can be anything - used for all other objects

MULTIFILE_EXT = '<multifile>'

def parse_item(item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                   file_mapping_conf: FileMappingConfiguration = None,
                   lazy_parsing: bool = False, indent_str_for_log: str = None) -> T:
    """
    Creates a RootParser() and calls its parse_item() method
    :param item_file_prefix:
    :param item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param lazy_parsing:
    :param indent_str_for_log:
    :return:
    """
    rp = RootParser()
    return rp.parse_item(item_file_prefix, item_type, item_name_for_log, file_mapping_conf, lazy_parsing,
                         indent_str_for_log)

def parse_collection(item_file_prefix: str, collection_or_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                         indent_str_for_log: str = None) -> Union[T, Dict[str, T], List[T], Set[T], Tuple[T]]:
    """
    Creates a RootParser() and calls its parse_collection() method
    :param item_file_prefix:
    :param collection_or_item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param lazy_parsing:
    :param indent_str_for_log:
    :return:
    """
    rp = RootParser()
    return rp.parse_collection(item_file_prefix, collection_or_item_type, item_name_for_log, file_mapping_conf,
                               lazy_parsing, indent_str_for_log)

class ObjectCannotBeParsedError(Exception):
    """
    Raised whenever an object can not be parsed - but there is a file present
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(ObjectCannotBeParsedError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_type: Type[Any], is_singlefile: bool, item_file_path: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        if is_singlefile:
            return ObjectCannotBeParsedError('The object \'' + item_name + '\' is present on file system as a '
                                             'singlefile object at path \'' + item_file_path + '\' but cannot be '
                                             'parsed because no parser is registered for this extension for object type'
                                             ' \'' + item_type.__name__ + '\', and the extension present is not one of the '
                                             'extensions that may be used for auto-parsing using a dictionary :'
                                             + get_default_dict_parsers().keys() )
        else:
            return ObjectCannotBeParsedError('The object \'' + item_name + '\' is present on file system as a '
                                             'multifile object at path \'' + item_file_path + '\' but cannot be parsed '
                                             'because no multifile parser is registered for object type \''
                                             + item_type.__name__)

class ParsingChain(Generic[T]):
    """
    Represents a parsing chain, with a mandatory initial parser function and a list of converters.
    The parser function may be
    * a singlefile parser - in which case the file will be opened by the framework and the signature of the function
    should be f(opened_file: TextIoBase) -> T
    * a multifile parser - in which case the framework will not open the files and the signature of the function should
    be f(multifile_path: str, file_ammping_conf: FileMappingConfiguration) -> T
    """
    def __init__(self, item_type: Type[T], parser_function:Union[Callable[[TextIOBase], T],
                                                                 Callable[[str, FileMappingConfiguration], T]]):
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
        Utility method to parse using the parser and all converters in order.
        :return:
        """
        res = self._parser_func(file_object)
        for converter_func in self._converters_list:
            res = converter_func(res)
        return res

    def parse_multifile_with_chain(self, file_prefix: str, file_mapping_conf: FileMappingConfiguration):
        """
        Utility method to parse a multifile item using the parser and all converters in order
        :param file_prefix:
        :param file_mapping_conf:
        :return:
        """
        res = self._parser_func(file_prefix, file_mapping_conf)
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
    def create(file_path: str, parsing_chain: ParsingChain[T], encoding: str, cause):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return ParsingException('Error while parsing file at path \'' + file_path + '\' with encoding \'' + encoding
                                + '\' and parser function \'' + str(parsing_chain)+ '\'.\n'
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
                                extension_parser: Union[Callable[[TextIOBase], T], Callable[[str, FileMappingConfiguration], T]]):
        """
        To register a single parsing function, for a single file extension, for a given object type
        :param object_type:
        :param extension:
        :param extension_parser:
        :return:
        """
        check_var(object_type, var_types=type)
        check_var(extension, var_types=str, min_len=1)

        # Extension should either be 'multifile' or start with EXT_SEPARATOR and contain only one EXT_SEPARATOR
        if not ((extension.startswith(EXT_SEPARATOR) and extension.count(EXT_SEPARATOR) == 1)
                or extension is MULTIFILE_EXT):
            raise ValueError('\'extension\' should either start with \'' + EXT_SEPARATOR + '\' and contain not other '
                             'occurence of \'' + EXT_SEPARATOR + '\', or be equal to '
                             '\'' + MULTIFILE_EXT + '\' (for multifile object parsing)')

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

    def register_parsers_for_type(self, object_type:Type[T], extension_parsers:Dict[str, Union[Callable[[TextIOBase], T], Callable[[str, FileMappingConfiguration], T]]]):
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

    def register_parsers(self, parsers:Dict[Type[T], Dict[str, Union[Callable[[TextIOBase], T], Callable[[str, FileMappingConfiguration], T]]]]):
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

    def get_parsers_copy(self) -> Dict[Type[T], Dict[str, Dict[str, Union[Callable[[TextIOBase], T], Callable[[str, FileMappingConfiguration], T]]]]]:
        """
        Returns a deep copy of the parsers dictionary
        :return:
        """
        return deepcopy(self.__parsers)

    def get_all_known_parsing_chains_for_type(self, item_type: Type[T]) \
            -> Dict[str, ParsingChain[T]]:
        """
        Utility method to return the parsing_chain associated to a given type. A dictionary extension > parsing_chain

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
                subchains = self.get_all_known_parsing_chains_for_type(source_type, error_if_not_found=False)
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

        return parsing_chains


    def get_all_known_parsing_chains(self):
        """
        Utility method to return all known parsing chains (obtained by assembling converters and parsers)

        :return:
        """
        return {type: self.get_all_known_parsing_chains_for_type(type)
                for type in list(self.__parsers.keys()) + list(self.__converters.keys())}


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

        # default to wrapped mode
        file_mapping_conf = file_mapping_conf or WrappedFileMappingConfiguration()
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
        base_collection_type = find_associated_typing_collection_class_or_none(collection_or_item_type)
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
        item_paths = file_mapping_conf.find_collectionobject_contents_file_occurrences(item_file_prefix)

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
        * First check if there is at least a registered parsing chain for `item_type`. If so, try to parse the file or
        folder at path `item_file_prefix` with the parsing chain corresponding to its file extension
        * If the above did not succeed, use either the collection parser (if `item_type` is a collection)
        or the single-file or multi-file object parser (if `item_type` is not a collection)

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


        # 1. Try to find and use registered parsing chains
        parsing_chains = self.get_all_known_parsing_chains_for_type(item_type)
        if len(parsing_chains) > 0:
            try:
                return parse_singlefile_object_with_parsing_chains(
                    item_file_prefix,
                    item_type,
                    file_mapping_conf,
                    parsing_chains,
                    item_name_for_log=item_name_for_log,
                    indent_str_for_log=indent_str_for_log)
            except ObjectNotFoundOnFileSystemError as e:
                # A file with a compliant extension was not found. Continue because maybe the other parsers will work
                RootParser.logger.info(
                    indent_str_for_log + str(len(parsing_chains)) + ' Explicitly registered parsing chain(s) were found'
                    ' for this type \'' + str(item_type.__name__) + '\' but no compliant file was found on the file system. '
                    'Trying to use the appropriate default auto-parser (singlefile, multifile, collection) depending on '
                    'what is found on the file system. For information, the registered parsing chain(s) are ' + str(parsing_chains))
        else:
            RootParser.logger.info(
                indent_str_for_log + 'There was no explicitly registered parsing chain for this type \'' + str(item_type.__name__)
                + '\'. Trying to use the appropriate default auto-parsers (singlefile, multifile, collection) depending '
                  'on what is found on the file system')

        # 2. Check if the item has a collection type. If so, redirects on the collection method.
        if is_multifile_collection(item_type):
            # parse collection
            return self.parse_collection(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                         file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                         indent_str_for_log=indent_str_for_log)
        else:
            # Check what kind of object is present on the filesystem with this prefix.
            # This method throws exceptions if no file is found or the object is found multiple times (for example with
            # several file extensions, or as a file AND a folder)
            default_extensions = list(get_default_dict_parsers().keys()) + [MULTIFILE_EXT]
            is_single_file, singlefile_ext, singlefile_path = find_unique_singlefile_or_multifile_object(
                                                                                         item_file_prefix,
                                                                                         item_type,
                                                                                         file_mapping_conf,
                                                                                         item_name_for_log,
                                                                                         default_extensions)
            if is_single_file:
                # parse singlefile object using default dict parsers + constructor call
                RootParser.logger.info(
                    indent_str_for_log + 'No registered parser could be used, but a single file was found')
                return self._parse_singlefile_object(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                    file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                    indent_str_for_log=indent_str_for_log)
            else:
                # parse multifile object using constructor inference
                return self._parse_multifile_object(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                   file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                   indent_str_for_log=indent_str_for_log)


    def _parse_singlefile_object(self, item_file_prefix: str, item_type: Type[T], item_name_for_log=None,
                                file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                                indent_str_for_log: str = None) -> T:
        """
        Helper method to read an object of type "item_type" from a file path, as a simple (single-file) object.

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :param indent_str_for_log:
        :return:
        """

        RootParser.logger.info(indent_str_for_log + 'Parsing singlefile object ' + str(item_name_for_log) + ' of type '
                               + item_type.__name__ + ' at ' + item_file_prefix + '. This means *first* trying to parse it '
                                                                              'as a dictionary, and *then* calling its '
                                                                              'class constructor with the parsed '
                                                                              'dictionary.')

        try:
            # 1. Try to find a configuration file that can be read as a "dictionary of dictionaries"
            parsers = get_default_dict_of_dicts_parsers()
            parsed_dict = parse_singlefile_object_with_parsers(item_file_prefix, dict,
                                                               file_mapping_conf,
                                                               parsers=parsers,
                                                               item_name_for_log=item_name_for_log,
                                                               indent_str_for_log=indent_str_for_log)

            # 2. Then create an object by creating a simple object for each of its constructor attributes
            return convert_dict_of_dicts_to_singlefile_object(parsed_dict, object_type=item_type)

        except (ObjectNotFoundOnFileSystemError, InvalidAttributeNameError,
                TypeInformationRequiredToBuildObjectError, TypeError) as e:
            # All these errors may happen:
            # * ObjectNotFoundOnFileSystemError if the object is present but in other extension
            # * TypeError, InvalidAttributeNameError and TypeInformationRequiredToBuildObjectError if the file is a
            # configuration file but it should be used in 'dict' mode, not 'dict of dicts'

            # in all these cases, the other simple 'dict' parsers may be the desired behaviour, so let it go
            pass

        # 2. switch to the 'normal' dictionary parsers
        parsers = get_default_dict_parsers()
        parsed_dict = parse_singlefile_object_with_parsers(item_file_prefix, dict,
                                                           file_mapping_conf,
                                                           parsers=parsers,
                                                           item_name_for_log=item_name_for_log,
                                                           indent_str_for_log=indent_str_for_log)
        return convert_dict_to_singlefile_object(parsed_dict, object_type=item_type)


    def _parse_multifile_object(self, item_file_prefix:str, item_type:Type[T], item_name_for_log=None,
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
        if is_multifile_collection(item_type):
            raise TypeError('Item ' + item_name_for_log + ' is a Collection-like object cannot be parsed with '
                            'parse_single_item(). Found type ' + item_type.__name__)


        # 2. Parse according to the mode.
        RootParser.logger.info(indent_str_for_log + 'Parsing multifile object ' + item_name_for_log + ' of type '
                               + item_type.__name__ + ' at \'' + item_file_prefix + '\'. This means trying to parse each '
                               'attribute of its class constructor as a separate file.')

        # -- (a) extract the schema from the class constructor
        s = _get_constructor_signature(item_type)

        # -- (b) parse each attribute required by the constructor
        parsed_object = {} # results will be put in this object
        for attribute_name, param in s.parameters.items():

            attribute_is_mandatory = param.default is Parameter.empty       # - is it a mandatory attribute ?
            attribute_type = param.annotation                               # - get the object class

            if attribute_name is 'self':
                pass # nothing to do, this is not an attribute
            else:
                attribute_file_prefix = file_mapping_conf.get_file_prefix_for_multifile_object_attribute(item_file_prefix,
                                                                                                         attribute_name)
                att_item_name_for_log = item_name_for_log + '.' + attribute_name
                try:
                    parsed_object[attribute_name] = self.parse_item(attribute_file_prefix, attribute_type,
                                                                    item_name_for_log=att_item_name_for_log,
                                                                    file_mapping_conf=file_mapping_conf,
                                                                    indent_str_for_log=indent_str_for_log + '--')
                except ObjectNotFoundOnFileSystemError as e:
                    if attribute_is_mandatory:
                        # raise the error only if the attribute was mandatory
                        raise e

        # -- (d) finally create the object and return it
        return item_type(**parsed_object)


def find_unique_singlefile_or_multifile_object(item_file_prefix: str, item_type: Type[Any],
                                               file_mapping_conf: FileMappingConfiguration,
                                               item_name_for_log: str, extensions_to_match: List[str]) \
        -> Tuple[bool, str, str]:
    """
    Utility method to find a unique singlefile or multifile object, matching one of the extensions provided.
    This method throws
    * ObjectNotFoundOnFileSystemError if no file is found
    * ObjectPresentMultipleTimesOnFileSystemError if the object is found multiple times (for example with
    several file extensions, or as a file AND a folder)
    * ObjectCannotBeParsedError if the object is present once but not with an extension matching extensions_to_match

    :param item_file_prefix:
    :param file_mapping_conf:
    :param item_name_for_log:
    :param extensions_to_match: the extensions that should be matched. If a single object file is found but its
    extension does not match any of the provided ones, a ObjectCannotBeParsedError will be thrown.
    :return: a tuple (bool, str, str). If a unique singlefile object is present this is set to [True, singlefile_ext,
    singlefile_path] ; if a unique multifile object is present this is set to [False, MULTIFILE_EXT, None]
    """
    simpleobjects_found = file_mapping_conf.find_simpleobject_file_occurrences(item_file_prefix)
    complexobject_attributes_found = file_mapping_conf.find_multifileobject_attribute_file_occurrences(
        item_file_prefix)
    if len(simpleobjects_found) > 1 or len(simpleobjects_found) == 1 and len(complexobject_attributes_found) > 0:
        # the object is present several times ! error
        raise ObjectPresentMultipleTimesOnFileSystemError.create(item_name_for_log, item_file_prefix,
                                                                 simpleobjects_found +
                                                                 complexobject_attributes_found)
    elif len(simpleobjects_found) == 1:
        is_single_file = True
        ext = list(simpleobjects_found.keys())[0]
        singlefile_object_file_path = simpleobjects_found[ext]
        if ext not in extensions_to_match:
            # a single file is there but is does not have the required extensions to be parsed automatically
            raise ObjectCannotBeParsedError.create(item_name_for_log, item_type, is_single_file, singlefile_object_file_path)

    elif len(complexobject_attributes_found) > 0:
        is_single_file = False
        ext = MULTIFILE_EXT
        singlefile_object_file_path = None
        if MULTIFILE_EXT not in extensions_to_match:
            # a multifile is there but this was not requested
            raise ObjectCannotBeParsedError.create(item_name_for_log, item_type, is_single_file,
                                                   complexobject_attributes_found[MULTIFILE_EXT])

    else:
        # the object was not found in a form that can be parsed
        raise ObjectNotFoundOnFileSystemError.create(item_name_for_log, item_file_prefix,
                                                     simpleobjects_found.keys())
    return is_single_file, ext, singlefile_object_file_path


def parse_singlefile_object_with_parsing_chains(item_file_prefix: str, item_type: Type[Any],
                                                file_mapping_conf: FileMappingConfiguration,
                                                parsing_chains: Dict[str, ParsingChain[T]],
                                                item_name_for_log, indent_str_for_log):
    """
    Utility function to parse a singlefile or multifile object with a bunch of available parsing chains
    (a [extension > parsing_chain] dictionary, where a special extension denotes a multifile).
    This method throws
    * ObjectNotFoundOnFileSystemError if no file is found
    * ObjectPresentMultipleTimesOnFileSystemError if the object is found multiple times (for example with
    several file extensions, or as a file AND a folder)
    * ObjectCannotBeParsedError if the object is present once but not with an extension matching extensions_to_match

    :param item_file_prefix:
    :param item_type:
    :param file_mapping_conf:
    :param parsing_chains:
    :param item_name_for_log:
    :param indent_str_for_log:
    :return:
    """

    # 0. check all vars
    indent_str_for_log, item_name_for_log = _check_common_vars_core(item_file_prefix, item_type,
                                                                    item_name_for_log,
                                                                    indent_str_for_log)

    # validate that there is at least one parser, otherwise this method should not have been called !
    check_var(parsing_chains, var_types=dict, var_name='parsers', min_len=1)
    check_var(file_mapping_conf, var_types=FileMappingConfiguration, var_name='file_mapping_conf')

    # 1. Check what kind of object is present on the filesystem with this prefix, that could be read with the extensions
    # supported by the parsers.
    #
    # This method throws exceptions if no file is found or the object is found multiple times (for example with
    # several file extensions, or as a file AND a folder)
    is_single_file, file_ext, singlefile_path = find_unique_singlefile_or_multifile_object(item_file_prefix,
                                                                                 item_type,
                                                                                 file_mapping_conf,
                                                                                 item_name_for_log,
                                                                                 parsing_chains.keys())
    if is_single_file:
        # parse this file and add to the result
        parsing_chain = parsing_chains[file_ext]
        RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_log + ' of type <' +
                               item_type.__name__ + '> as singlefile at ' + singlefile_path + ' with parsing chain '
                               + str(parsing_chain))
        return parse_single_file_with_parsing_chain(singlefile_path, parsing_chain, encoding=file_mapping_conf.encoding)
    else:
        # parse this file and add to the result
        parsing_chain = parsing_chains[file_ext]
        RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_log + ' of type ' + item_type.__name__ +
                               ' as multifile at ' + item_file_prefix + ' with parsing chain ' + str(parsing_chain))
        return parse_multifile_with_parsing_chain(item_file_prefix, file_mapping_conf, parsing_chain)


def parse_single_file_with_parsing_chain(file_path: str, parsing_chain: ParsingChain[T],
                                         encoding: str = None) -> T:
    """
    Utility function to parse a single-file object from the provided path, using the provided parsing chain. If an
    error happens during parsing it will be wrapped into a ParsingException

    :param file_path:
    :param parsing_chain:
    :param encoding:
    :return:
    """

    check_var(file_path, var_types=str, var_name='file_path')
    check_var(parsing_chain, var_types=ParsingChain, var_name='parsing_chain')
    encoding = encoding or 'utf-8'
    check_var(encoding, var_types=str, var_name='encoding')

    f = None
    try:
        # Open the file with the appropriate encoding
        f = open(file_path, 'r', encoding=encoding)

        # Apply the parsing function
        return parsing_chain.parse_with_chain(f)

    except Exception as e:
        # Wrap into a ParsingException
        raise ParsingException.create(file_path, parsing_chain, encoding, e)\
            .with_traceback(e.__traceback__) # 'from e' was hiding the inner traceback. This is much better for debug
    finally:
        if f is not None:
            # Close the File in any case
            f.close()


def parse_multifile_with_parsing_chain(file_prefix: str, file_mapping_conf: FileMappingConfiguration,
                                       parsing_chain: ParsingChain[T]) -> T:
    """
    In this method the parsing chain is used to parse the multifile object file_prefix. Therefore the parsing chain
    is responsible to open/close the files

    :param file_prefix:
    :param file_mapping_conf:
    :param parsing_chain:
    :return:
    """
    return parsing_chain.parse_multifile_with_chain(file_prefix, file_mapping_conf)


def parse_singlefile_object_with_parsers(item_file_prefix: str, item_type: Type[Any],
                                         file_mapping_conf: FileMappingConfiguration,
                                         parsers: Dict[str, Union[Callable[[TextIOBase], T],
                                                                  Callable[[str, FileMappingConfiguration], T]]],
                                         item_name_for_log, indent_str_for_log):
    """
    Utility function to parse a singlefile object with a bunch of available parsers (a [extension > function] dictionary).
    It will look if the file is present with a SINGLE supported extension, and parse with the associated parser if it
    is the case.

    :param item_file_prefix:
    :param item_type:
    :param file_mapping_conf:
    :param parsers:
    :param item_name_for_log:
    :param indent_str_for_log:
    :return:
    """

    # First transform all parser functions into parsing chains
    parsing_chains = {ext: ParsingChain(item_type, parser_function) for ext, parser_function in parsers.items()}

    # Then use the generic method with parsing chains
    return parse_singlefile_object_with_parsing_chains(item_file_prefix, item_type, file_mapping_conf,
                                                       parsing_chains, item_name_for_log, indent_str_for_log)


def parse_single_file_object_with_parser_function(file_path:str, item_type: Type[T],
                                                  parser_function:Callable[[TextIOBase], T],
                                                  encoding:str= None, *args, **kwargs) -> T:
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
    return parse_single_file_with_parsing_chain(file_path, ParsingChain(item_type, parser_function),
                                                encoding=encoding, *args, **kwargs)


# def get_singlefile_object_parser(object_type: Type[T]) -> RootParser:
#     """
#     Convenience method to create a parser ready to parse the singlefile object type provided, from supported dict files
#
#     :param object_type:
#     :return:
#     """
#     rp = RootParser()
#
#     def convert_dict_to_singlefile_typed_object(dict) -> T:
#         return convert_dict_to_singlefile_object(dict, object_type=object_type)
#
#     rp.register_converter(dict, object_type, convert_dict_to_singlefile_typed_object)
#     return rp


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


def is_multifile_collection(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}.

    :param object_type:
    :return:
    """
    return find_associated_typing_collection_class_or_none(object_type) is not None


def find_associated_typing_collection_class_or_none(object_type):
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


def _get_constructor_signature(item_type):
    constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
    if len(constructors) is not 1:
        raise ValueError('Several constructors were found for class ' + item_type.__name__)
    # extract constructor
    constructor = constructors[0]
    s = signature(constructor)
    return s


class InvalidAttributeNameError(Exception):
    """
    Raised whenever an object can not be parsed - but there is a file present
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(InvalidAttributeNameError, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any], constructor_atts: List[str], invalid_property_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return InvalidAttributeNameError('Cannot parse object of type <' + item_type + '> using the provided '
                                         'configuration file: configuration contains a property name (\''
                                         + invalid_property_name + '\') that is not an attribute of the object '
                                         'constructor. <' + item_type + '> constructor attributes are : '
                                         + str(constructor_atts))


class TypeInformationRequiredToBuildObjectError(Exception):
    """
    Raised whenever an object can not be parsed - but there is a file present
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(TypeInformationRequiredToBuildObjectError, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any], faulty_attribute_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return TypeInformationRequiredToBuildObjectError('Cannot parse object of type <' + item_type + '> using a '
                                                         'configuration file as a \'dictionary of dictionaries\': '
                                                         'attribute \'' + faulty_attribute_name + '\' has no valid '
                                                         'PEP484 type hint.')


def convert_dict_to_singlefile_object(parsed_dict: Dict[str, Any], object_type: Type[Any]) -> Any:
    """
    Utility method to create an object from a dictionary

    :param parsed_dict:
    :param object_type:
    :return:
    """
    check_var(object_type, var_types=type, var_name=object_type)
    try:
        # check constructor signature
        s = _get_constructor_signature(object_type)

        # for each attribute, convert the types of its parsed values if required
        dict_for_init = dict()
        for attr_name, parsed_attr_value in parsed_dict.items():
            if attr_name in s.parameters.keys():
                attribute_type = s.parameters[attr_name].annotation
                dict_for_init[attr_name] = try_convert_attribute_value_to_correct_type(object_type, attribute_type,
                                                                                       parsed_attr_value)
            else:
                # the dictionary entry does not correspond to a valid attribute of the object
                raise InvalidAttributeNameError.create(object_type, list(s.parameters.keys()), attr_name)

        # create the object using its constructor
        return object_type(**dict_for_init)

    except TypeError as e:
        warn('Error while trying to instantiate object of type ' + str(object_type) + ' using dictionary input_dict :')
        print_dict('input_dict', parsed_dict)
        raise e


def convert_dict_of_dicts_to_singlefile_object(parsed_dict: Dict[str, Any], object_type: Type[Any]) -> Any:
    """
    Utility method to create an object from a dictionary of dictionaries. The keys of the first dictionary should be
    attribute names of the object constructor, and their types should be available through annotations.

    :param parsed_dict:
    :param object_type:
    :return:
    """
    try:
        # check constructor signature
        s = _get_constructor_signature(object_type)

        # for each attribute, create the object corresponding to its type
        dict_for_init = dict()
        for attr_name, parsed_attr_dict in parsed_dict.items():
            if attr_name in s.parameters.keys():
                attribute_type = s.parameters[attr_name].annotation
                if type(attribute_type) is not type:
                    raise TypeInformationRequiredToBuildObjectError.create(object_type, attr_name)
                dict_for_init[attr_name] = convert_dict_to_singlefile_object(parsed_attr_dict, attribute_type)
            else:
                # the dictionary entry does not correspond to a valid attribute of the object
                raise InvalidAttributeNameError.create(object_type, list(s.parameters.keys()), attr_name)

        # create the object using its constructor
        return object_type(**dict_for_init)

    except TypeError as e:
        warn('Error while trying to instantiate object of type ' + str(object_type) + ' using dictionary input_dict :')
        print_dict('input_dict', parsed_dict)
        raise e

def try_convert_attribute_value_to_correct_type(object_type: Type[Any], attribute_type: Type[Any],
                                                parsed_attr_value: Any):
    """
    Utility method to try to convert the provided attribute value to the correct type

    :param object_type:
    :param attribute_type:
    :param parsed_attr_value:
    :return:
    """
    if type(attribute_type) == type:
        if not isinstance(parsed_attr_value, attribute_type):
            # try to convert the type by simply casting
            # TODO rather use the parsing chains
            res = attribute_type(parsed_attr_value)
        else:
            # we can safely use the value: it is already of the correct type
            res = parsed_attr_value
    else:
        warn('Constructor for type \'' + str(object_type) + '\' has no PEP484 Type hint, trying to use the '
                                                            'parsed value in the dict directly')
        res = parsed_attr_value
    return res


def print_dict(dict_name, dict_value):
    """
    Utility method to print a named dictionary

    :param dict_name:
    :param dict_value:
    :return:
    """
    print(dict_name + ' = ')
    try:
        from pprint import pprint
        pprint(dict_value)
    except:
        print(dict_value)