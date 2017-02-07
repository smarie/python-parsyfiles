from abc import ABCMeta, abstractmethod
from logging import Logger
from operator import methodcaller
from pprint import pprint
from typing import Type, Dict, Any, List, Set, Tuple
from warnings import warn

from parsyfiles.converting_core import S, Converter, ConversionChain
from parsyfiles.filesystem_mapping import PersistedObject
from parsyfiles.parsing_combining_parsers import ParsingChain, CascadingParser, DelegatingParser
from parsyfiles.parsing_core import AnyParser, T, InvalidParserException, _ParsingPlanElement, BaseParser
from parsyfiles.type_inspection_tools import get_pretty_type_str, get_base_generic_type, \
    get_pretty_type_keys_dict
from parsyfiles.var_checker import check_var


class ParserFinder(metaclass=ABCMeta):
    """
    Abstract class representing something able to find a parser for a given object
    """

    @abstractmethod
    def build_parser_for_fileobject_and_desiredtype(self, obj_on_filesystem: PersistedObject, object_type: Type[T],
                                                    logger: Logger = None) -> BaseParser[T]:
        """
        Returns the most appropriate parser to use to parse object obj_on_filesystem as an object of type object_type

        :param obj_on_filesystem: the filesystem object to parse
        :param object_type: the type of object that the parser is expected to produce
        :param logger:
        :return:
        """
        pass


class NoParserFoundForObjectExt(Exception):
    """
    Raised whenever an object can not be parsed - but there is a singlefile present with a given extension
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(NoParserFoundForObjectExt, self).__init__(contents)

    @staticmethod
    def create(obj: PersistedObject, obj_type: Type[T], extensions_supported: List[str]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param obj:
        :param obj_type:
        :param extensions_supported:
        :return:
        """

        # base message
        msg = str(obj) + ' cannot be parsed as a ' + get_pretty_type_str(obj_type) + ' because no parser supporting ' \
              'that extension (' + obj.get_pretty_file_ext() + ') is registered.\n'

        # add details
        if extensions_supported is not None and len(extensions_supported) > 0:
            msg += ' If you wish to parse this object in that type, you may replace the file with any of the ' \
                   'following extensions currently supported :' + str(extensions_supported) + '. \n' \
                   + 'Otherwise, please register a new parser for type ' + get_pretty_type_str(obj_type) \
                   + ' and extension ' + obj.get_pretty_file_ext() + '\n Reminder: use print_capabilities_by_ext()'\
                   + ' and print_capabilities_by_type() to diagnose what are the parsers available'
        else:
            raise ValueError('extensions_supported should be provided to create a NoParserFoundForObjectExt. If no '
                             'extension is supported, use NoParserFoundForObjectType.create instead')

        e = NoParserFoundForObjectExt(msg)

        # save the extensions supported
        e.extensions_supported = extensions_supported

        return e


class NoParserFoundForObjectType(Exception):
    """
    Raised whenever an object can not be parsed because no parser was found for this object type
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(NoParserFoundForObjectType, self).__init__(contents)

    @staticmethod
    def create(obj: PersistedObject, obj_type: Type[T], types_supported: List[str]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param obj:
        :param obj_type:
        :param types_supported:
        :return:
        """

        # base message
        msg = str(obj) + ' cannot be parsed as a ' + get_pretty_type_str(obj_type) + ' because no parser supporting ' \
              'that type is registered for ' + obj.get_pretty_file_ext() + '.\n'

        # add details
        if types_supported is not None and len(types_supported) > 0:
            msg += ' If you wish to parse this object from this extension, you may wish to parse it as one of the ' \
                   'following supported types : ' + str(types_supported) + '. \n' \
                   + 'Otherwise, please register a new parser for type ' + get_pretty_type_str(obj_type) \
                   + ' and extension ' + obj.get_pretty_file_ext() + '\n Reminder: use print_capabilities_by_ext()' \
                   + ' and print_capabilities_by_type() to diagnose what are the parsers available'
        else:
            raise ValueError('extensions_supported should be provided to create a NoParserFoundForObjectExt. If no '
                             'extension is supported, use NoParserFoundForObjectType.create instead')

        e = NoParserFoundForObjectType(msg)

        # save the extensions supported
        e.types_supported = types_supported

        return e


# class MultipleParsersFoundForObjectType(Exception):
#     """
#     Raised whenever several parsers are found that say they can specifically parse a given object type. (= non-generic
#     parsers). In that case there is no criterion to decide.. better throw an exception.
#     """
#     def __init__(self, contents):
#         """
#         We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
#         https://github.com/nose-devs/nose/issues/725
#         That's why we have a helper static method create()
#
#         :param contents:
#         """
#         super(MultipleParsersFoundForObjectType, self).__init__(contents)
#
#     @staticmethod
#     def create(obj_type: Type[T], specific_parsers: List[AnyParser]):
#         """
#         Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
#         https://github.com/nose-devs/nose/issues/725
#
#         :param obj_type:
#         :param specific_parsers:
#         :return:
#         """
#         msg = 'Multiple parsers are explicitly registered for type \'' + get_pretty_type_str(obj_type) + '\'. ' \
#               'Impossible to decide which one to choose. This is probably a mistake in parser registration. Found' \
#               ' parsers : ' + str(specific_parsers)
#
#         return MultipleParsersFoundForObjectType(msg)



# def find_parser_to_use_from_parser_list(obj_on_filesystem: PersistedObject, object_type: Type[T],
#                                         parsers: List[AnyParser],
#                                         logger: Logger = None) -> AnyParser[T]:
#     """
#     Checks in the provided parsers for the one to use to parse obj_on_filesystem as an object of type object_type
#
#     :param obj_on_filesystem:
#     :param object_type:
#     :param parsers:
#     :param logger:
#     :return:
#     """
#     # specific_parsers = []
#     # generic_parsers = []
#     #
#     # # First let's search for parsers able to parse this type of object.
#     # # Make the distinction between specific and generic.
#     # for parser in parsers:
#     #     if parser.supported_types:
#     #         if object_type in parser.supported_types:
#     #             # This means that the parser is dedicated for this type
#     #             specific_parsers.append(parser)
#     #     else:
#     #         # This means that the parser is generic for any type
#     #         generic_parsers.append(parser)
#     #
#     # if (len(specific_parsers) + len(generic_parsers)) == 0:
#     #     # no parser found
#     #     raise NoParserFoundForObjectType.create(object_type)
#     # else:
#     #     # if len(specific_parsers) > 1:
#     #     #     # several specific parsers found
#     #     #     raise MultipleParsersFoundForObjectType.create(object_type, specific_parsers)
#     #     # else:
#     #     # # one specific parser found. Check the file type (single/multi) to decide
#     #     # specific_found = specific_parsers[0]
#     #
#     #     if obj_on_filesystem.is_singlefile and isinstance(specific_found, SingleFileParser):
#     #         if specific_found.supports_file_extension(obj_on_filesystem.ext):
#     #             return specific_found
#     #         else:
#     #             # this is a singlefile parser for that type of object, but it does not support that extension
#     #             pass
#     #     elif (not obj_on_filesystem.is_singlefile) and isinstance(specific_found, MultiFileParser):
#     #         # ok for multifile
#     #         return specific_found
#     #
#     #     # if we're here, either
#     #     # - there is a signelfile parser and object is a singlefile with a different extension
#     #     # - there is a multifile parser and a singlefile found, or vice-versa
#     #     logger.info('There is a registered parsing chain for this type \'' + self.get_pretty_type_str()
#     #                 + '\' but not for extension ' + self.get_pretty_ext() + ', only for extensions '
#     #                 + str(e.extensions_supported) + '. Falling back on generic parsers.')




# # 2. Try to find and use registered parsing chains
    # try:
    #     return self.parse_object(obj, lazy_parsing=lazy_parsing, logger=logger)
    # except NoParserFoundForObjectType:
    #     logger.info(
    #         'There was no explicitly registered parsing chain for this type \'' + obj.get_pretty_type()
    #         + '\'. Falling back on default parsers.')
    # except NoParserFoundForObjectExt as e:
    #     logger.info('There is a registered parsing chain for this type \'' + obj.get_pretty_type()
    #                 + '\' but not for extension ' + obj.get_pretty_ext() + ', only for extensions '
    #                 + str(e.extensions_supported) + '. Falling back on default parsers.')
    #
    # # 3. Redirects on the appropriate parsing method : collection or single object
    # if obj.is_collection:
    #     return self._parse_collection_object(obj, lazy_parsing=lazy_parsing, logger=logger)
    # else:
    #     return self._parse_object(obj, logger)








# def _find_parsing_chain_to_use(obj: PersistedObject, obj_type: Type[T],
#                                parsing_chains_for_exts: Dict[str, TypedParsingChain[T]]) -> TypedParsingChain[T]:
#     """
#     Utility method to find a parsing chain among the ones provided, to parse object obj of type obj_type.
#     The choice is simply based on the object extension if the object is a singlefile. If the object is a multifile,
#     the dictionary is looked for an entry with the special key MULTIFILE_EXT
#
#     :param obj:
#     :param obj_type:
#     :param parsing_chains_for_exts:
#     :return:
#     """
#
#     # checks
#     check_var(obj, var_types=PersistedObject, var_name='obj')
#     check_var(obj_type, var_types=type, var_name='obj_type')
#     check_var(parsing_chains_for_exts, var_types=dict, var_name='parsing_chains', min_len=1)
#
#     # Check what kind of object is present on the filesystem with this prefix, and check if it cab be read with
#     # the parsing chains provided.
#     if obj.is_singlefile and obj.ext in parsing_chains_for_exts.keys():
#         return parsing_chains_for_exts[obj.ext]
#
#     elif MULTIFILE_EXT in parsing_chains_for_exts.keys():
#         return parsing_chains_for_exts[MULTIFILE_EXT]
#
#     else:
#         # there is a singlefile but not with the appropriate extension
#         # or
#         # there is a multifile, but there is no parsing chain for multifile
#         raise NoParserFoundForObjectExt.create(obj, obj_type, parsing_chains_for_exts.keys())

def insert_element_to_dict_of_list(dict_of_list, key, parser):
    """
    Utility method

    :param dict_of_list:
    :param key:
    :param parser:
    :return:
    """
    if key in dict_of_list.keys():
        dict_of_list[key].append(parser)
    else:
        dict_of_list[key] = [parser]


def insert_element_to_dict_of_dicts_of_list(dict_of_dict_of_list, first_key, second_key, parser):
    """
    Utility method

    :param dict_of_dict_of_list:
    :param first_key:
    :param second_key:
    :param parser:
    :return:
    """
    list_to_insert = parser if isinstance(parser, list) else [parser]

    if first_key not in dict_of_dict_of_list.keys():
        dict_of_dict_of_list[first_key] = {second_key: list_to_insert}
    else:
        if second_key not in dict_of_dict_of_list[first_key].keys():
            dict_of_dict_of_list[first_key][second_key] = list_to_insert
        else:
            dict_of_dict_of_list[first_key][second_key] += list_to_insert


