from inspect import Parameter, signature, stack, getmodule
from typing import TypeVar, MutableMapping, Dict, List, Set, Tuple, Type, Any, Mapping, Iterable, Optional, _ForwardRef

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


def get_alternate_types_resolving_forwardref_union_and_typevar(typ, _memo: List[Any] = None) \
        -> Tuple[Any, ...]:
    """
    Returns a tuple of all alternate types allowed by the `typ` type annotation.

    If typ is a TypeVar,
     * if the typevar is bound, return get_alternate_types_resolving_forwardref_union_and_typevar(bound)
     * if the typevar has constraints, return a tuple containing all the types listed in the constraints (with
     appropriate recursive call to get_alternate_types_resolving_forwardref_union_and_typevar for each of them)
     * otherwise return (object, )

    If typ is a Union, return a tuple containing all the types listed in the union (with
     appropriate recursive call to get_alternate_types_resolving_forwardref_union_and_typevar for each of them)

    If typ is a forward reference, it is evaluated and this method is applied to the results.

    Otherwise (typ, ) is returned

    Note that this function automatically prevent infinite recursion through forward references such as in
    `A = Union[str, 'A']`, by keeping a _memo of already met symbols.

    :param typ: 
    :return: 
    """
    # avoid infinite recursion by using a _memo
    _memo = _memo or []
    if typ in _memo:
        return tuple()

    # remember that this was already explored
    _memo.append(typ)
    if is_typevar(typ):
        if hasattr(typ, '__bound__') and typ.__bound__ is not None:
            # TypeVar is 'bound' to a class
            if hasattr(typ, '__contravariant__') and typ.__contravariant__:
                # Contravariant means that only super classes of this type are supported!
                raise Exception('Contravariant TypeVars are not supported')
            else:
                # only subclasses of this are allowed (even if not covariant, because as of today we cant do otherwise)
                return get_alternate_types_resolving_forwardref_union_and_typevar(typ.__bound__, _memo=_memo)

        elif hasattr(typ, '__constraints__') and typ.__constraints__ is not None:
            if hasattr(typ, '__contravariant__') and typ.__contravariant__:
                # Contravariant means that only super classes of this type are supported!
                raise Exception('Contravariant TypeVars are not supported')
            else:
                # TypeVar is 'constrained' to several alternate classes, meaning that subclasses of any of them are
                # allowed (even if not covariant, because as of today we cant do otherwise)
                return tuple(typpp for c in typ.__constraints__
                             for typpp in get_alternate_types_resolving_forwardref_union_and_typevar(c, _memo=_memo))

        else:
            # A non-parametrized TypeVar means 'any'
            return object,

    elif is_union_type(typ):
        # do not use typ.__args__, it may be wrong
        # the solution below works even in typevar+config cases such as u = Union[T, str][Optional[int]]
        return tuple(t for typpp in get_args(typ, evaluate=True)
                     for t in get_alternate_types_resolving_forwardref_union_and_typevar(typpp, _memo=_memo))

    elif is_forward_ref(typ):
        return get_alternate_types_resolving_forwardref_union_and_typevar(resolve_forward_ref(typ), _memo=_memo)

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
        # DO NOT resolve forward references otherwise this can lead to infinite recursion
        contents_item_type, contents_key_type = _extract_collection_base_type(object_type, resolve_fwd_refs=False)
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


def get_all_subclasses(typ, recursive: bool = True, memo = None) -> List[Type[Any]]:
    """
    Returns all subclasses, and supports generic types. It is recursive by default

    :param typ:
    :return:
    """
    memo = memo or []
    if typ in memo:
        return list()

    memo.append(typ)
    if is_generic_type(typ):
        # We now use get_origin() to also find all the concrete subclasses in case the desired type is a generic
        # TODO in that case we should also check that the subclass is compliant with all the TypeVar constraints
        # see if there is an easy way to do this in https://github.com/Stewori/pytypes/issues/31
        sub_list = get_origin(typ).__subclasses__()
    else:
        sub_list = typ.__subclasses__()

    # recurse
    if recursive:
        return sub_list + list(t for typpp in sub_list for t in get_all_subclasses(typpp, memo=memo))
    else:
        return sub_list


def is_forward_ref(typ):
    """
    Returns true if typ is a typing ForwardRef
    :param typ:
    :return:
    """
    return isinstance(typ, _ForwardRef)


class InvalidForwardRefError(Exception):
    """ Raised whenever some forward reference can not be evaluated """

    def __init__(self, invalid: _ForwardRef):
        self.invalid_ref = invalid

    def __str__(self):
        return "Invalid PEP484 type hint: forward reference {} could not be resolved with the current stack's " \
               "variables".format(self.invalid_ref)


def eval_forward_ref(typ: _ForwardRef):
    """
    Climbs the current stack until the given Forward reference has been resolved, or raises an InvalidForwardRefError

    :param typ: the forward reference to resolve
    :return:
    """
    for frame in stack():
        m = getmodule(frame[0])
        m_name = m.__name__ if m is not None else '<unknown>'
        if m_name.startswith('parsyfiles.tests') or not m_name.startswith('parsyfiles'):
            try:
                # print("File {}:{}".format(frame.filename, frame.lineno))
                return typ._eval_type(frame[0].f_globals, frame[0].f_locals)
            except NameError:
                pass

    raise InvalidForwardRefError(typ)


