import json
import shutil
from io import TextIOBase, StringIO
from logging import Logger
from typing import Any, Type

import os
from pprint import pprint
from copy import copy, deepcopy
from parsyfiles import RootParser
from parsyfiles.converting_core import AnyObject
from parsyfiles.parsing_core import SingleFileParserFunction

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(*args):
    """ utility method"""
    return os.path.join(THIS_DIR, 'test_data', *args)


def load(file_path):
    with open(get_path(file_path), mode='rt') as fp:
        return json.load(fp)


def dump(obj, file_path):
    res = json.dumps(obj, indent=4).replace('", "', '",\n"')
    with open(get_path(file_path), mode='wt') as fp:
        fp.write(res)


def to_str_coll(dct):
    """ converts a dictionary to a string dictionary """
    res = dict()
    try:
        for key, val in dct.items():
            # fill and recurse
            res[str(key)] = to_str_coll(val)
        return res
    except:
        # this is probably not a dict
        try:
            # a list ?
            return [str(val) for val in dct]
        except:
            # a value
            return str(dct)


def test_copy(root_parser: RootParser):
    """ Tests that a rootparser may be copied """
    copy(root_parser)


def test_deep_copy(root_parser: RootParser):
    """ Tests that a rootparser may be copied """
    deepcopy(root_parser)


def test_get_all_parsers(root_parser: RootParser):
    """ Tests that the default parsers are there and that their number is correct """

    parsers = root_parser.get_all_parsers(strict_type_matching=False)
    print('\n' + str(len(parsers)) + ' Root parser parsers:')
    pprint(parsers)
    assert len(parsers) == 127

    parsers_str = to_str_coll(parsers)
    # dump(parsers_str, 'reference_parsers.json')
    assert parsers_str == load('reference_parsers.json')


def test_option_hints(root_parser: RootParser):
    """ Tests the option_hints method on the first parser available """
    
    print('Testing option hints for parsing chain')
    p = root_parser.get_all_parsers(strict_type_matching=False)
    print(p[0].options_hints())


def test_get_all_conversion_chains(root_parser: RootParser):
    """ Tests that the default conversion chains are there and that their number is correct """

    chains = root_parser.get_all_conversion_chains()
    print('\n' + str(len(chains[0])) + '(generic) + ' + str(len(chains[2])) + '(specific) Root parser converters:')
    pprint(chains)
    assert len(chains[0]) == 22
    assert len(chains[1]) == 0
    assert len(chains[2]) == 200

    generic_chains_str = to_str_coll(chains[0])
    specific_chains_str = to_str_coll(chains[2])

    # dump(generic_chains_str, 'reference_generic_conversion_chains.json')
    assert generic_chains_str == load('reference_generic_conversion_chains.json')

    # dump(specific_chains_str, 'reference_specific_conversion_chains.json')
    assert specific_chains_str == load('reference_specific_conversion_chains.json')


def test_get_all_supported_exts(root_parser: RootParser):
    """ Tests that the declared supported extensions are there and that their number is correct """

    e = root_parser.get_all_supported_exts()
    print('\n' + str(len(e)) + ' Root parser supported extensions:')
    pprint(e)
    assert len(e) == 13

    # dump(list(e), 'reference_supported_exts.json')
    assert e == set(load('reference_supported_exts.json'))


def test_get_all_supported_types_pretty_str(root_parser: RootParser):
    """ Tests that the declared supported types are there and that their number is correct """
    
    t = root_parser.get_all_supported_types_pretty_str()
    print('\n' + str(len(t)) + ' Root parser supported types:')
    pprint(t)
    assert len(t) == 15
    # dump(list(t), 'reference_supported_types.json')
    assert t == set(load('reference_supported_types.json'))


def test_print_and_get_capabilities_by_ext(root_parser: RootParser):
    """ Tests that the declared capabilities by extension are correct """

    c = root_parser.get_capabilities_by_ext(strict_type_matching=False)
    print('\n' + str(len(c)) + ' Root parser capabilities by ext:')
    assert len(c) == 13

    cdict = to_str_coll(c)

    # dump(cdict, 'reference_capabilities_by_ext.json')
    assert cdict == load('reference_capabilities_by_ext.json')

    root_parser.print_capabilities_by_ext(strict_type_matching=False)


def test_print_and_get_capabilities_by_type(root_parser: RootParser):
    """ Tests that the declared capabilities by type are correct """

    c = root_parser.get_capabilities_by_type(strict_type_matching=False)
    print('\n' + str(len(c)) + ' Root parser capabilities by type:')
    assert len(c) == 15

    cdict = to_str_coll(c)

    # dump(cdict, 'reference_capabilities_by_type.json')
    assert cdict == load('reference_capabilities_by_type.json')

    root_parser.print_capabilities_by_type(strict_type_matching=False)


def test_root_parser_any():
    """
    Tests that we can ask the rootparser for its capabilities to parse a given type
    :return:
    """
    root_parser = RootParser()
    # print
    root_parser.print_capabilities_for_type(typ=Any)

    # details
    res = root_parser.find_all_matching_parsers(strict=False, desired_type=AnyObject, required_ext='.cfg')
    match_generic, match_approx, match_exact = res[0]
    assert len(match_generic) == 0
    assert len(match_approx) == 0


def test_custom_parser_ok_for_subclasses():
    """
    Tests that if you register a custom parser for a subclass of A, it gets correctly used to parse A (in non-strict
    mode, which is the default)
    :return:
    """
    root_parser = RootParser()

    class A:
        def __init__(self, txt):
            self.txt = txt

    class B(A):
        """ a subclass of A """
        pass

    def read_B_from_txt(desired_type: Type[dict], file_object: TextIOBase,
                      logger: Logger, *args, **kwargs) -> str:
        # read the entire stream into a string
        str_io = StringIO()
        shutil.copyfileobj(file_object, str_io)
        # only return the first character
        return B(str_io.getvalue()[0])

    # before registering a parser for B, only generic parsers are able to parse a A
    before_capa = root_parser.get_capabilities_for_type(A)['.txt']
    assert list(before_capa.keys()) == ['3_generic']

    # register a parser for B
    root_parser.register_parser(SingleFileParserFunction(parser_function=read_B_from_txt,
                                                         streaming_mode=True,
                                                         supported_exts={'.txt'},
                                                         supported_types={B}))

    # after registering the new parser appears in the list able to parse A
    after_capa = root_parser.get_capabilities_for_type(A)['.txt']
    assert str(after_capa['2_approx_match'][0]) == '<read_B_from_txt>'

    a = root_parser.parse_item(get_path('b64pickle-float-1.0=True'), A)
    # check that the custom parser was used, not the generic 'construct from string'
    assert len(a.txt) == 1
    assert a.txt == 'g'