def insert_element_to_dict_of_dicts(dict_of_dicts: Dict[str, Dict[str, str]], first_key: str, second_key: str, contents):
    """
    Utility method

    :param dict_of_dicts:
    :param first_key:
    :param second_key:
    :param contents:
    :return:
    """

    if first_key not in dict_of_dicts.keys():
        dict_of_dicts[first_key] = {second_key: contents}
    else:
        if second_key not in dict_of_dicts[first_key].keys():
            dict_of_dicts[first_key][second_key] = contents
        else:
            warn('Overriding contents for ' + first_key + '/' + second_key)
            dict_of_dicts[first_key][second_key] = contents


class AbstractParserCache(metaclass=ABCMeta):
    """
    The abstract methods that a parser cache should implement to be usable in the ParserRegistry, as well as the
    methods that can be automatically built from them
    """
    def register_parsers(self, parsers: List[AnyParser]):
        """
        Utility method to register any list of parsers.
        :return:
        """
        check_var(parsers, var_types=list, var_name='parsers')
        for parser in parsers:
            self.register_parser(parser)

    @abstractmethod
    def register_parser(self, parser: AnyParser[T]):
        pass

    @abstractmethod
    def get_all_parsers(self, strict_type_matching: bool) -> List[AnyParser]:
        pass

    def print_capabilities_by_ext(self, strict_type_matching: bool = False):
        """
        Used to print the list of all file extensions that can be parsed by this parser registry.
        :return:
        """
        l = self.get_capabilities_by_ext(strict_type_matching=strict_type_matching)
        pprint({ext: get_pretty_type_keys_dict(parsers) for ext, parsers in l.items()})

    def print_capabilities_by_type(self, strict_type_matching: bool = False):
        """
        Used to print the list of all file extensions that can be parsed by this parser registry.
        :return:
        """
        l = self.get_capabilities_by_type(strict_type_matching=strict_type_matching)
        pprint({get_pretty_type_str(typ): parsers for typ, parsers in l.items()})

    def get_all_supported_types_pretty_str(self) -> List[str]:
        return list({get_pretty_type_str(typ) for typ in self.get_all_supported_types()})

    def get_capabilities_by_type(self, strict_type_matching: bool) -> Dict[str, Dict[Type[T], AnyParser[T]]]:
        """
        For all types that are supported,
        lists all extensions that can be parsed into such a type.
        For each extension, provides the list of parsers supported. The order is "most pertinent first"

        This method is for monitoring and debug, so we prefer to not rely on the cache, but rather on the query engine.
        That will ensure consistency of the results.

        :param strict_type_matching:
        :return:
        """

        check_var(strict_type_matching, var_types=bool, var_name='strict_matching')

        res = dict()

        # List all types that can be parsed
        for typ in self.get_all_supported_types_for_ext(None):
            res[typ] = self.get_capabilities_for_type(typ, strict_type_matching)

        return res

    def print_capabilities_for_type(self, typ, strict_type_matching = False):
        pprint(self.get_capabilities_for_type(typ, strict_type_matching=strict_type_matching))


    def get_capabilities_for_type(self, typ, strict_type_matching):
        """
        Utility method to return, for a given type, all known ways to parse an object of this type, organized by file
        extension.

        :param typ:
        :param strict_type_matching:
        :return:
        """
        r = dict()
        # For all extensions that are supported,
        for ext in self.get_all_supported_exts_for_type(None, strict=strict_type_matching):
            # Use the query to fill
            matching = self.find_all_matching_parsers(strict_type_matching, desired_type=typ, required_ext=ext)[0]
            # matching_list = matching[0] + matching[1] + matching[2]
            # insert_element_to_dict_of_dicts_of_list(res, typ, ext, list(reversed(matching_list)))
            r[ext] = {'1_exact_match': list(reversed(matching[2])),
                      '2_approx_match': list(reversed(matching[1])),
                      '3_generic': list(reversed(matching[0]))}
            # insert_element_to_dict_of_dicts(res, typ, ext, matching_dict)
        return r

    def get_capabilities_by_ext(self, strict_type_matching: bool) -> Dict[str, Dict[Type[T], AnyParser[T]]]:
        """
        For all extensions that are supported,
        lists all types that can be parsed from this extension.
        For each type, provide the list of parsers supported. The order is "most pertinent first"

        This method is for monitoring and debug, so we prefer to not rely on the cache, but rather on the query engine.
        That will ensure consistency of the results.

        :param strict_type_matching:
        :return:
        """
        check_var(strict_type_matching, var_types=bool, var_name='strict_matching')
        res = dict()

        # For all extensions that are supported,
        for ext in self.get_all_supported_exts_for_type(None, strict=strict_type_matching):
            res[ext] = self.get_capabilities_for_ext(ext, strict_type_matching)

        return res

    def print_capabilities_for_ext(self, ext, strict_type_matching = False):
        pprint(get_pretty_type_keys_dict(self.get_capabilities_for_ext(ext, strict_type_matching)))

    def get_capabilities_for_ext(self, ext, strict_type_matching):
        """
        Utility method to return, for a given file extension, all known ways to parse a file with this extension,
        organized by target object type.

        :param ext:
        :param strict_type_matching:
        :return:
        """
        r = dict()
        # List all types that can be parsed from this extension.
        for typ in self.get_all_supported_types_for_ext(ext):
            # Use the query to fill
            matching = self.find_all_matching_parsers(strict_type_matching, desired_type=typ, required_ext=ext)[0]
            # matching_list = matching[0] + matching[1] + matching[2]
            # insert_element_to_dict_of_dicts_of_list(res, ext, typ, list(reversed(matching_list)))
            r[typ] = {'1_exact_match': list(reversed(matching[2])),
                      '2_approx_match': list(reversed(matching[1])),
                      '3_generic': list(reversed(matching[0]))}
            # insert_element_to_dict_of_dicts(res, ext, typ, matching_dict)
        return r

    def get_all_supported_types(self):
        return self.get_all_supported_types_for_ext(ext_to_match=None)

    @abstractmethod
    def get_all_supported_types_for_ext(self, ext_to_match: str) -> Set[Type[Any]]:
        pass

    def get_all_supported_exts(self):
        # no need to use strict = False here :)
        return self.get_all_supported_exts_for_type(type_to_match=None, strict=True)

    @abstractmethod
    def get_all_supported_exts_for_type(self, type_to_match: Type[Any], strict: bool) -> Set[str]:
        pass

    @abstractmethod
    def register_parser(self, parser: AnyParser[T]):
        pass

    @abstractmethod
    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = None, required_ext: str = None) \
            -> Tuple[List[AnyParser], List[AnyParser], List[AnyParser], List[AnyParser]]:
        """
        Main method to find parsers matching a query. It should return a list *without duplicates* of parsers :
        - first the generic ones, from first registered to last registered
        - then the specific ones approximately matching the required type (from first registered to last reg)
        - then the specific ones, from first registered to last registered

        :param strict:
        :param desired_type: a type of object to parse, or None for 'wildcard'(*) . WARNING: "object_type=Any" means "all
        parsers able to parse anything", which is different from "object_type=None" which means "all parsers".
        :param required_ext: a specific extension to parse, or None for 'wildcard'(*)
        :return: a tuple : [the list of matching parsers, the list of parsers matching the type but not the ext,
        the list of parsers matching the ext but not the type, the list of remaining parsers]
        """
        pass


