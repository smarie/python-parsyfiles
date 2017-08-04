from inspect import getmembers, signature, _empty, Parameter
from typing import Type, Any, Tuple, List, Set, Dict, Mapping, Iterable, MutableMapping, TypeVar

from parsyfiles.var_checker import check_var
from collections import OrderedDict

KT = TypeVar('KT')  # Key type.
VT = TypeVar('VT')  # Value type.


class OrderedDictType(OrderedDict, MutableMapping[KT, VT], extra=OrderedDict):
    """ Unfortunately this type does not exist in typing module so we define it here """
    __slots__ = ()

    def __new__(cls, *args, **kwds):
        raise TypeError("Type OrderedDictType cannot be instantiated; use OrderedDict() instead")


def robust_isinstance(inst, typ):
    """
    Similar to isinstance, but if 'typ' is a parametrized generic Type, it is first transformed into its base generic
    class so that the instance check works

    :param inst:
    :param typ:
    :return:
    """
    return isinstance(inst, get_base_generic_type(typ))


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


def is_parametrized_generic(object_type):
    """
    Utility method to check if a "typing" type is parametrized as in List[str], or if it not, as in List

    :param object_type:
    :return:
    """
    # TODO when https://github.com/python/typing/issues/423 is resolved, rely on it
    return hasattr(object_type, '__origin__') and object_type.__origin__ is not None
    # try:
    #     return issubclass(object_type, Generic)
    # except TypeError as e:
    #     if e.args[0].startswith('descriptor \'__subclasses__\' of'):
    #         # known bug that is supposed to be fixed by now https://github.com/python/typing/issues/266.
    #         # as a fallback, at least return true if class is a subclass of the 'must know' classes
    #         return issubclass(object_type, (List, Set, Tuple, Dict))
    #
    #     elif e.args[0].startswith('cannot create weak reference to'):
    #         # assuming this is fixed : https://github.com/python/typing/issues/345
    #         # then what remains is a type that is does not extend the typing module
    #         return False
    #
    #     else:
    #         raise e


def get_base_generic_type(object_type):
    """
    Utility method to return the equivalent non-customized type for a Generic type, including user-defined ones.
    for example calling it on typing.List<~T>[int] will return typing.List<~T>.

    If the type is not parametrized it is returned as is

    :param object_type:
    :return:
    """
    # TODO when https://github.com/python/typing/issues/423 is resolved, rely on it
    if is_parametrized_generic(object_type):
        # inferred_base_type = locate(object_type.__module__ + '.' + object_type.__name__)
        return object_type.__origin__
        # if inferred_base_type is not None:
        #     return inferred_base_type
        # else:
        #     # that may happen if your generic class has been defined inside a local class
        #     # For these classes, we cant' get the base (expressed with 'T') class, strangely enough
        #     warn('Unable to find the base generic class for ' + str(object_type) + ' although it seems to extend '
        #          'typing.Generic. Using the class directly')
        #     return object_type
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
    * an AttributeError if the collection_object_type is actually not a collection
    * a TypeInformationRequiredError if somehow the inner type can't be found from the collection type (either if dict,
    list, set, tuple were used instead of their typing module equivalents (Dict, List, Set, Tuple), or if the latter
    were specified without inner content types (as in Dict instead of Dict[str, Foo])

    :param collection_object_type:
    :return:
    """
    contents_item_type = None
    contents_key_type = None

    check_var(collection_object_type, var_types=type, var_name='collection_object_type')

    if issubclass(collection_object_type, Mapping):
        # Dictionary
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
            contents_key_type, contents_item_type = collection_object_type.__args__
            if not issubclass(contents_key_type, str):
                raise TypeError('Collection object has type Dict, but its PEP484 type hints declare '
                                'keys as being of type ' + str(contents_key_type) + ' which is not supported. Only str '
                                'keys are supported at the moment, since we use them as item names')

    elif issubclass(collection_object_type, Tuple):
        # Tuple
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
            contents_item_type = collection_object_type.__args__

    elif issubclass(collection_object_type, Iterable):
        # List or Set
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
            contents_item_type = collection_object_type.__args__[0]

    elif issubclass(collection_object_type, dict) or issubclass(collection_object_type, list) \
                or issubclass(collection_object_type, tuple) or issubclass(collection_object_type, set):
        # the error is now handled below with the other under-specified types situations
        pass

    else:
        # Not a collection
        raise AttributeError('Cannot extract collection base type, object type ' + str(collection_object_type)
                             + ' is not a collection')

    # Finally return if something was found, otherwise tell it
    if (contents_item_type is None or contents_item_type is _empty) and exception_if_none:
        raise TypeInformationRequiredError.create_for_collection_items(collection_object_type)
    else:
        return contents_item_type, contents_key_type


def _get_constructor_signature(item_type):
    """
    Utility method to extract a class constructor signature

    :param item_type:
    :return:
    """
    # --too slow
    # constructors = [f[1] for f in getmembers(item_type) if f[0] is '__init__']
    # if len(constructors) is not 1:
    #     raise ValueError('Several constructors were found for class <' + get_pretty_type_str(item_type) + '>')
    # # extract constructor
    # constructor = constructors[0]
    # --faster
    constructor = item_type.__init__

    s = signature(constructor)
    return s


def get_constructor_attributes_types(item_type) -> Dict[str, Tuple[Type[Any], bool]]:
    """
    Utility method to return a dictionary of attribute name > attribute type from the constructor of a given type
    It supports PEP484 and 'attrs' declaration.

    :param item_type:
    :return: a dictionary containing for each attr name, a tuple (type, is_mandatory)
    """

    try:
        # -- Try to read an attr declaration and to extract types and optionality
        from parsyfiles.plugins_optional.support_for_attrs import get_attrs_declarations
        res = get_attrs_declarations(item_type)

        # check that types are correct
        for attr_name, v in res.items():
            typ = v[0]
            if typ is None or typ is Parameter.empty or not isinstance(typ, type):
                raise TypeInformationRequiredError.create_for_object_attributes(item_type, attr_name)

    except:
        # -- Fallback to PEP484
        res = dict()

        # first get the signature of the class constructor
        s = _get_constructor_signature(item_type)

        # then extract the type and optionality of each attribute and raise errors if needed
        for attr_name in s.parameters.keys():
            # skip the 'self' attribute
            if attr_name != 'self':

                # -- get and check the attribute type
                typ = s.parameters[attr_name].annotation
                # TODO use the API rather, and support Optional (Union to NoneType) that is not an instance of type
                if typ is None or typ is Parameter.empty or not isinstance(typ, type):
                    raise TypeInformationRequiredError.create_for_object_attributes(item_type, attr_name)

                # -- is the attribute mandatory ?
                is_mandatory = s.parameters[attr_name].default is Parameter.empty

                # -- store both info in result dict
                res[attr_name] = (typ, is_mandatory)

    return res


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
        return TypeInformationRequiredError('Cannot parse object of type ' + str(item_type) + ' using a '
                                            'configuration file as a \'dictionary of dictionaries\': '
                                            'attribute \'' + faulty_attribute_name + '\' has no valid '
                                            'PEP484 type hint.')