def resolve_forward_ref(typ):
    """
    If typ is a forward reference, return a resolved version of it. If it is not, return typ 'as is'

    :param typ:
    :return:
    """
    if is_forward_ref(typ):
        return eval_forward_ref(typ)
    else:
        return typ


def is_valid_pep484_type_hint(typ_hint, allow_forward_refs: bool = False):
    """
    Returns True if the provided type is a valid PEP484 type hint, False otherwise.

    Note: string type hints (forward references) are not supported by default, since callers of this function in
    parsyfiles lib actually require them to be resolved already.

    :param typ_hint:
    :param allow_forward_refs:
    :return:
    """
    # most common case first, to be faster
    try:
        if isinstance(typ_hint, type):
            return True
    except:
        pass

    # optionally, check forward reference
    try:
        if allow_forward_refs and is_forward_ref(typ_hint):
            return True
    except:
        pass

    # finally check unions and typevars
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
    # TODO rely on typing_inspect if there is an answer to https://github.com/ilevkivskyi/typing_inspect/issues/14
    if typ is type(None):
        return True
    elif is_typevar(typ) or is_union_type(typ):
        return any(is_pep484_nonable(tt) for tt in get_alternate_types_resolving_forwardref_union_and_typevar(typ))
    else:
        return False


def _extract_collection_base_type(collection_object_type, exception_if_none: bool = True,
                                  resolve_fwd_refs: bool = True) -> Tuple[Type, Optional[Type]]:
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
    try:
        if contents_item_type is None or contents_item_type is Parameter.empty:
            # Empty type hints
            raise TypeInformationRequiredError.create_for_collection_items(collection_object_type, contents_item_type)
        
        elif is_tuple:
            # --- tuple: Iterate on all sub-types
            resolved = []
            for t in contents_item_type:
                # Check for empty type hints
                if contents_item_type is None or contents_item_type is Parameter.empty:
                    raise TypeInformationRequiredError.create_for_collection_items(collection_object_type, t)

                # Resolve any forward references if needed
                if resolve_fwd_refs:
                    t = resolve_forward_ref(t)
                resolved.append(t)

                # Final type hint compliance
                if not is_valid_pep484_type_hint(t):
                    raise InvalidPEP484TypeHint.create_for_collection_items(collection_object_type, t)

            if resolve_fwd_refs:
                contents_item_type = tuple(resolved)
        
        else:
            # --- Not a tuple
            # resolve any forward references first
            if resolve_fwd_refs:
                contents_item_type = resolve_forward_ref(contents_item_type)

            # check validity then
            if not is_valid_pep484_type_hint(contents_item_type):
                # Invalid type hints
                raise InvalidPEP484TypeHint.create_for_collection_items(collection_object_type, contents_item_type)

    except TypeInformationRequiredError as e:
        # only raise it if the flag says it
        if exception_if_none:
            raise e.with_traceback(e.__traceback__)

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


def get_validated_attribute_type_info(typ, item_type, attr_name):
    """
    Routine to validate that typ is a valid non-empty PEP484 type hint. If it is a forward reference, it will be 
    resolved 
    
    :param typ: 
    :param item_type: 
    :param attr_name: 
    :return: 
    """
    if (typ is None) or (typ is Parameter.empty):
        raise TypeInformationRequiredError.create_for_object_attributes(item_type, attr_name, typ)

    # resolve forward references
    typ = resolve_forward_ref(typ)

    if not is_valid_pep484_type_hint(typ):
        raise InvalidPEP484TypeHint.create_for_object_attributes(item_type, attr_name, typ)

    return typ


def get_constructor_attributes_types(item_type) -> Dict[str, Tuple[Type[Any], bool]]:
    """
    Utility method to return a dictionary of attribute name > attribute type from the constructor of a given type
    It supports PEP484 and 'attrs' declaration, see https://github.com/python-attrs/attrs.

    :param item_type:
    :return: a dictionary containing for each attr name, a tuple (type, is_mandatory)
    """
    res = dict()
    try:
        # -- Try to read an 'attr' declaration and to extract types and optionality
        from parsyfiles.plugins_optional.support_for_attrs import get_attrs_declarations
        decls = get_attrs_declarations(item_type)

        # check that types are correct
        for attr_name, v in decls.items():
            # -- Get and check that the attribute type is PEP484 compliant
            typ = get_validated_attribute_type_info(v[0], item_type, attr_name)

            # -- is the attribute mandatory ?
            is_mandatory = not is_pep484_nonable(typ)  # and TODO get the default value in the attrs declaration + check validator 'optional'

            # -- store both info in result dict
            res[attr_name] = (typ, is_mandatory)

    except Exception:  # ImportError or NotAnAttrsClassError but we obviously cant import the latter
        
        # -- Fallback to PEP484

        # first get the signature of the class constructor
        s = _get_constructor_signature(item_type)

        # then extract the type and optionality of each attribute and raise errors if needed
        for attr_name in s.parameters.keys():
            # skip the 'self' attribute
            if attr_name != 'self':

                # -- Get and check that the attribute type is PEP484 compliant
                typ = get_validated_attribute_type_info(s.parameters[attr_name].annotation, item_type, attr_name)

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
