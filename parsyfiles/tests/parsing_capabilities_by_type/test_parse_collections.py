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
