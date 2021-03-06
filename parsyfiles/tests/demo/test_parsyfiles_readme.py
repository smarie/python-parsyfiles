import os
import time
from logging import getLogger
from pprint import pprint
from typing import List, Any, Tuple, Dict, Set
from unittest import TestCase

from valid8 import is_in
from parsyfiles import parse_collection, RootParser, parse_item, ObjectNotFoundOnFileSystemError
from parsyfiles.converting_core import AnyObject
from parsyfiles.parsing_core import SingleFileParserFunction
from parsyfiles.parsing_core_api import ParsingException

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def fix_path(relative_path: str):
    """
    Helper method to transform a path relative to 'parsyfiles/' folder into an absolute path independent on the test 
    execution dir
    
    :param relative_path: 
    :return: 
    """
    return os.path.join(THIS_DIR, relative_path)


class DemoTests(TestCase):
    """
    The tests used in the README.md examples
    """

    def test_a_helloworld(self):

        with self.assertRaises(FileNotFoundError):
            result = parse_item(fix_path('hello_world'), str)

        with self.assertRaises(ObjectNotFoundOnFileSystemError):
            result = parse_item(fix_path('a_helloworld/hello_world.txt'), str)

        result = parse_item(fix_path('a_helloworld/hello_world'), str)
        print(result)
        assert result == 'hello'

    def test_simple_collection(self):
        """
        Parsing a collection of dataframes as a dictionary
        :return:
        """
        from pandas import DataFrame
        dfs = parse_collection(fix_path('./simple_collection'), DataFrame)
        pprint(dfs)

        df = parse_item(fix_path('./simple_collection/c'), DataFrame)
        pprint(df)

        RootParser().print_capabilities_for_type(typ=DataFrame)

    def test_simple_collection_set_list_tuple(self):
        """
        Parsing a collection of dataframes as a list or a tuple
        :return:
        """
        from pandas import DataFrame
        dfl = parse_item(fix_path('./simple_collection'), List[DataFrame])
        pprint(dfl)
        # dataframe objects_data are not mutable > can't be hashed and therefore no set can be built
        # dfs = parse_item('./simple_collection', Set[DataFrame], logger=getLogger())
        # pprint(dfs)
        dft = parse_item(fix_path('./simple_collection'),
                         Tuple[DataFrame, DataFrame, DataFrame, DataFrame, DataFrame])
        pprint(dft)

    def test_simple_collection_nologs(self):
        """
        parsing a collection of dataframe with a different logger
        :return:
        """
        from pandas import DataFrame
        dfs = parse_collection(fix_path('./simple_collection'), DataFrame, logger=getLogger())
        pprint(dfs)

        df = parse_item(fix_path('./simple_collection/c'), DataFrame, logger=getLogger())
        pprint(df)

        # -- this defaults to the default logger, so not interesting to test
        # dfs = parse_collection('./simple_collection', DataFrame, logger=None)
        # pprint(dfs)
        #
        # df = parse_item('./simple_collection/c', DataFrame, logger=None)
        # pprint(df)

    def test_simple_collection_lazy(self):
        """
        Parsing a collection of dataframes in lazy mode
        :return:
        """
        from pandas import DataFrame
        dfs = parse_collection(fix_path('./simple_collection'), DataFrame,
                               lazy_mfcollection_parsing=True)

        # check len
        assert len(dfs) == 5
        print('dfs length : ' + str(len(dfs)))

        # check keys
        assert dfs.keys() == {'a','b','c','d','e'}
        # assert that they are sorted
        assert list(dfs.keys()) == list(sorted(dfs.keys()))
        print('dfs keys : ' + str(dfs.keys()))

        # check contains
        self.assertTrue('b' in dfs)
        print('Is b in dfs : ' + str('b' in dfs))

        # check iter
        self.assertEquals({key for key in dfs}, {'a', 'b', 'c', 'd', 'e'})

        # check get
        self.assertIsNotNone(dfs.get('b'))
        pprint(dfs.get('b'))

        # check values
        for value in dfs.values():
            print(value)

        # check items
        for key, value in dfs.items():
            print(value)

        # finally print
        pprint(dfs)

    def test_simple_objects(self):
        """
        Parsing a collection of simple objects_data
        :return:
        """

        # First define the function that we want to test
        # (not useful, but just to show a complete story in the readme...)
        def exec_op(x: float, y: float, op: str) -> float:
            if op is '+':
                return x + y
            elif op is '-':
                return x - y
            else:
                raise ValueError('Unsupported operation : \'' + op + '\'')

        # Then define the simple class representing your test case
        class ExecOpTest(object):
            def __init__(self, x: float, y: float, op: str, expected_result: float):
                self.x = x
                self.y = y
                self.op = op
                self.expected_result = expected_result

            def __str__(self):
                return self.__repr__()

            def __repr__(self):
                return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)

        # Create the parser and parse a single file
        # e = parse_item('./test_data/objects_data/test_diff_1', ExecOpTest)
        # pprint(e)

        # parse all of them as dicts
        sf_tests_dct = parse_collection(fix_path('./simple_objects'), Dict)

        # assert that they are sorted
        assert list(sf_tests_dct.keys()) == list(sorted(sf_tests_dct.keys()))

        # parse all of them as objects_data
        sf_tests = parse_collection(fix_path('./simple_objects'), ExecOpTest)
        pprint(sf_tests)

        #
        RootParser().print_capabilities_for_type(typ=ExecOpTest)

    def test_simple_object_with_contract_autoclass_pycontract(self):
        """
        Parsing a collection of simple objects_data where the class is defined with `autoclass` and PyContracts
        :return:
        """

        from autoclass import autoprops, autoargs
        from contracts import contract, new_contract

        # custom contract used in the class
        new_contract('allowed_op', lambda x: x in {'+','*'})

        @autoprops
        class ExecOpTest(object):
            @autoargs
            @contract(x='int|float', y='int|float', op='str,allowed_op', expected_result='int|float')
            def __init__(self, x: float, y: float, op: str, expected_result: float):
                pass

            def __repr__(self):
                return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)

        try:
            sf_tests = parse_item(fix_path('./simple_objects/test_diff_1'), ExecOpTest)
        except ParsingException as e:
            self.assertIn("<class 'contracts.interface.ContractNotRespected'>"
                          + " Breach for argument 'op' to ExecOpTest:autoprops_generated_setter().\n"
                          + "Value does not pass criteria of <lambda>()() (module:", e.args[0])
            self.assertIn("checking: callable()       for value: Instance of <class 'str'>: '-'   \n"
                          + "checking: allowed_op       for value: Instance of <class 'str'>: '-'   \n"
                          + "checking: str,allowed_op   for value: Instance of <class 'str'>: '-'"
                          , e.args[0])

    def test_simple_object_with_contract_autoclass_enforce(self):
        """
        Parsing a collection of simple objects_data where the class is defined with `autoclass` and enforce
        :return:
        """

        from autoclass import autoprops, autoargs
        from valid8 import validate_io, gt, minlens
        from enforce import runtime_validation, config
        from numbers import Real, Integral

        config(dict(mode='covariant'))  # to accept subclasses in validation

        # this first example is in the index.md
        @runtime_validation
        @autoprops
        class MySimpleObject:
            @validate_io(age=gt(0), name=minlens(0))
            @autoargs
            def __init__(self, age: Integral, name: str):
                pass

        MySimpleObject(0, 'r')

        @runtime_validation
        @autoprops
        class ExecOpTest(object):
            @autoargs
            @validate_io(op=is_in({'+', '*'}))
            def __init__(self, x: Real, y: Real, op: str, expected_result: Real):
                pass

            def __repr__(self):
                return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)

        try:
            sf_tests = parse_item(fix_path('./simple_objects/test_diff_1'), ExecOpTest)
        except ParsingException as e:
            self.assertIn("InputValidationError[ValueError]", e.args[0])

    def test_simple_object_with_contract_attrs(self):
        """
        Parsing a collection of simple objects_data where the class is defined with `attrs`
        :return:
        """

        import attr
        from attr.validators import instance_of
        from parsyfiles.plugins_optional.support_for_attrs import chain

        # custom contract used in the class
        def validate_io_op(instance, attribute, value):
            allowed = {'+', '*'}
            if value not in allowed:
                raise ValueError('\'op\' has to be a string, in ' + str(allowed) + '!')

        @attr.s
        class ExecOpTest(object):
            x = attr.ib(convert=float, validator=instance_of(float))
            y = attr.ib(convert=float, validator=instance_of(float))
            op = attr.ib(convert=str, validator=chain(instance_of(str), validate_io_op))
            expected_result = attr.ib(convert=float, validator=instance_of(float))

        try:
            sf_tests = parse_collection(fix_path('./simple_objects'), ExecOpTest)
        except ParsingException as e:
            self.assertIn('<class \'ValueError\'> \'op\' has to be a string, in ', e.args[0])

    def test_multifile_objects(self):
        """
        Parsing a list of multifile objects_data
        :return:
        """
        from pandas import Series, DataFrame

        class AlgoConf(object):
            def __init__(self, foo_param: str, bar_param: int):
                self.foo_param = foo_param
                self.bar_param = bar_param

        class AlgoResults(object):
            def __init__(self, score: float, perf: float):
                self.score = score
                self.perf = perf

        def exec_op_series(x: Series, y: AlgoConf) -> AlgoResults:
            pass

        class ExecOpSeriesTest(object):
            def __init__(self, x: Series, y: AlgoConf, expected_results: AlgoResults):
                self.x = x
                self.y = y
                self.expected_results = expected_results

        # parse all of them
        mf_tests = parse_collection(fix_path('./complex_objects'), ExecOpSeriesTest)
        pprint(mf_tests)

        RootParser().print_capabilities_for_type(typ=ExecOpSeriesTest)

        from parsyfiles import FlatFileMappingConfiguration
        dfs = parse_collection(fix_path('./complex_objects_flat'), DataFrame,
                               file_mapping_conf=FlatFileMappingConfiguration())
        pprint(dfs)

    def test_simple_collection_dataframe_all(self):
        """
        All the possible ways to parse a dataframe
        :return:
        """
        from pandas import DataFrame
        # TODO recreate a t_pickle.pyc example with latest version of pandas (current file is obsolete)
        dfs = parse_collection(fix_path('./simple_collection_dataframe_inference'), DataFrame)
        pprint(dfs)

    def test_pass_parser_options(self):
        """
        Passes options to the pandas parser
        :return:
        """
        from pandas import DataFrame
        from parsyfiles import RootParser

        # create a root parser
        parser = RootParser()

        # retrieve the parsers of interest
        parsers = parser.get_capabilities_for_type(DataFrame, strict_type_matching=False)
        df_csv_parser = parsers['.csv']['1_exact_match'][0]
        p_id_csv = df_csv_parser.get_id_for_options()
        print('Parser id for csv is : ' + p_id_csv + ', implementing function is ' + repr(df_csv_parser._parser_func))
        print('option hints : ' + df_csv_parser.options_hints())
        df_xls_parser = parsers['.xls']['1_exact_match'][0]
        p_id_xls = df_xls_parser.get_id_for_options()
        print('Parser id for csv is : ' + p_id_xls + ', implementing function is ' + repr(df_xls_parser._parser_func))
        print('option hints : ' + df_xls_parser.options_hints())

        from parsyfiles import create_parser_options, add_parser_options

        # configure the DataFrame parsers to automatically parse dates and use the first column as index
        opts = create_parser_options()
        opts = add_parser_options(opts, 'read_df_or_series_from_csv', {'parse_dates': True, 'index_col': 0})
        opts = add_parser_options(opts, 'read_dataframe_from_xls', {'index_col': 0})

        dfs = parser.parse_collection(fix_path('./ts_collection'), DataFrame, options=opts)
        print(dfs)

    def test_parse_subclass_of_known_with_custom_converter(self):
        """
        Parses a subclass of DataFrame with a custom converter.
        :return:
        """

        # define your class
        from pandas import DataFrame, DatetimeIndex

        class TimeSeries(DataFrame):
            """
            A basic timeseries class that extends DataFrame
            """

            def __init__(self, df: DataFrame):
                """
                Constructor from a DataFrame. The DataFrame index should be an instance of DatetimeIndex
                :param df:
                """
                if isinstance(df, DataFrame) and isinstance(df.index, DatetimeIndex):
                    if df.index.tz is None:
                        df.index = df.index.tz_localize(tz='UTC')# use the UTC hypothesis in absence of other hints
                    self._df = df
                else:
                    raise ValueError('Error creating TimeSeries from DataFrame: provided DataFrame does not have a '
                                     'valid DatetimeIndex')

            def __getattr__(self, item):
                # Redirects anything that is not implemented here to the base dataframe.
                # this is called only if the attribute was not found the usual way

                # easy version of the dynamic proxy just to save time :)
                # see http://code.activestate.com/recipes/496741-object-proxying/ for "the answer"
                df = object.__getattribute__(self, '_df')
                if hasattr(df, item):
                    return getattr(df, item)
                else:
                    raise AttributeError('\'' + self.__class__.__name__ + '\' object has no attribute \'' + item + '\'')

            def update(self, other, join='left', overwrite=True, filter_func=None, raise_conflict=False):
                """ For some reason this method was abstract in DataFrame so we have to implement it """
                return self._df.update(other, join=join, overwrite=overwrite, filter_func=filter_func,
                                       raise_conflict=raise_conflict)

        # -- create your converter
        from typing import Type
        from logging import Logger
        from parsyfiles.converting_core import ConverterFunction

        def df_to_ts(desired_type: Type[TimeSeries], df: DataFrame, logger: Logger) -> TimeSeries:
            """ Converter from DataFrame to TimeSeries """
            return TimeSeries(df)

        my_converter = ConverterFunction(from_type=DataFrame, to_type=TimeSeries, conversion_method=df_to_ts)

        # -- create a parser and register your converter
        from parsyfiles import RootParser, create_parser_options, add_parser_options

        parser = RootParser('parsyfiles with timeseries')
        parser.register_converter(my_converter)

        # -- you might wish to configure the DataFrame parser, though:
        opts = create_parser_options()
        opts = add_parser_options(opts, 'read_df_or_series_from_csv', {'parse_dates': True, 'index_col': 0})
        opts = add_parser_options(opts, 'read_dataframe_from_xls', {'index_col': 0})

        dfs = parser.parse_collection(fix_path('./ts_collection'), TimeSeries, options=opts)

    def test_parse_with_custom_parser(self):
        """
        Parses a subclass of DataFrame with a custom converter.
        :return:
        """

        from typing import Type
        from parsyfiles.converting_core import T
        from logging import Logger
        from xml.etree.ElementTree import ElementTree, parse, tostring

        def read_xml(desired_type: Type[T], file_path: str, encoding: str,
                     logger: Logger, **kwargs):
            """
            Opens an XML file and returns the tree parsed from it as an ElementTree.

            :param desired_type:
            :param file_path:
            :param encoding:
            :param logger:
            :param kwargs:
            :return:
            """
            return parse(file_path)

        my_parser = SingleFileParserFunction(parser_function=read_xml,
                                             streaming_mode=False,
                                             supported_exts={'.xml'},
                                             supported_types={ElementTree})

        parser = RootParser('parsyfiles with timeseries')
        parser.register_parser(my_parser)
        xmls = parser.parse_collection(fix_path('./xml_collection'), ElementTree)
        pprint({name: tostring(x.getroot()) for name, x in xmls.items()})
