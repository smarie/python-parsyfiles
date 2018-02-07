from abc import abstractmethod, ABCMeta
from copy import copy, deepcopy
from logging import Logger
from typing import Generic, TypeVar, Type, Any, Set, Tuple, Callable, List, Dict

from parsyfiles.type_inspection_tools import get_pretty_type_str
from parsyfiles.var_checker import check_var


JOKER = '*J*'
""" A joker to be used when users query for capabilities. We used to use None but this was too confusing for code 
readability """


class AnyObject(object):
    """Helper class alias for 'Any', see method is_any_type below"""
    pass


def is_any_type(typ: Type[Any]) -> bool:
    """
    Helper function to check if a type is 'Any'. Created in order to easily change the behaviour for the whole module.
    Indeed before we used 'typing.Any' but now that typing.py prevents use of Any in isinstance and issubclass, we
    switched back to 'object'.

    Note that parsers/converters may use 'object' or 'Any' to denote 'any type', but at creation time the type will be
    converted to AnyObject (see get_validated_type method)

    :param typ:
    :return:
    """
    return typ is AnyObject


def is_any_type_set(sett: Set[Type]) -> bool:
    """
    Helper method to check if a set of types is the {AnyObject} singleton

    :param sett:
    :return:
    """
    return len(sett) == 1 and is_any_type(min(sett))  # min is a way to access the single element of a size 1 set


def get_validated_types(object_types: Set[Type], set_name: str) -> Set[Type]:
    """
    Utility to validate a set of types :
    * None is not allowed as a whole or within the set,
    * object and Any are converted into AnyObject
    * if AnyObject is in the set, it must be the only element

    :param object_types: the set of types to validate
    :param set_name: a name used in exceptions if any
    :return: the fixed set of types
    """
    check_var(object_types, var_types=set, var_name=set_name)
    res = {get_validated_type(typ, set_name + '[x]') for typ in object_types}
    if AnyObject in res and len(res) > 1:
        raise ValueError('The set of types contains \'object\'/\'Any\'/\'AnyObject\', so no other type must be present '
                         'in the set')
    else:
        return res


def get_validated_type(object_type: Type[Any], name: str, enforce_not_joker: bool = True) -> Type[Any]:
    """
    Utility to validate a type :
    * None is not allowed,
    * 'object', 'AnyObject' and 'Any' lead to the same 'AnyObject' type
    * JOKER is either rejected (if enforce_not_joker is True, default) or accepted 'as is'

    :param object_type: the type to validate
    :param name: a name used in exceptions if any
    :param enforce_not_joker: a boolean, set to False to tolerate JOKER types
    :return: the fixed type
    """
    if object_type is object or object_type is Any or object_type is AnyObject:
        return AnyObject
    else:
        # -- !! Do not check TypeVar or Union : this is already handled at higher levels --
        if object_type is JOKER:
            # optionally check if JOKER is allowed
            if enforce_not_joker:
                raise ValueError('JOKER is not allowed for object_type')
        else:
            # note: we dont check var earlier, since 'typing.Any' is not a subclass of type anymore
            check_var(object_type, var_types=type, var_name=name)
        return object_type


S = TypeVar('S')  # Can be anything - used for "source object"
T = TypeVar('T')  # Can be anything - used for all other objects


