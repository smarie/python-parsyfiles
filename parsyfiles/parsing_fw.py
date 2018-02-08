import traceback
from io import StringIO
from logging import getLogger, Logger
from typing import Type, Dict, Any, Set, Tuple, List
from warnings import warn

from copy import deepcopy

from parsyfiles.log_utils import default_logger
from parsyfiles.converting_core import JOKER
from parsyfiles.filesystem_mapping import FileMappingConfiguration, WrappedFileMappingConfiguration
from parsyfiles.parsing_core_api import T, Parser
from parsyfiles.parsing_registries import ParserRegistryWithConverters
from parsyfiles.plugins_base.support_for_collections import MultifileCollectionParser
from parsyfiles.plugins_base.support_for_objects import MultifileObjectParser
from parsyfiles.type_inspection_tools import get_pretty_type_str
from parsyfiles.var_checker import check_var

from pprint import pprint


def pprint_out(dct: Dict):
    """
    Utility methods to pretty-print a dictionary that is typically outputted by parsyfiles (an ordered dict)
    :param dct:
    :return:
    """
    for name, val in dct.items():
        print(name + ':')
        pprint(val, indent=4)


def warn_import_error(type_of_obj_support: str, caught: ImportError):
    """
    Utility method to print a warning message about failed import of some modules

    :param type_of_obj_support:
    :param caught:
    :return:
    """
    msg = StringIO()
    msg.writelines('Import Error while trying to add support for ' + type_of_obj_support + '. You may continue but '
                   'the associated parsers and converters wont be available : \n')
    traceback.print_tb(caught.__traceback__, file=msg)
    msg.writelines(str(caught.__class__.__name__) + ' : ' + str(caught) + '\n')
    warn(msg.getvalue())


