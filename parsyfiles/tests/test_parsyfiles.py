import time
from logging import getLogger
from pprint import pprint
from typing import List, Any, Tuple, Dict, Set
from unittest import TestCase

from pandas import DataFrame, Series

from parsyfiles import parse_collection, RootParser, parse_item


class Timer(object):
    def __init__(self, name=None):
        self.name = name

    def __enter__(self):
        self.tstart = time.time()

    def __exit__(self, type, value, traceback):
        if self.name:
            print('[%s]' % self.name)
        print('Elapsed: %s' % (time.time() - self.tstart))


class AllTests(TestCase):

    def setUp(self):
        self.root_parser = RootParser()

    def test_a_root_parser_capabilities(self):
        p = self.root_parser.get_all_parsers(strict_type_matching=False)
        print('\n' + str(len(p)) + ' Root parser parsers:')
        pprint(p)
        c = self.root_parser.get_all_conversion_chains()
        print('\n' + str(len(c[0]) + len(c[2])) + ' Root parser converters:')
        pprint(c)
        e = self.root_parser.get_all_supported_exts()
        print('\n' + str(len(e)) + ' Root parser supported extensions:')
        pprint(e)
        t = self.root_parser.get_all_supported_types_pretty_str()
        print('\n' + str(len(t)) + ' Root parser supported types:')
        pprint(t)
        print('\nRoot parser parsers by extensions:')
        self.root_parser.print_capabilities_by_ext(strict_type_matching=False)
        print('\nRoot parser parsers by types:')
        self.root_parser.print_capabilities_by_type(strict_type_matching=False)
        return

    def test_b_root_parser_any(self):
        # print
        self.root_parser.print_capabilities_for_type(typ=Any)

        # details
        res = self.root_parser.find_all_matching_parsers(strict=False, desired_type=Any, required_ext='.cfg')
        match_generic, match_approx, match_exact = res[0]
        self.assertEquals(len(match_generic), 0)
        self.assertEquals(len(match_approx), 0)

    def test_objects_support(self):

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

        # create the parser and parse a single file
        e = parse_item('./test_data/objects/test_diff_1', ExecOpTest)
        pprint(e)

        # parse all of them
        e = parse_collection('./test_data/objects', ExecOpTest)
        pprint(e)

    def test_simple_object_with_contract(self):

        from classtools_autocode import autoprops, autoargs
        from contracts import contract, new_contract

        # custom contract needed in the class
        new_contract('allowed_op', lambda x: x in {'+', '-'})

        @autoprops
        class ExecOpTest(object):
            @autoargs
            @contract(x='int|float', y='int|float', op='str,allowed_op', expected_result='int|float')
            def __init__(self, x: float, y: float, op: str, expected_result: float):
                pass

        # Test
        # create the parser and parse a single file
        e = parse_item('./test_data/objects/test_diff_1', ExecOpTest)
        print(e.x)
        print(e.y)
        print(e.op)
        print(e.expected_result)

        l = parse_collection('./test_data/objects', ExecOpTest)
        pprint(l)

    def test_collections(self):
        l = parse_item('./test_data/collections', Tuple[Dict[str, int], List[int], Set[int], Tuple[str, int, str]])
        print(l)


class DemoTests(TestCase):

    def test_simple_collection(self):
        dfs = parse_collection('./test_data/demo/simple_collection', DataFrame)
        pprint(dfs)

        df = parse_item('./test_data/demo/simple_collection/c', DataFrame)
        pprint(df)

        RootParser().print_capabilities_for_type(typ=DataFrame)

    def test_simple_collection_set_list_tuple(self):
        dfl = parse_item('./test_data/demo/simple_collection', List[DataFrame], logger=getLogger())
        pprint(dfl)
        # dataframe objects are not mutable > can't be hashed and therefore no set can be built
        #dfs = parse_item('./test_data/demo/simple_collection', Set[DataFrame], logger=getLogger())
        #pprint(dfs)
        dft = parse_item('./test_data/demo/simple_collection', Tuple[DataFrame, DataFrame, DataFrame, DataFrame, DataFrame],
                         logger=getLogger())
        pprint(dft)


    def test_simple_collection_nologs(self):
        dfs = parse_collection('./test_data/demo/simple_collection', DataFrame, logger=getLogger())
        pprint(dfs)

        df = parse_item('./test_data/demo/simple_collection/c', DataFrame, logger=getLogger())
        pprint(df)

        # this defaults to the default logger
        # dfs = parse_collection('./test_data/demo/simple_collection', DataFrame, logger=None)
        # pprint(dfs)
        #
        # df = parse_item('./test_data/demo/simple_collection/c', DataFrame, logger=None)
        # pprint(df)


    def test_simple_collection_lazy(self):
        dfs = parse_collection('./test_data/demo/simple_collection', DataFrame, lazy_mfcollection_parsing=True)
        # check len
        self.assertEquals(len(dfs), 5)
        # check keys
        self.assertEquals(dfs.keys(), {'a','b','c','d','e'})
        # check contains
        self.assertTrue(dfs.__contains__('b'))
        # check iter
        self.assertEquals({key for key in dfs}, {'a', 'b', 'c', 'd', 'e'})
        # check get
        self.assertIsNotNone(dfs.get('b'))
        # check values
        for value in dfs.values():
            print(value)
        # check items
        for key, value in dfs.items():
            print(value)
        # finally print
        pprint(dfs)

    def test_simple_objects(self):
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
        # e = parse_item('./test_data/objects/test_diff_1', ExecOpTest)
        # pprint(e)

        # parse all of them
        sf_tests = parse_collection('./test_data/demo/simple_objects', ExecOpTest)
        pprint(sf_tests)

        #
        RootParser().print_capabilities_for_type(typ=ExecOpTest)

    def test_multifile_objects(self):

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
        mf_tests = parse_collection('./test_data/demo/complex_objects', ExecOpSeriesTest)
        pprint(mf_tests)

        RootParser().print_capabilities_for_type(typ=ExecOpSeriesTest)

    def test_simple_collection_dataframe_all(self):
        dfs = parse_collection('./test_data/demo/simple_collection_dataframe_inference', DataFrame)
        pprint(dfs)
