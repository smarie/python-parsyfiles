from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from io import StringIO
from logging import Logger
from pprint import pprint
from typing import Type, Dict, Any, List, Set, Tuple, Union, Mapping, AbstractSet, Sequence, Iterable
from warnings import warn

from parsyfiles.converting_core import S, Converter, ConversionChain, is_any_type, get_validated_type, JOKER, \
    ConversionException
from parsyfiles.filesystem_mapping import PersistedObject
from parsyfiles.parsing_combining_parsers import ParsingChain, CascadingParser, DelegatingParser, \
    print_error_to_io_stream
from parsyfiles.parsing_core import _InvalidParserException
from parsyfiles.parsing_core_api import Parser, ParsingPlan, T
from parsyfiles.type_inspection_tools import get_pretty_type_str, get_base_generic_type, get_pretty_type_keys_dict, \
    robust_isinstance, is_collection, _extract_collection_base_type, is_typed_collection, resolve_union_and_typevar
from parsyfiles.var_checker import check_var


class ParserFinder(metaclass=ABCMeta):
    """
    Abstract class representing something able to find a parser for a given object
    """

    @abstractmethod
    def build_parser_for_fileobject_and_desiredtype(self, obj_on_filesystem: PersistedObject, object_type: Type[T],
                                                    logger: Logger = None) -> Parser:
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
    def create(obj: PersistedObject, obj_type: Type[T], extensions_supported: Iterable[str]):
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
            msg += ' If you wish to parse this fileobject in that type, you may replace the file with any of the ' \
                   'following extensions currently supported :' + str(extensions_supported) + ' (see ' \
                   'get_capabilities_for_type(' + get_pretty_type_str(obj_type) + ', strict_type_matching=False) for ' \
                   'details).\n' \
                   + 'Otherwise, please register a new parser for type ' + get_pretty_type_str(obj_type) \
                   + ' and extension ' + obj.get_pretty_file_ext()
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
    def create(obj: PersistedObject, obj_type: Type[T], types_supported: Iterable[str]):
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


