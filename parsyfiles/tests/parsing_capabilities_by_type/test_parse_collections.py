import os
from typing import Tuple, Dict, List, Set

from parsyfiles import parse_item

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'collections_data', *args)


def test_collections(root_parser):
    """
    Tests all the supported ways to parse collections_data
    :return:
    """
    l = parse_item(get_path('.'), Tuple[Dict[str, int], List[int], Set[int], Tuple[str, int, str]])
    print(l)


class Foo:
    def __init__(self, id: str, info: str):
        self.id = id
        self.info = info

    def __eq__(self, other):
        return self.id == other.id and self.info == other.info


class FooDct(Dict):
    def __init__(self, foo1: Foo, foo2: Foo):
        self.foo1 = foo1
        self.foo2 = foo2


def test_nested_and_custom_dict1(root_parser):
    """ tests that a collection of custom type works """

    result = root_parser.parse_item(os.path.join(THIS_DIR, 'collections_data2', 'foo_file'), Dict[str, Foo])
    assert type(result['foo1']) == Foo
    assert result['foo1'] == Foo('a', 'b')


def test_nested_and_custom_dict2(root_parser):
    """ Tests that a dictionary of custom collection type works """

    result = root_parser.parse_item(os.path.join(THIS_DIR, 'collections_data2', 'foo_file2'), Dict[str, FooDct])
    assert type(result['a']) == FooDct
    assert result['a'].foo1 == Foo('a', 'b')


def test_nested_and_custom_dict3(root_parser):
    """ Tests that a custom collection type works """
    result = root_parser.parse_item(os.path.join(THIS_DIR, 'collections_data2', 'foo_file'), FooDct)
    assert type(result) == FooDct
    assert result.foo1 == Foo('a', 'b')
