import os

from typing import Union, Dict

from parsyfiles import RootParser

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'unions_data', *args)


def test_union_1(root_parser: RootParser):
    """ Tests that parsing a Union works """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B:
        def __init__(self, bar: float):
            self.bar = bar

    item = root_parser.parse_item(get_path('test1', 'a'), Union[A, B])
    assert type(item) == A


def test_union_2(root_parser: RootParser):
    """ Tests that parsing a collection of Union works """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B:
        def __init__(self, bar: float):
            self.bar = bar

    items = root_parser.parse_collection(get_path('test1'), Union[A, B])
    assert len(items) == 2
    assert type(items['a']) == A
    assert type(items['b']) == B


def test_union_recursive_1(root_parser: RootParser):
    """ Tests that you can parse infinitely-nested dictionaries from a folder using forward references """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    # First (preferred) way
    InfiniteRecursiveDictOfA = Dict[str, Union[A, 'InfiniteRecursiveDictOfA']]

    items = root_parser.parse_item(get_path('test2'), InfiniteRecursiveDictOfA)

    assert type(items['a']['a']['a']) == A
    assert type(items['a']['a']['b']) == A
    assert type(items['a']['b']) == A
    assert type(items['b']) == A

    # Less preferred way, but check that it works too
    InfiniteRecursiveDictOfA2 = Union[A, Dict[str, 'InfiniteRecursiveDictOfA2']]

    items = root_parser.parse_collection(get_path('test2'), InfiniteRecursiveDictOfA2)

    assert type(items['a']['a']['a']) == A
    assert type(items['a']['a']['b']) == A
    assert type(items['a']['b']) == A
    assert type(items['b']) == A

    # This is a forward reference that is equivalent to 'A'.
    # It should be handled correctly by parsyfiles so as not to lead to infinite recursiong
    InfiniteRecursiveDictOfA3 = Union[A, 'InfiniteRecursiveDictOfA3']

    item = root_parser.parse_item(get_path('test2', 'b'), InfiniteRecursiveDictOfA3)
    assert type(item) == A
