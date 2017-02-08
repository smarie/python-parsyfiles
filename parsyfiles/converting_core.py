from abc import abstractmethod, ABCMeta
from copy import copy, deepcopy
from logging import Logger
from typing import Generic, TypeVar, Type, Any, Set, Tuple, Callable, List, Dict

from parsyfiles.type_inspection_tools import get_pretty_type_str
from parsyfiles.var_checker import check_var


def get_validated_types(object_types: Set[Type], set_name: str) -> Set[Type]:
    """
    Utility to validate a set of types :
    * None is not allowed as a whole or within the set,
    * object is converted into Any
    * if Any is in the set, it must be the only element

    :param object_types: the set of types to validate
    :param set_name: a name used in exceptions if any
    :return: the fixed set of types
    """
    check_var(object_types, var_types=set, var_name=set_name)
    res = {get_validated_type(typ, set_name + '[x]') for typ in object_types}
    if Any in res and len(res) > 1:
        raise ValueError('The set of types contains \'object\'/\'Any\', so no other type must be present in the set')
    else:
        return res


def get_validated_type(object_type: Type[Any], name: str) -> Type[Any]:
    """
    Utility to validate a type :
    * None is not allowed,
    * 'object' is converted into 'Any'

    :param object_type: the type to validate
    :param name: a name used in exceptions if any
    :return: the fixed type
    """
    check_var(object_type, var_types=type, var_name=name)
    if object_type is object:
        return Any
    else:
        return object_type


S = TypeVar('S')  # Can be anything - used for "source object"
T = TypeVar('T')  # Can be anything - used for all other objects


class Converter(Generic[S, T], metaclass=ABCMeta):
    """
    Parent class of all converters able to convert an object of a given source type to another, of a destination type.
    A destination type of 'Any' is allowed. In that case the converter is a 'generic' converter. A custom function
    may be provided at construction time, to enable converters to reject some conversions, even if their dest type is
    'Any'.
    """

    def __init__(self, from_type: Type[S], to_type: Type[T],
                 is_able_to_convert_func: Callable[[bool, Type[S], Type[T]], bool] = None):
        """
        Constructor for a converter from one source type (from_type) to one destination type (to_type).
        from_type may be any type except Any or object. to_type may be Any.

        A custom function may be provided to enable converters to reject some conversions, even if the provided type
        is a subclass of their source type and the expected type is a parent class of their dest type (or their dest
        type is 'Any').

        :param from_type: the source type
        :param to_type: the destination type, or Any (for generic converters)
        :param is_able_to_convert_func: an optional function taking a desired object type as an input and outputting a
        boolean. It will be called in 'is_able_to_convert'. This allows implementors to reject some conversions even if
        they are compliant with their declared 'to_type'.
        """
        # --from type
        self.from_type = get_validated_type(from_type, 'from_type')
        if from_type is Any:
            raise ValueError('A converter\'s \'from_type\' cannot be anything at the moment, it would be a mess.')

        # --to type
        self.to_type = get_validated_type(to_type, 'to_type')

        # --conversion function
        check_var(is_able_to_convert_func, var_types=Callable, var_name='is_able_to_convert_func',
                  enforce_not_none=False)
        self.is_able_to_convert_func = is_able_to_convert_func

    def __len__(self):
        # as opposed to conversion chains.. for use in sorting methods
        return 1

    def is_generic(self):
        """
        A converter is generic if its destination type is 'Any'.
        :return:
        """
        return self.to_type is Any

    def __str__(self):
        return '<Converter from ' + get_pretty_type_str(self.from_type) + ' to ' + get_pretty_type_str(self.to_type) \
               + '>'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def is_able_to_convert(self, strict: bool, from_type: Type[Any], to_type: Type[Any]) \
            -> Tuple[bool, bool, bool]:
        """
        Utility method to check if a parser is able to parse a given type, either in
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
        check_var(strict, var_types=bool, var_name='strict')

        # -- first call custom checker if provided
        if self.is_able_to_convert_func is not None and not self.is_able_to_convert_func(strict, from_type, to_type):
            return False, None, None

        # -- check from type strict
        if from_type is None or from_type is self.from_type:
            # -- check to type strict
            if to_type is None or self.is_generic() or (to_type is self.to_type):
                return True, True, True  # exact match
            # -- check to type non-strict
            elif (not strict) and issubclass(self.to_type, to_type):
                return True, True, False

        # -- check from type non-strict
        elif (not strict) and issubclass(from_type, self.from_type):
            # -- check to type strict
            if to_type is None or self.is_generic() or (to_type is self.to_type):
                return True, False, True  # exact match
            # -- check to type non-strict
            elif (not strict) and issubclass(self.to_type, to_type):
                return True, False, False

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

        :param left_converter:
        :param right_converter:
        :return:
        """
        if right_converter.to_type is Any:
            # Any is a capability to generate any type. So it is always interesting.
            return True
        elif issubclass(left_converter.from_type, right_converter.to_type) \
                or issubclass(left_converter.to_type, right_converter.to_type) \
                or issubclass(left_converter.from_type, right_converter.from_type):
            return False
        else:
            # Not interesting
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
        return self.is_able_to_convert(strict, from_type=left_converter.to_type, to_type=None)[0]

    @abstractmethod
    def convert(self, desired_type: Type[T], source_obj: S, logger: Logger, *args, **kwargs) -> T:
        """
        Implementing classes should implement this method to perform the conversion itself

        :param desired_type: the destination type of the conversion
        :param source_obj: the source object that should be converter
        :param logger: a logger to use if any is available, or None
        :param args: additional arguments. Note that this may contain options for other parsers/converters, implementing
         classes should just ignore them
        :param kwargs: additional arguments. Note that this may contain options for other parsers/converters,
        implementing classes should just ignore them
        :return:
        """
        pass