class NoParserFoundForUnionType(Exception):
    """
    Raised whenever a union object can not be parsed because no parser was found for each alternative
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(NoParserFoundForUnionType, self).__init__(contents)

    @staticmethod
    def create(obj: PersistedObject, obj_type: Type[T], errors: Dict[Type, Exception]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param obj:
        :param errors: a dictionary of the errors raised for each alternate type tried
        :return:
        """

        e = NoParserFoundForUnionType('{obj} cannot be parsed as a {typ} because no parser could be found for any of '
                                      'the alternate types. Caught exceptions: {errs}'
                                      ''.format(obj=obj, typ=get_pretty_type_str(obj_type), errs=errors))

        # save the errors
        e.errors = errors

        return e


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
    def register_parsers(self, parsers: List[Parser]):
        """
        Utility method to register any list of parsers.
        :return:
        """
        check_var(parsers, var_types=list, var_name='parsers')
        for parser in parsers:
            self.register_parser(parser)

    @abstractmethod
    def register_parser(self, parser: Parser):
        pass

    @abstractmethod
    def get_all_parsers(self, strict_type_matching: bool) -> List[Parser]:
        pass

    def print_capabilities_by_ext(self, strict_type_matching: bool = False):
        """
        Used to print the list of all file extensions that can be parsed by this parser registry.
        :return:
        """
        print('\nCapabilities by file extension: ')
        l = self.get_capabilities_by_ext(strict_type_matching=strict_type_matching)
        pprint({ext: get_pretty_type_keys_dict(parsers) for ext, parsers in l.items()})
        print('\n')

    def print_capabilities_by_type(self, strict_type_matching: bool = False):
        """
        Used to print the list of all file extensions that can be parsed by this parser registry.
        :return:
        """
        print('\nCapabilities by object type: ')
        l = self.get_capabilities_by_type(strict_type_matching=strict_type_matching)
        pprint({get_pretty_type_str(typ): parsers for typ, parsers in l.items()})
        print('\n')

    def get_all_supported_types_pretty_str(self) -> Set[str]:
        return {get_pretty_type_str(typ) for typ in self.get_all_supported_types()}

    def get_capabilities_by_type(self, strict_type_matching: bool = False) -> Dict[Type, Dict[str, Dict[str, Parser]]]:
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
        for typ in self.get_all_supported_types():
            res[typ] = self.get_capabilities_for_type(typ, strict_type_matching)

        return res

    def print_capabilities_for_type(self, typ, strict_type_matching: bool = False):
        pprint(self.get_capabilities_for_type(typ, strict_type_matching=strict_type_matching))

    def get_capabilities_for_type(self, typ, strict_type_matching: bool = False) -> Dict[str, Dict[str, Parser]]:
        """
        Utility method to return, for a given type, all known ways to parse an object of this type, organized by file
        extension.

        :param typ:
        :param strict_type_matching:
        :return:
        """
        r = dict()
        # For all extensions that are supported,
        for ext in self.get_all_supported_exts():
            # Use the query to fill
            matching = self.find_all_matching_parsers(strict_type_matching, desired_type=typ, required_ext=ext)[0]
            # matching_list = matching[0] + matching[1] + matching[2]
            # insert_element_to_dict_of_dicts_of_list(res, typ, ext, list(reversed(matching_list)))
            r[ext] = dict()
            exact = list(reversed(matching[2]))
            if len(exact) > 0:
                r[ext]['1_exact_match'] = exact

            approx = list(reversed(matching[1]))
            if len(approx) > 0:
                r[ext]['2_approx_match'] = approx

            generic = list(reversed(matching[0]))
            if len(generic) > 0:
                r[ext]['3_generic'] = generic

            # insert_element_to_dict_of_dicts(res, typ, ext, matching_dict)
        return r

    def get_capabilities_by_ext(self, strict_type_matching: bool = False) -> Dict[str, Dict[Type, Dict[str, Parser]]]:
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
        for ext in self.get_all_supported_exts_for_type(type_to_match=JOKER, strict=strict_type_matching):
            res[ext] = self.get_capabilities_for_ext(ext, strict_type_matching)

        return res

    def print_capabilities_for_ext(self, ext, strict_type_matching: bool = False):
        pprint(get_pretty_type_keys_dict(self.get_capabilities_for_ext(ext, strict_type_matching)))

    def get_capabilities_for_ext(self, ext, strict_type_matching: bool = False) -> Dict[Type, Dict[str, Parser]]:
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
            r[typ] = dict()
            exact = list(reversed(matching[2]))
            if len(exact) > 0:
                r[typ]['1_exact_match'] = exact

            approx = list(reversed(matching[1]))
            if len(approx) > 0:
                r[typ]['2_approx_match'] = approx

            generic = list(reversed(matching[0]))
            if len(generic) > 0:
                r[typ]['3_generic'] = generic

            # insert_element_to_dict_of_dicts(res, ext, typ, matching_dict)
        return r

    def get_all_supported_types(self, strict_type_matching: bool = False) -> Set[Type]:
        # note: we have to keep strict_type_matching for conversion chains... ?
        return self.get_all_supported_types_for_ext(ext_to_match=JOKER, strict_type_matching=strict_type_matching)

    @abstractmethod
    def get_all_supported_types_for_ext(self, ext_to_match: str, strict_type_matching: bool = False) -> Set[Type]:
        pass

    def get_all_supported_exts(self) -> Set[str]:
        # no need to use strict = False here - we just want a list of extensions :)
        return self.get_all_supported_exts_for_type(type_to_match=JOKER, strict=True)

    @abstractmethod
    def get_all_supported_exts_for_type(self, type_to_match: Type[Any], strict: bool) -> Set[str]:
        pass

    @abstractmethod
    def register_parser(self, parser: Parser):
        """
        Method used to register a parser in the registry

        :param parser:
        :return:
        """
        pass

    @abstractmethod
    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = JOKER, required_ext: str = JOKER) \
            -> Tuple[List[Parser], List[Parser], List[Parser], List[Parser]]:
        """
        Main method to find parsers matching a query. Its first output is made of three lists without duplicates:
        - first the generic ones, from first registered to last registered
        - then the specific ones approximately matching the required type (from first registered to last reg)
        - then the specific ones, from first registered to last registered
        each list should be ordered from less relevant (first) to most relevant (last).

        This function also outputs 3 other lists that correspond to parsers that don't match the query:
        - the list of parsers matching the type but not the extension
        - the list of parsers matching the extension but not the type,
        - the list of remaining parsers (no match at all)

        WARNING: the order of parsers in lists is the opposite of the order in get_capabilities_for_type and
        get_capabilities_for_ext methods

        :param strict:
        :param desired_type: a type of object to parse, or JOKER for 'wildcard'(*) .
        WARNING: "object_type=AnyObject/object/Any)"
        means "all parsers able to parse anything", which is different from "object_type=JOKER" which means "all parsers".
        :param required_ext: a specific extension to parse, or JOKER for 'wildcard'(*)
        :return: a tuple: [matching parsers(*), parsers matching type but not ext, parsers matching ext but not type,
        parsers not matching at all]. (*) matching parsers is actually a tuple : (matching_parsers_generic,
        matching_parsers_approx, matching_parsers_exact), each list from less relevant to most relevant.
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

        # new attempt: simply store the list of supported types and exts
        self._strict_types_to_ext = dict()
        self._ext_to_strict_types = dict()

    def register_parser(self, parser: Parser):
        """
        Utility method to register any parser. Parsers that support any type will be stored in the "generic"
        list, and the others will be stored in front of the types they support
        :return:
        """
        check_var(parser, var_types=Parser, var_name='parser')
        if (not parser.supports_multifile()) and (not parser.supports_singlefile()):
            # invalid
            raise _InvalidParserException.create(parser)

        # (0) sanity check : check that parser handles jokers properly
        res = parser.is_able_to_parse_detailed(desired_type=JOKER, desired_ext=JOKER, strict=True)
        if not (res[0] is True and res[1] is None):
            raise ValueError('Parser ' + str(parser) + ' can not be registered since it does not handle the JOKER cases '
                             'correctly')

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

    def get_all_parsers(self, strict_type_matching: bool = False) -> List[Parser]:
        """
        Returns the list of all parsers in order of relevance.
        :return:
        """
        matching = self.find_all_matching_parsers(strict=strict_type_matching)[0]

        # matching[1] (approx match) is supposed to be empty since we use a joker on type and a joker on ext : only
        # exact and generic match should exist, no approx match
        if len(matching[1]) > 0:
            raise Exception('Internal error - this matching[1] list is supposed to be empty for such a query')
        return matching[0] + matching[2]

    def get_all_supported_types_for_ext(self, ext_to_match: str, strict_type_matching: bool = False) -> Set[Type]:
        """
        Utility method to return the set of all supported types that may be parsed from files with the given extension.
        ext=JOKER is a joker that means all extensions

        :param ext_to_match:
        :param strict_type_matching:
        :return:
        """
        matching = self.find_all_matching_parsers(required_ext=ext_to_match, strict=strict_type_matching)[0]
        return {typ for types in [p.supported_types for p in (matching[0] + matching[1] + matching[2])]
                for typ in types}

    def get_all_supported_exts_for_type(self, type_to_match: Type[Any], strict: bool) -> Set[str]:
        """
        Utility method to return the set of all supported file extensions that may be converted to objects of the given
        type. type=JOKER is a joker that means all types

        :param type_to_match:
        :param strict:
        :return:
        """
        matching = self.find_all_matching_parsers(desired_type=type_to_match, strict=strict)[0]
        return {ext for exts in [p.supported_exts for p in (matching[0] + matching[1] + matching[2])]
                for ext in exts}

    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = JOKER, required_ext: str = JOKER) \
            -> Tuple[Tuple[List[Parser], List[Parser], List[Parser]],
                     List[Parser], List[Parser], List[Parser]]:
        """
        Implementation of the parent method by lookin into the registry to find the most appropriate parsers to use in
        order

        :param strict:
        :param desired_type: the desired type, or 'JOKER' for a wildcard
        :param required_ext:
        :return: match=(matching_parsers_generic, matching_parsers_approx, matching_parsers_exact),
                 no_type_match_but_ext_match, no_ext_match_but_type_match, no_match
        """

        # if desired_type is JOKER and required_ext is JOKER:
        #     # Easy : return everything (GENERIC first, SPECIFIC then) in order (make a copy first :) )
        #     matching_parsers_generic = self._generic_parsers.copy()
        #     matching_parsers_approx = []
        #     matching_parsers_exact = self._specific_parsers.copy()
        #     no_type_match_but_ext_match = []
        #     no_ext_match_but_type_match = []
        #     no_match = []
        # else:
        #
        # Although the above could be thought as an easy way to accelerate the process, it does not any more since the
        # JOKER  special cases are handled in parser.is_able_to_parse and converter.is_able_to_convert functions.
        #
        # It was also dangerous since it prevented us to get consistency across views - hence parser/converter
        # implementors could get the feeling that their parser was correctly registered where it wasn't

        check_var(strict, var_types=bool, var_name='strict')
        # first transform any 'Any' type requirement into the official class for that
        desired_type = get_validated_type(desired_type, 'desired_type', enforce_not_joker=False)

        matching_parsers_generic = []
        matching_parsers_approx = []
        matching_parsers_exact = []
        no_type_match_but_ext_match = []
        no_ext_match_but_type_match = []
        no_match = []

        # handle generic parsers first - except if desired type is Any
        for p in self._generic_parsers:
            match = p.is_able_to_parse(desired_type=desired_type, desired_ext=required_ext, strict=strict)
            if match:
                # match
                if is_any_type(desired_type):
                    # special case : what is required is Any, so put in exact match
                    matching_parsers_exact.append(p)
                else:
                    matching_parsers_generic.append(p)

            else:
                # type matches always
                no_ext_match_but_type_match.append(p)

        # then the specific
        for p in self._specific_parsers:
            match, exact_match = p.is_able_to_parse_detailed(desired_type=desired_type,
                                                             desired_ext=required_ext,
                                                             strict=strict)
            if match:
                if is_any_type(desired_type):
                    # special case: dont register as a type match
                    no_type_match_but_ext_match.append(p)
                else:
                    if exact_match is None or exact_match:
                        matching_parsers_exact.append(p)
                    else:
                        matching_parsers_approx.append(p)

            else:
                # try to set the type to a supported type to see if that makes a match
                if p.is_able_to_parse(desired_type=JOKER, desired_ext=required_ext, strict=strict):
                    no_type_match_but_ext_match.append(p)

                # try to set the ext to a supported ext to see if that makes a match
                elif p.is_able_to_parse(desired_type=desired_type, desired_ext=JOKER, strict=strict):
                    no_ext_match_but_type_match.append(p)

                # no match at all
                else:
                    no_match.append(p)

        return (matching_parsers_generic, matching_parsers_approx, matching_parsers_exact), \
               no_type_match_but_ext_match, no_ext_match_but_type_match, no_match


class ParserRegistry(ParserCache, ParserFinder, DelegatingParser):
    """
    A manager of specific and generic parsers
    """

    def __init__(self, pretty_name: str, strict_matching: bool, initial_parsers_to_register: List[Parser] = None):
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

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                             log_only_last: bool = False) -> ParsingPlan[T]:
        """
        Implementation of Parser API
        Relies on the underlying registry of parsers to provide the best parsing plan
        :param desired_type:
        :param filesystem_object:
        :param logger:
        :param log_only_last: a flag to only log the last part of the file path (default False)
        :return:
        """
        # find the parser for this object
        t, combined_parser = self.build_parser_for_fileobject_and_desiredtype(filesystem_object, desired_type,
                                                                           logger=logger)
        # ask the parser for the parsing plan
        return combined_parser.create_parsing_plan(t, filesystem_object, logger)

    def build_parser_for_fileobject_and_desiredtype(self, obj_on_filesystem: PersistedObject, object_type: Type[T],
                                                    logger: Logger = None) -> Tuple[Type, Parser]:
        """
        Builds from the registry, a parser to parse object obj_on_filesystem as an object of type object_type.

        To do that, it iterates through all registered parsers in the list in reverse order (last inserted first),
        and checks if they support the provided object format (single or multifile) and type.
        If several parsers match, it returns a cascadingparser that will try them in order.

        If several alternatives are requested (through a root Union type), this is done independently for each
        alternative.

        :param obj_on_filesystem:
        :param object_type:
        :param logger:
        :return: a type to use and a parser. The type to use is either directly the one provided, or a resolved one in
        case of TypeVar
        """
        # First resolve TypeVars and Unions to get a list of compliant types
        object_types = resolve_union_and_typevar(object_type)

        if len(object_types) == 1:
            # One type: proceed as usual
            return object_types[0], self._build_parser_for_fileobject_and_desiredtype(obj_on_filesystem,
                                                                                      object_typ=object_types[0],
                                                                                      logger=logger)
        else:
            # Several types are supported: try to build a parser for each
            parsers = OrderedDict()
            errors = dict()
            for typ in object_types:
                try:
                    parsers[typ] = self._build_parser_for_fileobject_and_desiredtype(obj_on_filesystem, object_typ=typ,
                                                                                     logger=logger)
                except NoParserFoundForObjectExt as e:
                    warn(e)
                    errors[e] = e
                except NoParserFoundForObjectType as f:
                    warn(f)
                    errors[f] = f

            # Combine if there are remaining, otherwise raise
            if len(parsers) > 0:
                return object_type, CascadingParser(parsers)
            else:
                raise NoParserFoundForUnionType.create(obj_on_filesystem, object_type, errors)

    def _build_parser_for_fileobject_and_desiredtype(self, obj_on_filesystem: PersistedObject, object_typ: Type[T],
                                                    logger: Logger = None) -> Parser:
        """
        Builds from the registry, a parser to parse object obj_on_filesystem as an object of type object_type.

        To do that, it iterates through all registered parsers in the list in reverse order (last inserted first),
        and checks if they support the provided object format (single or multifile) and type.
        If several parsers match, it returns a cascadingparser that will try them in order.

        :param obj_on_filesystem:
        :param object_typ:
        :param logger:
        :return:
        """

        # first remove any non-generic customization
        object_type = get_base_generic_type(object_typ)

        # find all matching parsers for this
        matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match = \
            self.find_all_matching_parsers(strict=self.is_strict, desired_type=object_type, required_ext=obj_on_filesystem.ext)
        matching_parsers = matching[0] + matching[1] + matching[2]

        if len(matching_parsers) == 0:
            # No match. Do we have a close match ? (correct type, but not correct extension ?)
            if len(no_ext_match_but_type_match) > 0:
                raise NoParserFoundForObjectExt.create(obj_on_filesystem, object_type,
                                                       set([ext_ for ext_set in
                                                        [p.supported_exts for p in no_ext_match_but_type_match]
                                                        for ext_ in ext_set]))
            else:
                # no, no match at all
                raise NoParserFoundForObjectType.create(obj_on_filesystem, object_type,
                                                        set([typ_ for typ_set in
                                                        [p.supported_types for p in no_type_match_but_ext_match]
                                                        for typ_ in typ_set]))

        elif len(matching_parsers) == 1:
            # return the match directly
            return matching_parsers[0]
        else:
            # return a cascade of all parsers, in reverse order (since last is our preferred one)
            # print('----- WARNING : Found several parsers able to parse this item. Combining them into a cascade.')
            return CascadingParser(list(reversed(matching_parsers)))


class AttrConversionException(ConversionException):
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
        super(AttrConversionException, self).__init__(contents)

    @staticmethod
    def create(att_name: str, parsed_att: S, attribute_type: Type[T], caught_exec: Dict[Converter[S, T], Exception]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param att_name:
        :param parsed_att:
        :param attribute_type:
        :param caught_exec:
        :return:
        """
        base_msg = 'Error while trying to convert parsed attribute value for attribute \'' + str(att_name) + '\' : \n' \
                   + '   - parsed value is : \'' + str(parsed_att) + '\' of type \'' + get_pretty_type_str(type(parsed_att)) + '\'\n' \
                   + '   - attribute type required by object constructor is \'' + get_pretty_type_str(attribute_type) \
                   + '\' \n'

        msg = StringIO()
        if len(list(caught_exec.keys())) > 0:
            msg.writelines('   - converters tried are : \n      * ')
            msg.writelines('\n      * '.join([str(converter) for converter in caught_exec.keys()]))
            msg.writelines(' \n Caught the following exceptions: \n')

            for converter, err in caught_exec.items():
                msg.writelines('--------------- From ' + str(converter) + ' caught: \n')
                print_error_to_io_stream(err, msg)
                msg.write('\n')

        return AttrConversionException(base_msg + msg.getvalue())


