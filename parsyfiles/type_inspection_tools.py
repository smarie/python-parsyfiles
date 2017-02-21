from inspect import getmembers, signature
from pydoc import locate
from typing import Type, Any, Tuple, List, Set, Dict, Generic
from warnings import warn

from parsyfiles.var_checker import check_var


def get_pretty_type_str(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}. In that case returns a
    user-friendly character string with the inner item types, such as Dict[str, int].

    :param object_type:
    :return: type.__name__ if type is not a subclass of typing.{List,Dict,Set,Tuple}, otherwise
    type__name__[list of inner_types.__name__]
    """

    try:
        contents_item_type, contents_key_type = _extract_collection_base_type(object_type)
        if isinstance(contents_item_type, tuple):
            return object_type.__name__ + '[' + ', '.join([item_type.__name__ for item_type in contents_item_type]) + ']'
        else:
            if contents_key_type is not None:
                return object_type.__name__ + '[' + contents_key_type.__name__ + ', ' + contents_item_type.__name__ + ']'
            elif contents_item_type is not None:
                return object_type.__name__ + '[' + contents_item_type.__name__ + ']'
    except Exception as e:
        pass

    try:
        return object_type.__name__
    except:
        return str(object_type)


def get_pretty_type_keys_dict(dict):
    return {get_pretty_type_str(typ): val for typ, val in dict.items()}


def is_generic(object_type):
    """
    Utility method to check for example if a type is a subclass of typing.{List,Dict,Set,Tuple}
    or of list, dict, set, tuple

    :param object_type:
    :return:
    """
    try:
        return issubclass(object_type, Generic)
    except TypeError as e:
        if e.args[0].startswith('descriptor \'__subclasses__\' of'):
            # known bug that is supposed to be fixed by now https://github.com/python/typing/issues/266.
            # as a fallback, at least return true if class is a subclass of the 'must know' classes
            # (todo find a better way?)
            return issubclass(object_type, (List, Set, Tuple, Dict))

        elif e.args[0].startswith('cannot create weak reference to'):
            # assuming this is fixed : https://github.com/python/typing/issues/345
            # then what remains is a type that is does not extend the typing module
            return False

        else:
            raise e


def get_base_generic_type(object_type):
    """
    Utility method to return the equivalent non-customized type for a Generic type, including user-defined ones.
    for example calling it on typing.List<~T>[int] will return typing.List<~T>

    :param object_type:
    :return:
    """
    if is_generic(object_type):
        inferred_base_type = locate(object_type.__module__ + '.' + object_type.__name__)
        if inferred_base_type is not None:
            return inferred_base_type
        else:
            # that may happen if your generic class has been defined inside a local class
            # For these classes, we cant' get the base (expressed with 'T') class, strangely enough
            # TODO improve.
            warn('Unable to find the base generic class for ' + str(object_type) + ' although it seems to extend '
                 'typing.Generic. Using the class directly')
            return object_type
    else:
        return object_type


def is_collection(object_type, strict: bool = False):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}
    or of list, dict, set, tuple.

    If strict is set to True, the method will return True only if the class is directly one of the base collection
    classes

    :param object_type:
    :return:
    """
    if object_type is None:
        return False
    elif strict:
        return object_type == dict \
               or object_type == list \
               or object_type == tuple \
               or object_type == set \
               or get_base_generic_type(object_type) == Dict \
               or get_base_generic_type(object_type) == List \
               or get_base_generic_type(object_type) == Set \
               or get_base_generic_type(object_type) == Tuple
    else:
        return issubclass(object_type, Dict) \
               or issubclass(object_type, List) \
               or issubclass(object_type, Set) \
               or issubclass(object_type, Tuple) \
               or issubclass(object_type, dict) \
               or issubclass(object_type, list) \
               or issubclass(object_type, tuple) \
               or issubclass(object_type, set)


def _extract_collection_base_type(collection_object_type: Type[Any], exception_if_none: bool = True):
    """
    Utility method to extract the base item type from a collection/iterable item type.
    Throws
    * a TypeError if the collection_object_type a Dict with non-string keys.
    * a TypeError if the collection_object_type is a Tuple (not handled yet)
    * an AttributeError if the collection_object_type is actually not a collection
    * a TypeInformationRequiredError if somehow the inner type can't be found from the collection type (either if dict,
    list, set, tuple were used instead of their typing module equivalents (Dict, List, Set, Tuple), or if the latter
    were specified without inner content types (as in Dict[str, Foo])

    :param collection_object_type:
    :return:
    """
    contents_item_type = None
    contents_key_type = None

    check_var(collection_object_type, var_types=type, var_name='collection_object_type')

    if issubclass(collection_object_type, Dict):
        # Dictionary
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__'):
            contents_key_type, contents_item_type = collection_object_type.__args__
            if not issubclass(contents_key_type, str):
                raise TypeError('Collection object has type Dict, but its PEP484 type hints declare '
                                'keys as being of type ' + str(contents_key_type) + ' which is not supported. Only str '
                                'keys are supported at the moment, since we use them as item names')

    elif issubclass(collection_object_type, List) or issubclass(collection_object_type, Set):
        # List or Set
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__'):
            contents_item_type = collection_object_type.__args__[0]

    elif issubclass(collection_object_type, Tuple):
        # Tuple
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__tuple_params__'):
            contents_item_type = collection_object_type.__tuple_params__

    elif issubclass(collection_object_type, dict) or issubclass(collection_object_type, list) \
                or issubclass(collection_object_type, tuple) or issubclass(collection_object_type, set):
        # the error is now handled below with the other under-specified types situations
        pass

    else:
        # Not a collection
        raise AttributeError('Cannot extract collection base type, object type ' + str(collection_object_type)
                             + ' is not a collection')

    # Finally return if something was found, otherwise tell it
    if contents_item_type is None and exception_if_none:
        raise TypeInformationRequiredError.create_for_collection_items(collection_object_type)
    else:
        return contents_item_type, contents_key_type


def _get_constructor_signature(item_type):
    """
    Utility method to extract a class constructor signature

    :param item_type:
    :return:
    """
    constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
    if len(constructors) is not 1:
        raise ValueError('Several constructors were found for class <' + get_pretty_type_str(item_type) + '>')
    # extract constructor
    constructor = constructors[0]
    s = signature(constructor)
    return s


def get_constructor_attributes_types(item_type):
    """
    Utility method to return a dictionary of attribute name > attribute type from the constructor of a given type
    :param item_type:
    :return:
    """
    s = _get_constructor_signature(item_type)
    return {attr_name: s.parameters[attr_name].annotation for attr_name in s.parameters.keys()}

class TypeInformationRequiredError(Exception):
    """
    Raised whenever an object can not be parsed - but there is a file present
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(TypeInformationRequiredError, self).__init__(contents)

    @staticmethod
    def create_for_collection_items(item_type: Type[Any]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError('Cannot parse object of type ' + str(item_type) + ' as a'
                                            ' collection: this type has no valid PEP484 type hint about its contents.'
                                            ' Please use a full declaration such as Dict[str, Foo] or List[Foo]')

    @staticmethod
    def create_for_object_attributes(item_type: Type[Any], faulty_attribute_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError('Cannot parse object of type <' + str(item_type) + '> using a '
                                            'configuration file as a \'dictionary of dictionaries\': '
                                            'attribute \'' + faulty_attribute_name + '\' has no valid '
                                            'PEP484 type hint.')