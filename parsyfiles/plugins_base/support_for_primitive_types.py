import shutil
from ast import literal_eval
from distutils.util import strtobool
from io import StringIO, TextIOBase
from logging import Logger
from typing import Type, Union, Any

from parsyfiles.converting_core import ConverterFunction, T, AnyObject
from parsyfiles.parsing_core import SingleFileParserFunction

any_primitive_type = Union[str, int, float, bool]
all_primitive_types = [str, int, float, bool]


def read_str_from_txt(desired_type: Type[dict], file_object: TextIOBase,
                      logger: Logger, *args, **kwargs) -> str:

    # read the entire stream into a string
    str_io = StringIO()
    shutil.copyfileobj(file_object, str_io)
    return str_io.getvalue()


def get_default_primitive_parsers():
    return [SingleFileParserFunction(parser_function=read_str_from_txt,
                                     streaming_mode=True,
                                     supported_exts={'.txt'},
                                     supported_types={str})]


def primitive_to_int(desired_type: Type[T], source: any_primitive_type, logger: Logger, *args, **kwargs) -> int:
    typ = type(source)
    # first handle the string case
    if typ is str:
        # ast.literal_eval will parse into the type that python would give
        # supports strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None.
        source = literal_eval(source)
        typ = type(source)

    # now lets convert
    if typ is int:
        return source
    elif typ is bool:
        return int(source)
    elif typ is float:
        res = int(source)
        if float(res) == source:
            return res
        else:
            raise ValueError('Cannot convert to int : source is a non-integer float: ' + str(source))
    else:
        raise ValueError('Cannot convert to int : source is a \'' + str(typ) + '\' ')


def primitive_to_float(desired_type: Type[T], source: any_primitive_type, logger: Logger, *args, **kwargs) -> float:
    typ = type(source)
    # first handle the string case
    if typ is str:
        # ast.literal_eval will parse into the type that python would give
        # supports strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None.
        source = literal_eval(source)
        typ = type(source)

    # now lets convert
    if typ is float:
        return source
    elif typ in {int, bool}:
        return float(source)
    else:
        raise ValueError('Cannot convert to float : source is a \'' + str(typ) + '\' ')


def primitive_to_bool(desired_type: Type[T], source: any_primitive_type, logger: Logger, *args, **kwargs) -> bool:
    typ = type(source)
    # first handle the string case
    if typ is str:
        # Two cases not handled by distutils, that we dont want to handle by allowing the converters to chain to the
        # moment. TODO: when the implementation will be based on graphs, then we will be able to release all of there restrictions
        if source in {'1.0'}:
            return True
        elif source in {'0.0'}:
            return False
        else:
            return bool(strtobool(source))
    elif typ in {float, int}:
        if source == 1:
            return True
        elif source == 0:
            return False
        else:
            raise ValueError('Cannot convert to bool : source is a number but is not 1 nor 0 : \'' + str(source) + '\'')
    else:
        raise ValueError('Cannot convert to bool : source is a \'' + str(typ) + '\' ')


def to_str(desired_type: Type[T], source: any_primitive_type, logger: Logger, *args, **kwargs) -> str:
    return str(source)


# This generic function could be tempting but why only primitive then ?
# 'object to anything' is good as well.. and we end up with a lot of conversion chains ending with that converter
# So frankly, no this is not a good option. If users a conversion between 'int' to their class, it is easier if they
# write it directly. An exception is str_to_any, so we'll propose it below.
#
# def primitive_to_anything_by_constructor_call(desired_type: Type[T], source: any_primitive_type,
#                                               logger: Logger, *args, **kwargs) -> T:
#     return desired_type(source)


def constructor_with_str_arg(desired_type: Type[T], source: str, logger: Logger, *args, **kwargs) -> T:
    return desired_type(source)


# def can_convert(strict: bool, from_type: Type[S], to_type: Type[T]):
#     if to_type in (all_primitive_types + all_np_primitive_types):
#         return True
#     else:
#         return False


