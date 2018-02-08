from inspect import Parameter, signature
from typing import TypeVar, MutableMapping, Dict, List, Set, Tuple, Type, Any, Mapping, Iterable, Optional

from typing_inspect import is_generic_type, get_origin, get_args, is_tuple_type, is_union_type, is_typevar

from parsyfiles.var_checker import check_var
from collections import OrderedDict

KT = TypeVar('KT')  # Key type.
VT = TypeVar('VT')  # Value type.


class OrderedDictType(OrderedDict, MutableMapping[KT, VT], extra=OrderedDict):
    """ Unfortunately this type does not exist in typing module so we define it here """
    __slots__ = ()

    def __new__(cls, *args, **kwds):
        raise TypeError("Type OrderedDictType cannot be instantiated; use OrderedDict() instead")


def resolve_union_and_typevar(typ) -> Tuple[Any, ...]:
    """
    If typ is a TypeVar,
     * if the typevar is bound, return resolve_union_and_typevar(bound)
     * if the typevar has constraints, return a tuple containing all the types listed in the constraints (with
     appropriate recursive call to resolve_union_and_typevar for each of them)
     * otherwise return (object, )

    If typ is a Union, return a tuple containing all the types listed in the union (with
     appropriate recursive call to resolve_union_and_typevar for each of them)

    Otherwise return (typ, )
    
    :param typ: 
    :return: 
    """
    if is_typevar(typ):
        if hasattr(typ, '__bound__') and typ.__bound__ is not None:
            return resolve_union_and_typevar(typ.__bound__)
        elif hasattr(typ, '__constraints__') and typ.__constraints__ is not None:
            return tuple(typpp for c in typ.__constraints__ for typpp in resolve_union_and_typevar(c))
        else:
            return object,
    elif is_union_type(typ):
        # do not use typ.__args__, it may be wrong
        # the solution below works even in typevar+config cases such as u = Union[T, str][Optional[int]]
        return get_args(typ, evaluate=True)
    else:
        return typ,
    
    
def robust_isinstance(inst, typ) -> bool:
    """
    Similar to isinstance, but if 'typ' is a parametrized generic Type, it is first transformed into its base generic
    class so that the instance check works. It is also robust to Union and Any.

    :param inst:
    :param typ:
    :return:
    """
    if typ is Any:
        return True
    if is_typevar(typ):
        if hasattr(typ, '__constraints__') and typ.__constraints__ is not None:
            typs = get_args(typ, evaluate=True)
            return any(robust_isinstance(inst, t) for t in typs)
        elif hasattr(typ, '__bound__') and typ.__bound__ is not None:
            return robust_isinstance(inst, typ.__bound__)
        else:
            # a raw TypeVar means 'anything'
            return True
    else:
        if is_union_type(typ):
            typs = get_args(typ, evaluate=True)
            return any(robust_isinstance(inst, t) for t in typs)
        else:
            return isinstance(inst, get_base_generic_type(typ))


def get_pretty_type_str(object_type) -> str:
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
            return object_type.__name__ + '[' \
                   + ', '.join([get_pretty_type_str(item_type) for item_type in contents_item_type]) + ']'
        else:
            if contents_key_type is not None:
                return object_type.__name__ + '[' + get_pretty_type_str(contents_key_type) + ', ' \
                       + get_pretty_type_str(contents_item_type) + ']'
            elif contents_item_type is not None:
                return object_type.__name__ + '[' + get_pretty_type_str(contents_item_type) + ']'
    except Exception as e:
        pass

    if is_union_type(object_type):
        return 'Union[' + ', '.join([get_pretty_type_str(item_type) 
                                     for item_type in get_args(object_type, evaluate=True)]) + ']'
    elif is_typevar(object_type):
        # typevars usually do not display their namespace so str() is compact. And it displays the cov/contrav symbol
        return str(object_type)
    else:
        try:
            return object_type.__name__
        except:
            return str(object_type)


def get_pretty_type_keys_dict(dict: Dict[Any, Any]) -> Dict[str, Any]:
    return {get_pretty_type_str(typ): val for typ, val in dict.items()}