class ParserCache(AbstractParserCache):
    """
    This object is responsible to store parsers in memory, and provide ways to access the information by queries
    (by type, by ext, by both, by none), using strict mode, or inference mode (subclass allowed)
    """
    def __init__(self):
        # Raw data
        self._specific_parsers = list()
        self._generic_parsers = list()

        # self._type_to_parser = dict()
        # self._ext_to_parser = dict()
        #
        # self._type_to_ext_to_parser = dict()
        # self._ext_to_type_to_parser = dict()

        # new attempt: simply store the list of supported types and exts
        self._strict_types_to_ext = dict()
        self._ext_to_strict_types = dict()



    def register_parser(self, parser: AnyParser[T]):
        """
        Utility method to register any parser. Parsers that support any type will be stored in the "generic"
        list, and the others will be stored in front of the types they support
        :return:
        """
        check_var(parser, var_types=AnyParser, var_name='parser')
        if (not parser.supports_multifile()) and (not parser.supports_singlefile()):
            # invalid
            raise InvalidParserException.create(parser)

        # (1) store in the main lists
        if parser.is_generic():
            self._generic_parsers.append(parser)
        else:
            self._specific_parsers.append(parser)

        # (2) simpler : simply store the ext <> type maps
        for ext in parser.supported_exts:
            for typ in parser.supported_types:
                insert_element_to_dict_of_list(self._strict_types_to_ext, typ, ext)
                insert_element_to_dict_of_list(self._ext_to_strict_types, ext, typ)

        # # (2) add to the ext > parser and ext > type > parser map
        # for ext in parser.supported_exts:
        #     insert_element_to_dict_of_list(self._ext_to_parser, ext, parser)
        #
        #     # add the parser supported types
        #     for typ in parser.supported_types:
        #         insert_element_to_dict_of_dicts_of_list(self._ext_to_type_to_parser, ext, typ, parser)
        #     # then check all other types that are compliant > NO, we dont want to do that in this cache but rather in
        #     # client codes explicitly requiring it (see get_capabilities_by_ext)
        #
        # # (3) add to the type > ext > parser map
        # for typ in parser.supported_types:
        #     insert_element_to_dict_of_list(self._type_to_parser, typ, parser)
        #
        #     # add the parser supported exts
        #     for ext in parser.supported_exts:
        #         insert_element_to_dict_of_dicts_of_list(self._type_to_ext_to_parser, typ, ext, parser)
        # then check all other types that are compliant > NO, we dont want to do that in this cache but rather in
        # client codes explicitly requiring it (see get_capabilities_by_type)

    def get_all_parsers(self, strict_type_matching: bool) -> List[AnyParser]:
        """
        Returns a deep copy of the parsers list
        :return:
        """
        # strict=True or strit=False will actually lead to the same result :)
        matching = self.find_all_matching_parsers(strict=strict_type_matching)[0]
        # matching[1] is supposed to be empty
        if len(matching[1]) > 0:
            raise Exception('Internal error - this matching[1] list is supposed to be empty for such a query')
        return matching[0] + matching[2]

    def get_all_supported_types_for_ext(self, ext_to_match: str) -> Set[str]:
        # if ext_to_match is None:
        #     # return all supported types
        #     return set(self._strict_types_to_ext.keys())
        # else:
        #     # return the types associated with that extension
        #     if ext_to_match in self._ext_to_strict_types.keys():
        #         # TO DO we should probably also return
        #         return set(self._ext_to_strict_types[ext_to_match])
        #     else:
        #         return []
        matching = self.find_all_matching_parsers(required_ext=ext_to_match, strict=True)[0]
        return {typ for types in [p.supported_types for p in (matching[0] + matching[1] + matching[2])]
                for typ in types}

    def get_all_supported_exts_for_type(self, type_to_match: Type[Any], strict: bool) -> Set[str]:
        # if type_to_match is None:
        #     # return all supported exts
        #     return set(self._ext_to_strict_types.keys())
        # else:
        #     # return the exts associated with that EXACT type
        #     if type_to_match in self._strict_types_to_ext.keys():
        #         res = set(self._strict_types_to_ext[type_to_match])
        #     else:
        #         res = {}
        #
        #     # in addition, if not strict, look at all the other types and add their associated extensions
        #     if not strict:
        #         # look at all the types that match APPROXIMATELY type_to_match
        #         for typ in self.get_all_supported_types_for_ext(None):
        #             if parser_is_able_to_parse(typ, type_to_match, strict)[0]:
        #                 res.union(set(self._strict_types_to_ext[typ]))
        #     return res
        matching = self.find_all_matching_parsers(desired_type=type_to_match, strict=strict)[0]
        return {ext for exts in [p.supported_exts for p in (matching[0] + matching[1] + matching[2])]
                for ext in exts}


    # def get_capabilities_by_ext(self, strict_matching: bool) -> Dict[str, Dict[Type[T], AnyParser[T]]]:
    #     """
    #     For all extensions that are supported,
    #     lists all types that can be parsed from this extension.
    #     For each type, provide the list of parsers supported.
    #
    #     This method is for monitoring and debug, so we prefer to not rely on the cache, but rather on the query engine.
    #     That will ensure consistency of the results.
    #
    #     :param strict_matching:
    #     :return:
    #     """
    #
    #     check_var(strict_matching, var_types=bool, var_name='strict_matching')
    #
    #     # we have to return the inner cache, but add in front of all non-Any types
    #     # * in non-strict mode, the parsers from the same ext that are able to parse the type
    #     # * the parsers that are able to parse anything
    #
    #     # first make a copy
    #     res = self._ext_to_type_to_parser.copy()
    #
    #     # then for each extension that is supported
    #     for ext in res.keys():
    #         # find all the parsers able to parse that ext
    #         for parser in self._get_all_parsers_supporting_ext(ext):
    #             # for all types, if the parser is able to parse it, add it
    #             for typ in res[ext].keys():
    #                 if typ is not Any:
    #                     # add only the non-generic parsers for now
    #                     if (not parser.is_generic()) and parser.is_able_to_parse(typ, strict_matching)[0]:
    #                         res[ext][typ].append(parser)
    #
    #             # finally add the generic parsers at the end
    #             for typ in res[ext].keys():
    #                 if typ is not Any:
    #                     # note: the order wont be respected
    #                     if parser.is_generic():
    #                         res[ext][typ].append(parser)
    #     return res

    # def get_capabilities_by_type(self, strict_matching: bool) -> Dict[str, Dict[Type[T], AnyParser[T]]]:
    #     """
    #     For all types that are supported,
    #     lists all extensions that can be parsed into such a type.
    #     For each extension, provides the list of parsers supported.
    #
    #     This method is for monitoring and debug, so we prefer to not rely on the cache, but rather on the query engine.
    #     That will ensure consistency of the results.
    #
    #     :param strict_matching:
    #     :return:
    #     """
    #
    #     check_var(strict_matching, var_types=bool, var_name='strict_matching')
    #
    #     res = dict()
    #
    #     # List all types that can be parsed from this extension.
    #     for typ in self.get_all_supported_types():
    #         # For all extensions that are supported,
    #         for ext in self._type_to_ext_to_parser[typ]:
    #             # Use the query to fill
    #             matching = self.find_all_matching_parsers(strict_matching, object_type=typ, required_ext=ext)[0]
    #             insert_element_to_dict_of_dicts_of_list(res, typ, ext, matching)
    #
    #     return res
    #
    #     check_var(strict_matching, var_types=bool, var_name='strict_matching')
    #
    #     # we have to return the inner cache, but add in front of all non-Any types
    #     # * in non-strict mode, the parsers from the same ext that are able to parse the type
    #     # * the parsers that are able to parse anything
    #
    #     # first make a copy
    #     res = self._type_to_ext_to_parser.copy()
    #
    #     # then if non-strict mode - for each specific parser, check if we can add it elsewhere
    #     if not strict_matching:
    #         for specific_parser in self._specific_parsers:
    #             # for each extension it supports
    #             for ext in specific_parser.supported_exts:
    #                 # we want to add it to the types it could support
    #                 for typ in res.keys():
    #                     if specific_parser.is_able_to_parse(typ, strict=False):
    #                         insert_element_to_dict_of_dicts_of_list(res, typ, ext, specific_parser)
    #
    #     # then for each generic parser, check if we can add it elsewhere
    #     for generic_parser in self._generic_parsers:
    #         # for each extension it supports
    #         for ext in generic_parser.supported_exts:
    #             # add it to all the types
    #             for typ in res.keys():
    #                 if typ is not Any:
    #                     insert_element_to_dict_of_dicts_of_list(res, typ, ext, specific_parser)
    #
    #     return res

    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = None, required_ext: str = None) \
            -> Tuple[Tuple[List[AnyParser], List[AnyParser], List[AnyParser]],
                     List[AnyParser], List[AnyParser], List[AnyParser]]:

        if desired_type is None and required_ext is None:
            # Easy : return everything (GENERIC first, SPECIFIC then) in order (make a copy first :) )
            matching_parsers_generic = self._generic_parsers.copy()
            matching_parsers_approx = []
            matching_parsers_exact = self._specific_parsers.copy()
            no_type_match_but_ext_match = []
            no_ext_match_but_type_match = []
            no_match = []
        else:
            check_var(strict, var_types=bool, var_name='strict')

            matching_parsers_generic = []
            matching_parsers_approx = []
            matching_parsers_exact = []
            no_type_match_but_ext_match = []
            no_ext_match_but_type_match = []
            no_match = []

            # handle generic parsers first - except if desired type is Any
            for p in self._generic_parsers:
                match = p.is_able_to_parse(desired_type=desired_type, desired_ext=required_ext, strict=strict)[0]
                if match:
                    # match
                    if desired_type not in {Any, object}:
                        matching_parsers_generic.append(p)
                    else:
                        # special case : what is required is Any, so put in exact match
                        matching_parsers_exact.append(p)
                else:
                    # type matches always
                    no_ext_match_but_type_match.append(p)

            # then the specific
            for p in self._specific_parsers:
                match, exact_match = p.is_able_to_parse(desired_type=desired_type, desired_ext=required_ext,
                                                        strict=strict)
                if match:
                    if desired_type not in {Any, object}:
                        if exact_match is None or exact_match:
                            matching_parsers_exact.append(p)
                        else:
                            matching_parsers_approx.append(p)
                    else:
                        # special case: dont register as a type match
                        no_type_match_but_ext_match.append(p)
                else:
                    if p.is_able_to_parse(desired_type=None, desired_ext=required_ext, strict=strict)[0]:
                        no_type_match_but_ext_match.append(p)
                    elif p.is_able_to_parse(desired_type=desired_type, desired_ext=None, strict=strict)[0]:
                        no_ext_match_but_type_match.append(p)
                    else:
                        no_match.append(p)

            # # finally generic - if that's what is required
            # if desired_type in {Any, object}:
            #     for p in self._generic_parsers:
            #         match = p.is_able_to_parse(desired_type=desired_type, desired_ext=required_ext, strict=strict)[0]
            #         if match:
            #             # match
            #             matching_parsers_exact.append(p)
            #         else:
            #             # type matches always
            #             no_ext_match_but_type_match.append(p)

            #nb_approx = len(matching_parsers_approx)
            #matching_parsers += matching_parsers_approx + matching_parsers_exact

        # elif object_type is None:
        #     # Only EXT is specified
        #     matching_parsers = self._get_all_parsers_supporting_ext(required_ext, strict)
        #     no_type_match_but_ext_match = []
        #
        # elif required_ext is None:
        #     # Only type is specified
        #     matching_parsers, no_type_match_but_ext_match = self._get_all_parsers_supporting_type(object_type, strict)
        #
        # else:
        #     if strict:
        #         # both are specified : use our lookup tables
        #         type_match = [p for sublist in self._type_to_ext_to_parser[object_type].values() for p in sublist]\
        #             if object_type in self._type_to_ext_to_parser.keys() else []
        #         # --add the Any parsers if needed
        #         if (object_type is not Any) and (Any in self._type_to_ext_to_parser.keys()):
        #             type_match += self._type_to_ext_to_parser[Any].values()
        #
        #         ext_match = [p for sublist in self._ext_to_type_to_parser[required_ext].values() for p in sublist]\
        #             if required_ext in self._ext_to_type_to_parser.keys() else []
        #
        #         # build from the two list the intersection and remainder
        #         matching_parsers, no_type_match_but_ext_match = [], []
        #         for parser in ext_match:
        #             if parser in type_match and parser not in matching_parsers:
        #                 matching_parsers.append(parser)
        #             elif parser not in type_match and parser not in no_type_match_but_ext_match:
        #                 no_type_match_but_ext_match.append(parser)
        #     else:
        #         # probably the fastest is to iterate through parsers here
        #         matching_parsers, no_type_match_but_ext_match = [], []
        #         for p in self._specific_parsers + self._generic_parsers:
        #             if p.is_able_to_parse(object_type, strict=False)[0]:
        #                 if required_ext in p.supported_exts:
        #                     matching_parsers.append(p)
        #                 else:
        #                     no_type_match_but_ext_match.append(p)

        return (matching_parsers_generic, matching_parsers_approx, matching_parsers_exact), \
               no_type_match_but_ext_match, no_ext_match_but_type_match, no_match

    # def _get_all_parsers_supporting_ext(self, ext: str):
    #     """
    #     Utility method to find all parsers supporting a given extension
    #
    #     :param ext:
    #     :return:
    #     """
    #     if ext in self._ext_to_type_to_parser.keys():
    #         # concatenate all lists of parsers (one for each type)
    #         return [parser for parsers_for_a_type in self._ext_to_type_to_parser[ext].values() for parser in parsers_for_a_type]
    #     else:
    #         return []
    #
    # def _get_all_parsers_supporting_type(self, typ: str, strict: bool):
    #
    #     # get all exact matches from our cache
    #     if typ in self._type_to_ext_to_parser.keys():
    #         # concatenate all lists of parsers (one for each ext)
    #         r = [parser for sublist in self._type_to_ext_to_parser[typ].values() for parser in sublist]
    #     else:
    #         r = []
    #
    #     # dont forget parsers supporting anything
    #     if (typ is not Any) and (Any in self._type_to_ext_to_parser.keys()):
    #         r = r + self._type_to_ext_to_parser[Any].values()
    #         # identical to r = r + self._generic_parsers
    #
    #     # finally add the 'non-strict' matches, too
    #     if not strict:
    #         # probably the fastest is to iterate through specific parsers and add the remaining parsers
    #         r = []
    #         for p in self._specific_parsers:
    #             is_able, strictly = p.is_able_to_parse(typ, False)
    #             if is_able and not strictly:
    #                 r.append(p)

