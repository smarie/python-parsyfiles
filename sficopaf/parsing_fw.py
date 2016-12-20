import logging
from copy import deepcopy
from inspect import getmembers, signature, Parameter
from io import TextIOBase
from os import listdir
from os.path import isfile, join, isdir, dirname, basename
from threading import RLock
from typing import Tuple, Any, Dict, Callable, Type, List, Set, Union

from sficopaf import check_var


class FolderAndFilesStructureError(Exception):
    """
    Raised whenever the folder and files structure does not match with the one expected
    """
    def __init__(self, contents):
        super(FolderAndFilesStructureError, self).__init__(contents)


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

class MultipleFilesError(Exception):
    """
    Raised whenever a given attribute is provided several times in the filesystem (with multiple extensions)
    """
    def __init__(self, contents:str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MultipleFilesError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str]):  # -> UnsupportedObjectTypeError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found:
        :return:
        """
        return MultipleFilesError('Attribute : ' + item_name + ' is present multiple times in the file '
                                                 'system under path ' + item_file_prefix + ', with '
                                                 'extensions : ' + str(extensions_found) + '. Only one version of each'
                                                 ' attribute should be provided')

class MandatoryFileNotFoundError(FileNotFoundError):
    """
    Raised whenever a given attribute is missing in the filesystem (no supported extensions found)
    """

    def __init__(self, contents: str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MandatoryFileNotFoundError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str]):  # -> MandatoryFileNotFoundError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found:
        :return:
        """
        return MandatoryFileNotFoundError('Mandatory attribute : ' + item_name + ' could not be found on the file '
                                          'system under path ' + item_file_prefix + ' with one of the supported '
                                          'extensions ' + str(extensions_found))

