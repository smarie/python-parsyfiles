from io import TextIOBase
from logging import Logger
from typing import Dict, Any, List, Union, Type, Set, Tuple

from parsyfiles.converting_core import Converter, ConverterFunction
from parsyfiles.filesystem_mapping import PersistedObject
from parsyfiles.parsing_core import SingleFileParserFunction, AnyParser, MultiFileParser, ParsingPlan, T
from parsyfiles.parsing_registries import ParserFinder
from parsyfiles.type_inspection_tools import _extract_collection_base_type, get_pretty_type_str
from parsyfiles.var_checker import check_var


def read_list_from_properties(desired_type: Type[dict], file_object: TextIOBase,
                              logger: Logger, *args, **kwargs) -> List[str]:
    """
    Reads a text file into a list of string lines
    :param desired_type:
    :param file_object:
    :param logger:
    :param args:
    :param kwargs:
    :return:
    """
    return [line_str for line_str in file_object]


def read_dict_from_properties(desired_type: Type[dict], file_object: TextIOBase,
                              logger: Logger, *args, **kwargs) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .properties file (java-style) using jprops.
    :param file_object:
    :return:
    """
    # lazy import in order not to force use of jprops
    import jprops

    # right now jprops relies on a byte stream. So we convert back our nicely decoded Text stream to a unicode
    # byte stream ! (urgh)
    class Unicoder:
        def __init__(self, file_object):
            self.f = file_object

        def __iter__(self):
            return self

        def __next__(self):
            line = self.f.__next__()
            return line.encode(encoding='utf-8')

    return jprops.load_properties(Unicoder(file_object))


def read_dict_or_list_from_json(desired_type: Type[dict], file_object: TextIOBase,
                                logger: Logger, *args, **kwargs) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .json file using json library
    :param file_object:
    :return:
    """
    # lazy import in order not to force use of jprops
    #jsonStr = StringIO(file_object).getvalue()
    import json
    return json.load(file_object)


class DictOfDict(Dict[str, Dict[str, Any]]):
    """
    Represents a dictionary of dictionaries. We can't use an alias here otherwise 'dict' would be considered a
    subclass of 'DictOfDict'
    """
    pass


class MultifileDictParser(MultiFileParser):
    """
    This class is able to read any collection type as long as they are PEP484 specified (Dict, List, Set, Tuple), from
     multifile objects. It simply inspects the required type to find the base type expected for items of the collection,
     and relies on a ParserFinder to parse each of them before creating the final collection.
    """
    def __init__(self, parser_finder: ParserFinder):
        """
        Constructor. The parser_finder will be used to find the most appropriate parser to parse each item of the
        collection
        :param parser_finder:
        """
        super(MultifileDictParser, self).__init__(supported_types={Dict, List})
        self.parser_finder = parser_finder

    def __str__(self):
        return 'Multifile Dict parser (based on \'' + str(self.parser_finder) + '\' to find the parser for each item)'

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Simply inspects the required type to find the base type expected for items of the collection,
        and relies on the ParserFinder to find the parsing plan

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """

        # first extract base collection type
        subtype, key_type = _extract_collection_base_type(desired_type)

        # then for each child create a plan with the appropriate parser
        children_plan = dict()
        # use sorting for reproducible results in case of multiple errors
        for child_name, child_fileobject in sorted(obj_on_fs.get_multifile_children().items()):
            # -- use the parserfinder to find the plan
            child_parser = self.parser_finder.build_parser_for_fileobject_and_desiredtype(child_fileobject, subtype, logger)
            children_plan[child_name] = child_parser.create_parsing_plan(subtype, child_fileobject, logger)

        return children_plan

    def _parse_multifile(self, desired_type: Type[Union[Dict, List]], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, ParsingPlan], logger: Logger,
                         lazy_parsing: bool = False, background_parsing: bool = False, *args, **kwargs) \
            -> Union[Dict, List]:
        """

        :param desired_type:
        :param obj:
        :param parsed_children:
        :param logger:
        :param lazy_parsing: if True, the method will return immediately without parsing all the contents. Instead, the
        returned collection will perform the parsing the first time an item is required.
        :param background_parsing: if True, the method will return immediately while a thread parses all the contents in
        the background. Note that users cannot set both lazy_parsing and background_parsing to True at the same time
        :return:
        """

        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
        check_var(background_parsing, var_types=bool, var_name='background_parsing')

        if lazy_parsing and background_parsing:
            raise ValueError('lazy_parsing and background_parsing cannot be set to true at the same time')

        if lazy_parsing:
            # -- TODO make a lazy dictionary
            raise ValueError('Lazy parsing is not yet supported')
        elif background_parsing:
            # -- TODO create a thread to perform the parsing in the background
            raise ValueError('Background parsing is not yet supported')
        else:
            # Parse right now
            results = {}

            # parse all children according to their plan
            # -- use key-based sorting on children to lead to reproducible results
            # (in case of multiple errors, the same error will show up first everytime)
            for child_name, child_plan in sorted(parsing_plan_for_children.items()):
                results[child_name] = child_plan.execute(logger, *args, **kwargs)

            logger.info('Assembling all parsed child items into a ' + get_pretty_type_str(desired_type)
                        + ' to build ' + str(obj))
            if issubclass(desired_type, list):
                # build a list sorted by the keys
                return [value for (key, value) in sorted(results.items())]
            else:
                return results


def list_to_set(desired_type: Type[T], contents_list: List[str], logger: Logger,
                 lazy_parsing: bool = False, background_parsing: bool = False,
                 *args, **kwargs) -> Set:
    return set(contents_list)


def list_to_tuple(desired_type: Type[T], contents_list: List[str], logger: Logger,
                lazy_parsing: bool = False, background_parsing: bool = False,
                *args, **kwargs) -> Tuple:
    return tuple(contents_list)


def get_default_collection_parsers(parser_finder: ParserFinder) -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_dict_or_list_from_json,
                                     streaming_mode=True,
                                     supported_exts={'.json'},
                                     supported_types={dict, list}),
            SingleFileParserFunction(parser_function=read_dict_from_properties,
                                     streaming_mode=True,
                                     supported_exts={'.properties', '.txt'},
                                     supported_types={dict}),
            SingleFileParserFunction(parser_function=read_list_from_properties,
                                     streaming_mode=True,
                                     supported_exts={'.properties', '.txt'},
                                     supported_types={list}),
            MultifileDictParser(parser_finder)
            ]


def get_default_collection_converters() -> List[Union[Converter[Any, dict], Converter[dict, Any]]]:
    """
    Utility method to return the default converters associated to dict (from dict to other type,
    and from other type to dict)
    :return:
    """
    return [ConverterFunction(from_type=List, to_type=Set, conversion_method=list_to_set),
            ConverterFunction(from_type=List, to_type=Tuple, conversion_method=list_to_tuple)]