class ParserRegistry(ParserCache, ParserFinder, DelegatingParser[T]):
    """
    A manager of specific and generic parsers
    """

    def __init__(self, pretty_name: str, strict_matching: bool, initial_parsers_to_register: List[AnyParser[T]] = None):
        """
        Constructor. Initializes the dictionary of parsers with the optionally provided initial_parsers, and
        inits the lock that will be used for access in multithreading context.

        :param initial_parsers_to_register:
        """
        super(ParserRegistry, self).__init__()

        self.pretty_name = pretty_name

        check_var(strict_matching, var_types=bool, var_name='strict_matching')
        self.is_strict = strict_matching

        # add provided parsers
        if initial_parsers_to_register is not None:
            self.register_parsers(initial_parsers_to_register)

    def __str__(self):
        return self.pretty_name

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger) \
            -> _ParsingPlanElement[T]:
        """
        Implementation of AnyParser API
        Relies on the underlying registry of parsers to provide the best parsing plan
        :param desired_type:
        :param filesystem_object:
        :param logger:
        :return:
        """
        # find the parser for this object
        combined_parser = self.build_parser_for_fileobject_and_desiredtype(filesystem_object, desired_type,
                                                                           logger=logger)
        # ask the parser for the parsing plan
        return combined_parser.create_parsing_plan(desired_type, filesystem_object, logger)

    def build_parser_for_fileobject_and_desiredtype(self, obj_on_filesystem: PersistedObject, object_type: Type[T],
                                                    logger: Logger = None) -> AnyParser[T]:
        """
        Builds from the registry, a parser to parse object obj_on_filesystem as an object of type object_type.

        To do that, it iterates through all registered parsers in the list in reverse order (last inserted first),
        and checks if they support the provided object format (single or multifile) and type.
        If several parsers match, it returns a cascadingparser that will try them in order.

        :param obj_on_filesystem:
        :param object_type:
        :param logger:
        :return:
        """

        # first remove any non-generic customization
        object_type = get_base_generic_type(object_type)

        # find all matching parsers for this
        matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match = \
            self.find_all_matching_parsers(strict=self.is_strict, desired_type=object_type, required_ext=obj_on_filesystem.ext)
        matching_parsers = matching[0] + matching[1] + matching[2]

        if len(matching_parsers) == 0:
            # No match. Do we have a close match ? (correct type, but not correct extension ?)
            if len(no_ext_match_but_type_match) > 0:
                raise NoParserFoundForObjectExt.create(obj_on_filesystem, object_type,
                                                       [ext_ for ext_list in
                                                        [p.supported_exts for p in no_ext_match_but_type_match]
                                                        for ext_ in ext_list])
            else:
                # no, no match at all
                raise NoParserFoundForObjectType.create(obj_on_filesystem, object_type,
                                                       [typ_ for typ_list in
                                                        [p.supported_types for p in no_type_match_but_ext_match]
                                                        for typ_ in typ_list])

        elif len(matching_parsers) == 1:
            # return the match directly
            return matching_parsers[0]
        else:
            # return a cascade of all parsers, in reverse order (since last is our preferred one)
            #print('----- WARNING : Found several parsers able to parse this item. Combining them into a cascade.')
            return CascadingParser(list(reversed(matching_parsers)))

        # try:
        #     if object_type in specific_parsers.keys():
        #
        #         # we have found parsers for that type of object
        #         found_specific_parsers_for_that_type = specific_parsers[object_type]
        #
        #         # but do we have one for the type of file + extension ?
        #         return ParserRegistry._find_parsers(obj_on_filesystem, object_type,
        #                                             found_specific_parsers_for_that_type)
        #     else:
        #         # no parser found for that type
        #         raise NoParserFoundForObjectType.create(object_type)
        #
        # except NoParserFoundForObjectType as e:
        #     if logger:
        #         logger.info(
        #             'There was no explicitly registered parser for this type \'' + get_pretty_type_str(object_type)
        #             + '\'. Falling back on generic parsers.')
        #
        # except NoParserFoundForObjectExt as e:
        #     if logger:
        #         logger.info('There is a registered parser for this type \'' + get_pretty_type_str(object_type)
        #                     + '\' but not for extension ' + obj_on_filesystem.get_pretty_file_ext() + ', only for '
        #                     'extensions ' + str(e.extensions_supported) + '. Falling back on generic parsers.')
        #
        # # Try the generic parsers
        # return ParserRegistry._find_parsers(obj_on_filesystem, object_type, generic_parsers)

    # def find_all_parsers_for_type(self, object_type: Type[T]) -> List[AnyParser]:
    #     # return [parser for parser in reversed(self._parsers)
    #     #         if parser.supported_types is None or object_type in parser.supported_types]
    #     exact_type_and_ext_match, approx_type_exact_ext_match, approx_type_but_not_ext, exact_ext_but_not_type, \
    #         no_type_no_ext = self._find_all_matching_parsers(object_type, None)
    #     return exact_type_and_ext_match + approx_type_exact_ext_match + approx_type_but_not_ext
    #
    # def find_all_parsers_for_ext(self, required_ext: str) -> List[AnyParser]:
    #
    #     exact_type_and_ext_match, approx_type_exact_ext_match, approx_type_but_not_ext, exact_ext_but_not_type, \
    #         no_type_no_ext = self._find_all_matching_parsers(None, required_ext)
    #     return exact_type_and_ext_match + approx_type_exact_ext_match + exact_ext_but_not_type

    # def _find_all_matching_parsers(self, object_type: Type[Any], required_ext: str):
    #     """
    #     Internal method to find all parsers matching some criterion
    #
    #     :param object_type: the type of object to match. !! here, 'None' does not mean 'Any' !!
    #     :param required_ext: the required extension. !! here, None means *any* !!!
    #     :return:
    #     """
    #
    #     parsers = self._parsers
    #
    #     # init
    #     exact_type_and_ext_match = []
    #     approx_type_exact_ext_match = []
    #     approx_type_but_not_ext = []
    #     exact_ext_but_not_type = []
    #     no_type_no_ext = []
    #
    #     # reverse order
    #     all_parsers = list(reversed(parsers))
    #
    #     for parser in all_parsers:
    #         # exact match on type and extension
    #         if self._parser_matches(parser, object_type, exact_type_match=True,
    #                                 required_ext=required_ext):
    #             exact_type_and_ext_match.append(parser)
    #
    #         # approx match on type, exact match on extension
    #         elif self._parser_matches(parser, object_type, exact_type_match=False,
    #                                   required_ext=required_ext):
    #             approx_type_exact_ext_match.append(parser)
    #
    #         # no match on extensions, approx or exact match on type
    #         elif self._parser_matches(parser, object_type, exact_type_match=False):
    #             approx_type_but_not_ext.append(parser)
    #
    #         # no match on types, exact match on extension
    #         elif self._parser_matches(parser, required_ext=required_ext):
    #             exact_ext_but_not_type.append(parser)
    #
    #         else:
    #             no_type_no_ext.append(parser)
    #
    #     return exact_type_and_ext_match, approx_type_exact_ext_match, approx_type_but_not_ext, exact_ext_but_not_type, \
    #            no_type_no_ext

    # @staticmethod
    # def _parser_matches(parser: AnyParser[T], required_type: Type[T] = None,
    #                     exact_type_match: bool = True, required_ext: str = None):
    #     """
    #     Inner method to test if a parser matches the requirements specified
    #
    #     :param parser:
    #     :param required_type: !!! None means anything but Any means only the parsers able to parse the "Any" type !!!
    #     :param exact_type_match:
    #     :param required_ext: !!! None means anything !!!
    #     :return:
    #     """
    #     check_var(parser, var_types=AnyParser, var_name='parser')
    #
    #     if required_type is not None:
    #         # First remove any customization from the typing module
    #         required_type = get_base_generic_type(required_type)
    #
    #     if required_type is None \
    #             or (exact_type_match and (parser.supported_types is None or required_type in parser.supported_types)) \
    #             or (not exact_type_match and
    #                     ((parser.supported_types is not None
    #                      and any([issubclass(parsed_type, required_type) for parsed_type in parser.supported_types]))
    #                 or (parser.supported_types is None))):
    #
    #         if required_ext is None:
    #             return True
    #
    #         elif (not (required_ext is MULTIFILE_EXT)) and parser.supports_singlefile():
    #             # does it support the extension ?
    #             if required_ext is None or required_ext in parser.supported_exts:
    #                 return True
    #
    #         elif (required_ext is MULTIFILE_EXT) and parser.supports_multifile():
    #             return True
    #
    #     return False


    # @staticmethod
    # def _find_parsers(obj_on_filesystem: PersistedObject, object_type: Type[Any],
    #                   parsers_for_type_by_extension: Dict[str, AnyParser[T]]):
    #     """
    #     Generic method to find parsers according to a query, in a registry
    #
    #     :param obj_on_filesystem:
    #     :param object_type:
    #     :param parsers_for_type_by_extension:
    #     :return:
    #     """
    #     if obj_on_filesystem.is_singlefile:
    #         if obj_on_filesystem.ext in parsers_for_type_by_extension.keys():
    #             res = parsers_for_type_by_extension[obj_on_filesystem.ext]
    #         else:
    #             # we don't have a parser for that file extension
    #             raise NoParserFoundForObjectExt.create(obj_on_filesystem, object_type,
    #                                                    parsers_for_type_by_extension.keys())
    #     else:
    #         if MULTIFILE_EXT in parsers_for_type_by_extension.keys():
    #             res = parsers_for_type_by_extension[MULTIFILE_EXT]
    #         else:
    #             # we don't have a parser for multifile
    #             raise NoParserFoundForObjectExt.create(obj_on_filesystem, object_type,
    #                                                    parsers_for_type_by_extension.keys())
    #     return res
    #
    # def find_all_parsers_for_desiredtype(self, object_type: Type[T], logger: Logger = None) -> Dict[str, AnyParser[T]]:
    #     """
    #     Returns the most appropriate parserS to use to parse any object of type object_type, in a dictionary by
    #     extension
    #
    #     :param object_type:
    #     :param logger:
    #     :return:
    #     """
    #     # use the inner dictionaries of typed parsers and generic parsers.
    #     return ParserRegistry._find_parser_from_specific_then_generic(object_type,
    #                                                                   self._typed_parsers_by_type,
    #                                                                   self._generic_obj_parsers_by_ext,
    #                                                                   logger=logger)

    # def _register_generic_parsers(self, object_parsers: Dict[str, AnyParser[T]]):
    #     """
    #     Registers the provided generic parsers.
    #     :param object_parsers: a dictionary of [extension, generic_parser]
    #     :return:
    #     """
    #     check_var(object_parsers, var_types=dict)
    #
    #     # don't use dict.update because we want to perform sanity checks here
    #     for extension, parser in object_parsers.items():
    #         self._register_generic_parser_for_ext(extension, parser)
    #     return
    #
    # def _register_generic_parser_for_ext(self, extension: str, object_parser: AnyParser[T]):
    #     """
    #     To register a single generic parser for one extension
    #
    #     :param extension:
    #     :param object_parser:
    #     :return:
    #     """
    #     check_var(extension, var_types=str)
    #     check_var(object_parser, var_types=AnyParser)
    #
    #     if object_parser.supported_types is not None:
    #         raise ValueError('Only generic parsers may be registered using register_generic_object_parser...')
    #
    #     self._types_lock.acquire()
    #     try:
    #         if extension in self.__generic_coll_parsers_by_ext.keys():
    #             warning('Warning : overriding existing generic object parser for ext ' + extension)
    #         self._generic_obj_parsers_by_ext[extension] = object_parser
    #     finally:
    #         self._types_lock.release()
    #     return
    #
    # def _register_typed_parsers(self, parsers:Dict[Type[T], Dict[str, AnyParser[T]]]):
    #     """
    #     Registers the provided parsers
    #     :param parsers:
    #     :return:
    #     """
    #     check_var(parsers, var_types=dict)
    #
    #     # don't use dict.update because we want to perform sanity checks here
    #     for object_type, extension_parsers in parsers.items():
    #         self._register_parsers_for_type(object_type, extension_parsers)
    #     return

    # def _register_parsers_for_type(self, object_type:Type[T], extension_parsers:Dict[str, AnyParser[T]]):
    #     """
    #     Registers a new type, with associated extension parsers
    #
    #     :param object_type:
    #     :param extension_parsers:
    #     :return:
    #     """
    #     check_var(object_type, var_types=type)
    #     check_var(extension_parsers, var_types=dict, min_len=1)
    #
    #     # don't use dict.update because we want to perform sanity checks here
    #     for extension, extension_parser in extension_parsers.items():
    #         self._register_unitary_parser_for_type(object_type, extension, extension_parser)
    #     return
    #
    # def _register_unitary_parser_for_type(self, object_type: Type[T], extension: str,
    #                                       extension_parser: AnyParser[T]):
    #     """
    #     To register a single parsing function, for a single file extension, for a given object type
    #     :param object_type:
    #     :param extension:
    #     :param extension_parser:
    #     :return:
    #     """
    #     check_var(object_type, var_types=type)
    #
    #     # extension
    #     check_extension(extension, allow_multifile=True)
    #
    #     # parser
    #     check_var(extension_parser, var_types=AnyParser)
    #     if extension_parser.supported_types is None:
    #         raise ValueError('Only specific parsers may be registered using register_unitary_parser_for_type...')
    #     if object_type not in extension_parser.supported_types:
    #         raise ValueError('Cannot register parser ' + str(extension_parser) + ' for type '
    #                          + get_pretty_type_str(object_type) + ' : parser does not support it')
    #
    #     # register
    #     self._types_lock.acquire()
    #     try:
    #         if object_type in self._typed_parsers_by_type.keys():
    #             if extension in self._typed_parsers_by_type[object_type]:
    #                 warn('Warning : overriding existing extension parser for type <' + get_pretty_type_str(object_type)
    #                      + '> and extension ' + extension)
    #             self._typed_parsers_by_type[object_type][extension] = extension_parser
    #         else:
    #             self._typed_parsers_by_type[object_type] = {extension: extension_parser}
    #     finally:
    #         self._types_lock.release()
    #     return
    #
    # def get_typed_parsers_copy(self) -> Dict[Type[T], Dict[str, AnyParser[T]]]:
    #     """
    #     Returns a deep copy of the parsers dictionary
    #     :return:
    #     """
    #     return deepcopy(self._typed_parsers_by_type)
    #
    # def get_generic_parsers_copy(self) -> Dict[str, AnyParser[T]]:
    #     """
    #     Returns a deep copy of the parsers dictionary
    #     :return:
    #     """
    #     return deepcopy(self._generic_obj_parsers_by_ext)

