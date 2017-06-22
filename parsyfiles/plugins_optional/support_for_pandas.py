from logging import Logger
from typing import Dict, List, Any, Union, Type

import pandas as pd

from parsyfiles.converting_core import Converter, ConverterFunction, T
from parsyfiles.parsing_core import SingleFileParserFunction, AnyParser


# def read_simpledf_from_xls_streaming(desired_type: Type[pd.DataFrame], file_object: TextIOBase,
#                            logger: Logger, **kwargs) -> pd.DataFrame:
#     """
#     Helper method to read a dataframe from a xls file stream. By default this is well suited for a dataframe with
#     headers in the first row, for example a parameter dataframe.
#     :param file_object:
#     :return:
#     """
#     return pd.read_excel(file_object, **kwargs)


def pandas_parsers_option_hints_xls():
    return 'all options from read_excel are supported, see http://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_excel.html'


def read_dataframe_from_xls(desired_type: Type[T], file_path: str, encoding: str,
                            logger: Logger, **kwargs) -> pd.DataFrame:
    """
    We register this method rather than the other because pandas guesses the encoding by itself.

    Also, it is easier to put a breakpoint and debug by trying various options to find the good one (in streaming mode
    you just have one try and then the stream is consumed)

    :param desired_type:
    :param file_path:
    :param encoding:
    :param logger:
    :param kwargs:
    :return:
    """
    return pd.read_excel(file_path, **kwargs)


def read_df_or_series_from_csv(desired_type: Type[pd.DataFrame], file_path: str, encoding: str,
                               logger: Logger, **kwargs) -> pd.DataFrame:
    """
    Helper method to read a dataframe from a csv file. By default this is well suited for a dataframe with
    headers in the first row, for example a parameter dataframe.

    :param desired_type:
    :param file_path:
    :param encoding:
    :param logger:
    :param kwargs:
    :return:
    """
    if desired_type is pd.Series:
        # as recommended in http://pandas.pydata.org/pandas-docs/stable/generated/pandas.Series.from_csv.html
        # and from http://stackoverflow.com/questions/15760856/how-to-read-a-pandas-series-from-a-csv-file

        # TODO there should be a way to decide between row-oriented (squeeze=True) and col-oriented (index_col=0)
        # note : squeeze=true only works for row-oriented, so we dont use it. We rather expect that a row-oriented
        # dataframe would be convertible to a series using the df to series converter below
        if 'index_col' not in kwargs.keys():
            one_col_df = pd.read_csv(file_path, encoding=encoding, index_col=0, **kwargs)
        else:
            one_col_df = pd.read_csv(file_path, encoding=encoding, **kwargs)

        if one_col_df.shape[1] == 1:
            return one_col_df[one_col_df.columns[0]]
        else:
            raise Exception('Cannot build a series from this csv: it has more than two columns (one index + one value).'
                            ' Probably the parsing chain $read_df_or_series_from_csv => single_row_or_col_df_to_series$'
                            'will work, though.')
    else:
        return pd.read_csv(file_path, encoding=encoding, **kwargs)


def pandas_parsers_option_hints_csv():
    return 'all options from read_csv are supported, see http://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html'


def get_default_pandas_parsers() -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_dataframe_from_xls,
                                     streaming_mode=False,
                                     supported_exts={'.xls', '.xlsx', '.xlsm'},
                                     supported_types={pd.DataFrame},
                                     option_hints=pandas_parsers_option_hints_xls),
            SingleFileParserFunction(parser_function=read_df_or_series_from_csv,
                                     streaming_mode=False,
                                     supported_exts={'.csv', '.txt'},
                                     supported_types={pd.DataFrame, pd.Series},
                                     option_hints=pandas_parsers_option_hints_csv),
            ]


