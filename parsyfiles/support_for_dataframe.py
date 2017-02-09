from io import TextIOBase
from logging import Logger
from typing import Dict, List, Any, Union, Type

import pandas as pd

from parsyfiles.converting_core import Converter, ConverterFunction, T
from parsyfiles.parsing_core import SingleFileParserFunction, AnyParser


# def read_simpledf_from_xls_streaming(desired_type: Type[pd.DataFrame], file_object: TextIOBase,
#                            logger: Logger, *args, **kwargs) -> pd.DataFrame:
#     """
#     Helper method to read a dataframe from a xls file stream. By default this is well suited for a dataframe with
#     headers in the first row, for example a parameter dataframe.
#     :param file_object:
#     :return:
#     """
#     return pd.read_excel(file_object, *args, **kwargs)


def read_simpledf_from_xls(desired_type: Type[T], file_path: str, encoding: str,
                           logger: Logger, *args, **kwargs) -> pd.DataFrame:
    """
    We register this method rather than the other because pandas guesses the encoding by itself.

    Also, it is easier to put a breakpoint and debug by trying various options to find the good one (in streaming mode
    you just have one try and then the stream is consumed)

    :param desired_type:
    :param file_path:
    :param encoding:
    :param logger:
    :param args:
    :param kwargs:
    :return:
    """
    return pd.read_excel(file_path, *args, **kwargs)


def read_simpledf_from_csv(desired_type: Type[pd.DataFrame], file_object: TextIOBase,
                           logger: Logger, *args, **kwargs) -> pd.DataFrame:
    """
    Helper method to read a dataframe from a csv file stream. By default this is well suited for a dataframe with
    headers in the first row, for example a parameter dataframe.
    :param file_object:
    :return:
    """
    return pd.read_csv(file_object, *args, **kwargs)


def get_default_dataframe_parsers() -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_simpledf_from_xls,
                                     streaming_mode=False,
                                     supported_exts={'.xls', '.xlsx', '.xlsm'},
                                     supported_types={pd.DataFrame}),
            SingleFileParserFunction(parser_function=read_simpledf_from_csv,
                                     streaming_mode=True,
                                     supported_exts={'.csv', '.txt'},
                                     supported_types={pd.DataFrame}),
            ]


def single_row_df_to_dict(desired_type: Type[T], param_df: pd.DataFrame, logger: Logger, *args, **kwargs) -> Dict[str, str]:
    """
    Helper method to convert a parameters dataframe with one row to a dictionary,
    or TODO a parameter dataframe with one column

    :param param_df:
    :return:
    """
    if len(param_df.index.values) == 1:
        return {col_name: param_df[col_name][param_df.index.values[0]] for col_name in param_df.columns}
    else:
        raise ValueError('Unable to convert provided dataframe to a parameters dictionary : '
                         'expected exactly 1 row, found : ' + str(len(param_df.index.values)))


def get_default_dataframe_converters() -> List[Union[Converter[Any, pd.DataFrame],
                                                     Converter[pd.DataFrame, Any]]]:
    """
    Utility method to return the default converters associated to dataframes (from dataframe to other type,
    and from other type to dataframe)
    :return:
    """
    return [ConverterFunction(pd.DataFrame, dict, single_row_df_to_dict)]

