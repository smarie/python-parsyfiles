from logging import Logger
from typing import Type, Any, List, Tuple, Dict, Set

from io import TextIOBase
import yaml

from parsyfiles.converting_core import AnyObject
from parsyfiles.parsing_core import AnyParser, SingleFileParserFunction
from parsyfiles.parsing_registries import ParserFinder, ConversionFinder


def read_object_from_yaml(desired_type: Type[Any], file_object: TextIOBase, logger: Logger,
                          fix_imports: bool = True, errors: str = 'strict', *args, **kwargs) -> Any:
    """
    Parses a yaml file.

    :param desired_type:
    :param file_object:
    :param logger:
    :param fix_imports:
    :param errors:
    :param args:
    :param kwargs:
    :return:
    """
    return yaml.load(file_object)


def get_default_yaml_parsers(parser_finder: ParserFinder, conversion_finder: ConversionFinder) -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse an object from a file.
    Note that MultifileObjectParser is not provided in this list, as it is already added in a hardcoded way in
    RootParser
    :return:
    """
    return [# yaml for any object
            SingleFileParserFunction(parser_function=read_object_from_yaml,
                                     streaming_mode=True,
                                     supported_exts={'.yaml','.yml'},
                                     supported_types={AnyObject},
                                     ),
            # yaml for collection objects
            SingleFileParserFunction(parser_function=read_object_from_yaml,
                                     custom_name='read_collection_from_yaml',
                                     streaming_mode=True,
                                     supported_exts={'.yaml','.yml'},
                                     supported_types={Tuple, Dict, List, Set},
                                     )
    ]
