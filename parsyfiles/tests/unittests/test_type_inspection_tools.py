from numbers import Integral
from typing import Tuple, List, Dict, Set, Any, Union, Callable, Optional, TypeVar, Generic

from parsyfiles.type_inspection_tools import robust_isinstance, get_base_generic_type, is_collection, \
    _extract_collection_base_type

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
