import shutil
from io import StringIO, TextIOBase
from logging import Logger
from typing import Type, Union

from parsyfiles.converting_core import ConverterFunction
from parsyfiles.parsing_core import SingleFileParserFunction

any_primitive_type = Union[str, int, float, bool]


def read_str_from_txt(desired_type: Type[dict], file_object: TextIOBase,
                      logger: Logger, *args, **kwargs) -> str:

    # read the entire stream into a string
    str_io = StringIO()
    shutil.copyfileobj(file_object, str_io)
    return str_io.getvalue()


def primitive_to_primitive_converter(desired_type: Type[any_primitive_type], source: any_primitive_type,
                                     logger: Logger, *args, **kwargs) -> any_primitive_type:
    return desired_type(source)


def get_default_primitive_parsers():
    return [SingleFileParserFunction(parser_function=read_str_from_txt,
                                     streaming_mode=True,
                                     supported_exts={'.txt'},
                                     supported_types={str})]


def get_default_primitive_converters():
    return [ConverterFunction(from_type=str, to_type=int, conversion_method=primitive_to_primitive_converter,
                              custom_name='str_to_int', can_chain=False),
            ConverterFunction(from_type=str, to_type=float, conversion_method=primitive_to_primitive_converter,
                              custom_name='str_to_float', can_chain=False),
            ConverterFunction(from_type=str, to_type=bool, conversion_method=primitive_to_primitive_converter,
                              custom_name='str_to_bool', can_chain=False),
            ConverterFunction(from_type=int, to_type=str, conversion_method=primitive_to_primitive_converter,
                              custom_name='int_to_str', can_chain=False),
            ConverterFunction(from_type=int, to_type=float, conversion_method=primitive_to_primitive_converter,
                              custom_name='int_to_float', can_chain=False),
            ConverterFunction(from_type=int, to_type=bool, conversion_method=primitive_to_primitive_converter,
                              custom_name='int_to_bool', can_chain=False),
            ConverterFunction(from_type=float, to_type=int, conversion_method=primitive_to_primitive_converter,
                              custom_name='float_to_int', can_chain=False),
            ConverterFunction(from_type=float, to_type=str, conversion_method=primitive_to_primitive_converter,
                              custom_name='float_to_str', can_chain=False),
            ConverterFunction(from_type=float, to_type=bool, conversion_method=primitive_to_primitive_converter,
                              custom_name='float_to_bool', can_chain=False),
            ConverterFunction(from_type=bool, to_type=int, conversion_method=primitive_to_primitive_converter,
                              custom_name='bool_to_int', can_chain=False),
            ConverterFunction(from_type=bool, to_type=float, conversion_method=primitive_to_primitive_converter,
                              custom_name='bool_to_float', can_chain=False),
            ConverterFunction(from_type=bool, to_type=str, conversion_method=primitive_to_primitive_converter,
                              custom_name='bool_to_str', can_chain=False)
            ]