def create_parser_options(lazy_mfcollection_parsing: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Utility method to create a default options structure with the lazy parsing inside

    :param lazy_mfcollection_parsing:
    :return: the options structure filled with lazyparsing option (for the MultifileCollectionParser)
    """
    return {MultifileCollectionParser.__name__: {'lazy_parsing': lazy_mfcollection_parsing}}


def add_parser_options(options: Dict[str, Dict[str, Any]], parser_id: str, parser_options: Dict[str, Dict[str, Any]],
                       overwrite: bool = False):
    """
    Utility method to add options for a given parser, to the provided options structure
    :param options:
    :param parser_id:
    :param parser_options:
    :param overwrite: True to silently overwrite. Otherwise an error will be thrown
    :return:
    """
    if parser_id in options.keys() and not overwrite:
        raise ValueError('There are already options in this dictionary for parser id ' + parser_id)
    options[parser_id] = parser_options
    return options


def register_default_plugins(root_parser: ParserRegistryWithConverters):
    """
    Utility method to register all default plugins on the given parser+converter registry

    :param root_parser:
    :return:
    """
    # -------------------- CORE ---------------------------
    try:
        # -- primitive types
        from parsyfiles.plugins_base.support_for_primitive_types import get_default_primitive_parsers, \
            get_default_primitive_converters
        root_parser.register_parsers(get_default_primitive_parsers())
        root_parser.register_converters(get_default_primitive_converters())
    except ImportError as e:
        warn_import_error('primitive types', e)
    try:
        # -- collections
        from parsyfiles.plugins_base.support_for_collections import get_default_collection_parsers, \
            get_default_collection_converters
        root_parser.register_parsers(get_default_collection_parsers(root_parser, root_parser))
        root_parser.register_converters(get_default_collection_converters(root_parser))
    except ImportError as e:
        warn_import_error('dict', e)
    try:
        # -- objects
        from parsyfiles.plugins_base.support_for_objects import get_default_object_parsers, \
            get_default_object_converters
        root_parser.register_parsers(get_default_object_parsers(root_parser, root_parser))
        root_parser.register_converters(get_default_object_converters(root_parser))
    except ImportError as e:
        warn_import_error('objects', e)
    try:
        # -- config
        from parsyfiles.plugins_base.support_for_configparser import get_default_config_parsers, \
            get_default_config_converters
        root_parser.register_parsers(get_default_config_parsers())
        root_parser.register_converters(get_default_config_converters(root_parser))
    except ImportError as e:
        warn_import_error('config', e)

    # ------------------------- OPTIONAL -----------------
    try:
        # -- jprops
        from parsyfiles.plugins_optional.support_for_jprops import get_default_jprops_parsers
        root_parser.register_parsers(get_default_jprops_parsers(root_parser, root_parser))
        # root_parser.register_converters()
    except ImportError as e:
        warn_import_error('jprops', e)
    try:
        # -- yaml
        from parsyfiles.plugins_optional.support_for_yaml import get_default_yaml_parsers
        root_parser.register_parsers(get_default_yaml_parsers(root_parser, root_parser))
        # root_parser.register_converters()
    except ImportError as e:
        warn_import_error('yaml', e)
    try:
        # -- numpy
        from parsyfiles.plugins_optional.support_for_numpy import get_default_np_parsers, get_default_np_converters
        root_parser.register_parsers(get_default_np_parsers())
        root_parser.register_converters(get_default_np_converters())
    except ImportError as e:
        warn_import_error('numpy', e)
    try:
        # -- pandas
        from parsyfiles.plugins_optional.support_for_pandas import get_default_pandas_parsers, \
            get_default_pandas_converters
        root_parser.register_parsers(get_default_pandas_parsers())
        root_parser.register_converters(get_default_pandas_converters())
    except ImportError as e:
        warn_import_error('pandas', e)


class RootParser(ParserRegistryWithConverters):
    """
    The root parser
    """

    # When register_default_parsers is True, return a copy of the DefaultRootParser singleton
    def __new__(cls, pretty_name: str = None, *, strict_matching: bool = False,
                register_default_parsers: bool = True, logger: Logger = default_logger):
        if cls is RootParser and register_default_parsers:
            # return a copy of the DefaultRootParser singleton with the new logger (urgh! not multithread safe!)
            c = DefaultRootParser.get_singleton_copy()
            c.logger = logger
            return c
        else:
            # new instance creation, as usual
            return super(RootParser, cls).__new__(cls)

    def __copy__(self):
        # be sure not to use DefaultRootParser new()
        newone = type(self)(register_default_parsers=self.default_parsers_installed)
        newone.__dict__.update(self.__dict__)
        return newone

    def __getstate__(self):
        """ Used for pickle and deepcopy: we have to replace the logger by something that CAN be pickled """
        d = self.__dict__.copy()
        if 'logger' in d.keys():
            d['logger'] = d['logger'].name
        return d

    def __setstate__(self, d):
        """ Used for pickle and deepcopy: put back the logger based on its name """
        if 'logger' in d.keys():
            d['logger'] = getLogger(d['logger'])
        self.__dict__.update(d)

    def __init__(self, pretty_name: str = None, *, strict_matching: bool = False,
                 register_default_parsers: bool = True, logger: Logger = default_logger):
        """
        Constructor. Initializes the dictionary of parsers with the optionally provided initial_parsers, and
        inits the lock that will be used for access in multithreading context.

        :param pretty_name:
        :param strict_matching:
        :param register_default_parsers:
        :param logger:
        """
        if not register_default_parsers:
            # otherwise this has already been done in __new__
            super(RootParser, self).__init__(pretty_name or 'parsyfiles defaults', strict_matching)

        # remember if the user registers the default parsers - for future calls to install_basic_multifile_support()
        self.multifile_installed = register_default_parsers
        self.default_parsers_installed = register_default_parsers

        if register_default_parsers:
            # register_default_plugins(self)
            # we are already a copy of the default instance : dont register anything
            # if this assertion fails, thats a discrepancy between __new__ and __init__ arguments
            assert len(self.get_all_parsers()) > 0

        logger = logger or default_logger
        check_var(logger, var_types=Logger, var_name='logger')
        self.logger = logger

    def install_basic_multifile_support(self):
        """
        Utility method for users who created a RootParser with register_default_plugins=False, in order to register only
         the multifile support
        :return:
        """
        if not self.multifile_installed:
            self.register_parser(MultifileCollectionParser(self))
            self.register_parser(MultifileObjectParser(self, self))
            self.multifile_installed = True
        else:
            raise Exception('Multifile support has already been installed')

    def parse_collection(self, item_file_prefix: str, base_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None,
                         options: Dict[str, Dict[str, Any]] = None) -> Dict[str, T]:
        """
        Main method to parse a collection of items of type 'base_item_type'.

        :param item_file_prefix:
        :param base_item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param options:
        :return:
        """
        # -- item_name_for_log
        item_name_for_log = item_name_for_log or ''
        check_var(item_name_for_log, var_types=str, var_name='item_name_for_log')

        # creating the wrapping dictionary type
        collection_type = Dict[str, base_item_type]
        if len(item_name_for_log) > 0:
            item_name_for_log = item_name_for_log + ' '
        self.logger.debug('**** Starting to parse ' + item_name_for_log + 'collection of <'
                          + get_pretty_type_str(base_item_type) + '> at location ' + item_file_prefix +' ****')

        # common steps
        return self._parse__item(collection_type, item_file_prefix, file_mapping_conf, options=options)

    def parse_item(self, location: str, item_type: Type[T], item_name_for_log: str = None,
                   file_mapping_conf: FileMappingConfiguration = None, options: Dict[str, Dict[str, Any]] = None) -> T:
        """
        Main method to parse an item of type item_type

        :param location:
        :param item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param options:
        :return:
        """

        # -- item_name_for_log
        item_name_for_log = item_name_for_log or ''
        check_var(item_name_for_log, var_types=str, var_name='item_name_for_log')

        if len(item_name_for_log) > 0:
            item_name_for_log = item_name_for_log + ' '
        self.logger.debug('**** Starting to parse single object ' + item_name_for_log + 'of type <'
                          + get_pretty_type_str(item_type) + '> at location ' + location + ' ****')

        # common steps
        return self._parse__item(item_type, location, file_mapping_conf, options=options)

    def _parse__item(self, item_type: Type[T], item_file_prefix: str,
                     file_mapping_conf: FileMappingConfiguration = None,
                     options: Dict[str, Dict[str, Any]] = None) -> T:
        """
        Common parsing steps to parse an item

        :param item_type:
        :param item_file_prefix:
        :param file_mapping_conf:
        :param options:
        :return:
        """

        # for consistency : if options is None, default to the default values of create_parser_options
        options = options or create_parser_options()

        # creating the persisted object (this performs required checks)
        file_mapping_conf = file_mapping_conf or WrappedFileMappingConfiguration()
        obj = file_mapping_conf.create_persisted_object(item_file_prefix, logger=self.logger)
        # print('')
        self.logger.debug('')

        # create the parsing plan
        pp = self.create_parsing_plan(item_type, obj, logger=self.logger)
        # print('')
        self.logger.debug('')

        # parse
        res = pp.execute(logger=self.logger, options=options)
        # print('')
        self.logger.debug('')

        return res


class DefaultRootParser(RootParser):
    """ an attempt to have a singleton instance with default parsers registered """

    _instance = None

    @staticmethod
    def get_singleton_copy():
        """
        Returns a copy of the singleton. This is faster than registering all parsers again
        :return:
        """
        return DefaultRootParser.__new__(DefaultRootParser, this_is_an_explicit_call=True)

    def __new__(cls, this_is_an_explicit_call: bool = False):
        if not this_is_an_explicit_call:
            # this is a copy operation, just create an instance
            return super(DefaultRootParser, cls).__new__(cls)
        else:
            # create if needed
            if DefaultRootParser._instance is None:
                # create the default instance and init it
                inst = super(DefaultRootParser, cls).__new__(cls)
                DefaultRootParser.__init__(inst)
                # save it
                DefaultRootParser._instance = inst

            # create a DEEP copy of the default instance otherwise the parsers/converters that use this object as the
            # 'finder' will get stuck on the previous one !
            return deepcopy(DefaultRootParser._instance)

    def __copy__(self):
        # be sure not to use the default instance here: pass the 'explicit' argument
        newone = type(self)(this_is_an_explicit_call=True)
        newone.__dict__.update(self.__dict__)
        return newone

    def __init__(self, *args, **kwargs):
        if DefaultRootParser._instance is None:
            # this is the first instance creation
            super(DefaultRootParser, self).__init__(register_default_parsers=False)
            register_default_plugins(self)
        else:
            # this object is already a copy of it
            pass


# _default_rp = None


def get_default_parser():
    """ Returns the default parser. """

    # # We used a cached instance in order to avoid paying the instantiation time
    # global _default_rp
    # if _default_rp is None:
    #     _default_rp = RootParser()
    # return _default_rp

    # Now the class itself has a cached default instance
    return RootParser()


def _create_parser_from_default(logger: Logger = default_logger):
    p = get_default_parser()
    p.logger = logger
    return p


def parse_item(location: str, item_type: Type[T], item_name_for_log: str = None,
               file_mapping_conf: FileMappingConfiguration = None,
               logger: Logger = default_logger, lazy_mfcollection_parsing: bool = False) -> T:
    """
    Creates a RootParser() and calls its parse_item() method

    :param location:
    :param item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param logger:
    :param lazy_mfcollection_parsing:
    :return:
    """
    rp = _create_parser_from_default(logger)
    opts = create_parser_options(lazy_mfcollection_parsing=lazy_mfcollection_parsing)
    return rp.parse_item(location, item_type, item_name_for_log=item_name_for_log, file_mapping_conf=file_mapping_conf,
                         options=opts)


def parse_collection(location: str, base_item_type: Type[T], item_name_for_log: str = None,
                     file_mapping_conf: FileMappingConfiguration = None, logger: Logger = default_logger,
                     lazy_mfcollection_parsing: bool = False)\
        -> Dict[str, T]:
    """
    Utility method to create a RootParser() with default configuration and call its parse_collection() method

    :param location:
    :param base_item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param logger:
    :param lazy_mfcollection_parsing:
    :return:
    """
    rp = _create_parser_from_default(logger)
    opts = create_parser_options(lazy_mfcollection_parsing=lazy_mfcollection_parsing)
    return rp.parse_collection(location, base_item_type, item_name_for_log=item_name_for_log,
                               file_mapping_conf=file_mapping_conf, options=opts)


def print_capabilities_by_ext(strict_type_matching: bool = False):
    get_default_parser().print_capabilities_by_ext(strict_type_matching=strict_type_matching)


def print_capabilities_by_type(strict_type_matching: bool = False):
    get_default_parser().print_capabilities_by_type(strict_type_matching=strict_type_matching)


def get_all_supported_types_pretty_str() -> Set[str]:
    return get_default_parser().get_all_supported_types_pretty_str()


def get_capabilities_by_type(strict_type_matching: bool = False) -> Dict[Type, Dict[str, Dict[str, Parser]]]:
    return get_default_parser().get_capabilities_by_type(strict_type_matching=strict_type_matching)


def print_capabilities_for_type(typ, strict_type_matching: bool = False):
    get_default_parser().print_capabilities_for_type(typ, strict_type_matching=strict_type_matching)


def get_capabilities_for_type(typ, strict_type_matching: bool = False) -> Dict[str, Dict[str, Parser]]:
    return get_default_parser().get_capabilities_for_type(typ, strict_type_matching=strict_type_matching)


def get_capabilities_by_ext(strict_type_matching: bool = False) -> Dict[str, Dict[Type, Dict[str, Parser]]]:
    return get_default_parser().get_capabilities_by_ext(strict_type_matching=strict_type_matching)


def print_capabilities_for_ext(ext, strict_type_matching: bool = False):
    get_default_parser().print_capabilities_for_ext(ext, strict_type_matching=strict_type_matching)


def get_capabilities_for_ext(ext, strict_type_matching: bool = False) -> Dict[Type, Dict[str, Parser]]:
    return get_default_parser().get_capabilities_for_ext(ext, strict_type_matching=strict_type_matching)


def get_all_supported_types(strict_type_matching: bool = False) -> Set[Type]:
    return get_default_parser().get_all_supported_types(strict_type_matching=strict_type_matching)


def get_all_supported_exts() -> Set[str]:
    return get_default_parser().get_all_supported_exts()


def find_all_matching_parsers(strict: bool, desired_type: Type[Any] = JOKER, required_ext: str = JOKER) \
        -> Tuple[List[Parser], List[Parser], List[Parser], List[Parser]]:
    return get_default_parser().find_all_matching_parsers(strict, desired_type, required_ext)
