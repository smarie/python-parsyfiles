import os
from time import perf_counter
from timeit import Timer

import pytest
from parsyfiles import RootParser, parse_item

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_with_new_instance():
    rp = RootParser()
    result = rp.parse_item(os.path.join(THIS_DIR, 'test_data/b64pickle-float-1.0=True'), bool)
    assert result == True


def parse_with_default_method():
    result = parse_item(os.path.join(THIS_DIR, 'test_data/b64pickle-float-1.0=True'), bool)
    assert result == True


def test_create_default_instance_with_constructor():
    """ This test creates the default instance with the default plugins, several times for profiling purposes """

    parse_with_new_instance2 = try_to_annotate_with_profile(parse_with_new_instance)

    # TODO one day use pytest benchmark instead
    start = perf_counter()

    for i in range(0,100):
        parse_with_new_instance2()

    elapsed = perf_counter() - start
    assert elapsed < 5  # in seconds


def try_to_annotate_with_profile(method):
    try:
        # ignore unresolved reference : method `profile` is created on the fly by the line_profiler
        return profile(method)
    except:
        return method


def test_create_default_instance_through_method():
    """ This test creates the default instance with the default plugins, several times for profiling purposes """

    parse_with_default_method2 = try_to_annotate_with_profile(parse_with_default_method)

    # TODO one day use pytest benchmark instead
    start = perf_counter()
    for i in range(0,100):
        parse_with_default_method2()

    elapsed = perf_counter() - start
    assert elapsed < 5  # in seconds


if __name__ == '__main__':
    # for profiling purposes...
    # * conda/pip install line_profiler
    # * kernprof -v -l -o prof/tmp.lprof parsyfiles\tests\combining_parsers_converters/test_default_instance_creation.py
    # * python -m line_profiler prof/tmp.lprof > prof/test_default_instance_creation.py.log

    # * pip/conda install -U memory_profiler
    # * pip/conda install psutil
    # * python -m memory_profiler parsyfiles\tests\combining_parsers_converters/test_default_instance_creation.py


    # all in one ! (need to install http://www.graphviz.org and add its bin directory to the path)
    # py.test parsyfiles\tests\combining_parsers_converters/test_default_instance_creation.py --profile --profile-svg
    # gprof2dot -f pstats prof/combined.prof > prof/tmp
    # dot -Tsvg -o prof/combined.svg prof/tmp
    pytest.main(['--profile', __file__])