class Converter(Generic[S, T], metaclass=ABCMeta):
    """
    Parent class of all converters able to convert an object of a given source type to another, of a destination type.
    A destination type of 'AnyObject' is allowed. In that case the converter is a 'generic' converter. A custom function
    may be provided at construction time, to enable converters to reject some conversions, even if their dest type is
    'AnyObject'.
    """

    def __init__(self, from_type: Type[S], to_type: Type[T],
                 is_able_to_convert_func: Callable[[bool, Type[S], Type[T]], bool] = None,
                 can_chain: bool = True):
        """
        Constructor for a converter from one source type (from_type) to one destination type (to_type).
        from_type may be any type except AnyObject or object. to_type may be AnyObject.

        A custom function may be provided to enable converters to reject some conversions, even if the provided type
        is a subclass of their source type and the expected type is a parent class of their dest type (or their dest
        type is 'AnyObject').

        :param from_type: the source type
        :param to_type: the destination type, or AnyObject (for generic converters)
        :param is_able_to_convert_func: an optional function taking a desired object type as an input and outputting a
        boolean. It will be called in 'is_able_to_convert'. This allows implementors to reject some conversions even if
        they are compliant with their declared 'to_type'. Implementors should handle a 'None' value as a joker
        :param can_chain: a boolean (default True) indicating if other converters can be appended at the end of this
        converter to create a chain. Dont change this except if it really can never make sense.
        """
        # --from type
        self.from_type = get_validated_type(from_type, 'from_type')
        if from_type is AnyObject:
            raise ValueError('A converter\'s \'from_type\' cannot be anything at the moment, it would be a mess.')

        # --to type
        self.to_type = get_validated_type(to_type, 'to_type')

        # --conversion function
        check_var(is_able_to_convert_func, var_types=Callable, var_name='is_able_to_convert_func',
                  enforce_not_none=False)
        if is_able_to_convert_func is not None:
            # sanity check : check that conversion function handles jokers properly
            try:
                res = is_able_to_convert_func(True, from_type=None, to_type=None)
                if not res:
                    raise ValueError('Conversion function ' + str(is_able_to_convert_func) + ' can not be registered '
                                     'since it does not handle the JOKER (None) cases correctly')
            except Exception as e:
                raise ValueError('Error while registering conversion function ' + str(is_able_to_convert_func)
                                 + ': ' + str(e)).with_traceback(e.__traceback__)

        self.is_able_to_convert_func = is_able_to_convert_func

        # -- can chain
        check_var(can_chain, var_types=bool, var_name='can_chain')
        self.can_chain = can_chain

    def __len__(self):
        # as opposed to conversion chains.. for use in sorting methods
        return 1

    def is_generic(self):
        """
        A converter is generic if its destination type is 'AnyObject'.
        :return:
        """
        return is_any_type(self.to_type)

    def __str__(self):
        return '<Converter from ' + get_pretty_type_str(self.from_type) + ' to ' + get_pretty_type_str(self.to_type) \
               + '>'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def options_hints(self):
        """
        Returns a string representing the options available for this converter
        :return:
        """
        return self.get_id_for_options() + ': No declared option'

    def is_able_to_convert(self, strict: bool, from_type: Type[Any], to_type: Type[Any]) -> bool:
        return self.is_able_to_convert_detailed(strict=strict, from_type=from_type, to_type=to_type)[0]

    def is_able_to_convert_detailed(self, strict: bool, from_type: Type[Any], to_type: Type[Any]) \
            -> Tuple[bool, bool, bool]:
        """
        Utility method to check if a parser is able to convert a given type to the given type, either in
        * strict mode : provided_type and desired_type must be equal to this converter's from_type and to_type
        respectively (or the to_type does not match but this converter is generic
        * inference mode (non-strict) : provided_type may be a subclass of from_type, and to_type may be a subclass
        of desired_type

        If a custom function was provided at construction time, it is called to enable converters to reject some
        conversions based on source and/or dest type provided.

        :param strict: a boolean indicating if matching should be in strict mode or not
        :param from_type:
        :param to_type:
        :return: a tuple of 3 booleans : (does match?, strict source match? (None if no match), strict dest match?
        (None if no match))
        """
        # (1) first handle the easy joker+joker case
        if from_type is JOKER and to_type is JOKER:
            return True, None, None

        # Don't validate types -- this is called too often at the initial RootParser instance creation time,
        # and this is quite 'internal' so the risk is very low
        #
        # check_var(strict, var_types=bool, var_name='strict')
        # if from_type is not JOKER:
        #     check_var(from_type, var_types=type, var_name='from_type')
        # if to_type is not JOKER:
        #     check_var(to_type, var_types=type, var_name='to_type')

        # -- first call custom checker if provided
        if self.is_able_to_convert_func is not None:
            # TODO Maybe one day, rather push the JOKER to the function ? not sure that it will be more explicit..
            if not self.is_able_to_convert_func(strict,
                                                from_type=None if from_type is JOKER else from_type,
                                                to_type=None if to_type is JOKER else to_type):
                return False, None, None

        # -- from_type strict match
        if (from_type is JOKER) or (from_type is self.from_type) or is_any_type(from_type):
            # -- check to type strict
            if (to_type is JOKER) or self.is_generic() or (to_type is self.to_type):
                return True, True, True  # strict to_type match
            # -- check to type non-strict
            elif (not strict) and issubclass(self.to_type, to_type):
                return True, True, False  # approx to_type match

        # -- from_type non-strict match
        elif (not strict) and issubclass(from_type, self.from_type):
            # -- check to type strict
            if (to_type is JOKER) or self.is_generic() or (to_type is self.to_type):
                return True, False, True  # exact to_type match
            # -- check to type non-strict
            elif (not strict) and issubclass(self.to_type, to_type):
                return True, False, False  # approx to_type match

        # -- otherwise no match
        return False, None, None

    @staticmethod
    def are_worth_chaining(left_converter, right_converter) -> bool:
        """
        Utility method to check if it makes sense to chain these two converters. Returns True if it brings value to
        chain the first converter with the second converter. To bring value,
        * the second converter's input should not be a parent class of the first converter's input (in that case, it is
          always more interesting to use the second converter directly for any potential input)
        * the second converter's output should not be a parent class of the first converter's input or output. Otherwise
        the chain does not even make any progress :)
        * The first converter has to allow chaining (with converter.can_chain=True)

        :param left_converter:
        :param right_converter:
        :return:
        """
        if not left_converter.can_chain:
            return False

        elif not is_any_type(left_converter.to_type) and is_any_type(right_converter.to_type):
            # we gain the capability to generate any type. So it is interesting.
            return True

        elif issubclass(left_converter.from_type, right_converter.to_type) \
                or issubclass(left_converter.to_type, right_converter.to_type) \
                or issubclass(left_converter.from_type, right_converter.from_type):
            # Not interesting : the outcome of the chain would be not better than one of the converters alone
            return False

        # Note: we dont say that chaining a generic converter with a converter is useless. Indeed it might unlock some
        # capabilities for the user (new file extensions, etc.) that would not be available with the generic parser
        # targetting to_type alone. For example parsing object A from its constructor then converting A to B might
        # sometimes be interesting, rather than parsing B from its constructor

        else:
            # interesting
            return True

    def can_be_appended_to(self, left_converter, strict: bool) -> bool:
        """
        Utility method to check if this (self) converter can be appended after the output of the provided converter.
        This method does not check if it makes sense, it just checks if the output type of the left converter is
        compliant with the input type of this converter. Compliant means:
        * strict mode : type equality
        * non-strict mode : output type of left_converter should be a subclass of input type of this converter

        In addition, the custom function provided in constructor may be used to reject conversion (see
        is_able_to_convert for details)

        :param left_converter:
        :param strict: boolean to
        :return:
        """
        is_able_to_take_input = self.is_able_to_convert(strict, from_type=left_converter.to_type, to_type=JOKER)
        if left_converter.is_generic():
            return is_able_to_take_input \
                   and left_converter.is_able_to_convert(strict, from_type=JOKER, to_type=self.from_type)
        else:
            return is_able_to_take_input

    def get_id_for_options(self):
        """
        Default implementation : the id to use in the options is the class name
        :return:
        """
        return self.__class__.__name__

    def get_applicable_options(self, options: Dict[str, Dict[str, Any]]):
        """
        Returns the options that are applicable to this particular converter, from the full map of options.
        It first uses 'get_id_for_options()' to know the id of this parser, and then simply extracts the contents of
        the options corresponding to this id, or returns an empty dict().

        :param options: a dictionary converter_id > options
        :return:
        """
        return get_options_for_id(options, self.get_id_for_options())

    def convert(self, desired_type: Type[T], source_obj: S, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        if self.is_able_to_convert(False, from_type=type(source_obj), to_type=desired_type):
            return self._convert(desired_type, source_obj, logger, options)
        else:
            raise ConversionException.create_not_able_to_convert(source_obj, self, desired_type)

    @abstractmethod
    def _convert(self, desired_type: Type[T], source_obj: S, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementing classes should implement this method to perform the conversion itself

        :param desired_type: the destination type of the conversion
        :param source_obj: the source object that should be converter
        :param logger: a logger to use if any is available, or None
        :param options: additional options map. Implementing classes may use 'self.get_applicable_options()' to get the
        options that are of interest for this converter.
        :return:
        """
        pass


class ConversionException(Exception):
    """
    Raised whenever parsing fails
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create_not_able_to_convert()

        :param contents:
        """
        super(ConversionException, self).__init__(contents)

    @staticmethod
    def create_not_able_to_convert(source: S, converter: Converter, desired_type: Type[T]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param source:
        :param converter:
        :param desired_type:
        :return:
        """
        base_msg = 'Converter ' + str(converter) + ' is not able to ingest source value \'' + str(source) + '\''\
                   ' of type \'' + get_pretty_type_str(type(source)) + '\' and/or convert it to type \'' \
                   + get_pretty_type_str(desired_type) + '\'.'
        base_msg += ' This can happen in a chain when the previous step in the chain is generic and actually produced '\
                    ' an output of the wrong type/content'

        return ConversionException(base_msg)


def get_options_for_id(options: Dict[str, Dict[str, Any]], identifier: str):
    """
    Helper method, from the full options dict of dicts, to return either the options related to this parser or an
    empty dictionary. It also performs all the var type checks

    :param options:
    :param identifier:
    :return:
    """
    check_var(options, var_types=dict, var_name='options')
    res = options[identifier] if identifier in options.keys() else dict()
    check_var(res, var_types=dict, var_name='options[' + identifier + ']')
    return res


# an alias for the conversion method signature
ConversionMethod = Callable[[Type[T], S, Logger], T]
conversion_method_example_signature_str = 'def my_convert_fun(desired_type: Type[T], source: S, logger: Logger, ' \
                                          '**kwargs) -> T'
MultiOptionsConversionMethod = Callable[[Type[T], S, Logger, Dict[str, Dict[str, Any]]], T]
multioptions_conversion_method_example_signature_str = 'def my_convert_fun(desired_type: Type[T], source: S, ' \
                                                   'logger: Logger, options: Dict[str, Dict[str, Any]]) -> T'


class CaughtTypeError(Exception):
    """
    Raised whenever a TypeError is caught during ConverterFunction's converter function execution
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(CaughtTypeError, self).__init__(contents)

    @staticmethod
    def create(converter_func: ConversionMethod, caught: Exception):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param converter_func:
        :param caught:
        :return:
        """
        msg = 'Caught TypeError while calling conversion function \'' + str(converter_func.__name__) + '\'. ' \
              'Note that the conversion function signature should be \'' + conversion_method_example_signature_str \
              + '\' (unpacked options mode - default) or ' + multioptions_conversion_method_example_signature_str \
              + ' (unpack_options = False).' \
              + 'Caught error message is : ' + caught.__class__.__name__ + ' : ' + str(caught)
        return CaughtTypeError(msg).with_traceback(caught.__traceback__)


class ConverterFunction(Converter[S, T]):
    """
    Helper class to create a Converter from a user-provided function. See Converter class for details.
    """
    def __init__(self, from_type: Type[S], to_type: Type[T], conversion_method: ConversionMethod,
                 custom_name: str = None, is_able_to_convert_func: Callable[[bool, Type[S], Type[T]], bool] = None,
                 can_chain: bool = True, function_args: dict = None, unpack_options: bool = True,
                 option_hints: Callable[[], str] = None):
        """
        Constructor with a conversion method. All calls to self.convert() will be delegated to this method. An optional
        name may be provided to override the provided conversion method's name. this might be useful for example if the
        same function is used in several converters.

        See Converter class for details on other arguments.

        :param from_type: the source type
        :param to_type: the destination type, or AnyObject (for generic converters)
        :param conversion_method: the function the conversion step will be delegated to
        :param custom_name: an optional custom name to override the provided function name. this might be useful for
        example if the same function is used in several converters
        :param is_able_to_convert_func: an optional function taking a desired object type as an input and outputting a
        boolean. It will be called in 'is_able_to_convert'. This allows implementors to reject some conversions even if
        they are compliant with their declared 'to_type'. Implementors should handle a 'None' value as a joker
        :param can_chain: a boolean (default True) indicating if other converters can be appended at the end of this
        converter to create a chain. Dont change this except if it really can never make sense.
        :param function_args: kwargs that will be passed to the function at every call
        :param unpack_options: if False, the full options dictionary will be passed to the conversion method, instead of
        the unpacked options for this conversion function id only.
        :param option_hints: an optional method returning a string containing the options descriptions
        """
        super(ConverterFunction, self).__init__(from_type, to_type, is_able_to_convert_func, can_chain)

        # the method
        check_var(conversion_method, var_types=Callable, var_name='conversion_method')
        self.conversion_method = conversion_method

        # custom name
        check_var(custom_name, var_types=str, var_name='custom_name', enforce_not_none=False)
        self.custom_name = custom_name

        # remember the static args values
        check_var(function_args, var_types=dict, var_name='function_args', enforce_not_none=False)
        self.function_args = function_args

        # -- unpack_options
        check_var(unpack_options, var_types=bool, var_name='unpack_options')
        self.unpack_options = unpack_options

        # -- option hints
        check_var(option_hints, var_types=Callable, var_name='option_hints', enforce_not_none=False)
        self._option_hints_func = option_hints

    def __str__(self):
        if self.custom_name is None:
            if self.function_args is None:
                return '<' + self.conversion_method.__name__ + '>'
            else:
                return '<' + self.conversion_method.__name__ + '(' + str(self.function_args) + ')>'
        else:
            return '<' + self.custom_name + '>'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def get_id_for_options(self):
        return self.custom_name or self.conversion_method.__name__

    def options_hints(self):
        """
        Returns a string representing the options available for this converter
        :return:
        """
        return self.get_id_for_options() + ': ' \
               + 'No declared option' if self._option_hints_func is None else self._option_hints_func()

    def _convert(self, desired_type: Type[T], source_obj: S, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Delegates to the user-provided method. Passes the appropriate part of the options according to the
        function name.

        :param desired_type:
        :param source_obj:
        :param logger:
        :param options:
        :return:
        """
        try:
            if self.unpack_options:
                opts = self.get_applicable_options(options)
                if self.function_args is not None:
                    return self.conversion_method(desired_type, source_obj, logger, **self.function_args, **opts)
                else:
                    return self.conversion_method(desired_type, source_obj, logger, **opts)
            else:
                if self.function_args is not None:
                    return self.conversion_method(desired_type, source_obj, logger, options, **self.function_args)
                else:
                    return self.conversion_method(desired_type, source_obj, logger, options)

        except TypeError as e:
            raise CaughtTypeError.create(self.conversion_method, e)


class ConversionChain(Converter[S, T]):
    """
    Represents a converter made of a list of converters chained with each other. A conversion chain has a 'strict' mode
    defined at construction time, defining if chaining will be allowed in strict mode (output type = input type)
    or in non-strict mode (output type is subclass of input type)
    """

    def __init__(self, initial_converters: List[Converter], strict_chaining: bool):
        """
        Constructor from a list of converters. An initial list of at least one should be provided. A conversion chain
        has a 'strict' mode defined at construction time, defining if chaining will be allowed in strict mode
        (output type = input type) or in non-strict mode (output type is subclass of input type)

        :param initial_converters: the initial list of converters
        :param strict_chaining: this is to indicate how chaining should be checked (exact type match or non-strict
        (subclasses).
        """
        # --init with the first converter of the list
        check_var(initial_converters, var_types=list, var_name='initial_converters', min_len=1)
        super(ConversionChain, self).__init__(initial_converters[0].from_type, initial_converters[0].to_type)

        #-- store the 'strict mode' status
        check_var(strict_chaining, var_types=bool, var_name='strict')
        self.strict = strict_chaining

        # -- then add the others
        self._converters_list = [initial_converters[0]]
        if len(initial_converters) > 1:
            self.add_conversion_steps(initial_converters[1:], inplace=True)

    def is_able_to_convert_detailed(self, strict: bool, from_type: Type[Any], to_type: Type[Any]):
        """
        Overrides the parent method to delegate left check to the first (left) converter of the chain and right check
        to the last (right) converter of the chain. This includes custom checking if they have any...
        see Converter.is_able_to_convert for details

        :param strict:
        :param from_type:
        :param to_type:
        :return:
        """
        # check if first and last converters are happy
        if not self._converters_list[0].is_able_to_convert(strict, from_type=from_type, to_type=JOKER):
            return False, None, None
        elif not self._converters_list[-1].is_able_to_convert(strict, from_type=JOKER, to_type=to_type):
            return False, None, None
        else:
            # behave as usual. This is probably useless but lets be sure.
            return super(ConversionChain, self).is_able_to_convert_detailed(strict, from_type, to_type)

    def __getattr__(self, item):
        # Redirect anything that is not implemented here to the base parser.
        # this is called only if the attribute was not found the usual way

        # easy version of the dynamic proxy just to save time :)
        # see http://code.activestate.com/recipes/496741-object-proxying/ for "the answer"
        bp = object.__getattribute__(self, '_base_parser')
        if hasattr(bp, item):
            return getattr(bp, item)
        else:
            raise AttributeError('\'' + self.__class__.__name__ + '\' object has no attribute \'' + item + '\'')

    def __str__(self):
        return '$' + str(self._converters_list[0]) + (' ' if len(self._converters_list) > 1 else '') + \
               ' '.join(['-> ' + str(converter) for converter in self._converters_list[1:]]) + '$'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def __copy__(self):
        copy_list = copy(self._converters_list)
        return ConversionChain(copy_list, strict_chaining=self.strict)

    def __deepcopy__(self, memo):
        copy_list = deepcopy(self._converters_list, memo=memo)
        return ConversionChain(copy_list, strict_chaining=self.strict)

    def __len__(self):
        """
        A method returning the chain size, that may be used for example to sort a list of candidate conversion chains
        :return: the chain size
        """
        return len(self._converters_list)

    def remove_first(self, inplace: bool = False):
        """
        Utility method to remove the first converter of this chain. If inplace is True, this object is modified and
        None is returned. Otherwise, a copy is returned

        :param inplace: boolean indicating whether to modify this object (True) or return a copy (False)
        :return: None or a copy with the first converter removed
        """
        if len(self._converters_list) > 1:
            if inplace:
                self._converters_list = self._converters_list[1:]
                # update the current source type
                self.from_type = self._converters_list[0].from_type
                return
            else:
                new = copy(self)
                new._converters_list = new._converters_list[1:]
                # update the current source type
                new.from_type = new._converters_list[0].from_type
                return new
        else:
            raise ValueError('cant remove first: would make it empty!')

    def add_conversion_steps(self, converters: List[Converter], inplace: bool = False):
        """
        Utility method to add converters to this chain. If inplace is True, this object is modified and
        None is returned. Otherwise, a copy is returned

        :param converters: the list of converters to add
        :param inplace: boolean indicating whether to modify this object (True) or return a copy (False)
        :return: None or a copy with the converters added
        """
        check_var(converters, var_types=list, min_len=1)
        if inplace:
            for converter in converters:
                self.add_conversion_step(converter, inplace=True)
        else:
            new = copy(self)
            new.add_conversion_steps(converters, inplace=True)
            return new

    def add_conversion_step(self, converter: Converter[S, T], inplace: bool = False):
        """
        Utility method to add a converter to this chain. If inplace is True, this object is modified and
        None is returned. Otherwise, a copy is returned

        :param converter: the converter to add
        :param inplace: boolean indicating whether to modify this object (True) or return a copy (False)
        :return: None or a copy with the converter added
        """
        # it the current chain is generic, raise an error
        if self.is_generic() and converter.is_generic():
            raise ValueError('Cannot chain this generic converter chain to the provided converter : it is generic too!')

        # if the current chain is able to transform its input into a valid input for the new converter
        elif converter.can_be_appended_to(self, self.strict):
            if inplace:
                self._converters_list.append(converter)
                # update the current destination type
                self.to_type = converter.to_type
                return
            else:
                new = copy(self)
                new._converters_list.append(converter)
                # update the current destination type
                new.to_type = converter.to_type
                return new
        else:
            raise TypeError('Cannnot register a converter on this conversion chain : source type \'' +
                            get_pretty_type_str(converter.from_type)
                            + '\' is not compliant with current destination type of the chain : \'' +
                            get_pretty_type_str(self.to_type) + ' (this chain performs '
                            + ('' if self.strict else 'non-') + 'strict mode matching)')

    def insert_conversion_steps_at_beginning(self, converters: List[Converter], inplace: bool = False):
        """
        Utility method to insert converters at the beginning ofthis chain. If inplace is True, this object is modified
        and  None is returned. Otherwise, a copy is returned

        :param converters: the list of converters to insert
        :param inplace: boolean indicating whether to modify this object (True) or return a copy (False)
        :return: None or a copy with the converters added
        """
        if inplace:
            for converter in reversed(converters):
                self.insert_conversion_step_at_beginning(converter, inplace=True)
            return
        else:
            new = copy(self)
            for converter in reversed(converters):
                # do inplace since it is a copy
                new.insert_conversion_step_at_beginning(converter, inplace=True)
            return new

    def insert_conversion_step_at_beginning(self, converter: Converter[S, T], inplace: bool = False):
        """
        Utility method to insert a converter at the beginning of this chain. If inplace is True, this object is modified
         and None is returned. Otherwise, a copy is returned

        :param converter: the converter to add
        :param inplace: boolean indicating whether to modify this object (True) or return a copy (False)
        :return: None or a copy with the converter added
        """
        # it the added converter is generic, raise an error
        if converter.is_generic() and self.is_generic():
            raise ValueError('Cannot add this converter at the beginning of this chain : it is already generic !')

        elif self.can_be_appended_to(converter, self.strict):
            if inplace:
                self._converters_list.insert(0, converter)
                # update the current source type
                self.from_type = converter.from_type
                return
            else:
                new = copy(self)
                new._converters_list.insert(0, converter)
                # update the current destination type
                new.from_type = converter.from_type
                return new
        else:
            raise TypeError('Cannnot register a converter on this conversion chain : source type \'' +
                            get_pretty_type_str(converter.from_type)
                            + '\' is not compliant with current destination type of the chain : \'' +
                            get_pretty_type_str(self.to_type) + ' (this chain performs '
                            + ('' if self.strict else 'non-') + 'strict mode matching)')

    def options_hints(self):
        """
        Returns a string representing the options available for this converter chain : it concatenates all options
        :return:
        """
        return '\n'.join([converter.options_hints() for converter in self._converters_list]) + '\n'

    def _convert(self, desired_type: Type[T], obj: S, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Apply the converters of the chain in order to produce the desired result. Only the last converter will see the
        'desired type', the others will be asked to produce their declared to_type.

        :param desired_type:
        :param obj:
        :param logger:
        :param options:
        :return:
        """
        for converter in self._converters_list[:-1]:
            # convert into each converters destination type
            obj = converter.convert(converter.to_type, obj, logger, options)

        # the last converter in the chain should convert to desired type
        return self._converters_list[-1].convert(desired_type, obj, logger, options)

    @staticmethod
    def are_worth_chaining(first_converter: Converter, second_converter: Converter) -> bool:
        """
        This is a generalization of Converter.are_worth_chaining(), to support ConversionChains.

        :param first_converter:
        :param second_converter:
        :return:
        """
        if isinstance(first_converter, ConversionChain):
            if isinstance(second_converter, ConversionChain):
                # BOTH are chains
                for sec_conv in second_converter._converters_list:
                    for fir_conv in first_converter._converters_list:
                        if not Converter.are_worth_chaining(fir_conv, sec_conv):
                            return False
            else:
                for fir_conv in first_converter._converters_list:
                    if not Converter.are_worth_chaining(fir_conv, second_converter):
                        return False
        else:
            if isinstance(second_converter, ConversionChain):
                for sec_conv in second_converter._converters_list:
                    if not Converter.are_worth_chaining(first_converter, sec_conv):
                        return False
            else:
                # Neither is a chain
                if not Converter.are_worth_chaining(first_converter, second_converter):
                    return False

        # finally return True if nothing proved otherwise
        return True

    @staticmethod
    def chain(first_converter, second_converter, strict: bool):
        """
        Utility method to chain two converters. If any of them is already a ConversionChain, this method "unpacks" it
        first. Note: the created conversion chain is created with the provided 'strict' flag, that may be different
        from the ones of the converters (if compliant). For example you may chain a 'strict' chain with a 'non-strict'
        chain, to produce a 'non-strict' chain.

        :param first_converter:
        :param second_converter:
        :param strict:
        :return:
        """
        if isinstance(first_converter, ConversionChain):
            if isinstance(second_converter, ConversionChain):
                # BOTH are chains
                if (first_converter.strict == strict) and (second_converter.strict == strict):
                    return first_converter.add_conversion_steps(second_converter._converters_list)
                else:
                    if not strict:
                        # create a non-strict chain
                        return ConversionChain(initial_converters=first_converter._converters_list,
                                               strict_chaining=False) \
                            .add_conversion_steps(second_converter._converters_list)
                    else:
                        raise ValueError('Trying to chain conversion chains with different strict modes than expected')

            else:
                # FIRST is a chain
                if strict == first_converter.strict:
                    return first_converter.add_conversion_step(second_converter)
                else:
                    if not strict:
                        # create a non-strict chain
                        return ConversionChain(initial_converters=[second_converter], strict_chaining=False) \
                            .insert_conversion_steps_at_beginning(first_converter._converters_list)
                    else:
                        raise ValueError('Trying to chain after a conversion chain that has different strict mode than '
                                         'expected')

        else:
            if isinstance(second_converter, ConversionChain):
                # SECOND is a chain
                if strict == second_converter.strict:
                    return second_converter.insert_conversion_step_at_beginning(first_converter)
                else:
                    if not strict:
                        # create a non-strict chain
                        return ConversionChain(initial_converters=[first_converter], strict_chaining=False) \
                            .add_conversion_steps(second_converter._converters_list)
                    else:
                        raise ValueError(
                            'Trying to chain before a conversion chain that has different strict mode than '
                            'expected')
            else:
                # Neither is a chain
                return ConversionChain([first_converter, second_converter], strict)