class ConversionFinder(metaclass=ABCMeta):
    """
    Abstract class for objects able to find a conversion chain between two types
    """
    def get_all_conversion_chains_to_type(self, to_type: Type[Any])\
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find all converters to a given type

        :param to_type:
        :return:
        """
        return self.get_all_conversion_chains(to_type=to_type)

    def get_all_conversion_chains_from_type(self, from_type: Type[Any]) \
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find all converters from a given type.

        :param from_type:
        :return:
        """
        return self.get_all_conversion_chains(from_type=from_type)

    @abstractmethod
    def get_all_conversion_chains(self, from_type: Type[Any] = None, to_type: Type[Any] = None)\
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find all converters or conversion chains matching the provided query.

        :param from_type: a required type of input object, or None for 'wildcard'(*) . WARNING: "from_type=Any" means
        "all converters able to source from anything", which is different from "from_type=None" which means "all
        converters whatever their source type".
        :param to_type: a required type of output object, or None for 'wildcard'(*) . WARNING: "to_type=Any" means "all
        converters able to produce any type of object", which is different from "to_type=None" which means "all
        converters whatever type they are able to produce".
        :return: a tuple of lists of matching converters, by type of *dest_type* match : generic, approximate, exact
        """
        pass

class AbstractConverterCache(ConversionFinder):
    """
    The abstract methods that a converter cache should implement to be usable in the ParserRegistryWithConverters,
    as well as the methods that can be automatically built from them
    """
    def __init__(self, strict: bool):
        self.strict = strict

    def register_converters(self, converters: List[Converter[S, T]]):
        check_var(converters, var_types=list, var_name='converters')
        for converter in converters:
            self.register_converter(converter)

    @abstractmethod
    def register_converter(self, converter: Converter[S, T]):
        pass

    @abstractmethod
    def get_all_conversion_chains(self, from_type: Type[Any] = None, to_type: Type[Any] = None)\
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        pass

class ConverterCache(AbstractConverterCache):
    """
    This object is responsible to store converters in memory, and provide ways to access the information by queries
    (by from_type, by to_type, both, none), using strict mode, or inference mode (subclass allowed). Note that
    due to the complexity of conversion chains, strict mode is set at creation time, not at query time.
    """
    def __init__(self, strict_matching: bool):
        super(ConverterCache, self).__init__(strict_matching)

        #self._specific_converters = list()
        #self._generic_converters = list()

        self._specific_conversion_chains = list()
        self._specific_non_strict_conversion_chains = list()
        self._generic_conversion_chains = list()
        self._generic_nonstrict_conversion_chains = list()

        # self._fromtype_to_dest_type_to_conversion_chain = dict()
        # self._desttype_to_fromtype_to_conversion_chain = dict()

    def register_converter(self, converter: Converter[S, T]):
        """
        Utility method to register any converter. Converters that support any type will be stored in the "generic"
        lists, and the others will be stored in front of the types they support
        :return:
        """
        check_var(converter, var_types=Converter, var_name='converter')

        # # (1) store in the main list
        # if converter.is_generic():
        #     self._generic_converters.append(converter)
        # else:
        #     self._specific_converters.append(converter)

        # compute all possible chains and save them
        generic_chains, generic_nonstrict_chains, specific_chains, specific_nonstrict_chains \
            = self._create_all_new_chains(converter)
        self._generic_nonstrict_conversion_chains += generic_nonstrict_chains
        self._generic_conversion_chains += generic_chains
        self._specific_non_strict_conversion_chains += specific_nonstrict_chains
        self._specific_conversion_chains += specific_chains

        # FINALLY sort all lists
        self._generic_nonstrict_conversion_chains = sorted(self._generic_nonstrict_conversion_chains,
                                                           key=methodcaller('size'), reverse=True)
        self._generic_conversion_chains = sorted(self._generic_conversion_chains, key=methodcaller('size'), reverse=True)
        self._specific_non_strict_conversion_chains = sorted(self._specific_non_strict_conversion_chains,
                                                             key=methodcaller('size'), reverse=True)
        self._specific_conversion_chains = sorted(self._specific_conversion_chains, key=methodcaller('size'),
                                                  reverse=True)


        # for chain in generic_chains + specific_nonstrict_chains + specific_chains:
        #     # (3) add all to the from > to > converter map
        #     insert_element_to_dict_of_dicts_of_list(self._fromtype_to_dest_type_to_conversion_chain, chain.from_type,
        #                                             chain.to_type, chain)
        #     # (4) add all to the to > from > converter map
        #     insert_element_to_dict_of_dicts_of_list(self._desttype_to_fromtype_to_conversion_chain, chain.to_type,
        #                                             chain.from_type, chain)

    def _create_all_new_chains(self, converter) -> Tuple[List[Converter], List[Converter],
                                                         List[Converter], List[Converter]]:
        """
        Creates all specific and generic chains that may be built by adding this converter to the existing chains.

        :param converter:
        :return: generic_chains, generic_nonstrict_chains, specific_chains, specific_nonstrict_chains
        """

        specific_chains, specific_nonstrict_chains, generic_chains, generic_nonstrict_chains = [], [], [], []

        if converter.is_generic():
            # the smaller chain :)
            generic_chains.append(ConversionChain(initial_converters=[converter], strict_chaining=True))

            # create new generic chain by appending this converter at the end of an existing *non-generic* one
            for existing_specific in self._specific_conversion_chains:
                if converter.can_be_appended_to(existing_specific, strict=True):
                    generic_chains.append(ConversionChain.chain(existing_specific, converter, strict=True))
                elif (not self.strict) and converter.can_be_appended_to(existing_specific, strict=False):
                    generic_nonstrict_chains.append(ConversionChain.chain(existing_specific, converter,
                                                                          strict=False))

            for existing_specific_ns in self._specific_non_strict_conversion_chains:
                if converter.can_be_appended_to(existing_specific_ns, strict=False):
                    generic_nonstrict_chains.append(ConversionChain.chain(existing_specific_ns, converter,
                                                                          strict=False))

            # FOLLOWING IS NOT POSSIBLE : generic
            # by inserting this converter at the beginning of an existing one
            # by combining both created chains into a big one
        else:
            # the smaller chain :)
            specific_chains.append(ConversionChain(initial_converters=[converter], strict_chaining=True))

            # 1) create new specific chains by adding this converter at the beginning or end of all *non-generic* ones
            # -- non-strict
            new_c_at_end_ns = []
            new_c_at_beginning_ns = []
            if not self.strict:
                # then there are non-strict chains already. Try to connect to them
                for existing_specific_nonstrict in self._specific_non_strict_conversion_chains:
                    if converter.can_be_appended_to(existing_specific_nonstrict, strict=False):
                        if ConversionChain.are_worth_chaining(existing_specific_nonstrict, converter):
                            new_c_at_end_ns.append(ConversionChain.chain(existing_specific_nonstrict, converter,
                                                                         strict=False))
                    if existing_specific_nonstrict.can_be_appended_to(converter, strict=False):
                        if ConversionChain.are_worth_chaining(converter, existing_specific_nonstrict):
                            new_c_at_beginning_ns.append(ConversionChain.chain(converter, existing_specific_nonstrict,
                                                                               strict=False))

            # -- strict
            new_c_at_end = []
            new_c_at_beginning = []
            for existing_specific in self._specific_conversion_chains:
                # first try *strict* mode
                if converter.can_be_appended_to(existing_specific, strict=True):
                    if ConversionChain.are_worth_chaining(existing_specific, converter):
                        new_c_at_end.append(ConversionChain.chain(existing_specific, converter, strict=True))
                elif (not self.strict) and converter.can_be_appended_to(existing_specific, strict=False):
                    if ConversionChain.are_worth_chaining(existing_specific, converter):
                        new_c_at_end_ns.append(ConversionChain.chain(existing_specific, converter, strict=False))

                if existing_specific.can_be_appended_to(converter, strict=True):
                    if ConversionChain.are_worth_chaining(converter, existing_specific):
                        new_c_at_beginning.append(ConversionChain.chain(converter, existing_specific, strict=True))
                elif (not self.strict) and existing_specific.can_be_appended_to(converter, strict=False):
                    if ConversionChain.are_worth_chaining(converter, existing_specific):
                        new_c_at_beginning_ns.append(ConversionChain.chain(converter, existing_specific, strict=False))

            specific_chains += new_c_at_end
            specific_chains += new_c_at_beginning
            specific_nonstrict_chains += new_c_at_end_ns
            specific_nonstrict_chains += new_c_at_beginning_ns

            # by combining all created chains into a big one
            for a in new_c_at_end:
                for b in new_c_at_beginning:
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=True):
                        if ConversionChain.are_worth_chaining(a, b_):
                            specific_chains.append(ConversionChain.chain(a, b_, strict=True))
                for b in new_c_at_beginning_ns:
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=False):
                        if ConversionChain.are_worth_chaining(a, b_):
                            specific_nonstrict_chains.append(ConversionChain.chain(a, b_, strict=False))
            for a in new_c_at_end_ns:
                for b in (new_c_at_beginning_ns + new_c_at_beginning):
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=False):
                        if ConversionChain.are_worth_chaining(a, b_):
                            specific_nonstrict_chains.append(ConversionChain.chain(a, b_, strict=False))

            # by inserting this converter at the beginning of an existing *generic*
            new_c_at_beginning_generic = []
            new_c_at_beginning_generic_ns = []
            for existing_specific in self._generic_conversion_chains:
                # start with strict
                if existing_specific.can_be_appended_to(converter, strict=True):
                    if ConversionChain.are_worth_chaining(converter, existing_specific):
                        new_c_at_beginning_generic.append(ConversionChain.chain(converter, existing_specific,
                                                                                strict=True))
                elif (not self.strict) and existing_specific.can_be_appended_to(converter, strict=False):
                    if ConversionChain.are_worth_chaining(converter, existing_specific):
                        new_c_at_beginning_generic_ns.append(ConversionChain.chain(converter, existing_specific,
                                                                                   strict=False))

            for existing_specific_ns in self._generic_nonstrict_conversion_chains:
                if existing_specific_ns.can_be_appended_to(converter, strict=False):
                    if ConversionChain.are_worth_chaining(converter, existing_specific_ns):
                        new_c_at_beginning_generic_ns.append(ConversionChain.chain(converter, existing_specific_ns,
                                                                               strict=False))
            generic_chains += new_c_at_beginning_generic
            generic_nonstrict_chains += new_c_at_beginning_generic_ns


            # by combining specific and generic created chains into a big one
            for a in new_c_at_end:
                for b in new_c_at_beginning_generic:
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=True):
                        if ConversionChain.are_worth_chaining(a, b_):
                            generic_chains.append(ConversionChain.chain(a, b_, strict=True))
                for b in new_c_at_beginning_generic_ns:
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=False):
                        if ConversionChain.are_worth_chaining(a, b_):
                            generic_nonstrict_chains.append(ConversionChain.chain(a, b_, strict=False))
            for a in new_c_at_end_ns:
                for b in (new_c_at_beginning_generic_ns + new_c_at_beginning_generic):
                    b_ = b.remove_first()
                    if b_.can_be_appended_to(a, strict=False):
                        if ConversionChain.are_worth_chaining(a, b_):
                            generic_nonstrict_chains.append(ConversionChain.chain(a, b_, strict=False))

        return generic_chains, generic_nonstrict_chains, specific_chains, specific_nonstrict_chains

    def get_all_conversion_chains(self, from_type: Type[Any] = None, to_type: Type[Any] = None) \
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find matching converters or conversion chains.

        :param from_type: a required type of input object, or None for 'wildcard'(*) . WARNING: "from_type=Any" means
        "all converters able to source from anything", which is different from "from_type=None" which means "all
        converters whatever their source type".
        :param to_type: a required type of output object, or None for 'wildcard'(*) . WARNING: "to_type=Any" means "all
        converters able to produce any type of object", which is different from "to_type=None" which means "all
        converters whatever type they are able to produce".
        :return: a tuple of lists of matching converters, by type of *dest_type* match : generic, approximate, exact.
        The order of each list is from *less relevant* to *most relevant*
        """

        if from_type is None and to_type is None:
            matching_dest_generic = self._generic_nonstrict_conversion_chains.copy() + \
                                    self._generic_conversion_chains.copy()
            matching_dest_approx = []
            matching_dest_exact = self._specific_non_strict_conversion_chains.copy() + \
                                  self._specific_conversion_chains.copy()

        else:
            matching_dest_generic, matching_dest_approx, matching_dest_exact = [], [], []

            # handle generic converters first
            for p in (self._generic_nonstrict_conversion_chains + self._generic_conversion_chains):
                match = p.is_able_to_convert(strict=self.strict, from_type=from_type, to_type=to_type)[0]
                if match:
                    # match
                    if to_type not in {Any, object}:
                        matching_dest_generic.append(p)
                    else:
                        # special case of Any
                        matching_dest_exact.append(p)

            # then the specific
            for p in (self._specific_non_strict_conversion_chains + self._specific_conversion_chains):
                match, source_exact, dest_exact = p.is_able_to_convert(strict=self.strict, from_type=from_type,
                                                                       to_type=to_type)
                if match:
                    if to_type not in {Any, object}:
                        if dest_exact:
                            # we dont care if source is exact or approximate as long as dest is exact
                            matching_dest_exact.append(p)
                        else:
                            # this means that dest is approximate.
                            matching_dest_approx.append(p)
                    else:
                        # we only want to keep the generic ones, and they have already been added
                        pass
                # else:
                #     if p.is_able_to_parse(desired_type=None, desired_ext=required_ext, strict=strict):
                #         no_type_match_but_ext_match.append(p)
                #     elif p.is_able_to_parse(desired_type=desired_type, desired_ext=None, strict=strict):
                #         no_ext_match_but_type_match.append(p)
                #     else:
                #         no_match.append(p)

            #matching_converters += matching_converters_approx + matching_converters_exact

        # elif from_type is None:
        #     # only to_type
        #     matching_converters = self._get_all_conversion_chains_to_type(to_type)
        #
        # elif to_type is None:
        #     # only from_type
        #     matching_converters = self._get_all_conversion_chains_from_type(from_type)
        #
        # else:
        #     # both are specified : use one of our lookup tables
        #
        #     # from_match = self._fromtype_to_dest_type_to_conversion_chain[from_type] \
        #     #    if from_type in self._fromtype_to_dest_type_to_conversion_chain.keys() else []
        #
        #     # maybe more selective to start from the dest type ? not even sure.
        #     to_match = self._desttype_to_fromtype_to_conversion_chain[to_type] \
        #         if to_type in self._desttype_to_fromtype_to_conversion_chain.keys() else []
        #     matching_converters = to_match[from_type] if from_type in to_match.keys() else []
        #

        return matching_dest_generic, matching_dest_approx, matching_dest_exact

    # def _get_all_conversion_chains_to_type(self, to_type: Type[Any]):
    #     """
    #     Utility method to find all converters to a given type
    #
    #     :param ext:
    #     :return:
    #     """
    #     if to_type in self._desttype_to_fromtype_to_conversion_chain.keys():
    #         # concatenate all lists of converters (one for each from_type)
    #         return [converter
    #                 for converters_from_a_type in self._desttype_to_fromtype_to_conversion_chain[to_type].values()
    #                 for converter in converters_from_a_type]
    #     else:
    #         return []
    #
    # def _get_all_conversion_chains_from_type(self, from_type: Type[Any]):
    #     """
    #     Utility method to find all converters to a given type
    #
    #     :param ext:
    #     :return:
    #     """
    #     if from_type in self._fromtype_to_dest_type_to_conversion_chain.keys():
    #         # concatenate all lists of converters (one for each to_type)
    #         return [converter
    #                 for converters_to_a_type in self._fromtype_to_dest_type_to_conversion_chain[from_type].values()
    #                 for converter in converters_to_a_type]
    #     else:
    #         return []