class ConverterFunction(Converter[S, T]):
    """
    Helper class to create a Converter from a user-provided function. See Converter class for details.
    """
    def __init__(self, from_type: Type[S], to_type: Type[T],
                 conversion_method: Callable[[Type[T], S, Logger, List, Dict], T],
                 custom_name: str = None, is_able_to_convert_func: Callable[[Type[T]], bool] = None):
        """
        Constructor with a conversion method. All calls to self.convert() will be delegated to this method. An optional
        name may be provided to override the provided conversion method's name. this might be useful for example if the
        same function is used in several converters.

        See Converter class for details on other arguments.

        :param from_type: the source type
        :param to_type: the destination type, or Any (for generic converters)
        :param conversion_method: the function the conversion step will be delegated to
        :param custom_name: an optional custom name to override the provided function name. this might be useful for
        example if the same function is used in several converters
        :param is_able_to_convert_func: an optional function taking a desired object type as an input and outputting a
        boolean. It will be called in 'is_able_to_convert'. This allows implementors to reject some conversions even if
        they are compliant with their declared 'to_type'.
        """
        super(ConverterFunction, self).__init__(from_type, to_type, is_able_to_convert_func)
        self.conversion_method = conversion_method
        self.custom_name = custom_name

    def __str__(self):
        return '<' + (self.custom_name or self.conversion_method.__name__) + '>'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def convert(self, desired_type: Type[T], source_obj: S, logger: Logger, *args, **kwargs) -> T:
        """
        Delegates to the user-provided method
        :param desired_type:
        :param source_obj:
        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        return self.conversion_method(desired_type, source_obj, logger, *args, **kwargs)


class ConverterFunctionWithStaticArgs(ConverterFunction[S, T]):
    """
    A dedicated class of ConverterFunction converters that can receive some parameters in the constructor. These
    parameters will always be passed to the conversion function in addition to the usual parameters of convert()
    """
    def __init__(self, from_type: Type[S], to_type: Type[T], conversion_method: Callable[[S], T],
                 custom_name: str = None, is_able_to_convert_func: Callable[[Type[T]], bool] = None, *args, **kwargs):
        """
        Constructor with static *args and **kwargs (preferred) for the conversion_method.
        See ConverterFunction class for details on other arguments.

        :param from_type: the source type
        :param to_type: the destination type, or Any (for generic converters)
        :param conversion_method: the function the conversion step will be delegated to
        :param custom_name: an optional custom name to override the provided function name. this might be useful for
        example if the same function is used in several converters
        :param is_able_to_convert_func: an optional function taking a desired object type as an input and outputting a
        boolean. It will be called in 'is_able_to_convert'. This allows implementors to reject some conversions even if
        they are compliant with their declared 'to_type'.
        :param args: optional static arguments that will always be passed to the function
        :param kwargs: optional static arguments that will always be passed to the function
        """
        super(ConverterFunctionWithStaticArgs, self).__init__(from_type, to_type, conversion_method,
                                                              is_able_to_convert_func=is_able_to_convert_func,
                                                              custom_name=custom_name)
        # remember the stati args values
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        if self.custom_name is None:
            return '<' + self.conversion_method.__name__ + '(' + str(self.args) + str(self.kwargs) + ')>'
        else:
            # the goal is to entirely hide the param values here
            return '<' + self.custom_name + '>'

    def convert(self, desired_type: Type[T], source_obj: S, logger: Logger, *args, **kwargs) -> T:
        # call the super with our additional arguments
        return super(ConverterFunctionWithStaticArgs, self).convert(desired_type, source_obj, logger, *self.args,
                                                                    *args, **self.kwargs, **kwargs)


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

    def is_able_to_convert(self, strict: bool, from_type: Type[Any], to_type: Type[Any]):
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
        if not self._converters_list[0].is_able_to_convert(strict, from_type, None)[0]:
            return False, None, None
        elif not self._converters_list[-1].is_able_to_convert(strict, None, to_type)[0]:
            return False, None, None
        else:
            # behave as usual. This is probably useless if the converters dont forget to call their super() method,
            # but lets be sure.
            return super(ConversionChain, self).is_able_to_convert(strict, from_type, to_type)

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
        if self.is_generic():
            raise ValueError('Cannot chain this converter chain to something else : it is already generic !')

        # if the current chain is able to transform its input into a valid input for the new converter
        elif self.is_able_to_convert(self.strict, to_type=converter.from_type, from_type=None)[0]:
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
        if converter.is_generic():
            raise ValueError('Cannot add this converter at the beginning of this chain : it is already generic !')

        # if the current chain is able to transform its input into a valid input for the new converter
        elif converter.is_able_to_convert(self.strict, from_type=converter.from_type, to_type=None)[0]:
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

    def convert(self, desired_type: Type[T], obj: S, logger: Logger, *args, **kwargs) -> T:
        """
        Apply the converters of the chain in order to produce the desired result. Only the last converter will see the
        'desired type', the others will be asked to produce their declared to_type.

        :param desired_type:
        :param obj:
        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        for converter in self._converters_list[:-1]:
            # convert into each converters destination type
            obj = converter.convert(converter.to_type, obj, logger, *args, **kwargs)

        # the last converter in the chain should convert to desired type
        return self._converters_list[-1].convert(desired_type, obj, logger, *args, **kwargs)

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
