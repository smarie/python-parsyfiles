import os
from pprint import pprint

import pytest

from parsyfiles.tests.parsing_capabilities_by_type.test_parse_custom_object import ExecOpTest, exec_op
from parsyfiles import parse_collection, parse_item, get_capabilities_for_type

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# check that we can parse this type
pprint(get_capabilities_for_type(ExecOpTest))

# let's parse the collection of tests
cases = parse_collection(os.path.join(THIS_DIR, '../parsing_capabilities_by_type/objects_data'), ExecOpTest,
                         lazy_mfcollection_parsing=True)


@pytest.mark.parametrize("case_name", cases.keys())
def test_simple_objects(case_name: str):
    """ pytest integration tests: reads simple test case data from a folder and executes the corresponding tests """
    case = cases[case_name]  # lazy-load case data (so that parsing errors don't fail the whole collection)
    print(case)
    assert exec_op(case.x, case.y, case.op) == case.expected_result
