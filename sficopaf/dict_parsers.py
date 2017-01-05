from io import StringIO
from io import TextIOBase
from typing import Dict, Union, Type, Any

from sficopaf import check_var


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

class NoConfigSectionError(Exception):
    """ This is raised whenever a configuration section does not exist in a config object.
    Like configparser.NoConfigSection but with a free error message."""


def read_dict_from_config(file_object: TextIOBase, config_section_name: str = None) \
        -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """
    Helper method to read a configuration file according to the 'configparser' format,
    and return it as a dictionary. If a configuration section name is
    provided in this method (you'll have to create a wrapper method with it set to a value),
    only the contents of the required section will be returned, as a dictionary.
    Otherwise a dictionary of dictionaries will be returned

    :param file_object:
    :param config_section_name: optional configuration section name to return
    :return:
    """
    check_var(file_object, var_types=TextIOBase, var_name='file_object')
    check_var(config_section_name, var_types=str, var_name='config_section_name', enforce_not_none=False)

    # lazy import configparser
    # see https://docs.python.org/3/library/configparser.html for details
    from configparser import ConfigParser
    config = ConfigParser()
    config.read_file(file_object)
    sections = config.sections()

    # convert the whole config to a dictionary of dictionaries
    config_as_dict = {
        section_name: {key: config[config_section_name][key] for key in config[config_section_name].keys()} for
        section_name in
        config.sections()}

    # return the required section or the whole configuration
    if config_section_name is None:
        return config_as_dict
    else:
        if config_section_name in config_as_dict.keys():
            return config_as_dict[config_section_name]
        else:
            raise NoConfigSectionError('Unknown configuration section : ' + config_section_name
                                       + '. Available section names are ' + str(config_as_dict.keys()))


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

def convert_dict_to_simple_object(dict, object_type: Type[Any]) -> Any:
    """
    Utility method to create an object from a dictionary

    :param dict:
    :param object_type:
    :return:
    """
    return object_type(**dict)