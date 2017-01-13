import logging
from configparser import DEFAULTSECT
from inspect import getmembers, signature, Parameter
from io import TextIOBase
from typing import Tuple, Any, Dict, Callable, Type, List, Set, Union
from warnings import warn

from sficopaf.dict_parsers import get_default_dict_parsers, get_default_dict_of_dicts_parsers, \
    get_default_collection_parsers
from sficopaf.parsing_chains import _ParsingChainsManager, T, log_parsing_info, MULTIFILE_EXT, \
    parse_object_with_parsing_chains, parse_singlefile_object_with_parsers, _check_common_vars_core, \
    find_unique_singlefile_or_multifile_object, ObjectCannotBeParsedError
from sficopaf.parsing_filemapping import FileMappingConfiguration, ObjectNotFoundOnFileSystemError, \
    WrappedFileMappingConfiguration
from sficopaf.parsing_types import get_pretty_type_str, _extract_collection_base_type, is_collection, \
    TypeInformationRequiredError
from sficopaf.var_checker import check_var


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


def parse_collection(item_file_prefix: str, base_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                         indent_str_for_log: str = None) -> Dict[str, T]:
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
    return rp.parse_collection(item_file_prefix, base_item_type, item_name_for_log, file_mapping_conf,
                                       lazy_parsing, indent_str_for_log)


