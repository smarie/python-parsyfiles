from io import TextIOBase
from logging import Logger
from typing import Type, Dict, Any, List

import jprops

from parsyfiles.parsing_core import AnyParser, SingleFileParserFunction
from parsyfiles.parsing_registries import ConversionFinder, ParserFinder
from parsyfiles.plugins_base.support_for_collections import convert_collection_values_according_to_pep


def read_dict_from_properties(desired_type: Type[dict], file_object: TextIOBase,
                              logger: Logger, conversion_finder: ConversionFinder, **kwargs) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .properties file (java-style) using jprops.
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

    # convert if required
    return convert_collection_values_according_to_pep(res, desired_type, conversion_finder, logger, **kwargs)


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