class NoConverterFoundForObjectType(Exception):
    """
    Raised whenever no ConversionFinder has been provided, while a dictionary value needs conversion to be used as an
     object constructor attribute
    """

    def __init__(self, contents: str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(NoConverterFoundForObjectType, self).__init__(contents)

    @staticmethod
    def create(conversion_finder, parsed_att: Any, attribute_type: Type[Any], errors: Dict[Type, Exception] = None):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parsed_att:
        :param attribute_type:
        :param conversion_finder:
        :return:
        """
        if conversion_finder is None:
            msg = "No conversion finder provided to find a converter between parsed attribute '{patt}' of type " \
                  "'{typ}' and expected type '{expt}'.".format(patt=str(parsed_att),
                                                               typ=get_pretty_type_str(type(parsed_att)),
                                                               expt=get_pretty_type_str(attribute_type))
        else:
            msg = "No conversion chain found between parsed attribute '{patt}' of type '{typ}' and expected type " \
                  "'{expt}' using conversion finder {conv}.".format(patt=parsed_att,
                                                                    typ=get_pretty_type_str(type(parsed_att)),
                                                                    expt=get_pretty_type_str(attribute_type),
                                                                    conv=conversion_finder)
        if errors is not None:
            msg = msg + ' ' + str(errors)

        return NoConverterFoundForObjectType(msg)


# def _handle_from_type_wildcard(desired_from_type: Optional[Type], c: Converter):
#     return desired_from_type or c.from_type
# 
# 
# def _handle_to_type_wildcard(desired_type: Optional[Type], c: Converter):
#     return desired_type or c.to_type


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
    def get_all_conversion_chains(self, from_type: Type[Any] = JOKER, to_type: Type[Any] = JOKER)\
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find all converters or conversion chains matching the provided query.

        :param from_type: a required type of input object, or JOKER for 'wildcard'(*) .
        WARNING: "from_type=AnyObject/object/Any" means
        "all converters able to source from anything", which is different from "from_type=JOKER" which means "all
        converters whatever their source type".
        :param to_type: a required type of output object, or JOKER for 'wildcard'(*) .
        WARNING: "to_type=AnyObject/object/Any" means "all
        converters able to produce any type of object", which is different from "to_type=JOKER" which means "all
        converters whatever type they are able to produce".
        :return: a tuple of lists of matching converters, by type of *dest_type* match : generic, approximate, exact
        """
        pass

    def find_and_convert(self, attr_name: str, attr_value: S, desired_attr_type: Type[T], logger: Logger,
                         options: Dict[str, Dict[str, Any]]) -> T:
        """
        Utility method to convert some value into the desired type. It relies on get_all_conversion_chains to find the
        converters, and apply them in correct order
        :return:
        """

        if robust_isinstance(attr_value, desired_attr_type) and not is_collection(desired_attr_type):
            # value is already of the correct type
            return attr_value

        else:
            # try to find conversion chains
            generic, approx, exact = self.get_all_conversion_chains(type(attr_value), desired_attr_type)
            all_chains = generic + approx + exact

            if len(all_chains) > 0:
                all_errors = dict()
                for chain in reversed(all_chains):
                    try:
                        return chain.convert(desired_attr_type, attr_value, logger, options)
                    except Exception as e:
                        all_errors[chain] = e
                raise AttrConversionException.create(attr_name, attr_value, desired_attr_type, all_errors)

            else:
                # did not find any conversion chain
                raise NoConverterFoundForObjectType.create(self, attr_value, desired_attr_type)

    @staticmethod
    def convert_collection_values_according_to_pep(coll_to_convert: Union[Dict, List, Set, Tuple],
                                                   desired_type: Type[T],
                                                   conversion_finder: 'ConversionFinder', logger: Logger, **kwargs) \
            -> T:
        """
        Helper method to convert the values of a collection into the required (pep-declared) value type in desired_type.
        If desired_type does not explicitly mention a type for its values, the collection will be returned as is, otherwise
        a  copy will be created and filled with conversions of the values, performed by the provided conversion_finder

        :param coll_to_convert:
        :param desired_type:
        :param conversion_finder:
        :param logger:
        :param kwargs:
        :return:
        """
        base_desired_type = get_base_generic_type(desired_type)

        if issubclass(base_desired_type, Mapping):  # or issubclass(base_desired_type, dict):
            # get the base collection type if provided (this raises an error if key type is not str)
            item_typ, _ = _extract_collection_base_type(desired_type, exception_if_none=False)

            if item_typ is None:
                # nothing is required in terms of dict values: use the base method
                return ConversionFinder.try_convert_value(conversion_finder, '', coll_to_convert, desired_type,
                                                          logger=logger, options=kwargs)
            else:
                # TODO resuse appropriate container type (not necessary a dict) according to type of coll_to_convert
                # there is a specific type required for the dict values.
                res = dict()
                # convert if required
                for key, val in coll_to_convert.items():
                    res[key] = ConversionFinder.try_convert_value(conversion_finder, '', val, item_typ, logger,
                                                                  options=kwargs)
                return res

        elif issubclass(base_desired_type, Sequence):  # or issubclass(base_desired_type, list):
            # get the base collection type if provided
            item_typ, _ = _extract_collection_base_type(desired_type, exception_if_none=False)

            if item_typ is None:
                # nothing is required in terms of dict values: use the base method
                return ConversionFinder.try_convert_value(conversion_finder, '', coll_to_convert, desired_type,
                                                          logger=logger, options=kwargs)
            else:
                # TODO resuse appropriate container type (not necessary a list) according to type of coll_to_convert
                # there is a specific type required for the list values.
                res = list()

                # special case where base_desired_type is a Tuple: in that case item_typ may be a tuple or else
                if type(item_typ) != tuple:
                    # convert each item if required
                    for val in coll_to_convert:
                        res.append(ConversionFinder.try_convert_value(conversion_finder, '', val, item_typ, logger,
                                                                      options=kwargs))
                else:
                    if len(item_typ) == 1:
                        item_typ_tuple = item_typ * len(coll_to_convert)
                    elif len(item_typ) == len(coll_to_convert):
                        item_typ_tuple = item_typ
                    else:
                        raise ValueError('Collection to convert is of length {} which is not compliant with desired '
                                         'type {}'.format(len(coll_to_convert), item_typ))
                    for val, item_t in zip(coll_to_convert, item_typ_tuple):
                        res.append(ConversionFinder.try_convert_value(conversion_finder, '', val, item_t, logger,
                                                                      options=kwargs))
                    res = tuple(res)

                return res

        elif issubclass(base_desired_type, AbstractSet):  # or issubclass(base_desired_type, set):
            # get the base collection type if provided
            item_typ, _ = _extract_collection_base_type(desired_type, exception_if_none=False)

            if item_typ is None:
                # nothing is required in terms of dict values: use the base method
                return ConversionFinder.try_convert_value(conversion_finder, '', coll_to_convert, desired_type,
                                                          logger=logger, options=kwargs)
            else:
                # TODO resuse appropriate container type (not necessary a set) according to type of coll_to_convert
                # there is a specific type required for the list values.
                res = set()
                # convert if required
                for val in coll_to_convert:
                    res.add(ConversionFinder.try_convert_value(conversion_finder, '', val, item_typ, logger,
                                                               options=kwargs))
                return res

        else:
            raise TypeError('Cannot convert collection values, expected type is not a supported collection '
                            '(dict, list, set, Mapping, Sequence, AbstractSet)! : ' + str(desired_type))

    @staticmethod
    def try_convert_value(conversion_finder, attr_name: str, attr_value: S, desired_attr_type: Type[T], logger: Logger,
                          options: Dict[str, Dict[str, Any]]) -> T:

        # First resolve TypeVars and Unions to get a list of compliant types
        object_types = resolve_union_and_typevar(desired_attr_type)

        if len(object_types) == 1:
            # One supported type: as usual
            return ConverterCache._try_convert_value(conversion_finder, attr_name=attr_name, attr_value=attr_value,
                                                     desired_attr_type=object_types[0], logger=logger,
                                                     options=options)
        else:
            # Several supported types: try to convert to each in sequence
            errors = dict()
            for alternate_typ in object_types:
                try:
                    return ConverterCache._try_convert_value(conversion_finder, attr_name=attr_name,
                                                             attr_value=attr_value, desired_attr_type=alternate_typ,
                                                             logger=logger, options=options)
                except NoConverterFoundForObjectType as e:
                    errors[alternate_typ] = e

            # Aggregate the errors if any
            raise NoConverterFoundForObjectType.create(conversion_finder, attr_value, desired_attr_type, errors)

    @staticmethod
    def _try_convert_value(conversion_finder, attr_name: str, attr_value: S, desired_attr_type: Type[T], logger: Logger,
                           options: Dict[str, Dict[str, Any]]) -> T:
        """
        Utility method to try to use provided conversion_finder to convert attr_value into desired_attr_type.
        If no conversion is required, the conversion finder is not even used (it can be None)

        :param conversion_finder:
        :param attr_name:
        :param attr_value:
        :param desired_attr_type:
        :param logger:
        :param options:
        :return:
        """

        # check if we need additional conversion

        # (a) a collection with details about the internal item type
        if is_typed_collection(desired_attr_type):
            return ConversionFinder.convert_collection_values_according_to_pep(coll_to_convert=attr_value,
                                                                               desired_type=desired_attr_type,
                                                                               conversion_finder=conversion_finder,
                                                                               logger=logger,
                                                                               **options)
        # --- typing types do not work with isinstance so there is a special check here
        elif not robust_isinstance(attr_value, desired_attr_type):
            if conversion_finder is not None:
                return conversion_finder.find_and_convert(attr_name,
                                                          attr_value,
                                                          desired_attr_type,
                                                          logger, options)
            else:
                raise NoConverterFoundForObjectType.create(conversion_finder,
                                                           attr_value,
                                                           desired_attr_type)
        else:
            # we can safely use the value: it is already of the correct type
            return attr_value


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
    def get_all_conversion_chains(self, from_type: Type[Any] = JOKER, to_type: Type[Any] = JOKER)\
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

        self._specific_conversion_chains = list()
        self._specific_non_strict_conversion_chains = list()
        self._generic_conversion_chains = list()
        self._generic_nonstrict_conversion_chains = list()

    def register_converter(self, converter: Converter[S, T]):
        """
        Utility method to register any converter. Converters that support any type will be stored in the "generic"
        lists, and the others will be stored in front of the types they support
        :return:
        """
        check_var(converter, var_types=Converter, var_name='converter')

        # (0) sanity check : check that parser handles jokers properly
        res = converter.is_able_to_convert_detailed(from_type=JOKER, to_type=JOKER, strict=True)
        if not (res[0] is True and res[1] is None and res[2] is None):
            raise ValueError('Converter ' + str(converter) + ' can not be registered since it does not handle the JOKER'
                             ' cases correctly')

        # compute all possible chains and save them
        generic_chains, generic_nonstrict_chains, specific_chains, specific_nonstrict_chains \
            = self._create_all_new_chains(converter)
        self._generic_nonstrict_conversion_chains += generic_nonstrict_chains
        self._generic_conversion_chains += generic_chains
        self._specific_non_strict_conversion_chains += specific_nonstrict_chains
        self._specific_conversion_chains += specific_chains

        # sort all lists by length
        self._generic_nonstrict_conversion_chains = sorted(self._generic_nonstrict_conversion_chains, key=len,
                                                           reverse=True)
        self._generic_conversion_chains = sorted(self._generic_conversion_chains, key=len, reverse=True)
        self._specific_non_strict_conversion_chains = sorted(self._specific_non_strict_conversion_chains, key=len,
                                                             reverse=True)
        self._specific_conversion_chains = sorted(self._specific_conversion_chains, key=len, reverse=True)

    def _create_all_new_chains(self, converter) -> Tuple[List[Converter], List[Converter],
                                                         List[Converter], List[Converter]]:
        """
        Creates all specific and generic chains that may be built by adding this converter to the existing chains.

        :param converter:
        :return: generic_chains, generic_nonstrict_chains, specific_chains, specific_nonstrict_chains
        """

        specific_chains, specific_nonstrict_chains, generic_chains, generic_nonstrict_chains = [], [], [], []

        if converter.is_generic():
            # the smaller chain : the singleton :)
            generic_chains.append(ConversionChain(initial_converters=[converter], strict_chaining=True))
        else:
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
                    # TODO this is where when chaining a generic to a specific, we would actually have to restrict it
                    # note: but maybe we dont care since now this is checked and prevented in the convert() method
                    new_c_at_beginning.append(ConversionChain.chain(converter, existing_specific, strict=True))
            elif (not self.strict) and existing_specific.can_be_appended_to(converter, strict=False):
                if ConversionChain.are_worth_chaining(converter, existing_specific):
                    # TODO this is where when chaining a generic to a specific, we would actually have to restrict it
                    # note: but maybe we dont care since now this is checked and prevented in the convert() method
                    new_c_at_beginning_ns.append(ConversionChain.chain(converter, existing_specific, strict=False))

        # append to the right list depending on the nature of this converter
        if converter.is_generic():
            generic_chains += new_c_at_end
            generic_nonstrict_chains += new_c_at_end_ns
        else:
            specific_chains += new_c_at_end
            specific_nonstrict_chains += new_c_at_end_ns
        # common for both types
        specific_chains += new_c_at_beginning
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
        if converter.is_generic():
            # we want to avoid chaining generic converters together
            pass
        else:
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

    def get_all_conversion_chains(self, from_type: Type[Any] = JOKER, to_type: Type[Any] = JOKER) \
            -> Tuple[List[Converter], List[Converter], List[Converter]]:
        """
        Utility method to find matching converters or conversion chains.

        :param from_type: a required type of input object, or JOKER for 'wildcard'(*) .
        WARNING: "from_type=AnyObject/object/Any" means
        "all converters able to source from anything", which is different from "from_type=JOKER" which means "all
        converters whatever their source type".
        :param to_type: a required type of output object, or JOKER for 'wildcard'(*) .
        WARNING: "to_type=AnyObject/object/Any" means "all
        converters able to produce any type of object", which is different from "to_type=JOKER" which means "all
        converters whatever type they are able to produce".
        :return: a tuple of lists of matching converters, by type of *dest_type* match : generic, approximate, exact.
        The order of each list is from *less relevant* to *most relevant*
        """

        if from_type is JOKER and to_type is JOKER:
            matching_dest_generic = self._generic_nonstrict_conversion_chains.copy() + \
                                    self._generic_conversion_chains.copy()
            matching_dest_approx = []
            matching_dest_exact = self._specific_non_strict_conversion_chains.copy() + \
                                  self._specific_conversion_chains.copy()

        else:
            matching_dest_generic, matching_dest_approx, matching_dest_exact = [], [], []

            # first transform any 'Any' type requirement into the official class for that
            to_type = get_validated_type(to_type, 'to_type', enforce_not_joker=False)

            # handle generic converters first
            for c in (self._generic_nonstrict_conversion_chains + self._generic_conversion_chains):
                match, source_exact, dest_exact = c.is_able_to_convert_detailed(strict=self.strict,
                                                                                from_type=from_type,
                                                                                to_type=to_type)
                if match:
                    # match
                    if is_any_type(to_type):
                        # special case where desired to_type is already Any : in that case a generic converter will
                        # appear in 'exact match'
                        matching_dest_exact.append(c)
                    else:
                        # this is a match from a generic parser to a specific type : add in 'generic' cataegory
                        matching_dest_generic.append(c)

            # then the specific
            for c in (self._specific_non_strict_conversion_chains + self._specific_conversion_chains):
                match, source_exact, dest_exact = c.is_able_to_convert_detailed(strict=self.strict,
                                                                                from_type=from_type,
                                                                                to_type=to_type)
                if match:
                    if not is_any_type(to_type):
                        if dest_exact:
                            # we dont care if source is exact or approximate as long as dest is exact
                            matching_dest_exact.append(c)
                        else:
                            # this means that dest is approximate.
                            matching_dest_approx.append(c)
                    else:
                        # we only want to keep the generic ones, and they have already been added
                        pass

        return matching_dest_generic, matching_dest_approx, matching_dest_exact


class ParserRegistryWithConverters(ConverterCache, ParserRegistry, ConversionFinder):
    """
    Base class able to combine parsers and converters to create parsing chains.
    """

    def __init__(self, pretty_name: str, strict_matching: bool, initial_parsers_to_register: List[Parser] = None,
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

        # then add provided converters
        if initial_converters_to_register is not None:
            self.register_converters(initial_converters_to_register)

    def find_all_matching_parsers(self, strict: bool, desired_type: Type[Any] = JOKER, required_ext: str = JOKER) \
        -> Tuple[Tuple[List[Parser], List[Parser], List[Parser]],
                 List[Parser], List[Parser], List[Parser]]:
        """
        Overrides the parent method to find parsers appropriate to a given extension and type.
        This leverages both the parser registry and the converter registry to propose parsing chains in a relevant order

        :param strict:
        :param desired_type: the type of object to match.
        :param required_ext: the required extension.
        :return: match=(matching_parsers_generic, matching_parsers_approx, matching_parsers_exact),
                 no_type_match_but_ext_match, no_ext_match_but_type_match, no_match
        """
        # transform any 'Any' type requirement into the official class for that
        desired_type = get_validated_type(desired_type, 'desired_type', enforce_not_joker=False)

        # (1) call the super method to find all parsers
        matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match = \
            super(ParserRegistryWithConverters, self).find_all_matching_parsers(strict=self.is_strict,
                                                                                desired_type=desired_type,
                                                                                required_ext=required_ext)
        # these are ordered with 'preferred last'
        matching_p_generic, matching_p_approx, matching_p_exact = matching

        if desired_type is JOKER:
            # then we want to try to append every possible converter chain, even if we have already found an exact match
            # (exact match will probably contain all parsers in that case?...)
            parsers_to_complete_with_converters = no_type_match_but_ext_match + matching_p_generic + matching_p_approx \
                                                  + matching_p_exact
        else:
            # then we can try to complete all the ones matching the extension (even the generic because combining them
            # with a conversion chain might provide another way to reach the result - different from using the generic
            # alone to reach the to_type)
            parsers_to_complete_with_converters = no_type_match_but_ext_match + matching_p_generic + matching_p_approx

        # (2) find all conversion chains that lead to the expected result
        matching_c_generic_to_type, matching_c_approx_to_type, matching_c_exact_to_type = \
            self.get_all_conversion_chains_to_type(to_type=desired_type)
        all_matching_converters = matching_c_generic_to_type + matching_c_approx_to_type + matching_c_exact_to_type

        # (3) combine both (parser + conversion chain), and append to the appropriate list depending on the match
        # -- (a) first Parsers matching EXT (not type) + Converters matching their type
        # for all parsers able to parse this extension, and for all the types they support
        #
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
                # prepend the existing lists with the new match
                matching_p_generic = match_results[1] + matching_p_generic
                matching_p_approx = match_results[3] + matching_p_approx
                matching_p_exact = match_results[5] + matching_p_exact

                # store the approximate matchs in the separate lists
                matching_p_generic_with_approx_chain = match_results[0] + matching_p_generic_with_approx_chain
                matching_p_approx_with_approx_chain = match_results[2] + matching_p_approx_with_approx_chain
                matching_p_exact_with_approx_chain = match_results[4] + matching_p_exact_with_approx_chain

        # finally prepend the approximate match lists
        matching_p_generic = matching_p_generic_with_approx_chain + matching_p_generic
        matching_p_approx = matching_p_approx_with_approx_chain + matching_p_approx
        matching_p_exact = matching_p_exact_with_approx_chain + matching_p_exact

        # -- (b) then parsers that do not match at all (not the file extension nor the type): we can find parsing chains
        # that make them at least match the type
        #
        # (we have to reverse it because it was 'best last', now it will be 'best first')
        for parser in reversed(no_match):
            for typ in parser.supported_types:
                for converter in reversed(all_matching_converters):
                    # if converter is able to source from this parser
                    if converter.is_able_to_convert(self.is_strict, from_type=typ, to_type=desired_type):
                        if ParsingChain.are_worth_chaining(parser, typ, converter):
                            # insert it at the beginning since it should have less priority
                            no_ext_match_but_type_match.insert(0, ParsingChain(parser, converter, strict=self.is_strict,
                                                                               base_parser_chosen_dest_type=typ))

        # Finally sort by chain length
        matching_p_generic = sorted(matching_p_generic, key=len, reverse=True)
        matching_p_approx = sorted(matching_p_approx, key=len, reverse=True)
        matching_p_exact = sorted(matching_p_exact, key=len, reverse=True)

        # Return
        return (matching_p_generic, matching_p_approx, matching_p_exact), no_type_match_but_ext_match, \
               no_ext_match_but_type_match, no_match

    def _complete_parsers_with_converters(self, parser, parser_supported_type, desired_type, matching_c_generic_to_type,
                                          matching_c_approx_to_type, matching_c_exact_to_type):
        """
        Internal method to create parsing chains made of a parser and converters from the provided lists.
        Once again a JOKER for a type means 'joker' here.

        :param parser:
        :param parser_supported_type:
        :param desired_type:
        :param matching_c_generic_to_type:
        :param matching_c_approx_to_type:
        :param matching_c_exact_to_type:
        :return:
        """

        matching_p_generic, matching_p_generic_with_approx_chain, \
        matching_p_approx, matching_p_approx_with_approx_chain,\
        matching_p_exact, matching_p_exact_with_approx_chain = [], [], [], [], [], []

        # resolve Union and TypeVar
        desired_types = resolve_union_and_typevar(desired_type)

        for desired_type in desired_types:

            # first transform any 'Any' type requirement into the official class for that
            desired_type = get_validated_type(desired_type, 'desired_type', enforce_not_joker=False)

            # ---- Generic converters - only if the parsed type is not already 'any'
            if not is_any_type(parser_supported_type):
                for cv in matching_c_generic_to_type:
                    # if the converter can attach to this parser, we have a matching parser !

                    # --start from strict
                    if cv.is_able_to_convert(strict=True,
                                             from_type=parser_supported_type,
                                             to_type=desired_type):
                        if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                            chain = ParsingChain(parser, cv, strict=True,
                                                 base_parser_chosen_dest_type=parser_supported_type)
                            # insert it at the beginning since it should have less priority
                            matching_p_generic.append(chain)

                    # --then non-strict
                    elif (not self.strict) \
                            and cv.is_able_to_convert(strict=False,
                                                      from_type=parser_supported_type,
                                                      to_type=desired_type):
                        if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                            chain = ParsingChain(parser, cv, strict=False,
                                                 base_parser_chosen_dest_type=parser_supported_type)
                            # insert it at the beginning since it should have less priority
                            matching_p_generic_with_approx_chain.append(chain)

            # ---- Approx to_type
            for cv in matching_c_approx_to_type:
                # if the converter can attach to this parser, we have a matching parser !
                # -- start from strict
                if cv.is_able_to_convert(strict=True,
                                         from_type=parser_supported_type,
                                         to_type=desired_type):
                    if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                        chain = ParsingChain(parser, cv, strict=True,
                                             base_parser_chosen_dest_type=parser_supported_type)
                        # insert it at the beginning since it should have less priority
                        matching_p_approx.append(chain)
                # then non-strict
                elif (not self.strict) \
                        and cv.is_able_to_convert(strict=False,
                                                  from_type=parser_supported_type,
                                                  to_type=desired_type):
                    if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                        chain = ParsingChain(parser, cv, strict=False,
                                             base_parser_chosen_dest_type=parser_supported_type)
                        # insert it at the beginning since it should have less priority
                        matching_p_approx_with_approx_chain.append(chain)

            # ---- Exact to_type
            for cv in matching_c_exact_to_type:
                # if the converter can attach to this parser, we have a matching parser !
                if cv.is_able_to_convert(strict=True,
                                         from_type=parser_supported_type,
                                         to_type=desired_type):
                    if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                        chain = ParsingChain(parser, cv, strict=True,
                                             base_parser_chosen_dest_type=parser_supported_type)
                        # insert it at the beginning since it should have less priority
                        matching_p_exact.append(chain)
                elif (not self.strict) \
                        and cv.is_able_to_convert(strict=False,
                                                  from_type=parser_supported_type,
                                                  to_type=desired_type):
                    if ParsingChain.are_worth_chaining(parser, parser_supported_type, cv):
                        chain = ParsingChain(parser, cv, strict=False,
                                             base_parser_chosen_dest_type=parser_supported_type)
                        # insert it at the beginning since it should have less priority
                        matching_p_exact_with_approx_chain.append(chain)

        # Preferred is LAST, so approx should be first
        return matching_p_generic_with_approx_chain, matching_p_generic, \
               matching_p_approx_with_approx_chain, matching_p_approx, \
               matching_p_exact_with_approx_chain, matching_p_exact
