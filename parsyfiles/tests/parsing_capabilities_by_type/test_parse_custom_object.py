from pprint import pprint
import os
from parsyfiles import parse_item, parse_collection


THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'objects_data', *args)


# The function that we want to test
def exec_op(x: float, y: float, op: str) -> float:
    # if op is '+':
    #     return x + y
    # elif op is '-':
    #     return x - y
    # else:
    #     raise ValueError('Unsupported operation : \'' + op + '\'')
    return eval(str(x) + op + str(y))


# Defines what is a test case for exec_op
class ExecOpTest(object):
    def __init__(self, x: float, y: float, op: str, expected_result: float):
        self.x = x
        self.y = y
        self.op = op
        self.expected_result = expected_result

    def __repr__(self):
        return str(self.x) + ' ' + self.op + ' ' + str(self.y) + ' =? ' + str(self.expected_result)


def test_simple_objects_support():
    """
    Tests all the supported ways to parse a simple object
    :return:
    """

    # create the parser and parse a single file
    e = parse_item(get_path('./test_diff_1'), ExecOpTest)
    pprint(e)

    # parse all of them
    e = parse_collection(get_path('.'), ExecOpTest)
    pprint(e)

    for case_name, case in e.items():
        assert exec_op(case.x, case.y, case.op) == case.expected_result
