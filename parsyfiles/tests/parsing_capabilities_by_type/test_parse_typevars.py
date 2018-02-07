import os

from typing import TypeVar, Generic

from parsyfiles import RootParser

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'typevars_data', *args)


def test_typevars_1(root_parser: RootParser):
    """ Tests that a constructor containing TypeVars is correctly handled """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B(A):
        def __init__(self, bar: float):
            super(B, self).__init__(foo=bar)

    TV = TypeVar('TV', bound=A)

    class Test(Generic[TV]):
        def __init__(self, obj: TV):
            self.obj = obj

    items = root_parser.parse_collection(get_path('test1'), Test)

    assert len(items) == 2
    assert type(items['a'].obj) == A
    assert type(items['b'].obj) == B


def test_typevars_2(root_parser: RootParser):
    """ Tests that a TypeVar with 'bound' may be used as a desired Type directly -> it will be replaced with the bound 
    type """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B(A):
        def __init__(self, bar: float):
            super(B, self).__init__(foo=str(bar))

    TV = TypeVar('TV', bound=A)

    item = root_parser.parse_item(get_path('test2/a'), TV)
    assert type(item) == A

    item = root_parser.parse_item(get_path('test2/b'), TV)
    assert type(item) == B

    items = root_parser.parse_collection(get_path('test2'), TV)

    assert len(items) == 2
    assert type(items['a']) == A
    assert type(items['b']) == B


def test_typevars_3(root_parser: RootParser):
    """ Tests that a TypeVar with 'constraints' may be used as a desired Type -> it will be a Union """

    class A:
        def __init__(self, foo: str):
            self.foo = foo

    class B:
        def __init__(self, bar: float):
            self.bar = bar

    TV = TypeVar('TV', A, B)

    item = root_parser.parse_item(get_path('test2/a'), TV)
    assert type(item) == A

    item = root_parser.parse_item(get_path('test2/b'), TV)
    assert type(item) == B

    items = root_parser.parse_collection(get_path('test2'), TV)

    assert len(items) == 2
    assert type(items['a']) == A
    assert type(items['b']) == B