# def is_parametrized_generic(object_type):
#     """
#     Utility method to check if a "typing" type is parametrized as in List[str], or if it not, as in List
#
#     :param object_type:
#     :return:
#     """
#     # Referenced by https://github.com/python/typing/issues/423
#     # return hasattr(object_type, '__origin__') and object_type.__origin__ is not None
#     return is_generic_type(object_type)
#     # try:
#     #     return issubclass(object_type, Generic)
#     # except TypeError as e:
#     #     if e.args[0].startswith('descriptor \'__subclasses__\' of'):
#     #         # known bug that is supposed to be fixed by now https://github.com/python/typing/issues/266.
#     #         # as a fallback, at least return true if class is a subclass of the 'must know' classes
#     #         return issubclass(object_type, (List, Set, Tuple, Dict))
#     #
#     #     elif e.args[0].startswith('cannot create weak reference to'):
#     #         # assuming this is fixed : https://github.com/python/typing/issues/345
#     #         # then what remains is a type that is does not extend the typing module
#     #         return False
#     #
#     #     else:
#     #         raise e


def get_base_generic_type(object_type):
    """
    Utility method to return the equivalent non-customized type for a Generic type, including user-defined ones.
    for example calling it on typing.List<~T>[int] will return typing.List<~T>.

    If the type is not parametrized it is returned as is

    :param object_type:
    :return:
    """
    return get_origin(object_type) or object_type
    #
    #
    # # Solution referenced by https://github.com/python/typing/issues/423
    # # note: is_generic_type excludes special typing constructs such as Union, Tuple, Callable, ClassVar
    # if is_generic_type(object_type) or is_tuple_type(object_type):
    #     # inferred_base_type = locate(object_type.__module__ + '.' + object_type.__name__)
    #     # return object_type.__origin__
    #     return get_origin(object_type)
    #     # if inferred_base_type is not None:
    #     #     return inferred_base_type
    #     # else:
    #     #     # that may happen if your generic class has been defined inside a local class
    #     #     # For these classes, we cant' get the base (expressed with 'T') class, strangely enough
    #     #     warn('Unable to find the base generic class for ' + str(object_type) + ' although it seems to extend '
    #     #          'typing.Generic. Using the class directly')
    #     #     return object_type
    # else:
    #     return object_type


def is_typed_collection(object_type) -> bool:
    """
    Returns True if the object type is a collection with correct PEP type hints about its contents
    :param object_type:
    :return:
    """
    return is_collection(object_type) and \
           _extract_collection_base_type(object_type, exception_if_none=False)[0] is not None


