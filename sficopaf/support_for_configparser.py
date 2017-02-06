from configparser import ConfigParser
from io import TextIOBase
from logging import Logger
from typing import List, Union, Any, Dict, Type

from sficopaf.converting_core import Converter, ConverterFunction, T
from sficopaf.parsing_core import SingleFileParserFunction, AnyParser
from sficopaf.support_for_collections import DictOfDict


def read_config(desired_type: Type[ConfigParser], file_object: TextIOBase,
                logger: Logger, *args, **kwargs) -> ConfigParser:
    """
    Helper method to read a configuration file according to the 'configparser' format, and return it as a dictionary
    of dictionaries (section > [property > value])

    :param file_object:
    :return:
    """

    # see https://docs.python.org/3/library/configparser.html for details
    config = ConfigParser()
    config.read_file(file_object)

    return config


def get_default_config_parsers() -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_config,
                                     streaming_mode=True,
                                     supported_exts={'.cfg', '.ini'},
                                     supported_types={ConfigParser}),
            ]

class MultipleKeyOccurenceInConfigurationError(Exception):
    """
    Raised whenever a configuration file is being read as a 'flat' dictionary (merging all sections into one dict) but
    the same key appears in several sections
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MultipleKeyOccurenceInConfigurationError, self).__init__(contents)

    @staticmethod
    def create(key_name: str, sections: List[str]): # -> NoParserFoundForObject:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param key_name:
        :param sections:
        :return:
        """
        return MultipleKeyOccurenceInConfigurationError('Cannot read the provided config file as a flat dictionary : '
                                                        'key \'' + key_name + '\' appears several times, in sections'
                                                                              '\'' + str(sections) + '\'.')


# Useless AND ambiguous about the returned type.
# If other functions need such an object, why would they not directly use ConfirParser ?
# Otherwise, we'll have to create a specific class representing a 'universal' config
#
# def read_dict_of_dicts_from_config(config: ConfigParser, logger: Logger) -> Dict[str, Dict[str, Any]]:
#     """
#     Helper method to read a configuration file according to the 'configparser' format, and return it as a dictionary
#     of dictionaries (section > [property > value])
#
#     :param file_object:
#     :return:
#     """
#     return dict(config)

def config_to_dict_of_dict(desired_type: Type[T], config: ConfigParser, logger: Logger, *args, **kwargs) -> DictOfDict:
    """
    Helper method to read a configuration file according to the 'configparser' format, and return it as a dictionary
    of dictionaries [section > [property > value]].

    :param file_object:
    :return:
    """
    return dict(config)


def merge_all_config_sections_into_a_single_dict(desired_type: Type[T], config: ConfigParser, logger: Logger,
                                                 *args, **kwargs) -> Dict[str, Any]:
    """
    Helper method to convert a 'configparser' into a dictionary [property > value].
    Properties from all sections are collected. If the same key appears in several sections, an
    error will be thrown

    :param file_object:
    :return:
    """
    # convert the whole config to a dictionary by flattening all sections. If a key is found twice in two different
    # sections an error is raised
    results = dict()
    for section, props in config.items():
        for key, value in props.items():
            if key in results.keys():
                # find all sections where it appears
                sections_where_it_appears = [s for s, p in config.items() if key in p.keys()]
                raise MultipleKeyOccurenceInConfigurationError.create(key, sections_where_it_appears)
            else:
                results[key] = value
    return results


def get_default_config_converters() -> List[Union[Converter[Any, ConfigParser], Converter[ConfigParser, Any]]]:
    """
    Utility method to return the default converters associated to ConfigParser (from ConfigParser to other type,
    and from other type to ConfigParser)
    :return:
    """
    return [ConverterFunction(ConfigParser, dict, merge_all_config_sections_into_a_single_dict),
            ConverterFunction(ConfigParser, DictOfDict, config_to_dict_of_dict)]