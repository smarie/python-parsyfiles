import os
import pickle
from base64 import b64encode
from distutils.util import strtobool
from itertools import product
from pprint import pprint

import pytest
from shutil import rmtree

from parsyfiles import get_pretty_type_str, RootParser, get_capabilities_for_type
from parsyfiles.parsing_core_api import ParsingException

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'primitives_data', *args)


# that's where we generate all 'difficult' files
def clean_tests(typ):
    typ_str = get_pretty_type_str(typ)
    try:
        rmtree(get_path(typ_str))
    except:
        pass


def escape_specials(s):
    """ utility method to escape special characters in a string """
    return s.replace('\n', '%%n').replace('\r', '%%r').replace('\t', '%%t')


def unescape_specials(s):
    """ utility method to escape special characters in a string """
    return s.replace('%%n', '\n').replace('%%r', '\r').replace('%%t', '\t')


def write_tests(typ, ok_or_err, val, answer = None, write_pickle: bool = True, write_b64pickle: bool = True,
                write_txt: bool = True):
    """
    Utility to write all the test files for type typ to the folder <typ>/<ok_or_err>, typically <typ>/ok or <typ>/err.
    If 'answer' is provided, it wil be inserted in the file name so as to be decoded for the final assertion.

    :param typ:
    :param ok_or_err:
    :param val:
    :param answer:
    :param write_pickle: flag to activate/deactivate writing pickle files (.pyc)
    :param write_b64pickle: flag to activate/deactivate writing base64-encoded pickle files (.txt)
    :param write_txt: flag to activate/deactivate writing text files (.txt)
    :return:
    """
    typ_str = get_pretty_type_str(typ)

    val_txt = str(val)
    if answer is not None:
        val_txt = escape_specials(val_txt) + '=' + escape_specials(str(answer))

    val_typ = get_pretty_type_str(type(val))

    os.makedirs(get_path(typ_str, ok_or_err), exist_ok=True)

    # write the value as binary pickle
    if write_pickle:
        with open(get_path(typ_str, ok_or_err, 'pickle-' + val_typ + '-' + val_txt + '.pyc'), mode='wb') as f:
            pickle.dump(val, f)

    # write the value as a base64-encoded pickle string
    if write_b64pickle:
        with open(get_path(typ_str, ok_or_err, 'b64pickle-' + val_typ + '-' + val_txt + '.txt'), mode='wb') as f:
            f.write(b64encode(pickle.dumps(val)))

    # write the value as a string
    if write_txt:
        with open(get_path(typ_str, ok_or_err, 'txt-' + val_typ + '-' + val_txt + '.txt'), mode='wt') as f:
            f.write(str(val))


# ** BOOL
typ = bool
clean_tests(typ)
for ok_val, answer in [(False, False),(True, True),  # bool
                       (0.0, False), (1.0, True),  # floats
                       (0, False), (1, True),  # ints
                       ('y', True), ('No', False)]:  # special strs that are not str(above)
    write_tests(typ, 'ok', ok_val, answer)
for bad_val in [0.1, -1.0,  # floats
                6,  # ints
                'truth', '']:  # strs
    write_tests(typ, 'err', bad_val)


# ** INT
typ = int
clean_tests(typ)
for ok_val, answer in [(0, 0),(5, 5), (-2, -2),  # ints
                       (False, 0), (True, 1),  # bools
                       (0.0, 0), (10.0, 10), (-5.0, -5),  # floats
                       ]:  # special strs that are not str(above): none
    write_tests(typ, 'ok', ok_val, answer)
for bad_val in [-5.5,  # floats
                  # ints
                'truth', '']:  # strs
    write_tests(typ, 'err', bad_val)


# ** FLOAT
typ = float
clean_tests(typ)
for ok_val, answer in [(0, 0.0),(5, 5.0), (-2, -2.0),  # ints
                       (False, 0.0), (True, 1.0),  # bools
                       (0.0, 0.0), (10.1, 10.1), (-5.2, -5.2),  # floats
                       ]:  # special strs that are not str(above): none
    write_tests(typ, 'ok', ok_val, answer)
for bad_val in [  # floats
                  # ints
                'truth', '']:  # strs
    write_tests(typ, 'err', bad_val)


# ** STR
typ = str
clean_tests(typ)
for ok_val, answer in [(0, '0'), (5, '5'), (-2, '-2'),  # ints
                       (False, 'False'), (True, 'True'),  # bools
                       (0.0, '0.0'), (10.1, '10.1'), (-5.2, '-5.2'),  # floats
                       ('toto', 'toto'), ('', ''), ('lots\tof\nspecial\rchars', 'lots\tof\nspecial\rchars')]:  # str
    # unfortunately there is no way as of today to be able to read b64-encoded strings.
    # TODO add an exception in the conversion chain rules so that txt>b64>str is tried BEFORE txt>str
    write_tests(typ, 'ok', ok_val, answer, write_b64pickle=False)
# add one test at least so that we see the failure in the reports
for ok_val, answer in [('a', 'a')]:
    write_tests(typ, 'ok', ok_val, answer, write_b64pickle=True)

for bad_val in [  # floats
                  # ints
                 ]:  # strs
    write_tests(typ, 'err', bad_val)

# -------------
types = os.listdir(os.path.join(THIS_DIR, 'primitives_data'))
types = [typ for typ in types if typ != '.gitignore']  # ignore .gitignore


@pytest.mark.parametrize("typ", types)
def test_get_capabilities_for_type(typ: str):
    typp = eval(typ)
    pprint(get_capabilities_for_type(typp))


all_tests = []
for typ, ok_or_err in product(types, ['ok', 'err']):
    folder_path = get_path(typ, ok_or_err)
    if os.path.exists(folder_path):
        for fil in os.listdir(folder_path):
            all_tests.append((typ, ok_or_err, fil))
print(all_tests)


def get_file_path_no_ext(*args):
    """ utility method"""
    a = get_path(*args)
    return os.path.splitext(a)[0]


def get_expected_answer(fil, typ):
    res = os.path.splitext(fil)[0]
    expected = res[res.find('=')+1:]
    if typ is bool:
        return strtobool(expected)
    elif typ is str:
        return unescape_specials(typ(expected))
    else:
        return typ(expected)


@pytest.mark.parametrize("typ,ok_or_err,file", all_tests)
def test_parse_by_type(typ: str, ok_or_err: str, file: str, root_parser):
    typp = eval(typ)
    # pprint(get_capabilities_for_type(typp))

    # Known skipped cases
    if typ == 'str' and ok_or_err == 'ok' and file == 'b64pickle-str-a=a.txt':
        pytest.skip("There is no way as of today that parsyfiles detects that the string present in the file is not the"
                    "string that you actually want, but a pickled version of that string. This is really not a failure")

    try:
        # ignore unresolved reference : method `profile` is created on the fly by the line_profiler
        RootParser.parse_item = profile(RootParser.parse_item)
    except:
        pass

    if ok_or_err is 'ok':
        parsed = root_parser.parse_item(location=get_file_path_no_ext(typ, ok_or_err, file), item_type=typp)
        assert parsed == get_expected_answer(file, typp)
        print("%s==%s" % (parsed, get_expected_answer(file, typp)))

    else:
        with pytest.raises(ParsingException):
            root_parser.parse_item(location=get_file_path_no_ext(typ, ok_or_err, file), item_type=typp)