def is_collection(object_type, strict: bool = False) -> bool:
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}
    or of list, dict, set, tuple.

    If strict is set to True, the method will return True only if the class IS directly one of the base collection
    classes

    :param object_type:
    :param strict: if set to True, this method will look for a strict match.
    :return:
    """
    if object_type is None or object_type is Any or is_union_type(object_type) or is_typevar(object_type):
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


def get_all_subclasses(typ):
    """
    Returns all subclasses, and supports generic types
    :param typ:
    :return:
    """
    if is_generic_type(typ):
        # We now use get_origin() to also find all the concrete subclasses in case the desired type is a generic
        # TODO in that case we should also check that the subclass is compliant with all the TypeVar constraints
        return get_origin(typ).__subclasses__()
    else:
        return typ.__subclasses__()


def is_valid_pep484_type_hint(typ_hint):
    """
    Returns True if the provided type is a valid PEP484 type hint, False otherwise.
    Note: string type hints are not supported by parsyfiles as of today

    :param typ_hint:
    :return:
    """
    try:
        # most common case first, to be faster
        if isinstance(typ_hint, type):
            return True
        else:
            try:
                return is_union_type(typ_hint) or is_typevar(typ_hint)
            except:
                return False
    except:
        try:
            return is_union_type(typ_hint) or is_typevar(typ_hint)
        except:
            return False


def is_pep484_nonable(typ):
    """
    Checks if a given type is nonable, meaning that it explicitly or implicitly declares a Union with NoneType.
    Nested TypeVars and Unions are supported.

    :param typ:
    :return:
    """
    if typ is type(None):
        return True
    elif is_typevar(typ) or is_union_type(typ):
        return any(is_pep484_nonable(tt) for tt in resolve_union_and_typevar(typ))
    else:
        return False


def _extract_collection_base_type(collection_object_type, exception_if_none: bool = True) \
        -> Tuple[Type, Optional[Type]]:
    """
    Utility method to extract the base item type from a collection/iterable item type.
    Throws
    * a TypeError if the collection_object_type a Dict with non-string keys.
    * an AttributeError if the collection_object_type is actually not a collection
    * a TypeInformationRequiredError if somehow the inner type can't be found from the collection type (either if dict,
    list, set, tuple were used instead of their typing module equivalents (Dict, List, Set, Tuple), or if the latter
    were specified without inner content types (as in Dict instead of Dict[str, Foo])

    :param collection_object_type:
    :return: a tuple containing the collection's content type (which may itself be a Tuple in case of a Tuple) and the
    collection's content key type for dicts (or None)
    """
    contents_item_type = None
    contents_key_type = None

    check_var(collection_object_type, var_types=type, var_name='collection_object_type')

    is_tuple = False
    if is_tuple_type(collection_object_type):  # Tuple is a special construct, is_generic_type does not work
        is_tuple = True
        # --old: hack into typing module
        # if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
        # contents_item_type = collection_object_type.__args__

        # --new : using typing_inspect
        # __args = get_last_args(collection_object_type)
        # this one works even in typevar+config cases such as t = Tuple[int, Tuple[T, T]][Optional[int]]
        __args = get_args(collection_object_type, evaluate=True)
        if len(__args) > 0:
            contents_item_type = __args

    elif issubclass(collection_object_type, Mapping):  # Dictionary-like
        if is_generic_type(collection_object_type):
            # --old: hack into typing module
            # if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
            # contents_key_type, contents_item_type = collection_object_type.__args__

            # --new : using typing_inspect
            # __args = get_last_args(collection_object_type)
            # this one works even in typevar+config cases such as d = Dict[int, Tuple[T, T]][Optional[int]]
            __args = get_args(collection_object_type, evaluate=True)
            if len(__args) > 0:
                contents_key_type, contents_item_type = __args
                if not issubclass(contents_key_type, str):
                    raise TypeError('Collection object has type Dict, but its PEP484 type hints declare '
                                    'keys as being of type ' + str(contents_key_type) + ' which is not supported. Only '
                                    'str keys are supported at the moment, since we use them as item names')

    elif issubclass(collection_object_type, Iterable):  # List or Set. Should we rather use Container here ?
        if is_generic_type(collection_object_type):
            # --old: hack into typing module
            # if hasattr(collection_object_type, '__args__') and collection_object_type.__args__ is not None:
            # contents_item_type = collection_object_type.__args__[0]

            # --new : using typing_inspect
            # __args = get_last_args(collection_object_type)
            # this one works even in typevar+config cases such as i = Iterable[Tuple[T, T]][Optional[int]]
            __args = get_args(collection_object_type, evaluate=True)
            if len(__args) > 0:
                contents_item_type, = __args

    elif issubclass(collection_object_type, dict) or issubclass(collection_object_type, list)\
            or issubclass(collection_object_type, tuple) or issubclass(collection_object_type, set):
        # the error is now handled below with the other under-specified types situations
        pass

    else:
        # Not a collection
        raise AttributeError('Cannot extract collection base type, object type ' + str(collection_object_type)
                             + ' is not a collection')

    # Finally return if something was found, otherwise tell it
    if not exception_if_none:
        # always return, whatever it is
        return contents_item_type, contents_key_type
    elif contents_item_type is None or contents_item_type is Parameter.empty:
        # Empty type hints
        raise TypeInformationRequiredError.create_for_collection_items(collection_object_type, contents_item_type)
    elif is_tuple:
        # Iterate on all sub-types
        for t in contents_item_type:
            if contents_item_type is None or contents_item_type is Parameter.empty:
                # Empty type hints
                raise TypeInformationRequiredError.create_for_collection_items(collection_object_type, t)
            if not is_valid_pep484_type_hint(t):
                # Invalid type hints
                raise InvalidPEP484TypeHint.create_for_collection_items(collection_object_type, t)
    elif not is_valid_pep484_type_hint(contents_item_type):
        # Invalid type hints
        raise InvalidPEP484TypeHint.create_for_collection_items(collection_object_type, contents_item_type)

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
    It supports PEP484 and 'attrs' declaration, see https://github.com/python-attrs/attrs.

    :param item_type:
    :return: a dictionary containing for each attr name, a tuple (type, is_mandatory)
    """

    try:
        # -- Try to read an 'attr' declaration and to extract types and optionality
        from parsyfiles.plugins_optional.support_for_attrs import get_attrs_declarations
        res = get_attrs_declarations(item_type)

        # check that types are correct
        for attr_name, v in res.items():
            typ = v[0]
            if typ is None or typ is Parameter.empty or not isinstance(typ, type):
                raise TypeInformationRequiredError.create_for_object_attributes(item_type, attr_name, typ)

    except:
        # -- Fallback to PEP484
        res = dict()

        # first get the signature of the class constructor
        s = _get_constructor_signature(item_type)

        # then extract the type and optionality of each attribute and raise errors if needed
        for attr_name in s.parameters.keys():
            # skip the 'self' attribute
            if attr_name != 'self':

                # -- Get and check that the attribute type is PEP484 compliant
                typ = s.parameters[attr_name].annotation
                if (typ is None) or (typ is Parameter.empty):
                    raise TypeInformationRequiredError.create_for_object_attributes(item_type, attr_name, typ)
                elif not is_valid_pep484_type_hint(typ):
                    raise InvalidPEP484TypeHint.create_for_object_attributes(item_type, attr_name, typ)

                # -- is the attribute mandatory ?
                is_mandatory = (s.parameters[attr_name].default is Parameter.empty) and not is_pep484_nonable(typ)

                # -- store both info in result dict
                res[attr_name] = (typ, is_mandatory)

    return res


