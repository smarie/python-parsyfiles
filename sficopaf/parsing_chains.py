import logging
from copy import deepcopy
from io import TextIOBase
from threading import RLock
from typing import TypeVar, Generic, Union, Type, Callable, Dict, Any, List, Tuple
from warnings import warn

from sficopaf.dict_parsers import get_default_dict_parsers
from sficopaf.parsing_filemapping import FileMappingConfiguration, EXT_SEPARATOR, ObjectNotFoundOnFileSystemError, \
    ObjectPresentMultipleTimesOnFileSystemError
from sficopaf.parsing_types import get_pretty_type_str
from sficopaf.var_checker import check_var

S = TypeVar('S')  # Can be anything - used for "source object"
T = TypeVar('T')  # Can be anything - used for all other objects

MULTIFILE_EXT = '<multifile>'


def _check_common_vars_core(item_file_prefix, item_type, item_name_for_log, indent_str_for_log):
    """
    Utility method to check all these variables and apply defaults
    :param item_file_prefix:
    :param item_type:
    :param item_name_for_log:
    :param indent_str_for_log:
    :return:
    """
    # TODO should not be in this file..
    check_var(item_file_prefix, var_types=str, var_name='item_path')
    check_var(item_type, var_types=type, var_name='item_type')
    item_name_for_log = item_name_for_log or '<item>'
    check_var(item_name_for_log, var_types=str, var_name='item_name')
    indent_str_for_log = indent_str_for_log or ''
    check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

    return indent_str_for_log, item_name_for_log


class ParsingChain(Generic[T]):
    """
    Represents a parsing chain, with a mandatory initial parser function and a list of converters.
    The parser function may be
    * a singlefile parser - in which case the file will be opened by the framework and the signature of the function
    should be f(opened_file: TextIoBase) -> T
    * a multifile parser - in which case the framework will not open the files and the signature of the function should
    be f(multifile_path: str, file_ammping_conf: FileMappingConfiguration) -> T
    """
    logger = logging.getLogger(__name__)

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
            raise TypeError('Cannnot register a converter on this conversion chain : source type \'' +
                            get_pretty_type_str(source_item_type)
                            + '\' is not compliant with current destination type of the chain : \'' +
                            get_pretty_type_str(self._item_type))

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


class _ParsingChainsManager(object):
    """
    The base class able to combine parsers and converters to create prsing chains. It also provides the capabilities
    to modify the registered parsers and converters
    """

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
                    warn('Warning : overriding existing converter from type ' + str(from_type) + ' to type ' +
                         str(to_type))
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
                                extension_parser: Union[Callable[[TextIOBase], T],
                                                        Callable[[str, FileMappingConfiguration], T]]):
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
                             'occurence of \'' + EXT_SEPARATOR + '\', or be equal to \'' + MULTIFILE_EXT + '\' (for '
                             'multifile object parsing)')

        check_var(extension_parser, var_types=Callable)

        self.__types_lock.acquire()
        try:
            if object_type in self.__parsers.keys():
                if extension in self.__parsers[object_type]:
                    warn('Warning : overriding existing extension parser for type <' + get_pretty_type_str(object_type)
                         + '> and extension ' + extension)
                self.__parsers[object_type][extension] = extension_parser
            else:
                self.__parsers[object_type] = {extension: extension_parser}
        finally:
            self.__types_lock.release()
        return

    def register_parsers_for_type(self, object_type:Type[T],
                                  extension_parsers:Dict[str, Union[Callable[[TextIOBase], T],
                                                                    Callable[[str, FileMappingConfiguration], T]]]):
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

    def register_parsers(self, parsers:Dict[Type[T], Dict[str,
                                                          Union[Callable[[TextIOBase], T],
                                                                Callable[[str, FileMappingConfiguration], T]]]]):
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

    def get_parsers_copy(self) -> Dict[Type[T], Dict[str, Dict[str,
                                                               Union[Callable[[TextIOBase], T],
                                                                     Callable[[str, FileMappingConfiguration], T]]]]]:
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
            parsing_chains = {ext: ParsingChain(item_type, parser_fun)
                              for ext, parser_fun in self.__parsers[item_type].items()}
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