class RootParser(object):
    """
    The root parser
    """
    EXT_SEPARATOR = '.'

    logger = logging.getLogger(__name__)

    def __init__(self, initial_parsers: Dict[Type[Any], Dict[str, Callable[[TextIOBase], Any]]] = None):
        """
        Constructor. Initializes the dictionary of parsers with the optionally provided initial_parsers, and
        inits the lock that will be used for access in multithreading context.

        :param initial_parsers:
        """
        self.__types_lock = RLock() # lock for self.__parsers
        self.__parsers = {} # Dict[Type > Dict[ext > parser]]

        if initial_parsers is not None:
            self.register_parsers(initial_parsers)
        return


    def register_extension_parser(self, object_type: Type[Any], extension: str,
                                  extension_parser: Callable[[TextIOBase], Any]):
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


    def register_type(self, object_type:Type[Any], extension_parsers:Dict[str, Callable[[TextIOBase], Any]]):
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
            self.register_extension_parser(object_type, extension, extension_parser)
        return


    def register_parsers(self, parsers:Dict[Type[Any], Dict[str, Callable[[TextIOBase], Any]]]):
        """
        Registers the provided parsers
        :param parsers:
        :return:
        """
        check_var(parsers, var_types=dict)

        # don't use dict.update because we want to perform sanity checks here
        for object_type, extension_parsers in parsers.items():
            self.register_type(object_type, extension_parsers)
        return


    def get_parsers_copy(self) -> Dict[Type[Any], Dict[str, Dict[str, Callable[[TextIOBase], Any]]]]:
        """
        Returns a deep copy of the parsers dictionary
        :return:
        """
        return deepcopy(self.__parsers)


    def get_parsers_for_type(self, item_type: Type[Any]) -> Dict[str, Callable[[TextIOBase], Any]]:
        """
        Utility method to return the parsers associated to a given type.
        Throws an UnsupportedObjectTypeError if not found

        :param item_type:
        :return: the dictionary of (extension, parsers) for the given type
        """
        try:
            # get associated parsers - throws KeyError if not found
            attribute_parsers = self.__parsers[item_type]
        except KeyError as e:
            # find a compliant parent type
            compliant_types = [supported_type for supported_type in self.__parsers.keys() if issubclass(item_type, supported_type)]
            if len(compliant_types) == 1:
                return self.__parsers[compliant_types[0]]
            elif len(compliant_types) > 1:
                raise TypeError('Several registered types exist that would fit requested type ' + str(item_type) +
                                '. Unknown behaviour, exiting.')
            else:
                raise UnsupportedObjectTypeError.create(item_type)
        return attribute_parsers


    def parse_item(self, item_file_prefix: str, item_type: Type[Any], item_name_for_log: str = None,
                   flat_mode: bool = False, sep_for_flat: str = '.', lazy_parsing: bool = False,
                   indent_str_for_log: str = None) -> Any:
        """
        Method to parse an item at the given parent path. Note that the type of this item may be a collection,
        this method will silently redirect to parse_collection.
        * If flat_mode = False, each item is a folder.
        * If flat_mode = True, each item is a set of files with the same prefix separated from the attribute name by
        the character sequence <sep_for_flat>

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param flat_mode:
        :param sep_for_flat:
        :param lazy_parsing:
        :param indent_str_for_log:
        :return:
        """

        # 0. check all inputs and perform defaults
        check_var(item_file_prefix, var_types=str, var_name='item_path')
        check_var(item_type, var_types=type, var_name='item_type')
        item_name_for_log = item_name_for_log or '<item>'
        check_var(item_name_for_log, var_types=str, var_name='item_name')
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')
        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
        indent_str_for_log = indent_str_for_log or ''
        check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

        # 1. Check if the item has a type for which a registered parser is available.
        try:
            self.get_parsers_for_type(item_type)
            # if we are here that means that there is a parser. Therefore parse single item
            return self.parse_single_item(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                          flat_mode=flat_mode, sep_for_flat=sep_for_flat, lazy_parsing=lazy_parsing,
                                          indent_str_for_log=indent_str_for_log)

        except UnsupportedObjectTypeError as e:
            # this means that no parser may be found, we can fallback to default behaviour

            # 2. Check if the item has a collection type. If so, redirects on the collection method.
            item_type_base = self._extract_base_item_type_if_collection_or_none_if_single(item_type, item_name_for_log)
            if item_type_base is not None:
                # parse collection
                return self.parse_collection(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                             flat_mode=flat_mode, sep_for_flat=sep_for_flat, lazy_parsing=lazy_parsing,
                                             indent_str_for_log=indent_str_for_log)
            else:
                # parse single item
                return self.parse_single_item(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                              flat_mode=flat_mode, sep_for_flat=sep_for_flat, lazy_parsing=lazy_parsing,
                                             indent_str_for_log=indent_str_for_log)


    def _extract_base_item_type_if_collection_or_none_if_single(self, collection_or_item_type, item_name_for_log):
        """
        Utility method to extract the base item type from a collection/iterable item type. R
        eturns None if the item type is not a collection, and throws an error if it is a collection but it uses the
        base types instead of relying on the typing module (typing.List, etc.).

        :param collection_or_item_type:
        :param item_name_for_log:
        :return:
        """
        # default value, if no wrapper collection type is found
        item_type = None

        if not hasattr(collection_or_item_type, '__args__'):
            # typically custom subclasses that don't way to be treated as collections
            pass

        elif issubclass(collection_or_item_type, Dict):
            # Dictionary
            # noinspection PyUnresolvedReferences
            key_type, item_type = collection_or_item_type.__args__
            if key_type is not str:
                raise TypeError(
                    'Item ' + item_name_for_log + ' has type Dict, but the keys are of type ' + key_type + ' which '
                                                                                                           'is not supported. Only str keys are supported')
        elif issubclass(collection_or_item_type, List) or issubclass(collection_or_item_type, Set):
            # List or Set
            # noinspection PyUnresolvedReferences
            item_type = collection_or_item_type.__args__[0]

        elif issubclass(collection_or_item_type, Tuple):
            # Tuple
            # noinspection PyUnresolvedReferences
            item_type = collection_or_item_type.__args__[0]
            raise TypeError('Tuple attributes are not supported yet')

        elif issubclass(collection_or_item_type, dict) or issubclass(collection_or_item_type, list) \
                or issubclass(collection_or_item_type, tuple) or issubclass(collection_or_item_type, set):
            # unsupported collection types
            raise TypeError('Found attribute type \'' + str(collection_or_item_type) + '\'. Please use one of '
                            'typing.Dict, typing.Set, typing.List, or typing.Tuple instead, in order to enable '
                            'type discovery for collection items')
        return item_type


    def parse_collection(self, parent_path: str, collection_or_item_type: Type[Any],
                         item_name_for_log: str = None, flat_mode: bool = False, sep_for_flat: str = '.',
                         lazy_parsing: bool = False, indent_str_for_log: str = None) \
            -> Union[Dict[str, Type[Any]], List[Type[Any]], Set[Type[Any]]]:
        """
        Method to start parsing a collection of items under the given folder path.
        * If flat_mode = False, each item is a folder.
        * If flat_mode = True, each item is a set of files with the same prefix separated from the attribute name by
        the character sequence <sep_for_flat>

        :param parent_path: the path of the parent item. it may be a folder or an absolute file prefix
        :param collection_or_item_type: the type of objects to parse in this collection. It should be a class from the typing
        package (PEP484), either List, Set, or Dict. If a different type T is provided, it is assumed that the desired
        result is Dict[T]
        :param item_name_for_log: the optional item name, just for logging information
        :param flat_mode: a boolean indicating if items should be represented by folders or a file name
         prefix
        :param sep_for_flat: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode
        :param lazy_parsing: if True, the method will return without parsing all the contents. Instead, the returned
        dictionary will perform the parsing only the first time an item is required.
        :return: a dictionary of named items and content
        """

        # 0. check inputs/params
        check_var(parent_path, var_types=str, var_name='folder_path')
        check_var(collection_or_item_type, var_types=type, var_name='collection_or_item_type')
        # optional
        check_var(item_name_for_log, var_types=str, var_name='item_name', enforce_not_none=False)
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')
        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
        indent_str_for_log = indent_str_for_log or ''
        check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

        item_name_for_main_log = (item_name_for_log or '<root>')

        # 1. Check the collection type and extract the base item type
        item_type = self._extract_base_item_type_if_collection_or_none_if_single(collection_or_item_type,
                                                                                 item_name_for_main_log)
        if item_type is None:
            # default behaviour when a non-collection type is provided : return a dictionary
            item_type = collection_or_item_type
            collection_or_item_type = Dict[str, item_type]


        # 2. Parse the collection
        RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_main_log + ' as a ' + str(collection_or_item_type) + ' collection at path ' + parent_path)

        # list all items in the collection and get their paths
        item_paths = self._list_collection_item_file_prefixes(parent_path, flat_mode=flat_mode, sep_for_flat=sep_for_flat)

        # create a dictionary item > content
        if lazy_parsing:
            # TODO make this a lazy dictionary instead (if required)
            raise ValueError('Lazy parsing is unsupported at the moment')
        else:
            # parse them right now
            results = {}
            for item, item_path in item_paths.items():
                results[item] = self.parse_item(item_path, item_type,
                                                item_name_for_log=(item_name_for_log or '') + '[' + item + ']',
                                                flat_mode=flat_mode, sep_for_flat=sep_for_flat,
                                                indent_str_for_log=indent_str_for_log + '--')

        # format output if needed
        if issubclass(collection_or_item_type, List):
            results = list(results.values())
        elif issubclass(collection_or_item_type, Set):
            results = set(results.values())
        elif issubclass(item_type, Tuple):
            raise TypeError('Tuple attributes are not supported yet')

        return results


    def parse_single_item(self, item_file_prefix: str, item_type: Type[Any], item_name_for_log: str = None,
                   flat_mode: bool = False, sep_for_flat: str = '.', lazy_parsing: bool = False,
                   indent_str_for_log: str = None) -> Any:
        """

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param flat_mode:
        :param sep_for_flat:
        :param indent_str_for_log:
        :return:
        """

        # 0. check all inputs and perform defaults
        check_var(item_file_prefix, var_types=str, var_name='item_path')
        check_var(item_type, var_types=type, var_name='item_type')
        item_name_for_log = item_name_for_log or '<item>'
        check_var(item_name_for_log, var_types=str, var_name='item_name')
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')
        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
        indent_str_for_log = indent_str_for_log or ''
        check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

        # 1. Check if the item has a collection type. If so, redirects on the collection method.
        item_type_base = self._extract_base_item_type_if_collection_or_none_if_single(item_type, item_name_for_log)
        if item_type_base is not None:
            raise TypeError('Item ' + item_name_for_log + ' is a Collection-like item cannot be parsed with '
                            'parse_single_item(). Found type ' + str(item_type))

        #RootParser.logger.info(indent_str_for_log + 'Parsing ' + str(item_name_for_log) + ' of type ' + str(item_type)
        #                       + ' at ' + item_file_prefix)
        if not flat_mode:
            # ****** FOLDER MODE *******
            if isdir(item_file_prefix):
                # attribute is a folder and not a collection : parse with constructor inference
                parsed_obj = self._parse_item_with_constructor_inference(
                    item_file_prefix,
                    item_type,
                    item_name_for_log=item_name_for_log,
                    flat_mode=flat_mode,
                    sep_for_flat=sep_for_flat,
                    indent_str_for_log=indent_str_for_log)
            else:
                # attribute MUST be a file, parse it with a registered parser
                parsed_obj = self._parse_item_with_registered_parsers(
                    item_file_prefix,
                    item_type,
                    item_name_for_log=item_name_for_log,
                    indent_str_for_log=indent_str_for_log)

        else:
            # ****** FLAT MODE ******
            # try to see if there are any files
            # - with that exact name and just one extension afterwards (only one dot):
            parent_dir = dirname(item_file_prefix)
            base_prefix = basename(item_file_prefix)
            min_sep_count = (1 if sep_for_flat == RootParser.EXT_SEPARATOR else 0)
            possible_attribute_files = [attribute_file for attribute_file in listdir(parent_dir) if
                                        attribute_file.startswith(base_prefix)
                                        and (attribute_file[len(base_prefix):]).count(RootParser.EXT_SEPARATOR) == 1
                                        and (attribute_file[len(base_prefix):]).count(sep_for_flat) == min_sep_count]
            # - with that name and a suffix and an extension (more than one dot)
            possible_attribute_field_files = [attribute_file for attribute_file in listdir(parent_dir) if
                                              attribute_file.startswith(base_prefix)
                                              and (attribute_file[len(base_prefix):]).count(RootParser.EXT_SEPARATOR) >= 1
                                              and (attribute_file[len(base_prefix):]).count(sep_for_flat) > min_sep_count]
            if len(possible_attribute_files) > 0:
                # -- there is at least one exact match: parse it with registered parsers
                parsed_obj = self._parse_item_with_registered_parsers(
                    item_file_prefix,
                    item_type,
                    item_name_for_log=item_name_for_log,
                    indent_str_for_log=indent_str_for_log)

            elif len(possible_attribute_field_files) > 0:
                # -- there is at least one file that looks like a field : parse with constructor inference
                parsed_obj = self._parse_item_with_constructor_inference(
                    item_file_prefix,
                    item_type,
                    item_name_for_log=item_name_for_log,
                    flat_mode=flat_mode,
                    sep_for_flat=sep_for_flat,
                    indent_str_for_log=indent_str_for_log)
            else:
                raise MandatoryFileNotFoundError.create(item_name_for_log, item_file_prefix, list())
        return parsed_obj


    def _parse_item_with_constructor_inference(self, item_path:str, item_type:Type[Any],
                                               item_name_for_log=None, flat_mode: bool = False, sep_for_flat: str = '.',
                                               indent_str_for_log: str = None) -> Any:
        """
        Helper method to read an object of type "item_type" from a file path. The constructor of the provided
        item_type is used to check the names and types of the attributes of the object, as well as if they are
        collections and/or optional.

        * If wrap_items_in_folders = True, the object is a folder containing as files named after its attribute names:
            item1/
            |-attribute1.<ext>
            |-attribute2.<ext>

        * If wrap_items_in_folders = False, the object is a set of files with the same prefix, and with a suffix that
        is the attribute name:
            .
            |-item1<sep>attribute1.<ext>
            |-item1<sep>attribute2.<ext>

        :param item_path: the path of the object to read. if flat_mode is False , this path should be the path of a
        folder. Otherwise it should be an absolute file prefix.
        :param item_type: the type of the object to read.
        :param flat_mode: true for flat mode, false for folder wrapping mode
        :param sep_for_flat: the character sequence used in 'flat' mode
        :return:
        """

        # 0. check all inputs and perform defaults
        check_var(item_path, var_types=str, var_name='item_path')
        check_var(item_type, var_types=type, var_name='item_type')
        if item_name_for_log is None:
            item_name_for_log = ''
        check_var(item_name_for_log, var_types=str, var_name='item_name')
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')
        if indent_str_for_log is None:
            indent_str_for_log = ''
        check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

        # RootParser.logger.info(indent_str_for_log + 'Parsing ' + str(item_name_for_log) + ' of type ' + str(item_type)
        #                        + ' at ' + item_path)


        # 1. First extract the schema from the class constructor
        constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
        if len(constructors) is not 1:
            raise ValueError('Several constructors were found for class ' + str(item_type))
        # extract constructor
        constructor = constructors[0]
        s = signature(constructor)


        # 2. Check that the item is a folder in non-flat mode
        if (not flat_mode) and (not isdir(item_path)):
            raise FolderAndFilesStructureError(
                'Cannot get item in non-flat mode, item path is not a folder : ' + item_path)

        # 3. Then read the various attributes
        parsed_object = {} # results will be put in this object
        for attribute_name, param in s.parameters.items():

            attribute_is_mandatory = param.default is Parameter.empty       # - is it a mandatory attribute ?
            attribute_type = param.annotation                               # - get the object class

            if attribute_name is 'self':
                pass # nothing to do, this is not an attribute
            else:
                attribute_file_prefix = self._get_attribute_item_file_prefix(item_path, attribute_name,
                                                                             flat_mode=flat_mode,
                                                                             sep_for_flat=sep_for_flat)
                att_item_name_for_log = item_name_for_log + '.' + attribute_name
                try:
                    parsed_object[attribute_name] = self.parse_item(attribute_file_prefix, attribute_type,
                                                                    item_name_for_log=att_item_name_for_log,
                                                                    flat_mode=flat_mode, sep_for_flat=sep_for_flat,
                                                                    indent_str_for_log=indent_str_for_log + '--')
                except MandatoryFileNotFoundError as e:
                    if attribute_is_mandatory:
                        # raise only if mandatory
                        raise e

                # # two main cases :
                # # (a) the item is a collection type
                # # (b) the item is a 'non-collection' type
                # #
                # if issubclass(attribute_type, Dict) or issubclass(attribute_type, List) \
                #            or issubclass(attribute_type, Set) or issubclass(attribute_type, Tuple)\
                #            or issubclass(attribute_type, dict) or issubclass(attribute_type, list) \
                #            or issubclass(attribute_type, tuple) or issubclass(attribute_type, set):
                #     # (a) the item is a collection type
                #     parsed_object[attribute_name] = self.parse_collection(attribute_file_prefix, attribute_type,
                #                                                           item_name_for_log=att_item_name_for_log,
                #                                                           flat_mode=flat_mode,
                #                                                           sep_for_flat=sep_for_flat,
                #                                                           lazy_parsing=False,
                #                                                           indent_str_for_log=indent_str_for_log + '--')
                #
                # else:
                #     # (b) the item is a 'non-collection' type
                #     try:
                #         parsed_object[attribute_name] = self.parse_item(attribute_file_prefix, attribute_type,
                #                                                         item_name_for_log=att_item_name_for_log,
                #                                                         flat_mode=flat_mode, sep_for_flat=sep_for_flat,
                #                                                         indent_str_for_log=indent_str_for_log + '--')
                #     except MandatoryFileNotFoundError as e:
                #         if attribute_is_mandatory:
                #             # raise only if mandatory
                #             raise e

        # 3. finally create the object and return it
        item = item_type(**parsed_object)

        return item


    def _list_collection_item_file_prefixes(self, parent_item_prefix: str,
                                            flat_mode: bool = False, sep_for_flat: str = '.') -> Dict[str, str]:
        """
        Utility method to list all sub-items of a given parent item.
        * If flat_mode = False, root_path should be a valid folder, and each item is a subfolder.
        * If flat_mode = True, root_path may be a folder or an absolute file prefix, and each item is a set of files
        with the same prefix separated from the attribute name by the character sequence <sep_for_flat>

        :param parent_item_prefix: the absolute file prefix of the parent item. it may be a folder (non-flat mode)
        or a folder + a file name prefix (flat mode)
        :param flat_mode: a boolean indicating if items should be represented by folders or a file name
         prefix
        :param sep_for_flat: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode
        :return: a dictionary of <item_name>, <item_path>
        """
        if not flat_mode:
            # assert that folder_path is a folder
            if not isdir(parent_item_prefix):
                # try to check if this is a missing item or a structure problem
                files_with_that_prefix = [f for f in listdir(dirname(parent_item_prefix)) if f.startswith(basename(parent_item_prefix))]
                if len(files_with_that_prefix) > 0:
                    raise FolderAndFilesStructureError('Cannot list items, parent item path is not a '
                                                   'folder : ' + parent_item_prefix + '. Either change the data type '
                                                   'to a non-iterable one, or create a folder to contain the various '
                                                   'items in the iteration. Alternatively you may wish to use the flat '
                                                   'mode to make all files stay in the same root folder')
                else:
                    raise MandatoryFileNotFoundError.create('', parent_item_prefix, list())


            # List folders
            onlyfolders = [f for f in listdir(parent_item_prefix) if isdir(join(parent_item_prefix, f))]
            item_paths = {item: join(parent_item_prefix, item) for item in onlyfolders}
            # Add files without their extension(collections of simple types are files
            item_paths.update({f[0:f.rindex(RootParser.EXT_SEPARATOR)]: join(parent_item_prefix, f[0:f.rindex(RootParser.EXT_SEPARATOR)])
                          for f in listdir(parent_item_prefix) if isfile(join(parent_item_prefix, f)) and RootParser.EXT_SEPARATOR in f})
        else:
            # List files
            if isdir(parent_item_prefix): # this is for special case of root folder
                parent_dir = parent_item_prefix
                base_name = ''
            else:
                parent_dir = dirname(parent_item_prefix)
                base_name = basename(parent_item_prefix) + sep_for_flat

            # list all files that are under the parent_item
            all_file_suffixes_under_parent = [f[len(base_name):] for f in listdir(parent_dir)
                                      if isfile(join(parent_dir, f)) and f.startswith(base_name)]

            # find the set of file prefixes that exist under this parent item
            prefixes = {file_name_suffix[0:file_name_suffix.index(sep_for_flat)]: file_name_suffix
                        for file_name_suffix in all_file_suffixes_under_parent if (sep_for_flat in file_name_suffix)}
            prefixes.update({file_name_suffix[0:file_name_suffix.rindex(RootParser.EXT_SEPARATOR)]: file_name_suffix
                        for file_name_suffix in all_file_suffixes_under_parent if (sep_for_flat not in file_name_suffix)})
            item_paths = {}
            for prefix, file_name_suffix in prefixes.items():
                if len(prefix) == 0:
                    raise ValueError('Error while trying to read item ' + parent_item_prefix + ' as a collection: a '
                                     'file already exist with this name and an extension : ' + base_name +
                                     sep_for_flat + file_name_suffix)
                if prefix not in item_paths.keys():
                    if isdir(parent_item_prefix):
                        item_paths[prefix] = join(parent_item_prefix, prefix)
                    else:
                        item_paths[prefix] = parent_item_prefix + sep_for_flat + prefix

        return item_paths


    def _get_attribute_item_file_prefix(self, parent_path: str, item_name: str, flat_mode: bool=False,
                                        sep_for_flat: str = '.'):
        """
        Utility method to get the file prefix of an item that is an attribute of a parent item.
        * If flat_mode = False, the sub item is a folder in the parent folder
        * if flat_mode = True, the sub item is a file with the same prefix, separated from the attribute name by
        the character sequence <sep_for_flat>

        :param parent_path:
        :param item_name:
        :param flat_mode:
        :param sep_for_flat:
        :return:
        """
        check_var(parent_path, var_types=str, var_name='parent_path')
        check_var(item_name, var_types=str, var_name='item_name')
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')

        if not flat_mode:
            # assert that folder_path is a folder
            if not isdir(parent_path):
                raise ValueError('Cannot get attribute item in non-flat mode, parent item path is not a folder : ' + parent_path)
            return join(parent_path, item_name)

        else:
            return parent_path + sep_for_flat + item_name


    # def get_item_file_prefix(self, parent_item_path: str, attribute_name: str, flat_mode: bool = True,
    #                          sep_for_flat: str = '.'):
    #     """
    #     Returns the file path prefix associated with the given attribute
    #
    #     :param parent_item_path:
    #     :param attribute_name:
    #     :param flat_mode:
    #     :param sep_for_flat:
    #     :return:
    #     """
    #     check_var(parent_item_path, var_types=str, var_name='parent_item_path')
    #     check_var(attribute_name, var_types=str, var_name='attribute_name')
    #     check_var(flat_mode, var_types=bool, var_name='flat_mode')
    #     check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')
    #
    #     if flat_mode:
    #         # the object is a set of files with the same prefix
    #         attribute_file_without_ext = parent_item_path + sep_for_flat + attribute_name
    #     else:
    #         # the object is a folder containing attribute files
    #         if isdir(parent_item_path):
    #             attribute_file_without_ext = join(parent_item_path, attribute_name)
    #         else:
    #             raise ValueError(
    #                 'In non-flat mode, each item is represented by a folder. Could not find '
    #                 'folder for item : ' + parent_item_path)
    #
    #     return attribute_file_without_ext


    def _parse_item_with_registered_parsers(self, item_file_prefix: str, item_type: Type[Any],
                                            item_name_for_log:str = None, indent_str_for_log: str = None):
        """
        Utility to parse an attribute that has a non-collection type

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param indent_str_for_log:
        :return:
        """

        check_var(item_file_prefix, var_types=str, var_name='item_file_prefix')
        check_var(item_type, var_types=type, var_name='item_type')
        if item_name_for_log is None:
            item_name_for_log = ''
        else:
            check_var(item_name_for_log, var_types=str, var_name='item_name')
        check_var(indent_str_for_log, var_types=str, var_name='indent_str_for_log')

        if isdir(item_file_prefix):
            raise FolderAndFilesStructureError('Error parsing item ' + item_name_for_log + ' with registered parsers. '
                                               'Item file prefix ' + item_file_prefix + ' is a folder !')

        # 1. retrieve the parsers
        try:
            attribute_parsers = self.get_parsers_for_type(item_type)
        except UnsupportedObjectTypeError as e:
            raise UnsupportedObjectTypeError.create_with_details(item_name_for_log, item_file_prefix, item_type)

        # list all possible file names that could exist, according to supported extensions
        possible_files = {item_file_prefix + ext: ext for ext in attribute_parsers.keys()}

        # find all the ones that actually exist on the file system
        found_files = {file_path: ext for file_path, ext in possible_files.items() if
                       isfile(file_path)}
        if len(found_files) is 1:
            # parse this file and add to the result
            file_path, file_ext = list(found_files.items())[0]
            parsing_function = attribute_parsers[file_ext]
            RootParser.logger.info(indent_str_for_log + 'Parsing ' + item_name_for_log + ' of type ' + str(item_type) +
                                   ' at ' + file_path + ' with parsing function ' + str(parsing_function))
            return RootParser._read_with_parser_function(file_path, parsing_function)

        elif len(found_files) is 0:
            # item is mandatory and no compliant file was found : error
            raise MandatoryFileNotFoundError.create(item_name_for_log, item_file_prefix, list(attribute_parsers.keys()))

        else:
            # the file is present several times with various extensions
            raise MultipleFilesError.create(item_name_for_log, item_file_prefix, list(found_files.values()))





    # @staticmethod
    # def find_supported_file(file_path_prefix:str, object_type:Type[Any]) -> Tuple[str, str]:
    #     """
    #     Helper method to find files with a file path prefix and any of the supported extensions in order of preference.
    #
    #     :param file_path_prefix:
    #     :param object_type:
    #     :return: the file path of the first found compliant extension, and the extension itself
    #     """
    #     check_var(file_path_prefix, var_types=str, var_name='file_path')
    #
    #     # we have to add the functions type because types created by typing.NewType are functions... :(
    #     check_var(object_type, var_types=[type, FunctionType], var_name='object_type')
    #
    #     if object_type in ReadingHelpers.READERS.keys():
    #         supported_extensions = ReadingHelpers.READERS[object_type].keys()
    #     else:
    #         raise UnsupportedObjectTypeError.create(object_type)
    #
    #     for extension in supported_extensions:
    #         if os.path.isfile(file_path_prefix + '.csv'):
    #             file_extension = '.csv'
    #             return file_path_prefix + file_extension, file_extension
    #
    #     raise ValueError('Could not find a file with prefix ' + file_path_prefix + ' with any of the supported extensions : ' + str(
    #         supported_extensions))


    @staticmethod
    def _read_with_parser_function(file_path:str, parser_function:Callable[[TextIOBase], Any], *args, **kwargs) -> Any:
        """
        A function to execute any reading function on a file path while handling the close() properly.

        :param file_path:
        :param parser_function:
        :param args:
        :param kwargs:
        :return:
        """
        global f
        check_var(file_path, var_types=str, var_name='file_path')
        check_var(parser_function, var_types=Callable, var_name='parser_function')

        try:
            f = open(file_path, 'r')
            res = parser_function(f, *args, **kwargs)

            return res
        finally:
            f.close()

