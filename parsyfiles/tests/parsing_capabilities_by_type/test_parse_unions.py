import os

from typing import Union

from parsyfiles import RootParser

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'unions_data', *args)


def test_union_1(root_parser: RootParser):
    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B:
        def __init__(self, bar: float):
            self.bar = bar

    item = root_parser.parse_item(get_path('test1/a'), Union[A, B])
    assert type(item) == A


def test_union_2(root_parser: RootParser):
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