def parse_object_with_parsing_chains(item_file_prefix: str, item_type: Type[Any],
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
        log_parsing_info(indent_str=indent_str_for_log, item_name=item_name_for_log, item_type=item_type,
                         item_file_prefix=item_file_prefix, parser_name=str(parsing_chain),
                         is_single_file=True, additional_details='')

        return parse_single_file_with_parsing_chain(singlefile_path, parsing_chain, encoding=file_mapping_conf.encoding)
    else:
        # parse this file and add to the result
        parsing_chain = parsing_chains[file_ext]
        log_parsing_info(indent_str=indent_str_for_log, item_name=item_name_for_log, item_type=item_type,
                         item_file_prefix=item_file_prefix, parser_name=str(parsing_chain),
                         is_single_file=False, additional_details='')
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
    return parse_object_with_parsing_chains(item_file_prefix, item_type, file_mapping_conf,
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


def find_unique_singlefile_or_multifile_object(item_file_prefix: str, item_type: Type[Any],
                                               file_mapping_conf: FileMappingConfiguration,
                                               item_name_for_log: str, extensions_to_match: List[str]) \
        -> Tuple[bool, str, Union[str, Dict[str, str]]]:
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
    :return: If a unique singlefile object is present this is set to [True, singlefile_ext,
    singlefile_path] ; if a unique multifile object is present this is set to [False, MULTIFILE_EXT,
    complexobject_attributes_found], with complexobject_attributes_found being a dictionary
    """
    simpleobjects_found = file_mapping_conf.find_simpleobject_file_occurrences(item_file_prefix)
    complexobject_attributes_found = file_mapping_conf.find_multifileobject_contents(item_file_prefix)
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
            raise ObjectCannotBeParsedError.create(item_name_for_log, item_type, is_single_file,
                                                   singlefile_object_file_path, extensions_to_match)
        else:
            return is_single_file, ext, singlefile_object_file_path

    elif len(complexobject_attributes_found) > 0:
        is_single_file = False
        ext = MULTIFILE_EXT
        if MULTIFILE_EXT not in extensions_to_match:
            # a multifile is there but this was not requested
            raise ObjectCannotBeParsedError.create(item_name_for_log, item_type, is_single_file,
                                                   complexobject_attributes_found[MULTIFILE_EXT],
                                                   extensions_to_match)
        else:
            if '' in complexobject_attributes_found.keys() or None in complexobject_attributes_found.keys():
                raise IllegalContentNameError.create(item_name_for_log, item_type,
                                                     complexobject_attributes_found[MULTIFILE_EXT])
            return is_single_file, ext, complexobject_attributes_found
    else:
        # the object was not found in a form that can be parsed
        raise ObjectNotFoundOnFileSystemError.create(item_name_for_log, item_file_prefix,
                                                     simpleobjects_found.keys())


def log_parsing_info(indent_str: str, item_name: str, item_type: Type[Any], item_file_prefix: str,
                     parser_name: str, is_single_file: bool, additional_details: str):
    """
    Utility method for logging information about a parsing operation that is starting

    :param indent_str:
    :param item_name:
    :param item_type:
    :param item_file_prefix:
    :param parser_name:
    :param is_single_file:
    :param additional_details:
    :return:
    """
    file_type = 'singlefile' if is_single_file else 'multifile'
    ParsingChain.logger.info(indent_str + 'Parsing object \'' + item_name + '\' of type <' +
                           get_pretty_type_str(item_type) + '> '
                           'at *' + file_type + '* location \'' + item_file_prefix + '\' with ' + parser_name + '. '
                           + additional_details)


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
    def create(item_name: str, item_type: Type[Any], is_singlefile: bool, item_file_path: str, extensions_to_match: dict):
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
                                             ' \'' + get_pretty_type_str(item_type) + '\', and the extension present '
                                             'is not one of the extensions that may be used for auto-parsing : '
                                             + str(extensions_to_match))
        else:
            return ObjectCannotBeParsedError('The object \'' + item_name + '\' is present on file system as a '
                                             'multifile object at path \'' + item_file_path + '\' but cannot be parsed '
                                             'because no multifile parser is registered for object type <'
                                             + get_pretty_type_str(item_type) + '>')


class IllegalContentNameError(Exception):
    """
    Raised whenever a attribute of a multifile object or collection has an empty name
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(IllegalContentNameError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_type: Type[Any], item_file_path: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return IllegalContentNameError('The object \'' + item_name + '\' of type <' + get_pretty_type_str(item_type) + '> is '
                                       'present on file system as a multifile object at path \'' + item_file_path + '\''
                                       ' but contains an attribute with an empty name at path \'' + item_file_path
                                       + '\'')