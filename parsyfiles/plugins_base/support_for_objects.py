from abc import ABCMeta
from inspect import Parameter
from warnings import warn
from logging import Logger, warning, DEBUG
from typing import Type, Any, List, Dict, Union

from parsyfiles.converting_core import Converter, ConverterFunction, AnyObject, S, T, is_any_type, JOKER
from parsyfiles.filesystem_mapping import PersistedObject
from parsyfiles.parsing_core import MultiFileParser, AnyParser, SingleFileParserFunction
from parsyfiles.parsing_registries import ParserFinder, ConversionFinder
from parsyfiles.plugins_base.support_for_collections import DictOfDict
from parsyfiles.type_inspection_tools import get_pretty_type_str, get_constructor_attributes_types, \
    TypeInformationRequiredError, is_collection
from parsyfiles.var_checker import check_var


def read_object_from_pickle(desired_type: Type[T], file_path: str, encoding: str,
                            fix_imports: bool = True, errors: str = 'strict', *args, **kwargs) -> Any:
    """
    Parses a pickle file.

    :param desired_type:
    :param file_path:
    :param encoding:
    :param fix_imports:
    :param errors:
    :param args:
    :param kwargs:
    :return:
    """
    import pickle
    file_object = open(file_path, mode='rb')
    try:
        return pickle.load(file_object, fix_imports=fix_imports, encoding=encoding, errors=errors)
    finally:
        file_object.close()


class b64str(metaclass=ABCMeta):
    pass


b64str.register(str)
assert issubclass(str, b64str)
assert isinstance('', b64str)


def base64_ascii_str_pickle_to_object(desired_type: Type[T], b64_ascii_str: b64str, logger: Logger,
                                      *args, **kwargs) -> Any:
    import base64
    import pickle
    return pickle.loads(base64.b64decode(b64_ascii_str), fix_imports=True, encoding="ASCII", errors="strict")