class RootParser(_ParsingChainsManager):
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
        super(RootParser, self).__init__(initial_parsers=initial_parsers, register_dict_parsers=register_dict_parsers)

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
        # lazy parsing
        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')

        # finally return the modified vars
        return file_mapping_conf, indent_str_for_log, item_name_for_log

    def parse_collection(self, item_file_prefix: str, base_item_type: Type[T],
                         item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                         indent_str_for_log: str = None) -> Dict[str, T]:
        """
        Main method to parse a collection of items of type 'base_item_type'.

        :param item_file_prefix:
        :param base_item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :param indent_str_for_log:
        :return:
        """
        collection_type = Dict[str, base_item_type]

        item_name_for_log = item_name_for_log or '<collection>'
        RootParser.logger.info('**** Starting to parse collection of objects \'' + item_name_for_log + '\' of base type'
                               ' <' + get_pretty_type_str(base_item_type) + '> ****')

        return self._parse_multifile_collection_object(item_file_prefix, collection_type=collection_type,
                                                       item_name_for_log=item_name_for_log, file_mapping_conf=file_mapping_conf,
                                                       lazy_parsing=lazy_parsing, indent_str_for_log=indent_str_for_log)

    def parse_item(self, item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                    file_mapping_conf: FileMappingConfiguration = None,
                    lazy_parsing: bool = False, indent_str_for_log: str = None) -> T:

        item_name_for_log = item_name_for_log or '<item>'
        RootParser.logger.info('**** Starting to parse object \'' + item_name_for_log + '\' of type'
                               ' <' + get_pretty_type_str(item_type) + '> ****')

        return self._parse_item(item_file_prefix, item_type=item_type,
                                item_name_for_log=item_name_for_log, file_mapping_conf=file_mapping_conf,
                                lazy_parsing=lazy_parsing, indent_str_for_log=indent_str_for_log)

    def _parse_item(self, item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                    file_mapping_conf: FileMappingConfiguration = None,
                    lazy_parsing: bool = False, indent_str_for_log: str = None) -> T:
        """
        Inner method to parse an item at the given parent path. Note that the type of this item may be a collection,
        this method will silently redirect to parse_collection.

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
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(item_file_prefix,
                                                                                                 item_type,
                                                                                                 file_mapping_conf,
                                                                                                 item_name_for_log,
                                                                                                 indent_str_for_log,
                                                                                                 lazy_parsing)

        RootParser.logger.info(indent_str_for_log + 'Handling object \'' + item_name_for_log + '\' of type <' +
                               get_pretty_type_str(item_type) + '> at path ' + item_file_prefix)

        # 1. Try to find and use registered parsing chains
        parsing_chains = self.get_all_known_parsing_chains_for_type(item_type)
        if len(parsing_chains) > 0:
            try:
                return parse_object_with_parsing_chains(
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
                    ' for this type \'' + get_pretty_type_str(item_type) + '\' but no compliant file was found on the file '
                    'system. Fallback on default parsers (singlefile, multifile, collection). For information, the '
                    'found registered parsing chain(s) - that wont be used - are ' + str(parsing_chains))
        else:
            RootParser.logger.info(
                indent_str_for_log + 'There was no explicitly registered parsing chain for this type \'' +
                get_pretty_type_str(item_type)
                + '\'. Fallback on default parsers depending on the object type and the files that are present.')

        # 2. Check if the item has a collection type. If so, redirects on the collection method.
        if is_collection(item_type):
            # parse collection
            default_extensions = list(get_default_collection_parsers().keys()) + [MULTIFILE_EXT]
            is_single_file, extension, contents = find_unique_singlefile_or_multifile_object(
                item_file_prefix,
                item_type,
                file_mapping_conf,
                item_name_for_log,
                default_extensions)
            if is_single_file:
                # parse singlefile object using default dict parsers + constructor call
                RootParser.logger.info(indent_str_for_log + 'Since <' + get_pretty_type_str(item_type) + '> is a '
                                       'singlefile collection, trying to use the default single collection parser')
                raise NotImplementedError('Singlefile collections are not implemented yet')
            else:
                # parse multifile collection object
                RootParser.logger.info(indent_str_for_log + 'Since <' + get_pretty_type_str(item_type) + '> is a '
                                       'multifile collection, trying to use the default multifile collection parser')
                return self._parse_multifile_collection_object(item_file_prefix, item_type,
                                                               item_name_for_log=item_name_for_log,
                                                               file_mapping_conf=file_mapping_conf,
                                                               lazy_parsing=lazy_parsing,
                                                               indent_str_for_log=indent_str_for_log)

        else:
            # Check what kind of object is present on the filesystem with this prefix.
            # This method throws exceptions if no file is found or the object is found multiple times (for example with
            # several file extensions, or as a file AND a folder)
            default_extensions = list(get_default_dict_parsers().keys()) + [MULTIFILE_EXT]
            is_single_file, extension, contents = find_unique_singlefile_or_multifile_object(
                                                                                         item_file_prefix,
                                                                                         item_type,
                                                                                         file_mapping_conf,
                                                                                         item_name_for_log,
                                                                                         default_extensions)
            if is_single_file:
                # parse singlefile object using default dict parsers + constructor call
                RootParser.logger.info(indent_str_for_log + 'A single file was found: ' + contents + '. '
                                       'Trying to use the default singlefile parser.')
                return self._parse_singlefile_object(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                    file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                    indent_str_for_log=indent_str_for_log)
            else:
                # parse multifile object using constructor inference
                RootParser.logger.info(indent_str_for_log + 'A multifile object was found for ' + item_file_prefix +
                                       ' with attributes [' + str(contents.keys()) + ']. Trying to use the default '
                                       'multifile parser.')
                return self._parse_multifile_object(item_file_prefix, item_type, item_name_for_log=item_name_for_log,
                                                   file_mapping_conf=file_mapping_conf, lazy_parsing=lazy_parsing,
                                                   indent_str_for_log=indent_str_for_log)

    def _parse_multifile_collection_object(self, item_file_prefix: str, collection_type: Type[T], item_name_for_log: str = None,
                                           file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                                           indent_str_for_log: str = None) -> Union[T, Dict[str, T], List[T], Set[T], Tuple[T]]:
        """
        Inner method to parse a collection of items of type base_type under the given folder path.

        :param item_file_prefix: the path of the parent item. it may be a folder or an absolute file prefix
        :param collection_type: the type of objects to parse in this collection. It should be a class from the typing
        package (PEP484), either List, Set, or Dict.
        :param item_name_for_log: the optional item name, just for logging information
        :param file_mapping_conf:
        :param lazy_parsing: if True, the method will return without parsing all the contents. Instead, the returned
        dictionary will perform the parsing only the first time an item is required.
        :return: a dictionary of named items and content
        """

        # 0. check inputs/params
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(
            item_file_prefix,
            collection_type,
            file_mapping_conf,
            item_name_for_log,
            indent_str_for_log,
            lazy_parsing)
        item_name_for_main_log = '<collection>' if item_name_for_log in {None, '<item>'} else item_name_for_log

        # 1. Check the collection type and extract the base item type
        if not is_collection(collection_type):
            raise TypeError('Item ' + item_name_for_log + ' has type <' + get_pretty_type_str(collection_type) + '> that '
                            'is not a Collection-like object, so it cannot be parsed with this default collection '
                            'parser')

        # it is a collection. Find the base type of objects in that collection
        item_type, key_type = _extract_collection_base_type(collection_type, item_name_for_main_log)

        # 2. Parse the collection
        log_parsing_info(indent_str=indent_str_for_log, item_name=item_name_for_log, item_type=collection_type,
                         item_file_prefix=item_file_prefix, parser_name='(default collection parser)',
                         is_single_file=False, additional_details='Inner type of objects in the collection is <'
                          + get_pretty_type_str(item_type) + '>')

        extensions_to_match = [MULTIFILE_EXT]

        # TODO remove when it is done before
        is_single_file, ext, item_prefixes = find_unique_singlefile_or_multifile_object(item_file_prefix, item_type,
                                                                                        file_mapping_conf,
                                                                                        item_name_for_log,
                                                                                        extensions_to_match)
        if is_single_file:
            # this will not happen since extensions_to_match is just multifile right now so an error will be thrown
            # TODO add support for singlefile collections
            raise Exception('should not happen')
        else:
            # create a dictionary item > content to store the results
            if lazy_parsing:
                # TODO make a lazy dictionary
                raise ValueError('Lazy parsing is unsupported at the moment')
            else:
                # parse them right now
                results = {}
                # use key-based sorting to lead to reproducible results
                for item, item_path in sorted(item_prefixes.items()):
                    results[item] = self._parse_item(item_path, item_type,
                                                     item_name_for_log=(item_name_for_log or '') + '[' + item + ']',
                                                     file_mapping_conf=file_mapping_conf,
                                                     indent_str_for_log=indent_str_for_log + '--')

        # format output if needed
        if issubclass(collection_type, List):
            results = list(results.values())
        elif issubclass(collection_type, Set):
            results = set(results.values())
        elif issubclass(item_type, Tuple):
            raise TypeError('Tuple attributes are not supported yet')

        return results

    def _parse_singlefile_object(self, item_file_prefix: str, item_type: Type[T], item_name_for_log=None,
                                file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                                indent_str_for_log: str = None, item_file_path_for_log: str = None) -> T:
        """
        Inner method to read an object of type "item_type" from a file path, as a simple (single-file) object.

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :param indent_str_for_log:
        :return:
        """
        item_file_path_for_log = item_file_path_for_log or item_file_prefix
        log_parsing_info(indent_str=indent_str_for_log, item_name=item_name_for_log, item_type=item_type,
                         item_file_prefix=item_file_path_for_log, parser_name='(default singlefile parser)',
                         is_single_file=True, additional_details='This means *first* trying to parse it '
                         'as a dictionary, and *then* calling its class constructor with the parsed dictionary.')

        dict_item_name_for_log = item_name_for_log + '(constructor kwargs)'
        try:
            # 1. Try to find a configuration file that can be read as a "dictionary of dictionaries"
            parsers = get_default_dict_of_dicts_parsers()
            parsed_dict = parse_singlefile_object_with_parsers(item_file_prefix, dict,
                                                               file_mapping_conf,
                                                               parsers=parsers,
                                                               item_name_for_log=dict_item_name_for_log,
                                                               indent_str_for_log=indent_str_for_log)

            # 2. Then create an object by creating a simple object for each of its constructor attributes
            return convert_dict_of_dicts_to_singlefile_object(parsed_dict, object_type=item_type)

        except (ObjectCannotBeParsedError, ObjectNotFoundOnFileSystemError, InvalidAttributeNameForConstructorError,
                TypeInformationRequiredError, TypeError) as e:
            # All these errors may happen:
            # * ObjectNotFoundOnFileSystemError if the object is present but in other extension
            # * TypeError, InvalidAttributeNameForConstructorError and TypeInformationRequiredError if the file is a
            # configuration file but it should be used in 'dict' mode, not 'dict of dicts'

            # in all these cases, the other simple 'dict' parsers may be the desired behaviour, so let it go
            pass

        # 2. switch to the 'normal' dictionary parsers
        parsers = get_default_dict_parsers()
        parsed_dict = parse_singlefile_object_with_parsers(item_file_prefix, dict,
                                                           file_mapping_conf,
                                                           parsers=parsers,
                                                           item_name_for_log=dict_item_name_for_log,
                                                           indent_str_for_log=indent_str_for_log)
        return convert_dict_to_singlefile_object(parsed_dict, object_type=item_type)

    def _parse_multifile_object(self, item_file_prefix:str, item_type:Type[T], item_name_for_log=None,
                                file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False,
                                indent_str_for_log: str = None) -> T:
        """
        Inner method to read an object of type "item_type" from a file prefix, as a complex (multi-file) object.
        The constructor of the provided item_type is used to check the names and types of the attributes of the object,
        as well as if they are collections and/or optional.

        :param item_file_prefix: the path of the object to read. if flat_mode is False , this path should be the path of a
        folder. Otherwise it should be an absolute file prefix.
        :param item_type: the type of the object to read.
        :param file_mapping_conf:
        :return:
        """

        # 0. check all inputs and perform defaults
        file_mapping_conf, indent_str_for_log, item_name_for_log = RootParser._check_common_vars(item_file_prefix,
                                                                                                 item_type,
                                                                                                 file_mapping_conf,
                                                                                                 item_name_for_log,
                                                                                                 indent_str_for_log,
                                                                                                 lazy_parsing)

        # 1. Check if the item has a collection type. If so, raise an error.
        if is_collection(item_type):
            raise TypeError('Item ' + item_name_for_log + ' is a Collection-like object cannot be parsed with '
                            '_parse_multifile_object(). Found type ' + get_pretty_type_str(item_type))

        # 2. Parse according to the mode.
        log_parsing_info(indent_str=indent_str_for_log, item_name=item_name_for_log, item_type=item_type,
                         item_file_prefix=item_file_prefix, parser_name='(default multifile parser)',
                         is_single_file=False, additional_details='This means trying to parse each attribute of its '
                          'class constructor as a separate file.')

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
                    parsed_object[attribute_name] = self._parse_item(attribute_file_prefix, attribute_type,
                                                                     item_name_for_log=att_item_name_for_log,
                                                                     file_mapping_conf=file_mapping_conf,
                                                                     indent_str_for_log=indent_str_for_log + '--')
                except ObjectNotFoundOnFileSystemError as e:
                    if attribute_is_mandatory:
                        # raise the error only if the attribute was mandatory
                        raise e

        # -- (d) finally create the object and return it
        return item_type(**parsed_object)


def _get_constructor_signature(item_type):
    """
    Utility method to extract a class constructor signature

    :param item_type:
    :return:
    """
    constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
    if len(constructors) is not 1:
        raise ValueError('Several constructors were found for class <' + get_pretty_type_str(item_type) + '>')
    # extract constructor
    constructor = constructors[0]
    s = signature(constructor)
    return s


class InvalidAttributeNameForConstructorError(Exception):
    """
    Raised whenever an attribute of a multifile object has a name that is not compliant with that object's constructor
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(InvalidAttributeNameForConstructorError, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any], constructor_atts: List[str], invalid_property_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return InvalidAttributeNameForConstructorError('Cannot parse object of type <' + get_pretty_type_str(item_type) + '> using the provided '
                                         'configuration file: configuration contains a property name (\''
                                                       + invalid_property_name + '\') that is not an attribute of the object '
                                         'constructor. <' + get_pretty_type_str(item_type) + '> constructor attributes are : '
                                                       + str(constructor_atts))


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
                raise InvalidAttributeNameForConstructorError.create(object_type, list(s.parameters.keys()), attr_name)

        # create the object using its constructor
        return object_type(**dict_for_init)

    except TypeError as e:
        warn('Error while trying to instantiate object of type <' + get_pretty_type_str(object_type) + '> using dictionary input_dict :')
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
                    raise TypeInformationRequiredError.create_for_object_attributes(object_type, attr_name)
                dict_for_init[attr_name] = convert_dict_to_singlefile_object(parsed_attr_dict, attribute_type)
            else:
                if attr_name != DEFAULTSECT:
                    # the dictionary entry does not correspond to a valid attribute of the object
                    raise InvalidAttributeNameForConstructorError.create(object_type, list(s.parameters.keys()),
                                                                         attr_name)

        # create the object using its constructor
        return object_type(**dict_for_init)

    except TypeError as e:
        warn('Error while trying to instantiate object of type <' + get_pretty_type_str(object_type) + '> using '
             'dictionary input_dict :')
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
        warn('Constructor for type <' + get_pretty_type_str(object_type) + '> has no PEP484 Type hint, trying to use '
             'the parsed value in the dict directly')
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