class ParserRegistryWithConverters(ConverterCache, ParserRegistry, ConversionFinder):
    """
    The base class able to combine parsers and converters to create parsing chains.
    """

    def __init__(self, pretty_name: str, strict_matching: bool, initial_parsers_to_register: List[AnyParser] = None,
                 initial_converters_to_register: List[Converter] = None):
        """
        Constructor. See parent class ParserRegistry for details

        :param pretty_name:
        :param strict_matching:
        :param initial_parsers_to_register:
        :param initial_converters_to_register:
        """

        # make sure all init are called
        ConverterCache.__init__(self, strict_matching=strict_matching)
        ParserRegistry.__init__(self, pretty_name=pretty_name, strict_matching=strict_matching,
                                initial_parsers_to_register=initial_parsers_to_register)

        # init the converters list
        #self.converters_cache = ConverterCache(strict_matching)

        # then add provided converters
        if initial_converters_to_register is not None:
            self.register_converters(initial_converters_to_register)

        #self.__converters_by_dest_type = {} # Dict[DestinationType > Dict[SourceType > converter]]

    # def find_all_parsers_for_type(self, desired_type: Type[T]) -> List[AnyParser]:
    #
    #     # first as usual find direct matches
    #     parsers = super().find_all_parsers_for_type(desired_type)
    #
    #     # then build parsing chains with the other parsers
    #     parsing_chains = [ParsingChain(base_parser=other_parser, initial_converters=conversion_chain,
    #                                    base_parser_chosen_dest_type=type_this_parser_can_parse)
    #                       # for all other parsers
    #                       for other_parser in reversed(self._parsers) if other_parser not in parsers
    #                       # for all the types they can parse
    #                       for type_this_parser_can_parse in other_parser.supported_types
    #                       # create the chain between that type and the desired type
    #                       for conversion_chain in
    #                       ParserRegistryWithConverters.create_all_conversion_chains(type_this_parser_can_parse,
    #                                                                                 desired_type,
    #                                                                                 self._converters)]
    #
    #     return parsers + parsing_chains

    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = None, required_ext: str = None) \
        -> Tuple[Tuple[List[AnyParser], List[AnyParser], List[AnyParser]],
                 List[AnyParser], List[AnyParser], List[AnyParser]]:
        """
        Internal method to find all parsers matching some criterion

        :param strict:
        :param desired_type: the type of object to match.
        :param required_ext: the required extension.
        :return:
        """
        # (1) call the super method to find all parsers
        matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match = \
            super(ParserRegistryWithConverters, self).find_all_matching_parsers(strict=self.is_strict,
                                                                                desired_type=desired_type,
                                                                                required_ext=required_ext)
        # these are ordered with 'preferred last'
        matching_p_generic, matching_p_approx, matching_p_exact = matching

        if desired_type is None:
            # then we want to append everything even exact match
            parsers_to_complete_with_converters = no_type_match_but_ext_match + matching_p_approx + matching_p_exact
        else:
            # then at least try with the approx
            parsers_to_complete_with_converters = no_type_match_but_ext_match + matching_p_approx

        # (2) find all conversion chains that lead to the expected result
        matching_c_generic_to_type, matching_c_approx_to_type, matching_c_exact_to_type = \
            self.get_all_conversion_chains_to_type(to_type=desired_type)
        all_matching_converters = matching_c_generic_to_type + matching_c_approx_to_type + matching_c_exact_to_type


        # (3) combine both and append to the appropriate list depending on the match
        # -- first Parsers matching EXT (not type) + Converters matching their type
        # for all parsers able to parse this extension, and for all the types they support
        # (we have to reverse the list because now we want 'preferred first'. Indeed we wish to prepend to the match
        # lists in order not to hide the parser direct matches)
        matching_p_generic_with_approx_chain, matching_p_approx_with_approx_chain, matching_p_exact_with_approx_chain\
            = [], [], []
        for parser in reversed(parsers_to_complete_with_converters):
            for typ in parser.supported_types:
                match_results = self._complete_parsers_with_converters(parser, typ, desired_type,
                                                                       matching_c_generic_to_type,
                                                                       matching_c_approx_to_type,
                                                                       matching_c_exact_to_type)
                matching_p_generic = match_results[1] + matching_p_generic
                matching_p_generic_with_approx_chain = match_results[0] + matching_p_generic_with_approx_chain
                matching_p_approx = match_results[3] + matching_p_approx
                matching_p_approx_with_approx_chain = match_results[2] + matching_p_approx_with_approx_chain
                matching_p_exact = match_results[5] + matching_p_exact
                matching_p_exact_with_approx_chain = match_results[4] + matching_p_exact_with_approx_chain

        # now merge the approx/approx
        matching_p_generic = matching_p_generic_with_approx_chain + matching_p_generic
        matching_p_approx = matching_p_approx_with_approx_chain + matching_p_approx
        matching_p_exact = matching_p_exact_with_approx_chain + matching_p_exact

        # -- then parsers that do not match at all: we can find parsing chains that make them at least match the type
        # we have to reverse it because it was 'best last', now it will be 'best first'
        for parser in reversed(no_match):
            for typ in parser.supported_types:
                for converter in reversed(all_matching_converters):
                    # if converter is able to source from this parser
                    if converter.is_able_to_convert(self.is_strict, from_type=typ, to_type=desired_type):

                        # insert it at the beginning since it should have less priority
                        no_ext_match_but_type_match.insert(0, ParsingChain(parser, converter, strict=self.is_strict,
                                                                           base_parser_chosen_dest_type=typ))

        # Finally sort by chain length
        matching_p_generic = sorted(matching_p_generic, key=methodcaller('size'), reverse=True)
        matching_p_approx = sorted(matching_p_approx, key=methodcaller('size'), reverse=True)
        matching_p_exact = sorted(matching_p_exact, key=methodcaller('size'), reverse=True)

        return (matching_p_generic, matching_p_approx, matching_p_exact), no_type_match_but_ext_match, \
               no_ext_match_but_type_match, no_match

        # # Then iterate one more time to build some parsing chains
        # # parsers = self._parsers
        # converters = self._converters
        #
        # for parser in exact_ext_but_not_type:
        #     # TYPE > no match
        #     # EXT > match
        #     # we can try to create chains to the correct TYPE: for any type this parser supports,
        #     # we will try to create a chain between that intermediate type and the desired type
        #     for intermediate_type in parser.supported_types or {}:
        #         esed, ased, esad, asad = \
        #             ParserRegistryWithConverters.create_all_conversion_chains(intermediate_type, desired_type, converters)
        #         exact_type_chains = (esed + ased)
        #         approx_type_chains = (esad + asad)
        #         for conversion_chain in exact_type_chains:
        #             # TYPE > now, match (exact)
        #             # EXT > still match
        #             exact_type_and_ext_match.append(ParsingChain(base_parser=parser,
        #                                                        base_parser_chosen_dest_type=intermediate_type,
        #                                                        initial_converters=conversion_chain))
        #         for conversion_chain in approx_type_chains:
        #             # TYPE > now, match (approx)
        #             # EXT > still match
        #             approx_type_exact_ext_match.append(ParsingChain(base_parser=parser,
        #                                                        base_parser_chosen_dest_type=intermediate_type,
        #                                                        initial_converters=conversion_chain))
        #
        # for parser in no_type_no_ext:
        #     # TYPE > no match
        #     # EXT > no match
        #     # we can try to create chains to the correct TYPE at least: for any type this parser supports,
        #     # we will try to create a chain between that intermediate type and the desired type
        #     for intermediate_type in parser.supported_types or {}:
        #         esed, ased, esad, asad = \
        #             ParserRegistryWithConverters.create_all_conversion_chains(intermediate_type, desired_type, converters)
        #         exact_type_chains = (esed + ased)
        #         approx_type_chains = (esad + asad)
        #         for conversion_chain in (exact_type_chains + approx_type_chains):
        #             # TYPE > now, match (approx or exact)
        #             # EXT > still no match
        #             approx_type_but_not_ext.append(ParsingChain(base_parser=parser,
        #                                                        base_parser_chosen_dest_type=intermediate_type,
        #                                                        initial_converters=conversion_chain))
        #
        # return exact_type_and_ext_match, approx_type_exact_ext_match, approx_type_but_not_ext, exact_ext_but_not_type, \
        #        no_type_no_ext

    def _complete_parsers_with_converters(self, parser, typ, desired_type, matching_c_generic_to_type,
                                          matching_c_approx_to_type, matching_c_exact_to_type):

        matching_p_generic, matching_p_generic_with_approx_chain, \
        matching_p_approx, matching_p_approx_with_approx_chain,\
        matching_p_exact, matching_p_exact_with_approx_chain = [], [], [], [], [], []

        # ---- Generic converters
        for converter in matching_c_generic_to_type:
            # if the converter can attach to this parser, we have a matching parser !
            # --start from strict
            if converter.is_able_to_convert(True, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=True, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_generic.append(chain)
            elif (not self.strict) and converter.is_able_to_convert(False, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=False, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_generic_with_approx_chain.append(chain)

        # ---- Approx to_type
        for converter in matching_c_approx_to_type:
            # if the converter can attach to this parser, we have a matching parser !
            if converter.is_able_to_convert(True, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=True, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_approx.append(chain)
            elif (not self.strict) and converter.is_able_to_convert(False, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=False, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_approx_with_approx_chain.append(chain)


        # ---- Exact to_type
        for converter in matching_c_exact_to_type:
            # if the converter can attach to this parser, we have a matching parser !
            if converter.is_able_to_convert(True, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=True, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_exact.append(chain)
            elif (not self.strict) and converter.is_able_to_convert(False, from_type=typ, to_type=desired_type)[0]:
                chain = ParsingChain(parser, converter, strict=False, base_parser_chosen_dest_type=typ)
                # insert it at the beginning since it should have less priority
                matching_p_exact_with_approx_chain.append(chain)

        # Preferred is LAST, so approx should be first
        return matching_p_generic_with_approx_chain, matching_p_generic, \
               matching_p_approx_with_approx_chain, matching_p_approx, \
               matching_p_exact_with_approx_chain, matching_p_exact

    # def _complete_parser_with_converters(self, parser, typ, desired_type, matching_c_approx_to_type,
    #                                      matching_c_exact_to_type, matching_c_generic_to_type, matching_p_approx,
    #                                      matching_p_exact, matching_p_generic):
    #     # ---- Generic converters
    #     # now we want "preferred first" : reverse
    #     for converter in reversed(matching_c_generic_to_type):
    #         # if the converter can attach to this parser, we have a matching parser !
    #         if converter.is_able_to_convert(self.is_strict, from_type=typ)[0]:
    #             chain = ParsingChain(parser, converter, strict=self.is_strict, base_parser_chosen_dest_type=typ)
    #             # insert it at the beginning since it should have less priority
    #             if desired_type not in {Any, object}:
    #                 matching_p_generic.insert(0, chain)
    #             else:
    #                 # special case : what is required is Any, so put in exact match
    #                 matching_p_exact.insert(0, chain)
    #     if desired_type not in {Any, object}:
    #         # ---- Approx to_type
    #         for converter in reversed(matching_c_approx_to_type):
    #             # if the converter can attach to this parser, we have a matching parser !
    #             if converter.is_able_to_convert(self.is_strict, from_type=typ)[0]:
    #                 chain = ParsingChain(parser, converter, strict=self.is_strict, base_parser_chosen_dest_type=typ)
    #                 # insert it at the beginning since it should have less priority
    #                 matching_p_approx.insert(0, chain)
    #
    #         # ---- Exact to_type
    #         for converter in reversed(matching_c_exact_to_type):
    #             # if the converter can attach to this parser, we have a matching parser !
    #             if converter.is_able_to_convert(self.is_strict, from_type=typ)[0]:
    #                 chain = ParsingChain(parser, converter, strict=self.is_strict, base_parser_chosen_dest_type=typ)
    #                 # insert it at the beginning since it should have less priority
    #                 matching_p_exact.insert(0, chain)

    # def get_all_conversion_chains(self, source_type: Type[S], destination_type: Type[T]) -> List[List[Converter]]:
    #     """
    #     Implementation of ConversionFinder API
    #     """
    #     return ParserRegistryWithConverters.create_all_conversion_chains(source_type, destination_type,
    #                                                                      self._converters)

    # @staticmethod
    # def create_all_conversion_chains(source_type: Type[S], destination_type: Type[T],
    #                                  available_converters: List[Converter], initial_call = True) -> List[List[Converter]]:
    #     """
    #     Recursive method to find all conversion chains between a source type and a destination type using the available
    #     converters.
    #     :param source_type:
    #     :param destination_type:
    #     :param available_converters:
    #     :return:
    #     """
    #
    #     check_var(source_type, var_types=type, var_name='source_type')
    #     #check_var(destination_type, var_types=type, var_name='destination_type')
    #     check_var(available_converters, var_types=list, var_name='available_converters')
    #
    #     if initial_call:
    #         # start from the end.
    #         available_converters = list(reversed(available_converters))
    #
    #     # init
    #     exact_source_and_dest_match = [] if (source_type is not None) else None
    #     approx_source_exact_dest_match = [] if (source_type is not None) else None
    #     exact_source_approx_dest_match = [] if (source_type is not None) else None
    #     approx_source_approx_dest_match = [] if (source_type is not None) else None
    #
    #     #no_source_exact_dest_match = [] if destination_type is not None else None
    #     #exact_source_no_dest_match = [] if source_type is not None else None
    #     #approx_source_no_dest_match = [] if source_type is not None else None
    #     #remaining = []
    #
    #
    #     for conv in available_converters:
    #         if (source_type is not None):
    #             # if (destination_type is not None):
    #             # SOURCE > exact
    #             # DEST > exact
    #             if ParserRegistryWithConverters._converter_matches(conv, destination_type, source_type,
    #                                                                exact_source_type_match=True,
    #                                                                exact_dest_type_match=True):
    #                 # create a conversion chain that contains only this converter
    #                 exact_source_and_dest_match.append([conv])
    #
    #             # SOURCE > approx
    #             # DEST > exact
    #             elif ParserRegistryWithConverters._converter_matches(conv, destination_type, source_type,
    #                                                                  exact_source_type_match=False,
    #                                                                  exact_dest_type_match=True):
    #                 # create a conversion chain that contains only this converter
    #                 approx_source_exact_dest_match.append([conv])
    #
    #             # SOURCE > exact
    #             # DEST > approx
    #             elif ParserRegistryWithConverters._converter_matches(conv, destination_type, source_type,
    #                                                                  exact_source_type_match=True,
    #                                                                  exact_dest_type_match=False):
    #                 # create a conversion chain that contains only this converter
    #                 exact_source_approx_dest_match.append([conv])
    #
    #             # SOURCE > approx
    #             # DEST > approx
    #             elif ParserRegistryWithConverters._converter_matches(conv, destination_type, source_type,
    #                                                                  exact_source_type_match=False,
    #                                                                  exact_dest_type_match=False):
    #                 # create a conversion chain that contains only this converter
    #                 approx_source_approx_dest_match.append([conv])
    #
    #             # SOURCE > exact
    #             # DEST > NO MATCH
    #             elif ParserRegistryWithConverters._converter_matches(conv, None, source_type,
    #                                                                exact_source_type_match=True):
    #                 # append all conversion chains that can be successfully created from this converter to the
    #                 # destination_type, without itself
    #                 remaining_cvrtrs = available_converters.copy()
    #                 remaining_cvrtrs.remove(conv)  # list(set(available_converters) - {conv})
    #
    #                 esed, ased, esad, asad = \
    #                     ParserRegistryWithConverters.create_all_conversion_chains(source_type,
    #                                                                               conv.from_type,
    #                                                                               remaining_cvrtrs,
    #                                                                               initial_call=False
    #                                                                               )
    #                 for conversion_chain in (esed + ased):
    #                     conversion_chain.append(conv)
    #                     exact_source_and_dest_match.append(conversion_chain)
    #
    #                 for conversion_chain in (esad + asad):
    #                     conversion_chain.append(conv)
    #                     exact_source_approx_dest_match.append(conversion_chain)
    #
    #
    #             # SOURCE > approx
    #             # DEST > NO MATCH
    #             elif ParserRegistryWithConverters._converter_matches(conv, None, source_type,
    #                                                                  exact_source_type_match=False):
    #
    #                 # append all conversion chains that can be successfully created from this converter to the
    #                 # destination_type, without itself
    #                 remaining_cvrtrs = available_converters.copy()
    #                 remaining_cvrtrs.remove(conv)  # list(set(available_converters) - {conv})
    #
    #                 esed, ased, esad, asad = \
    #                     ParserRegistryWithConverters.create_all_conversion_chains(source_type,
    #                                                                           conv.from_type,
    #                                                                           remaining_cvrtrs,
    #                                                                           initial_call=False
    #                                                                           )
    #                 for conversion_chain in (esed + ased):
    #                     conversion_chain.append(conv)
    #                     approx_source_exact_dest_match.append(conversion_chain)
    #
    #                 for conversion_chain in (esad + asad):
    #                     conversion_chain.append(conv)
    #                     approx_source_approx_dest_match.append(conversion_chain)
    #
    #             else:
    #                 # no match on source at all
    #                 pass
    #
    #             # # No match
    #             # else:
    #             #     if ParserRegistryWithConverters._converter_matches(conv, None, source_type,
    #             #                                                        exact_source_type_match=True):
    #             #
    #             #     elif ParserRegistryWithConverters._converter_matches(conv, None, source_type,
    #             #                                                        exact_source_type_match=True):
    #             #
    #             #     else:
    #             #         # no match on source at all
    #             #         pass
    #         else:
    #             # source_type is None
    #             raise NotImplementedError('')
    #
    #     return exact_source_and_dest_match, approx_source_exact_dest_match, \
    #            exact_source_approx_dest_match, approx_source_approx_dest_match
    #
    # @staticmethod
    # def _converter_matches(converter: Converter[S, T], destination_type: Type[T], source_type: Type[T] = None,
    #                        exact_source_type_match: bool = True, exact_dest_type_match: bool = True):
    #     """
    #     Inner method to test if a converter matches the requirements specified
    #
    #     :param converter:
    #     :param destination_type:
    #     :param source_type:
    #     :param exact_source_type_match:
    #     :return:
    #     """
    #
    #     check_var(converter, var_types=Converter, var_name='converter')
    #
    #     if destination_type is not None:
    #         # First remove any customization from the typing module
    #         destination_type = get_base_generic_type(destination_type)
    #
    #     # does the converter support that type ?
    #     # (None means all)
    #     if destination_type is None \
    #             or (exact_dest_type_match and (converter.to_type is None or destination_type is converter.to_type)) \
    #             or (not exact_dest_type_match and (converter.to_type is not None and
    #                                                    issubclass(converter.to_type, destination_type))):
    #
    #         # (None means all)
    #         if source_type is None \
    #                 or (exact_source_type_match and (source_type is converter.from_type)) \
    #                 or (not exact_source_type_match and (issubclass(source_type, converter.from_type))):
    #             return True
    #
    #     return False



    # def _register_converters(self, converters:Dict[Type[T], Dict[Type[S], Converter[S, T]]]):
    #     """
    #     Registers the provided converters (a dictionary)
    #     :param converters:
    #     :return:
    #     """
    #     check_var(converters, var_types=dict)
    #
    #     # don't use dict.update because we want to perform sanity checks here
    #     for to_type, converters_to_this_type in converters.items():
    #         for from_type, converter in converters_to_this_type.items():
    #             self.register_converter(from_type, to_type, converter)
    #     return
    #
    # def _register_converter_for_type(self, from_type: Type[S], to_type: Type[T], converter: Converter[S, T]):
    #     """
    #     To register a single converter from one object type to another.
    #
    #     :param from_type:
    #     :param to_type:
    #     :param converter:
    #     :return:
    #     """
    #     check_var(from_type, var_types=type)
    #     check_var(to_type, var_types=type)
    #     check_var(converter, var_types=Converter)
    #
    #     self._types_lock.acquire()
    #     try:
    #         if to_type in self.__converters_by_dest_type.keys():
    #             if from_type in self.__converters_by_dest_type[to_type]:
    #                 warn('Warning : overriding existing converter from type ' + str(from_type) + ' to type ' +
    #                      str(to_type))
    #             self.__converters_by_dest_type[to_type][from_type] = converter
    #         else:
    #             self.__converters_by_dest_type[to_type] = {from_type: converter}
    #     finally:
    #         self._types_lock.release()
    #     return
    #
    # def get_converters_copy(self) -> Dict[Type[T], Dict[S, Dict[str, Converter[S, T]]]]:
    #     """
    #     Returns a deep copy of the converters dictionary
    #     :return:
    #     """
    #     return deepcopy(self.__converters_by_dest_type)



    # def get_all_known_parsing_chains(self):
    #     """
    #     Utility method to return all known parsing chains that can be made for that object type,
    #     using registered parsers and converters
    #     :return: a dictionary of object_type
    #     """
    #     return {type: self.get_all_known_parsing_chains_for_type(type)
    #             for type in list(self._typed_parsers_by_type.keys()) + list(self.__converters_by_dest_type.keys())}
    #
    # def get_all_parsing_chains_for_type(self, item_type: Type[T]) \
    #         -> Dict[str, ParsingChain[T]]:
    #     """
    #     Utility method to return the parsing_chain associated to a given type. A dictionary extension > parsing_chain
    #
    #     :param item_type:
    #     :return: the dictionary of (source_type, converter) for the given type
    #     """
    #
    #     return ParserRegistryWithConverters.create_all_parsing_chains_for_type(item_type, self._typed_parsers_by_type,
    #                                                                         self.__converters_by_dest_type)
    #
    # @staticmethod
    # def create_all_parsing_chains_for_type(item_type: Type[T],
    #                                        parsers: Dict[Type[T], Dict[str, AnyParser[T]]],
    #                                        converters: Dict[Type[T], Dict[S, Converter[S, T]]],
    #                                        error_if_not_found: bool = True) \
    #         -> Dict[str, ParsingChain[T]]:
    #     """
    #     Utility method to return parsing chains associated to a given type, by combining all base parsers and converters.
    #     This method is recursive.
    #     A dictionary extension > parsing_chain is returned.
    #
    #     :param item_type:
    #     :param parsers:
    #     :param converters:
    #     :param error_if_not_found:
    #     :return: the dictionary of (source_type, converter) for the given type
    #     """
    #
    #     # First collect all basic parsers that are able to directly read that type
    #     try:
    #
    #         parsing_chains = {ext: ParsingChain(parser)
    #                           for ext, parser in parsers[item_type].items()}
    #     except KeyError:
    #         if error_if_not_found:
    #             raise NoParserFoundForObjectType.create(item_type)
    #
    #     # Then add all converters for which a conversion chain ending with a parser can be found
    #     try:
    #         converters_to_type = converters[item_type]
    #         for source_type, converter in converters_to_type.items():
    #             # recurse to find a parsing chain up to source_type
    #             subchains = create_all_parsing_chains_for_type(source_type, parsers, converter,
    #                                                            error_if_not_found=False)
    #             for ext, subchain in subchains.items():
    #                 if ext not in parsing_chains:
    #                     # add the chain to the result set (dont forget to add the converter)
    #                     parsing_chains[ext] = subchain.add_conversion_step(source_type, item_type, converter)
    #                 else:
    #                     # we already know how to parse item_type from this extension. Is the new solution better ?
    #                     if parsing_chains[ext].chain_length() > (subchain.chain_length() + 1):
    #                         # we found a shorter conversion chain to get the same result ! Use it
    #                         parsing_chains[ext] = subchain.add_conversion_step(source_type, item_type, converter)
    #     except KeyError:
    #         # ignore: that means that there was no converter at all for this type
    #         pass
    #
    #     return parsing_chains




