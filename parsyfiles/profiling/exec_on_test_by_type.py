import os
import pytest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


if __name__ == '__main__':
    # for profiling purposes...
    pytest.main(os.path.join(THIS_DIR, '../tests/test_parsyfiles_by_type.py'))
