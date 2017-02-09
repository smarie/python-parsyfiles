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


def read_dataframe_from_xls(desired_type: Type[T], file_path: str, encoding: str,
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


def read_dataframe_from_csv(desired_type: Type[pd.DataFrame], file_object: TextIOBase,
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
    return [SingleFileParserFunction(parser_function=read_dataframe_from_xls,
                                     streaming_mode=False,
                                     supported_exts={'.xls', '.xlsx', '.xlsm'},
                                     supported_types={pd.DataFrame}),
            SingleFileParserFunction(parser_function=read_dataframe_from_csv,
                                     streaming_mode=True,
                                     supported_exts={'.csv', '.txt'},
                                     supported_types={pd.DataFrame}),
            ]


def dict_to_single_row_or_col_df(desired_type: Type[T], dict_obj: Dict, logger: Logger,
                                 orient: str = None, *args, **kwargs) -> pd.DataFrame:
    """
    Helper method to convert a dictionary into a dataframe with one row

    :param dict_obj:
    :return:
    """
    orient = orient or 'columns'
    if orient is 'columns':
        return pd.DataFrame(dict_obj, index=[0])
    else:
        res = pd.DataFrame.from_dict(dict_obj, orient='index')
        res.index.name = 'key'
        return res.rename(columns={0:'value'})


def single_row_or_col_df_to_dict(desired_type: Type[T], single_row_df: pd.DataFrame, logger: Logger, *args, **kwargs) -> Dict[str, str]:
    """
    Helper method to convert a dataframe with one row into a dictionary,
    or
    TODO a parameter dataframe with one column

    :param single_row_df:
    :return:
    """
    if single_row_df.shape[0] == 1:
        return {col_name: single_row_df[col_name][single_row_df.index.values[0]] for col_name in single_row_df.columns}
    elif single_row_df.shape[1] == 2 and isinstance(single_row_df.index, pd.RangeIndex):
        d = single_row_df.set_index(single_row_df.columns[0])
        return d[d.columns[0]].to_dict()
    elif single_row_df.shape[1] == 1:
        d = single_row_df
        return d[d.columns[0]].to_dict()
    else:
        raise ValueError('Unable to convert provided dataframe to a parameters dictionary : '
                         'expected exactly 1 row or 1 column, found : ' + str(single_row_df.shape) + '')


def get_default_dataframe_converters() -> List[Union[Converter[Any, pd.DataFrame],
                                                     Converter[pd.DataFrame, Any]]]:
    """
    Utility method to return the default converters associated to dataframes (from dataframe to other type,
    and from other type to dataframe)
    :return:
    """
    return [ConverterFunction(pd.DataFrame, dict, single_row_or_col_df_to_dict),
            ConverterFunction(dict, pd.DataFrame, dict_to_single_row_or_col_df)]

