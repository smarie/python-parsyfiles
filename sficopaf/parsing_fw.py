import sys
import traceback
from io import StringIO
from logging import getLogger, StreamHandler

from sficopaf.filesystem_mapping import *
from sficopaf.parsing_core import *
from sficopaf.parsing_registries import ParserRegistryWithConverters
from sficopaf.support_for_collections import MultifileDictParser
from sficopaf.support_for_objects import MultifileObjectParser
from sficopaf.type_inspection_tools import *
from sficopaf.var_checker import check_var

default_logger = getLogger()
ch = StreamHandler(sys.stdout)
default_logger.addHandler(ch)

def parse_item(item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                   file_mapping_conf: FileMappingConfiguration = None,
                   lazy_parsing: bool = False) -> T:
    """
    Creates a RootParser() and calls its parse_item() method
    :param item_file_prefix:
    :param item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param lazy_parsing:
    :return:
    """
    rp = RootParser('parsyfiles defaults')
    return rp.parse_item(item_file_prefix, item_type, item_name_for_log, file_mapping_conf, lazy_parsing)


def parse_collection(item_file_prefix: str, base_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False)\
        -> Dict[str, T]:
    """
    Creates a RootParser() and calls its parse_collection() method
    :param item_file_prefix:
    :param base_item_type:
    :param item_name_for_log:
    :param file_mapping_conf:
    :param lazy_parsing:
    :return:
    """
    rp = RootParser('parsyfiles defaults')
    return rp.parse_collection(item_file_prefix, base_item_type, item_name_for_log, file_mapping_conf, lazy_parsing)


def warnImportError(type_of_obj_support: str, caught: ImportError):
    msg = StringIO()
    msg.writelines('Import Error while trying to add support for ' + type_of_obj_support + '. You may continue but '
                   'the associated parsers and converters wont be available : \n')
    traceback.print_tb(caught.__traceback__, file=msg)
    msg.writelines(str(caught.__class__.__name__) + ' : ' + str(caught) + '\n')
    warn(msg.getvalue())


class RootParser(ParserRegistryWithConverters):
    """
    The root parser
    """

    def __init__(self, pretty_name: str = None, strict_matching: bool = False,
                 register_default_parsers: bool = True, logger: Logger = None):
        """
        Constructor. Initializes the dictionary of parsers with the optionally provided initial_parsers, and
        inits the lock that will be used for access in multithreading context.

        :param pretty_name:
        :param strict_matching:
        :param register_default_parsers:
        :param logger:
        """

        super(RootParser, self).__init__(pretty_name or 'parsyfiles defaults', strict_matching)

        self.multifile_installed = register_default_parsers

        if register_default_parsers:
            try:
                # primitive types
                from sficopaf.support_for_primitive_types import get_default_primitive_parsers, get_default_primitive_converters
                self.register_parsers(get_default_primitive_parsers())
                self.register_converters(get_default_primitive_converters())
            except ImportError as e:
                warnImportError('primitive types', e)

            try:
                # collections
                from sficopaf.support_for_collections import get_default_collection_parsers, get_default_collection_converters
                self.register_parsers(get_default_collection_parsers(self))
                self.register_converters(get_default_collection_converters())
            except ImportError as e:
                warnImportError('dict', e)

            try:
                # objects
                from sficopaf.support_for_objects import get_default_object_parsers, get_default_object_converters
                self.register_parsers(get_default_object_parsers(self, self))
                self.register_converters(get_default_object_converters(self))
            except ImportError as e:
                warnImportError('objects', e)

            try:
                # config
                from sficopaf.support_for_configparser import get_default_config_parsers, get_default_config_converters
                self.register_parsers(get_default_config_parsers())
                self.register_converters(get_default_config_converters())
            except ImportError as e:
                warnImportError('config', e)

            try:
                # dataframe
                from sficopaf.support_for_dataframe import get_default_dataframe_parsers, get_default_dataframe_converters
                self.register_parsers(get_default_dataframe_parsers())
                self.register_converters(get_default_dataframe_converters())
            except ImportError as e:
                warnImportError('DataFrame', e)

        if logger is None:
            # Configure a logger to print logs to std out
            logger = default_logger

        self._logger = logger


    def install_basic_multifile_support(self):
        if not self.multifile_installed:
            self.register_parser(MultifileDictParser(self))
            self.register_parser(MultifileObjectParser(self, self))
            self.multifile_installed = True
        else:
            raise Exception('Multifile support has already been installed')

    # @property
    # def logger(self):
    #     return self._logger
    #
    # @logger.setter
    # def logger(self, logger: Logger):
    #     check_var(logger, var_types=Logger, var_name='logger')
    #     if isinstance(logger, IndentedLogger):
    #         self._logger = logger
    #     else:
    #         self._logger = IndentedLogger(logger)

    def parse_collection(self, item_file_prefix: str, base_item_type: Type[T], item_name_for_log: str = None,
                         file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False) -> Dict[str, T]:
        """
        Main method to parse a collection of items of type 'base_item_type'.

        :param item_file_prefix:
        :param base_item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :return:
        """
        # -- item_name_for_log
        item_name_for_log = item_name_for_log or ''
        check_var(item_name_for_log, var_types=str, var_name='item_name_for_log')

        # creating the wrapping dictionary type
        collection_type = Dict[str, base_item_type]
        self._logger.info('**** Starting to parse ' + item_name_for_log + ' collection of <'
                          + get_pretty_type_str(base_item_type) + '> at location ' + item_file_prefix +' ****')

        # common steps
        return self._parse__item(collection_type, item_file_prefix, file_mapping_conf, lazy_parsing)

    def parse_item(self, item_file_prefix: str, item_type: Type[T], item_name_for_log: str = None,
                   file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False) -> T:
        """
        Main method to parse an item of type item_type

        :param item_file_prefix:
        :param item_type:
        :param item_name_for_log:
        :param file_mapping_conf:
        :param lazy_parsing:
        :return:
        """

        # -- item_name_for_log
        item_name_for_log = item_name_for_log or ''
        check_var(item_name_for_log, var_types=str, var_name='item_name_for_log')

        print('**** Starting to parse single object ' + item_name_for_log + ' of type <'
                          + get_pretty_type_str(item_type) + '> at location ' + item_file_prefix +' ****')

        # common steps
        return self._parse__item(item_type, item_file_prefix, file_mapping_conf, lazy_parsing)

    def _parse__item(self, item_type: Type[T], item_file_prefix: str,
                     file_mapping_conf: FileMappingConfiguration = None, lazy_parsing: bool = False) -> T:
        """
        Common parsing steps to parse an item

        :param item_type:
        :param item_file_prefix:
        :param file_mapping_conf:
        :param lazy_parsing:
        :return:
        """

        # creating the persisted object (this performs required checks)
        file_mapping_conf = file_mapping_conf or WrappedFileMappingConfiguration()
        obj = file_mapping_conf.create_persisted_object(item_file_prefix, logger=self._logger)
        #print('')
        self._logger.info('')

        # create the parsing plan
        pp = self.create_parsing_plan(item_type, obj, logger=self._logger)
        #print('')
        self._logger.info('')

        # parse
        res = pp.execute(logger=self._logger, lazy_parsing=lazy_parsing)
        #print('')
        self._logger.info('')

        return res


