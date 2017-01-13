from io import StringIO
from io import TextIOBase
from typing import Dict, Any, List

from sficopaf.var_checker import check_var


def get_default_collection_parsers():
    a = get_default_dict_parsers()
    a.update(get_default_list_and_set_parsers())
    return a

def get_default_list_and_set_parsers():
    """
    Utility method to return the default parsers for list and set types
    :return:
    """
    #TODO
    return {

    }

def get_default_dict_parsers():
    """
    Utility method to return the default parsers for dictionary type
    :return:
    """
    return {
        '.cfg': read_dict_from_config,
        '.ini': read_dict_from_config,
        '.json': read_dict_from_json,
        '.properties': read_dict_from_properties,
        '.txt': read_dict_from_properties
    }


def get_default_dict_of_dicts_parsers():
    """
    Utility method to return the default parsers for 'dictionary of dictionary' type
    :return:
    """
    return {
        '.cfg': read_dict_of_dicts_from_config,
        '.ini': read_dict_of_dicts_from_config,
    }


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
    def create(key_name: str, sections: List[str]): # -> ObjectCannotBeParsedError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return MultipleKeyOccurenceInConfigurationError('Cannot read the provided config file as a flat dictionary : '
                                                        'key \'' + key_name + '\' appears several times, in sections'
                                                                              '\'' + sections + '\'.')


def read_dict_of_dicts_from_config(file_object: TextIOBase) -> Dict[str, Dict[str, Any]]:
    """
    Helper method to read a configuration file according to the 'configparser' format, and return it as a dictionary
    of dictionaries (section > [property > value])

    :param file_object:
    :return:
    """
    check_var(file_object, var_types=TextIOBase, var_name='file_object')

    # lazy import configparser
    # see https://docs.python.org/3/library/configparser.html for details
    from configparser import ConfigParser
    config = ConfigParser()
    config.read_file(file_object)

    return dict(config)


def read_dict_from_config(file_object: TextIOBase) \
        -> Dict[str, Any]:
    """
    Helper method to read a configuration file according to the 'configparser' format, and return it as a dictionary
    [property > value]. Properties from all sections are collected. If the same key appears in several sections, an
    error will be thrown

    :param file_object:
    :return:
    """
    check_var(file_object, var_types=TextIOBase, var_name='file_object')

    # lazy import configparser
    # see https://docs.python.org/3/library/configparser.html for details
    from configparser import ConfigParser
    config = ConfigParser()
    config.read_file(file_object)

    # convert the whole config to a dictionary by flattening all sections
    results = dict()
    for section, props in config.items():
        for key, value in props.items():
            if key in results.keys():
                raise MultipleKeyOccurenceInConfigurationError.create()
            else:
                results[key] = value
    return results



def read_dict_from_csv(file_object: TextIOBase) -> Dict[str, str]:
    """
    Helper method to read a dictionary from a two-rows csv file using pandas
    :param file_object:
    :return:
    """
    # lazy import in order not to force use pandas
    from sficopaf.dataframe_parsers import DataFrameParsers, Converters
    pdf = DataFrameParsers.read_simpledf_from_csv(file_object)
    return Converters.paramdf_to_paramdict(pdf)


def read_dict_from_xls(file_object: TextIOBase) -> Dict[str, str]:
    """
    Helper method to read a dictionary from a two-rows xls file using pandas
    :param file_object:
    :return:
    """
    # lazy import in order not to force use pandas
    from sficopaf.dataframe_parsers import DataFrameParsers, Converters
    pdf = DataFrameParsers.read_simpledf_from_xls(file_object)
    return Converters.paramdf_to_paramdict(pdf)



def read_dict_from_properties(file_object: TextIOBase) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .properties file (java-style) using jprops.
    :param file_object:
    :return:
    """
    # lazy import in order not to force use of jprops
    import jprops
    return jprops.load_properties(file_object)


def read_dict_from_json(file_object: TextIOBase) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .json file using json library
    :param file_object:
    :return:
    """
    # lazy import in order not to force use of jprops
    jsonStr = StringIO(file_object).getvalue()
    import json
    return json.loads(jsonStr)
