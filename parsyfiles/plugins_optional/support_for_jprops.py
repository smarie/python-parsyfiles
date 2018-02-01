from io import TextIOBase
from logging import Logger
from typing import Type, Dict, Any, List

import jprops

from parsyfiles.parsing_core import AnyParser, SingleFileParserFunction
from parsyfiles.parsing_registries import ConversionFinder, ParserFinder


def try_parse_num_and_booleans(num_str):
    """
    Tries to parse the provided string as a number or boolean
    :param num_str:
    :return:
    """
    if isinstance(num_str, str):
        # bool
        if num_str.lower() == 'true':
            return True
        elif num_str.lower() == 'false':
            return False
        # int
        if num_str.isdigit():
            return int(num_str)
        # float
        try:
            return float(num_str)
        except ValueError:
            # give up
            return num_str
    else:
        # dont try
        return num_str


def read_dict_from_properties(desired_type: Type[dict], file_object: TextIOBase,
                              logger: Logger, conversion_finder: ConversionFinder, **kwargs) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .properties file (java-style) using jprops.
    Since jprops does not provide automatic handling for boolean and numbers, this tries to add the feature.

    :param file_object:
    :return:
    """

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

    res = jprops.load_properties(Unicoder(file_object))

    # first automatic conversion of strings > numbers
    res = {key: try_parse_num_and_booleans(val) for key, val in res.items()}

    # further convert if required
    return ConversionFinder.convert_collection_values_according_to_pep(res, desired_type, conversion_finder, logger, 
                                                                       **kwargs)


def get_default_jprops_parsers(parser_finder: ParserFinder, conversion_finder: ConversionFinder) -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a properties file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_dict_from_properties,
                                     streaming_mode=True, custom_name='read_dict_from_properties',
                                     supported_exts={'.properties', '.txt'},
                                     supported_types={dict},
                                     function_args={'conversion_finder': conversion_finder}),
            # SingleFileParserFunction(parser_function=read_list_from_properties,
            #                          streaming_mode=True,
            #                          supported_exts={'.properties', '.txt'},
            #                          supported_types={list}),
        ]