#     def _parse_item(self, obj: _RecursiveParsingPlan[T], lazy_parsing: bool = False, logger: Logger = None) -> T:
#         """
#         Inner method to parse an object from the file system. Note that the type of this item may be a collection,
#         this method will silently redirect to parse_collection.
#
#         The parser uses the following algorithm to perform the parsing:
#         * First check if there is at least a registered parsing chain for this object's type. If so, try to parse the
#         object with the parsing chain corresponding to its file extension (including multifile)
#         * If the above did not succeed, use either the collection parser (if the object is a collection)
#         or the object parser (if the object is not a collection)
#
#         :param obj:
#         :param lazy_parsing:
#         :param logger:
#         :return: the created object
#         """
#
#         # 0. check all inputs and apply defaults
#         lazy_parsing, logger = _check_common_vars_core(obj, lazy_parsing=lazy_parsing, logger=logger)
#
#         # 1. Log
#         logger.info('Handling ' + str(obj))
#
#         # 2. Try to find and use registered parsing chains
#         try:
#             return self.parse_object(obj, lazy_parsing=lazy_parsing, logger=logger)
#         except NoParserFoundForObjectType:
#             logger.info('There was no explicitly registered parsing chain for this type \'' + obj.get_pretty_type_str()
#                         + '\'. Falling back on default parsers.')
#         except NoParserFoundForObjectExt as e:
#             logger.info('There is a registered parsing chain for this type \'' + obj.get_pretty_type_str()
#                         + '\' but not for extension ' + obj.get_pretty_file_ext() + ', only for extensions '
#                         + str(e.extensions_supported) + '. Falling back on default parsers.')
#
#         # 3. Redirects on the appropriate parsing method : collection or single object
#         if obj.is_collection:
#             return self._parse_collection_object(obj, lazy_parsing=lazy_parsing, logger=logger)
#         else:
#             return self._parse_object(obj, logger)
#
#     def _parse_collection_object(self, obj: _RecursiveParsingPlan[T], lazy_parsing: bool = False,
#                                  logger: IndentedLogger = None) \
#             -> Union[Dict[str, T], List[T], Set[T], Tuple[T]]:
#         """
#         Inner method to parse an object obj of 'collection' type.
#
#         :param obj: the collection object to parse
#
#         :param logger:
#         :return: the created collection
#         """

#
#         # 2. Parse the collection
#         if obj.is_singlefile:
#             # (A) parse singlefile object using default dict parsers + constructor call
#             log_parsing_info(logger=logger, obj=obj, parser_name='(default collection parser for single files)',
#                              additional_details='Each item in the collection will be parsed independently and the '
#                                                 'result will be merged in a collection afterwards')
#             if obj.ext in list(get_default_collection_parsers().keys()):
#                 # TO DO parse the file as a dict or list
#                 pass
#             else:
#                 # TO DO raise exception unknown extension
#                 pass
#             raise NotImplementedError('Singlefile collections are not implemented yet')
#
#         else:
#             # (B) parse multifile collection object
#             # (A) parse singlefile object using default dict parsers + constructor call
#             log_parsing_info(logger=logger, obj=obj, parser_name='(default collection parser for multi-files)',
#                              additional_details='Each item in the collection will be parsed independently and the '
#                                                 'result will be merged in a collection afterwards')
#             return self.parse_collection_object_multifile(obj, lazy_parsing=lazy_parsing, logger=logger)