class TypeInformationRequiredError(Exception):
    """
    Raised whenever there is a missing type hint in a collection declaration or an object constructor attribute
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
    def create_for_collection_items(item_type, hint):
        """
        Helper method for collection items

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError("Cannot parse object of type {t} as a collection: this type has no "
                                            "PEP484 type hint about its contents. Please use a full "
                                            "PEP484 declaration such as Dict[str, Foo] or List[Foo]"
                                            "".format(t=str(item_type)))

    @staticmethod
    def create_for_object_attributes(item_type, faulty_attribute_name: str, hint):
        """
        Helper method for constructor attributes

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError("Cannot create instances of type {t}: constructor attribute '{a}' has no "
                                            "PEP484 type hint.".format(t=str(item_type), a=faulty_attribute_name))


class InvalidPEP484TypeHint(TypeInformationRequiredError):
    """
    Raised whenever there is an invalid type hint in a collection declaration or an object constructor attribute
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(InvalidPEP484TypeHint, self).__init__(contents)

    @staticmethod
    def create_for_collection_items(item_type, hint):
        """
        Helper method for collection items

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError("Cannot parse object of type {t} as a collection: this type has no valid "
                                            "PEP484 type hint about its contents: found {h}. Please use a standard "
                                            "PEP484 declaration such as Dict[str, Foo] or List[Foo]"
                                            "".format(t=str(item_type), h=hint))

    @staticmethod
    def create_for_object_attributes(item_type, faulty_attribute_name: str, hint):
        """
        Helper method for constructor attributes

        :param item_type:
        :return:
        """
        # this leads to infinite loops
        # try:
        #     prt_type = get_pretty_type_str(item_type)
        # except:
        #     prt_type = str(item_type)
        return TypeInformationRequiredError("Cannot create instances of type {t}: constructor attribute '{a}' has an"
                                            " invalid PEP484 type hint: {h}.".format(t=str(item_type),
                                                                                     a=faulty_attribute_name, h=hint))