def _can_construct_from_str(strict_mode: bool, from_type: Type, to_type: Type) -> bool:
    """
    Returns true if the provided types are valid for constructor_with_str_arg conversion
    Explicitly declare that we are not able to convert primitive types (they already have their own converters)

    :param strict_mode:
    :param from_type:
    :param to_type:
    :return:
    """
    return to_type not in {int, float, bool}


def get_default_primitive_converters():
    # There are plenty of ways to build this list. Several attempts were made, with generic or specific functions. Each
    # eventually had drawbacks in specific cases. The following points are essential to not exponentially
    # create conversion chains that dont make sense
    # - first, for most primitive converters, dont allow chaining. Otherwise chains such as str > bool > int > float
    # will be created, thats pointless. A possible alternative would be to have a SINGLE converter to convert between
    # any primitive and any primitive. However it would be a lot less readable and still would not be able to chain
    # because it would not know the desired_type (apart from 'any')
    # - second, separate known functions (such as str to int) from generic functions (str to anything), otherwise it is
    # harder to understand and debug. This led to the following list organized by target type.
    prim_to_prim = []

    # primitive to int
    for t in [str, float, bool]:
        prim_to_prim.append(ConverterFunction(from_type=t, to_type=int, conversion_method=primitive_to_int,
                                              custom_name=t.__name__ + '_to_int', can_chain=False))

    # primitive to float
    for t in [str, int, bool]:
        prim_to_prim.append(ConverterFunction(from_type=t, to_type=float, conversion_method=primitive_to_float,
                                              custom_name=t.__name__ + '_to_float', can_chain=False))
    # primitive to bool
    for t in [str, int, float]:
        prim_to_prim.append(ConverterFunction(from_type=t, to_type=bool, conversion_method=primitive_to_bool,
                                              custom_name=t.__name__ + '_to_bool', can_chain=False))

    # primitive to str
    prim_to_prim += [ConverterFunction(from_type=t, to_type=str, conversion_method=to_str,
                                       custom_name=t.__name__ + '_to_string', can_chain=False)
                     for t in [int, float, bool]]

    # construct anything from str
    # TODO this should be removed... but useful for np.int_ etc ? Most probably we would need instead a 'construct from single argument' + 'construct from positional arguments')
    return prim_to_prim + [ConverterFunction(from_type=str, to_type=AnyObject,
                                             conversion_method=constructor_with_str_arg,
                                             is_able_to_convert_func=_can_construct_from_str,
                                             can_chain=False)]


    # build one converter for each target primitive type
    # return [ConverterFunction(from_type=t, to_type=Any, conversion_method=primitive_to_anything_by_constructor_call,
    #                           # is_able_to_convert_func=can_convert,
    #                           custom_name='construct_from_' + t.__name__) for t in all_primitive_types]
            # ConverterFunction(from_type=str, to_type=int, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='str_to_int', can_chain=False),
            # ConverterFunction(from_type=str, to_type=float, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='str_to_float', can_chain=False),
            # ConverterFunction(from_type=str, to_type=bool, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='str_to_bool', can_chain=False),
            # ConverterFunction(from_type=int, to_type=str, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='int_to_str', can_chain=False),
            # ConverterFunction(from_type=int, to_type=float, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='int_to_float', can_chain=False),
            # ConverterFunction(from_type=int, to_type=bool, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='int_to_bool', can_chain=False),
            # ConverterFunction(from_type=float, to_type=int, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='float_to_int', can_chain=False),
            # ConverterFunction(from_type=float, to_type=str, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='float_to_str', can_chain=False),
            # ConverterFunction(from_type=float, to_type=bool, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='float_to_bool', can_chain=False),
            # ConverterFunction(from_type=bool, to_type=int, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='bool_to_int', can_chain=False),
            # ConverterFunction(from_type=bool, to_type=float, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='bool_to_float', can_chain=False),
            # ConverterFunction(from_type=bool, to_type=str, conversion_method=primitive_to_primitive_converter,
            #                   custom_name='bool_to_str', can_chain=False)