#
#
#     def _parse_object(self, obj: _RecursiveParsingPlan[T], logger: IndentedLogger = None) -> T:
#         """
#         Inner method to parse a single (non-collection) object obj
#
#         :param obj: the collection object to parse
#         :param logger:
#         :return: the created collection
#         """
#         # 0. check inputs/params
#         lazy_parsing, logger = _check_common_vars_core(obj, logger=logger)
#
#         # 1. Check that this is not a collection
#         if obj.is_collection:
#             raise TypeError(str(obj) + ' is a collection, so it cannot be parsed with this default object parser')
#
#         # 2. Parse according to the files present on the filesystem
#         if obj.is_singlefile:
#             # parse singlefile object using default dict parsers + constructor call
#             logger.info('A single file was found: ' + str(obj) + '. Trying to use the default singlefile parser.')
#             res = self._parse_singlefile_object(obj, logger=logger)
#
#         else:
#             # parse multifile object using constructor inference + constructor call
#             logger.info('A multifile object was found: ' + str(obj) + '. '
#                         'Trying to use the default multifile parser.')
#             res = self._parse_multifile_object(obj, logger=logger)
#         return res
#
#     def _parse_singlefile_object(self, obj: _RecursiveParsingPlan[T], logger: Logger = None) -> T:
#         """
#         Inner method to read a single-file object
#
#         :param obj: the singlefile object
#         :param lazy_parsing:
#         :param indent_str_for_log:
#         :return:
#         """
#         log_parsing_info(logger=logger, obj=obj, parser_name='(default singlefile parser)',
#                          additional_details='This means *first* trying to parse it as a dictionary, and *then* '
#                                             'calling its class constructor with the parsed dictionary.')
#
#         # We will try to read a dictionary object and THEN invoke the true type's constructor
#         dict_obj = _RecursiveParsingPlan(obj.location, object_type=dict, typed_parsing_chains={},
#                              generic_obj_parsing_chains=self.get_all_generic_obj_parsers(),
#                              generic_coll_parsing_chains=self.get_all_generic_coll_parsers(), logger=logger)
#         try:
#             # 1. Try to find a configuration file that can be read as a "dictionary of dictionaries"
#             parsers = get_default_dict_of_dicts_parsers()
#             parsed_dict = parse_singlefile_object_with_parsers(dict_obj, parsers=parsers, logger=logger)
#
#             # 2. Then create an object by creating a simple object for each of its constructor attributes
#             return create_object_from_parsed_contents(obj, parsed_dict, is_dict_of_dicts=True)
#
#         except (NoParserFoundForObject, ObjectNotFoundOnFileSystemError, InvalidAttributeNameForConstructorError,
#                 TypeInformationRequiredError, TypeError) as e:
#             # All these errors may happen:
#             # * ObjectNotFoundOnFileSystemError if the object is present but in other extension
#             # * TypeError, InvalidAttributeNameForConstructorError and TypeInformationRequiredError if the file is a
#             # configuration file but it should be used in 'dict' mode, not 'dict of dicts'
#
#             # in all these cases, the other simple 'dict' parsers may be the desired behaviour, so let it go
#             pass
#
#         # 2. switch to the 'normal' dictionary parsers
#         parsers = get_default_dict_parsers()
#         parsed_dict = parse_singlefile_object_with_parsers(dict_obj, parsers=parsers, logger=logger)
#
#         return create_object_from_parsed_contents(obj, parsed_dict)
#
#     def _parse_multifile_object(self, obj: _RecursiveParsingPlan[T], logger: Logger = None) -> T:
#         """
#         Inner method to read a multifile object
#         The constructor of the object type is used to check the names and types of the attributes of the object,
#         as well as if they are collections and/or optional. These attributes are first parsed from the children of this
#         multifile object, and finally the constructor is being called
#
#         :param obj: the multifile object to read
#         :param indent_str_for_log:
#         :return:
#         """
#
#         log_parsing_info(logger, obj, parser_name='(default multifile parser)', additional_details='This means trying '
#                          'to parse each attribute of its class constructor as a separate file.')
#
#         # parse the attributes required by the constructor
#         children = {}
#
#         # -- use key-based sorting on children to lead to reproducible results
#         # (in case of multiple errors, the same error will show up first everytime)
#         for item, child_obj in sorted(obj.get_multifile_children().items()):
#             try:
#                 children[item] = self._parse_item(child_obj, logger=logger.indent())
#             except ObjectNotFoundOnFileSystemError as e:
#                 if item in obj.mandatory_attributes:
#                     # raise the error only if the attribute was mandatory
#                     raise e
#         return create_object_from_parsed_contents(obj, children)
#
#
