from logging import Logger
from typing import Type, Union

from numpy import bool_, int8, int16, int32, int64, uint8, uint16, uint32, uint64, \
    float16, float32, float64, complex64, complex128

from parsyfiles.converting_core import ConverterFunction, T, S, AnyObject
from parsyfiles.plugins_base.support_for_primitive_types import all_primitive_types

# dont include int_, intc, intp, float_ and complex_ as they are only aliases
any_numpy_primitive_type = Union[bool_, int8, int16, int32, int64, uint8, uint16, uint32, uint64,
                                 float16, float32, float64, complex64, complex128]
all_np_primitive_types = [bool_, int8, int16, int32, int64, uint8, uint16, uint32, uint64,
                          float16, float32, float64, complex64, complex128]


def np_primitive_to_anything_by_constructor_call(desired_type: Type[T], source: any_numpy_primitive_type,
                                                 logger: Logger, *args, **kwargs) -> T:
    return desired_type(source)


def get_default_np_parsers():
    return []


def can_convert(strict: bool, from_type: Type[S], to_type: Type[T]):
    """
    None should be treated as a Joker here (but we know that never from_type and to_type will be None at the same time)

    :param strict:
    :param from_type:
    :param to_type:
    :return:
    """
    if (to_type is not None) and (to_type not in (all_primitive_types + all_np_primitive_types)):
        return False
    else:
        return True


def get_default_np_converters():
    # for each type create a converter
    return [ConverterFunction(from_type=t, to_type=AnyObject,
                              conversion_method=np_primitive_to_anything_by_constructor_call,
                              is_able_to_convert_func=can_convert,
                              custom_name='construct_from_' + t.__name__) for t in all_np_primitive_types]