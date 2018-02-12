from numbers import Integral
from typing import Tuple, List, Dict, Set, Any, Union, Callable, Optional, TypeVar, Generic

from parsyfiles.type_inspection_tools import robust_isinstance, get_base_generic_type, is_collection, \
    _extract_collection_base_type, get_all_subclasses, get_alternate_types_resolving_forwardref_union_and_typevar

import pytest

T = TypeVar('T')

test_robust_isinstance_data = [
    # standard type
    ('r', str, True),
    ('r', int, False),
    # typing types
    ([], List, True),
    ([], Set, False),
    ({1: 2}, Dict, True),
    (set(), Set, True),
    # special typing types
    (T, TypeVar, True),
    (T, str, False),
    ((1, 2), Tuple, True),
    ([], Union[Any, str], True),
    (lambda x: x, Callable, True),
    (lambda x: x, Tuple, False),
    # parametrized generic types
    ((1, 2), Tuple[Integral, Integral], True),
    ((1, 2), Tuple[str, str], True),            # just to show that this does not take internal type into account
    (['r', None], List[str], True),
    ({1: 2}, Dict[Any, Any], True),
    ({1: 2}, Set[Any], False),
    (set(), Set[str], True),
]


@pytest.mark.parametrize('inst, typ, expected', test_robust_isinstance_data, ids=str)
def test_robust_isinstance(inst, typ, expected):
    assert robust_isinstance(inst, typ) == expected


test_get_base_generic_type_data = [
    # standard types
    (str, str),
    (int, int),
    # non-parametrized generic types
    (Dict, Dict),
    (List, List),
    (Set, Set),
    (Tuple, Tuple),
    # parametrized generic types
    (Dict[str, int], Dict),
    (List[List[str]], List),
    (Set[str], Set),
    (Tuple[int, str], Tuple),
    # special cases
    (Any, Any),
    (Union, Union),
    (Optional[Any], Union)  # Optional is a Union
]


@pytest.mark.parametrize('typ, expected', test_get_base_generic_type_data, ids=str)
def test_get_base_generic_type(typ, expected):
    assert get_base_generic_type(typ) == expected


class MyDict(dict):
    pass


class MyDict2(Dict):
    pass


class MyDict3(Dict[str, int]):
    pass


class MyDict4(Dict, Generic[T]):
    pass


test_is_collection_data = [
    # standard types
    (str, True, False),
    (int, False, False),
    (list, True, True),
    (list, False, True),
    (set, True, True),
    (dict, True, True),
    (tuple, True, True),
    # non-parametrized generic types
    (Dict, True, True),
    (List, True, True),
    (Set, True, True),
    (Tuple, True, True),
    # parametrized generic types
    (Dict[str, int], True, True),
    (List[List[str]], True, True),
    (Set[str], True, True),
    (Tuple[int, str], True, True),
    # extensions
    (MyDict, True, False),
    (MyDict, False, True),
    (MyDict2, True, False),
    (MyDict2, False, True),
    (MyDict3, True, False),
    (MyDict3, False, True),
    (MyDict4, True, False),
    (MyDict4, False, True),
    # special cases
    (Any, False, False),
    (Union, False, False),
    (Optional[Any], False, False)
]


@pytest.mark.parametrize('typ, strict, expected', test_is_collection_data, ids=str)
def test_is_collection(typ, strict, expected):
    assert is_collection(typ, strict=strict) == expected


test_extract_collection_base_type_data = [
    (Dict[str, int], (int, str)),
    (Set[int], (int, None)),
    (List[int], (int, None)),
    (Tuple[int, str], ((int, str), None)),
    (Dict[str, Tuple[int, str]], (Tuple[int, str], str)),
    (Tuple[Dict[str, int], List[int], Set[int], Tuple[str, int, str]], ((Dict[str, int], List[int], Set[int], Tuple[str, int, str]), None))
    ]


@pytest.mark.parametrize('typ, expected', test_extract_collection_base_type_data, ids=str)
def test__extract_collection_base_type(typ, expected):
    assert _extract_collection_base_type(typ) == expected


def test_get_alternate_types_resolving_forwardref_union_and_typevar():
    """ Tests that infinite recursion is prevented when using forward references """

    InfiniteRecursiveDictOfInt = Union[int, 'InfiniteRecursiveDictOfInt']
    assert get_alternate_types_resolving_forwardref_union_and_typevar(InfiniteRecursiveDictOfInt) == (int, )


def test_get_subclasses_simple():
    """ Checks that the method to get all subclasses is recursive """

    class A:
        pass

    class B(A):
        def __init__(self, foo: str):
            self.foo = foo

    class C(B):
        def __init__(self, bar: str):
            super(C, self).__init__(foo=bar)

    assert get_all_subclasses(A) == [B, C]


def test_get_subclasses_generic():
    """ Tests that the method to get all subclasses works even in Generic cases """

    from typing import TypeVar, Generic

    T = TypeVar('T', covariant=True)
    U = TypeVar('U', covariant=True)

    class FullUnparam(Generic[T, U]):
        pass

    class FullUnparam2(FullUnparam):
        pass

    class HalfParam(FullUnparam[T, int]):
        pass

    class EntirelyParam(FullUnparam[str, int]):
        pass

    class EntirelyParam2(HalfParam[str]):
        pass

    # def get_all_subclasses(cls):
    #     from pytypes.type_util import _find_base_with_origin
    #     from pytypes import is_subtype
    #     orig = _find_base_with_origin(cls, object)
    #     res = cls.__subclasses__()
    #     if not orig is None and hasattr(orig, "__origin__") and not orig.__origin__ is None:
    #         candidates = orig.__origin__.__subclasses__()
    #         for candidate in candidates:
    #             if candidate != cls and is_subtype(candidate, cls):
    #                 res.append(candidate)
    #     return res

    # This works with FullUnparam.__subclasses__() today
    assert get_all_subclasses(FullUnparam) == [FullUnparam2, FullUnparam[T, int], HalfParam, HalfParam[str], FullUnparam[str, int], EntirelyParam, EntirelyParam2]  # EntirelyParam2 is missing

    # This does not work with FullUnparam.__subclasses__() today. Maybe a bug of stdlib ?
    assert get_all_subclasses(FullUnparam[str, int]) == [EntirelyParam, HalfParam[str], EntirelyParam2]  # Wrong: also contains FullUnparam2, FullUnparam[+T, int], HalfParam, FullUnparam[str, int] ???

    # This does not work with HalfParam.__subclasses__() today.
    assert get_all_subclasses(HalfParam) == [HalfParam[str], EntirelyParam2]

    assert get_all_subclasses(HalfParam[str]) == [EntirelyParam2]

    # # variant 1:  only Generic subclasses
    # assert get_all_subclasses(FullUnparam, only_generics=True) == [FullUnparam2, HalfParam]
    # assert get_all_subclasses(HalfParam, only_generics=True) == []
    #
    # # variant 2: only Generic subclasses with same number of free parameters
    # assert get_all_subclasses(FullUnparam, only_generics=True, parametrized=False) == [FullUnparam2]