class MissingMandatoryAttributeFiles(FileNotFoundError):
    """
    Raised whenever a given object can not be constructed because one of its mandatory constructor attributes
    is missing on the filesystem (no singlefile or multifile found,
    typically underlying ObjectNotFoundOnFileSystemError caught)
    """

    def __init__(self, contents: str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MissingMandatoryAttributeFiles, self).__init__(contents)

    @staticmethod
    def create(obj: PersistedObject, obj_type: Type[Any], arg_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param obj:
        :param obj_type:
        :param arg_name:
        :return:
        """

        return MissingMandatoryAttributeFiles('Multifile object ' + str(obj) + ' cannot be built from constructor of '
                                              'type, ' + str(obj_type) +
                                              'mandatory constructor argument \'' + arg_name + '\'was not found on '
                                                                                               'filesystem')


class InvalidAttributeNameForConstructorError(Exception):
    """
    Raised whenever an attribute of a multifile object has a name that is not compliant with that object's constructor
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(InvalidAttributeNameForConstructorError, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any], constructor_atts: List[str], invalid_property_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return InvalidAttributeNameForConstructorError('Cannot parse object of type <' + get_pretty_type_str(item_type)
                                                       + '> using the provided configuration file: configuration '
                                                       + 'contains a property name (\'' + invalid_property_name + '\')'\
                                                       + 'that is not an attribute of the object constructor. <'
                                                       + get_pretty_type_str(item_type) + '> constructor attributes '
                                                       + 'are : ' + str(constructor_atts))


class ObjectInstantiationException(Exception):
    """
    Raised whenever an error happens during instantiation of an object through constructor creation
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(ObjectInstantiationException, self).__init__(contents)

    @staticmethod
    def create(item_type: Type[Any], constructor_args: Dict[str, Any], cause: Exception):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return ObjectInstantiationException('Error while building object of type <' + get_pretty_type_str(item_type)
                                            + '> using its constructor and parsed contents : ' + str(constructor_args)
                                            + ' : \n' + str(cause.__class__) + ' ' + str(cause)
                                            ).with_traceback(cause.__traceback__)  # 'from e' was hiding the inner traceback. This is much better for debug


class CaughtTypeErrorDuringInstantiation(Exception):
    """
    Raised whenever a TypeError is caught during object instantiation
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(CaughtTypeErrorDuringInstantiation, self).__init__(contents)

    @staticmethod
    def create(desired_type: Type[Any], contents_dict: Dict, caught: Exception):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param desired_type:
        :param contents_dict:
        :param caught:
        :return:
        """
        msg = 'Error while trying to instantiate object of type ' + str(desired_type) + ' using dictionary input_dict:'\
              + 'Caught error message is : ' + caught.__class__.__name__ + ' : ' + str(caught) + '\n'
        try:
            from pprint import pformat
            msg += 'Dict provided was ' + pformat(contents_dict)
        except:
            msg += 'Dict provided was ' + str(contents_dict)

        return CaughtTypeErrorDuringInstantiation(msg).with_traceback(caught.__traceback__)


def _is_valid_for_dict_to_object_conversion(strict_mode: bool, from_type: Type, to_type: Type) -> bool:
    """
    Returns true if the provided types are valid for dict_to_object conversion

    Explicitly declare that we are not able to parse collections nor able to create an object from a dictionary if the
    object's constructor is non correctly PEP484-specified.

    None should be treated as a Joker here (but we know that never from_type and to_type will be None at the same time)

    :param strict_mode:
    :param from_type:
    :param to_type:
    :return:
    """
    if to_type is None or is_any_type(to_type):
        # explicitly handle the 'None' (joker) or 'any' type
        return True

    elif is_collection(to_type, strict=True):
        # if the destination type is 'strictly a collection' (not a subclass of a collection) we know that we can't
        # handle it here, the constructor is not pep484-typed
        return False

    else:
        try:
            # can we find enough pep-484 information in the constructor to be able to understand what is required ?
            get_constructor_attributes_types(to_type)
            return True
        except TypeInformationRequiredError as e:
            # failed: we cant guess the required types of constructor arguments
            if hasattr(to_type, '__module__') and to_type.__module__ not in {'builtins'} \
                    and not to_type.__module__.startswith('parsyfiles') and not to_type.__name__ == 'DataFrame':
                warn('Object constructor signature for type {} does not allow parsyfiles to automatically create '
                     'instances from dict content. Caught {}: {}'.format(to_type, type(e).__name__, e))
            return False


def dict_to_object(desired_type: Type[T], contents_dict: Dict[str, Any], logger: Logger,
                   options: Dict[str, Dict[str, Any]], conversion_finder: ConversionFinder = None,
                   is_dict_of_dicts: bool = False) -> T:
    """
    Utility method to create an object from a dictionary of constructor arguments. Constructor arguments that dont have
    the correct type are intelligently converted if possible

    :param desired_type:
    :param contents_dict:
    :param logger:
    :param options:
    :param conversion_finder:
    :param is_dict_of_dicts:
    :return:
    """
    check_var(desired_type, var_types=type, var_name='obj_type')
    check_var(contents_dict, var_types=dict, var_name='contents_dict')

    if is_collection(desired_type, strict=True):
        # if the destination type is 'strictly a collection' (not a subclass of a collection) we know that we can't
        # handle it here, the constructor is not pep484-typed
        raise TypeError('Desired object type \'' + get_pretty_type_str(desired_type) + '\' is a collection, '
                        'so it cannot be created using this generic object creator')

    # collect pep-484 information in the constructor to be able to understand what is required
    constructor_args_types_and_opt = get_constructor_attributes_types(desired_type)

    try:
        # for each attribute, convert the types of its parsed values if required
        dict_for_init = dict()
        for attr_name, provided_attr_value in contents_dict.items():

            # check if this attribute name is required by the constructor
            if attr_name in constructor_args_types_and_opt.keys():

                # check the theoretical type wanted by the constructor
                attr_type_required = constructor_args_types_and_opt[attr_name][0]

                if not is_dict_of_dicts:
                    if isinstance(attr_type_required, type):
                        # this will not fail if type information is not present;the attribute will only be used 'as is'
                        full_attr_name = get_pretty_type_str(desired_type) + '.' + attr_name

                        dict_for_init[attr_name] = ConversionFinder.try_convert_value(conversion_finder, full_attr_name,
                                                                                      provided_attr_value,
                                                                                      attr_type_required, logger,
                                                                                      options)

                    else:
                        warning('Constructor for type <' + get_pretty_type_str(desired_type) + '> has no PEP484 Type '
                                'hint, trying to use the parsed value in the dict directly')
                        dict_for_init[attr_name] = provided_attr_value

                else:
                    # in that mode, the attribute value itself is a dict, so the attribute needs to be built from that
                    # dict first
                    if isinstance(provided_attr_value, dict):
                        # recurse : try to build this attribute from the dictionary provided. We need to know the type
                        # for this otherwise we wont be able to call the constructor :)
                        if attr_type_required is Parameter.empty or not isinstance(attr_type_required, type):
                            raise TypeInformationRequiredError.create_for_object_attributes(desired_type, attr_name)
                        else:
                            # we can build the attribute from the sub-dict
                            dict_for_init[attr_name] = dict_to_object(attr_type_required, provided_attr_value,
                                                                      logger, options,
                                                                      conversion_finder=conversion_finder)

                    else:
                        raise ValueError('Error while trying to build object of type ' + str(desired_type) + ' from a '
                                         'dictionary of dictionaries. Entry \'' + attr_name + '\' is not a dictionary')
            else:
                if is_dict_of_dicts and attr_name is 'DEFAULT':
                    # -- tolerate but ignore - this is probably due to a configparser
                    # warning('Property name \'' + attr_name + '\' is not an attribute of the object constructor. <'
                    #         + get_pretty_type_str(desired_type) + '> constructor attributes are : '
                    #         + list(set(constructor_args_types.keys()) - {'self'}) + '. However it is named DEFAULT')
                    pass
                else:
                    # the dictionary entry does not correspond to a valid attribute of the object
                    raise InvalidAttributeNameForConstructorError.create(desired_type,
                                                                         list(set(constructor_args_types_and_opt.keys()) - {'self'}),
                                                                         attr_name)

        # create the object using its constructor
        try:
            return desired_type(**dict_for_init)
        except Exception as e:
            # Wrap into an Exception
            raise ObjectInstantiationException.create(desired_type, dict_for_init, e)

    except TypeError as e:
        raise CaughtTypeErrorDuringInstantiation.create(desired_type, contents_dict, e)


def print_dict(dict_name, dict_value, logger: Logger = None):
    """
    Utility method to print a named dictionary

    :param dict_name:
    :param dict_value:
    :return:
    """
    if logger is None:
        print(dict_name + ' = ')
        try:
            from pprint import pprint
            pprint(dict_value)
        except:
            print(dict_value)
    else:
        logger.info(dict_name + ' = ')
        try:
            from pprint import pformat
            logger.info(pformat(dict_value))
        except:
            logger.info(dict_value)


def get_default_object_parsers(parser_finder: ParserFinder, conversion_finder: ConversionFinder) -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse an object from a file.
    Note that MultifileObjectParser is not provided in this list, as it is already added in a hardcoded way in
    RootParser
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_object_from_pickle,
                                     streaming_mode=False,
                                     supported_exts={'.pyc'},
                                     supported_types={AnyObject}),
            MultifileObjectParser(parser_finder, conversion_finder)
            ]


def get_default_object_converters(conversion_finder: ConversionFinder) \
        -> List[Union[Converter[Any, Type[None]], Converter[Type[None], Any]]]:
    """
    Utility method to return the default converters associated to dict (from dict to other type,
    and from other type to dict)
    :return:
    """

    return [
            ConverterFunction(from_type=b64str, to_type=AnyObject, conversion_method=base64_ascii_str_pickle_to_object),
            ConverterFunction(from_type=DictOfDict, to_type=Any, conversion_method=dict_to_object,
                              custom_name='dict_of_dict_to_object',
                              is_able_to_convert_func=_is_valid_for_dict_to_object_conversion, unpack_options=False,
                              function_args={'conversion_finder': conversion_finder, 'is_dict_of_dicts': True}),
            ConverterFunction(from_type=dict, to_type=AnyObject, conversion_method=dict_to_object,
                              custom_name='dict_to_object', unpack_options=False,
                              is_able_to_convert_func=_is_valid_for_dict_to_object_conversion,
                              function_args={'conversion_finder': conversion_finder, 'is_dict_of_dicts': False})
            ]


class MultifileObjectParser(MultiFileParser):
    """
    This class is able to read any non-collection type as long as they are PEP484 specified, from
    multifile objects. It simply inspects the required type to find the names and types of its constructor arguments.
    Then it relies on a ParserFinder to parse each of them before creating the final object.
    """

    def __init__(self, parser_finder: ParserFinder, conversion_finder: ConversionFinder):
        """
        Constructor. The parser_finder will be used to find the most appropriate parser to parse each item of the
        collection
        :param parser_finder:
        """
        super(MultifileObjectParser, self).__init__(supported_types={AnyObject})
        self.parser_finder = parser_finder
        self.conversion_finder = conversion_finder

    def is_able_to_parse_detailed(self, desired_type: Type[Any], desired_ext: str, strict: bool):
        """
        Explicitly declare that we are not able to parse collections

        :param desired_type:
        :param desired_ext:
        :param strict:
        :return:
        """

        if not _is_valid_for_dict_to_object_conversion(strict, None, None if desired_type is JOKER else desired_type):
            return False, None
        else:
            return super(MultifileObjectParser, self).is_able_to_parse_detailed(desired_type, desired_ext, strict)

    def __str__(self):
        return 'Multifile Object parser (' + str(self.parser_finder) + ')'
        # '(based on \'' + str(self.parser_finder) + '\' to find the parser for each attribute)'

    # def __repr__(self):
    #     # should we rather use the full canonical names ? yes, but pprint uses __repr__ so we'd like users to see
    #     # the small and readable version, really
    #     return self.__str__()

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Simply simply inspects the required type to find the names and types of its constructor arguments.
        Then relies on the inner ParserFinder to parse each of them.

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """

        if is_collection(desired_type, strict=True):
            # if the destination type is 'strictly a collection' (not a subclass of a collection) we know that we can't
            # handle it here, the constructor is not pep484-typed
            raise TypeError('Desired object type \'' + get_pretty_type_str(desired_type) + '\' is a collection, '
                            'so it cannot be parsed with this default object parser')

        # First get the file children
        children_on_fs = obj_on_fs.get_multifile_children()

        # -- (a) collect pep-484 information in the class constructor to be able to understand what is required
        constructor_args_types_and_opt = get_constructor_attributes_types(desired_type)

        # -- (b) plan to parse each attribute required by the constructor
        children_plan = dict()  # results will be put in this object

        # --use sorting in order to lead to reproducible results in case of multiple errors
        for attribute_name, att_desc in sorted(constructor_args_types_and_opt.items()):
            attribute_is_mandatory = att_desc[1]
            attribute_type = att_desc[0]

            # get the child
            if attribute_name in children_on_fs.keys():
                child_on_fs = children_on_fs[attribute_name]

                # find a parser
                parser_found = self.parser_finder.build_parser_for_fileobject_and_desiredtype(child_on_fs,
                                                                                              attribute_type,
                                                                                              logger=logger)
                # create a parsing plan
                children_plan[attribute_name] = parser_found.create_parsing_plan(attribute_type, child_on_fs,
                                                                                 logger=logger, _main_call=False)
            else:
                if attribute_is_mandatory:
                    raise MissingMandatoryAttributeFiles.create(obj_on_fs, desired_type, attribute_name)
                else:
                    # we don't care : optional attribute
                    # dont use warning since it does not show up nicely
                    msg = 'NOT FOUND - This optional constructor attribute for type ' \
                          + get_pretty_type_str(desired_type) + ' was not found on file system, but this may be normal'\
                          ' - this message is displayed \'just in case\'.'
                    if logger.isEnabledFor(DEBUG):
                        logger.warning('(B) ' + obj_on_fs.get_pretty_child_location(attribute_name,
                                                                                    blank_parent_part=True) + ': '
                                       + msg)
                    else:
                        logger.warning('WARNING parsing [{loc}] as a [{typ}]: optional constructor attribute [{att}] '
                                       'not found on file system. This may be normal - this message is displayed \'just'
                                       ' in case\'.'.format(
                            loc=obj_on_fs.get_pretty_location(blank_parent_part=False, append_file_ext=False),
                            typ=get_pretty_type_str(desired_type),
                            att=attribute_name))

        return children_plan

    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan], logger: Logger,
                         options: Dict[str, Dict[str, Any]]) -> T:
        """

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param options:
        :return:
        """

        # Parse children right now
        results = {}

        # 1) first parse all children according to their plan
        # -- use key-based sorting on children to lead to reproducible results
        # (in case of multiple errors, the same error will show up first everytime)
        for child_name, child_plan in sorted(parsing_plan_for_children.items()):
            results[child_name] = child_plan.execute(logger, options)

        # 2) finally build the resulting object
        # not useful
        # logger.debug('Assembling a ' + get_pretty_type_str(desired_type) + ' from all parsed children of ' + str(obj)
        #             + ' by passing them as attributes of the constructor')

        return dict_to_object(desired_type, results, logger, options, conversion_finder=self.conversion_finder)