def dict_to_df(desired_type: Type[T], dict_obj: Dict, logger: Logger, orient: str = None, **kwargs) -> pd.DataFrame:
    """
    Helper method to convert a dictionary into a dataframe. It supports both simple key-value dicts as well as true
    table dicts. For this it uses pd.DataFrame constructor or pd.DataFrame.from_dict intelligently depending on the
    case.

    The orientation of the resulting dataframe can be configured, or left to default behaviour. Default orientation is
    different depending on the contents:
    * 'index' for 2-level dictionaries, in order to align as much as possible with the natural way to express rows in
    JSON
    * 'columns' for 1-level (simple key-value) dictionaries, so as to preserve the data types of the scalar values in
    the resulting dataframe columns if they are different

    :param desired_type:
    :param dict_obj:
    :param logger:
    :param orient: the orientation of the resulting dataframe.
    :param kwargs:
    :return:
    """

    if len(dict_obj) > 0:
        first_val = dict_obj[next(iter(dict_obj))]
        if isinstance(first_val, dict) or isinstance(first_val, list):
            # --'full' table

            # default is index orientation
            orient = orient or 'index'

            # if orient is 'columns':
            #     return pd.DataFrame(dict_obj)
            # else:
            return pd.DataFrame.from_dict(dict_obj, orient=orient)
        else:
            # --scalar > single-row or single-col

            # default is columns orientation
            orient = orient or 'columns'

            if orient is 'columns':
                return pd.DataFrame(dict_obj, index=[0])
            else:
                res = pd.DataFrame.from_dict(dict_obj, orient=orient)
                res.index.name = 'key'
                return res.rename(columns={0: 'value'})
    else:
        # for empty dictionaries, orientation does not matter
        # but maybe we should still create a column 'value' in this empty dataframe ?
        return pd.DataFrame.from_dict(dict_obj)


def dict_to_single_row_or_col_df_opts():
    return 'orient: either \'columns\'(default) or \'index\'. Determines if the resulting dataframe will contain the ' \
           'keys of the dictionary as column names (default) or row index names.'


def single_row_or_col_df_to_series(desired_type: Type[T], single_rowcol_df: pd.DataFrame, logger: Logger, **kwargs)\
        -> pd.Series:
    """
    Helper method to convert a dataframe with one row or one or two columns into a Series

    :param desired_type:
    :param single_col_df:
    :param logger:
    :param kwargs:
    :return:
    """
    if single_rowcol_df.shape[0] == 1:
        # one row
        return single_rowcol_df.transpose()[0]
    elif single_rowcol_df.shape[1] == 2 and isinstance(single_rowcol_df.index, pd.RangeIndex):
        # two columns but the index contains nothing but the row number : we can use the first column
        d = single_rowcol_df.set_index(single_rowcol_df.columns[0])
        return d[d.columns[0]]
    elif single_rowcol_df.shape[1] == 1:
        # one column and one index
        d = single_rowcol_df
        return d[d.columns[0]]
    else:
        raise ValueError('Unable to convert provided dataframe to a series : '
                         'expected exactly 1 row or 1 column, found : ' + str(single_rowcol_df.shape) + '')


def single_row_or_col_df_to_dict(desired_type: Type[T], single_rowcol_df: pd.DataFrame, logger: Logger, **kwargs)\
        -> Dict[str, str]:
    """
    Helper method to convert a dataframe with one row or one or two columns into a dictionary

    :param desired_type:
    :param single_rowcol_df:
    :param logger:
    :param kwargs:
    :return:
    """
    if single_rowcol_df.shape[0] == 1:
        return single_rowcol_df.transpose()[0].to_dict()
        # return {col_name: single_rowcol_df[col_name][single_rowcol_df.index.values[0]] for col_name in single_rowcol_df.columns}
    elif single_rowcol_df.shape[1] == 2 and isinstance(single_rowcol_df.index, pd.RangeIndex):
        # two columns but the index contains nothing but the row number : we can use the first column
        d = single_rowcol_df.set_index(single_rowcol_df.columns[0])
        return d[d.columns[0]].to_dict()
    elif single_rowcol_df.shape[1] == 1:
        # one column and one index
        d = single_rowcol_df
        return d[d.columns[0]].to_dict()
    else:
        raise ValueError('Unable to convert provided dataframe to a parameters dictionary : '
                         'expected exactly 1 row or 1 column, found : ' + str(single_rowcol_df.shape) + '')


def get_default_pandas_converters() -> List[Union[Converter[Any, pd.DataFrame],
                                                  Converter[pd.DataFrame, Any]]]:
    """
    Utility method to return the default converters associated to dataframes (from dataframe to other type,
    and from other type to dataframe)
    :return:
    """
    return [ConverterFunction(from_type=pd.DataFrame, to_type=dict, conversion_method=single_row_or_col_df_to_dict),
            ConverterFunction(from_type=dict, to_type=pd.DataFrame, conversion_method=dict_to_df,
                              option_hints=dict_to_single_row_or_col_df_opts),
            ConverterFunction(from_type=pd.DataFrame, to_type=pd.Series,
                              conversion_method=single_row_or_col_df_to_series)]

