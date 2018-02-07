from abc import abstractmethod
from logging import Logger
from typing import TypeVar, Generic, Type, Callable, Dict, Any, Set, Tuple, List

from parsyfiles.global_config import GLOBAL_CONFIG
from parsyfiles.converting_core import get_validated_types, S, Converter, get_options_for_id, is_any_type, \
    is_any_type_set, JOKER
from parsyfiles.filesystem_mapping import EXT_SEPARATOR, MULTIFILE_EXT, PersistedObject
from parsyfiles.type_inspection_tools import get_pretty_type_str, robust_isinstance, resolve_union_and_typevar
from parsyfiles.var_checker import check_var

T = TypeVar('T')  # Can be anything - used for all other objects


def check_extensions(extensions: Set[str], allow_multifile: bool = False):
    """
    Utility method to check that all extensions in the provided set are valid

    :param extensions:
    :param allow_multifile:
    :return:
    """
    check_var(extensions, var_types=set, var_name='extensions')

    # -- check them one by one
    for ext in extensions:
        check_extension(ext, allow_multifile=allow_multifile)


def check_extension(extension: str, allow_multifile: bool = False):
    """
    Utility method to check that the provided extension is valid. Extension should either be MULTIFILE_EXT
    (='multifile') or start with EXT_SEPARATOR (='.') and contain only one occurence of EXT_SEPARATOR

    :param extension:
    :param allow_multifile:
    :return:
    """
    check_var(extension, var_types=str, var_name='extension')

    # Extension should either be 'multifile' or start with EXT_SEPARATOR and contain only one EXT_SEPARATOR
    if (extension.startswith(EXT_SEPARATOR) and extension.count(EXT_SEPARATOR) == 1) \
            or (allow_multifile and extension is MULTIFILE_EXT):
        # ok
        pass
    else:
        raise ValueError('\'extension\' should start with \'' + EXT_SEPARATOR + '\' and contain not other '
                         'occurrence of \'' + EXT_SEPARATOR + '\'' + (', or be equal to \'' + MULTIFILE_EXT + '\' (for '
                         'multifile object parsing)' if allow_multifile else ''))


class _BaseParserDeclarationForRegistries(object):
    """
    Represents the base API to declare a parser in Parser registries, in order to determine which parsers are available
    and what are their capabilities : supported object types and supported file extensions.

    It is possible to declare that a parser is able to parse any type (typically, a pickle parser). It is also possible
    to declare a custom function telling if a specific object type is supported, in order to accept most types but not
    all.

    Since this class does not integrate the methods to actually create parsing plans and perform the parsing step, it
    should not be called, nor extended by users - please rather extend AnyParser or any of its subclasses.
    """

    def __init__(self, supported_types: Set[Type], supported_exts: Set[str], can_chain: bool = True,
                 is_able_to_parse_func: Callable[[bool, Type[Any]], bool] = None):
        """
        Constructor for a parser declaring support for possibly both singlefile and multifile, with a mandatory list of
        supported object types.

        It is possible to declare that a parser is able to parse any type (typically, a pickle parser), by using
        supported_types={Any} or {object} or {AnyObject}. It is also possible to declare a custom function
        'is_able_to_parse_func' telling if a specific object type is supported, in order to accept most types but not
        all.

        Note: users wishing to only implement singlefile OR multifile should rather use or extend SingleFileParser or
        MultiFileParser classes.

        :param supported_types: a set of supported object types that may be parsed. To declare that a parser is able to
        parse any type this should be {AnyObject} ({object} ans {Any} is allowed but will be automatically replaced
        with {AnyObject}).
        :param supported_exts: a set of supported file extensions that may be parsed
        :param can_chain: a boolean (default True) indicating if converters can be appended at the end of this
        parser to create a chain. Dont change this except if it really can never make sense.
        :param is_able_to_parse_func: an optional custom function to allow parsers to reject some types. This function
        signature should be my_func(strict_mode, desired_type) -> bool
        """
        # -- check types
        self.supported_types = get_validated_types(supported_types, 'supported_types')

        # -- check extensions
        check_extensions(supported_exts, allow_multifile=True)
        self.supported_exts = supported_exts

        # -- check can_chain
        check_var(can_chain, var_types=bool, var_name='can_chain')
        self.can_chain = can_chain

        # -- check is_able_to_parse_func
        check_var(is_able_to_parse_func, var_types=Callable, var_name='is_able_to_parse_func', enforce_not_none=False)
        self.is_able_to_parse_func = is_able_to_parse_func

    def __str__(self):
        return 'Parser for ' + str([get_pretty_type_str(typ) for typ in self.supported_types]) \
               + ' for extensions ' + str(self.supported_exts)

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version that will be offered in
        # str()
        return self.__str__()

    def __len__(self):
        # as opposed to parsing chains, a parser has size 1
        return 1

    def is_generic(self):
        return is_any_type_set(self.supported_types)

    def is_able_to_parse(self, desired_type: Type[Any], desired_ext: str, strict: bool) -> bool:
        return self.is_able_to_parse_detailed(desired_type=desired_type, desired_ext=desired_ext, strict=strict)[0]

    def is_able_to_parse_detailed(self, desired_type: Type[Any], desired_ext: str, strict: bool) -> Tuple[bool, bool]:
        """
        Utility method to check if a parser is able to parse a given type, either in
        * strict mode (desired_type must be one of the supported ones, or the parser should be generic)
        * inference mode (non-strict) : desired_type may be a parent class of one the parser is able to produce

        :param desired_type: the type of the object that should be parsed,
        :param desired_ext: the file extension that should be parsed
        :param strict: a boolean indicating whether to evaluate in strict mode or not
        :return: a first boolean indicating if there was a match, and a second boolean indicating if that match was
        strict (None if no match)
        """

        # (1) first handle the easy joker+joker case
        if desired_ext is JOKER and desired_type is JOKER:
            return True, None

        # (2) if ext is not a joker we can quickly check if it is supported
        if desired_ext is not JOKER:
            check_var(desired_ext, var_types=str, var_name='desired_ext')
            if desired_ext not in self.supported_exts:
                # ** no match on extension - no need to go further
                return False, None

            # (3) if type=joker and ext is supported => easy
            if desired_type is JOKER:
                # ** only extension match is required - ok.
                return True, None

        # (4) at this point, ext is JOKER OR supported and type is not JOKER. Check type match
        check_var(desired_type, var_types=type, var_name='desired_type_of_output')
        check_var(strict, var_types=bool, var_name='strict')

        # -- first call custom checker if provided
        if self.is_able_to_parse_func is not None and not self.is_able_to_parse_func(strict, desired_type):
            return False, None

        # -- strict match : either the parser is able to parse Anything, or the type is in the list of supported types
        if self.is_generic() or (desired_type in self.supported_types):
            return True, True  # exact match

        # -- non-strict match : if the parser is able to parse a subclass of the desired type, it is ok
        elif (not strict) \
                and any(issubclass(supported, desired_type) for supported in self.supported_types):
            return True, False  # approx match

        # -- no match at all
        else:
            return False, None  # no match

    def supports_singlefile(self) -> bool:
        """
        Returns True if the parser is able to read singlefiles, False otherwise

        :return: True if the parser is able to read singlefiles, False otherwise
        """
        return (len(self.supported_exts) > 1) or (MULTIFILE_EXT not in self.supported_exts)

    def supports_multifile(self) -> bool:
        """
        Returns True if the parser is able to read multifiles, False otherwise

        :return: True if the parser is able to read multifiles, False otherwise
        """
        return MULTIFILE_EXT in self.supported_exts

    @staticmethod
    def are_worth_chaining(parser, to_type: Type[S], converter: Converter[S, T]) -> bool:
        """
        Utility method to check if it makes sense to chain this parser with the given destination type, and the given
        converter to create a parsing chain. Returns True if it brings value to chain them.

        To bring value,
        * the converter's output should not be a parent class of the parser's output. Otherwise
        the chain does not even make any progress :)
        * The parser has to allow chaining (with converter.can_chain=True)

        :param parser:
        :param to_type:
        :param converter:
        :return:
        """
        if not parser.can_chain:
            # The base parser prevents chaining
            return False

        elif not is_any_type(to_type) and is_any_type(converter.to_type):
            # we gain the capability to generate any type. So it is interesting.
            return True

        elif issubclass(to_type, converter.to_type):
            # Not interesting : the outcome of the chain would be not better than one of the parser alone
            return False

        # Note: we dont say that chaining a generic parser with a converter is useless. Indeed it might unlock some
        # capabilities for the user (new file extensions, etc.) that would not be available with the generic parser
        # targetting to_type alone. For example parsing object A from its constructor then converting A to B might
        # sometimes be interesting, rather than parsing B from its constructor

        else:
            # Interesting
            return True


class ParsingException(Exception):
    """
    Exception raised whenever parsing fails.
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(ParsingException, self).__init__(contents)

    @staticmethod
    def create_for_caught_error(parser: _BaseParserDeclarationForRegistries, desired_type: Type[T],
                                obj: PersistedObject, caught: Exception, options: Dict[str, Dict[str, Any]]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param desired_type:
        :param obj:
        :param caught:
        :param options:
        :return:
        """
        try:
            typ = get_pretty_type_str(desired_type)
        except:
            typ = str(desired_type)

        return ParsingException('Error while parsing ' + str(obj) + ' as a ' + typ + ' with parser \''
                                + str(parser) + '\' using options=(' + str(options) + ') : caught \n  '
                                + str(caught.__class__.__name__) + ' : ' + str(caught))\
            .with_traceback(caught.__traceback__) # 'from e' was hiding the inner traceback. This is much better for debug

    @staticmethod
    def create_for_wrong_result_type(parser: _BaseParserDeclarationForRegistries, desired_type: Type[T],
                                     obj: PersistedObject, result: T, options: Dict[str, Dict[str, Any]]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param desired_type:
        :param obj:
        :param result:
        :param options:
        :return:
        """
        return ParsingException('Error while parsing ' + str(obj) + ' as a ' + str(desired_type) + ' with parser \''
                                + str(parser) + '\' using options=(' + str(options) + ') : \n      parser returned '
                                + str(result) + ' of type ' + str(type(result))
                                + ' which is not an instance of ' + str(desired_type))

    @staticmethod
    def create_for_wrong_result_type_multifile(desired_type: Type[T], parser: _BaseParserDeclarationForRegistries,
                                               result: T, multifile_location: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param desired_type:
        :param parser:
        :param result:
        :param multifile_location:
        :return:
        """
        return ParsingException('Error while parsing multifile at location \'' + multifile_location + '\' with parser'
                                ' \'' + str(parser) + '\' : parser returned ' + str(result) + ' of type ' +
                                str(type(result)) + ' while it was supposed to parse instances of ' +
                                str(desired_type))


def get_parsing_plan_log_str(obj_on_fs_to_parse, desired_type, log_only_last: bool, parser):
    """
    Utility method used by several classes to log a message indicating that a given file object is planned to be parsed
    to the given object type with the given parser. It is in particular used in str(ParsingPlan), but not only.

    :param obj_on_fs_to_parse:
    :param desired_type:
    :param log_only_last: a flag to only log the last part of the file path (default False). Note that this can be
    overriden by a global configuration 'full_paths_in_logs'
    :param parser:
    :return:
    """
    loc = obj_on_fs_to_parse.get_pretty_location(blank_parent_part=(log_only_last
                                                                    and not GLOBAL_CONFIG.full_paths_in_logs),
                                                 compact_file_ext=True)
    return '{loc} -> {type} ------- using {parser}'.format(loc=loc, type=get_pretty_type_str(desired_type),
                                                           parser=str(parser))


class ParsingPlan(Generic[T], PersistedObject):
    """
    Represents the association between a parser and a persisted file object to parse a given type.
    Once created (typically by the parser), a parsing plan element may be 'execute'd to perform the parsing action.

    ParsingPlan instances should not be created directly by users, but through implementations of Parser class.

    This class can be typed with PEP484 (e.g. ParsingPlan[int], etc.)
    """

    def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject,
                 parser: _BaseParserDeclarationForRegistries, accept_union_types: bool = False):
        """
        Creates a parsing plan, from an object's type, an object's files, and a parser.

        :param object_type:
        :param obj_on_filesystem:
        :param parser:
        :param accept_union_types: a boolean to accept when object_type is a Union or a TypeVar with union constraints
        """
        # DON'T CALL SUPER INIT, since we wrap/proxy an existing object

        # check and apply defaults
        # -- object_type
        t = resolve_union_and_typevar(object_type)
        if len(t) == 1:
            check_var(t[0], var_types=type, var_name='object_type')
            self.obj_type = t[0]
        elif not accept_union_types:
            raise ValueError('Parsing Plan can not be created for Union type {}'.format(object_type))
        else:
            self.obj_type = object_type
        # -- obj_files
        check_var(obj_on_filesystem, var_types=PersistedObject, var_name='obj_on_filesystem')
        self.obj_on_fs_to_parse = obj_on_filesystem
        # -- parser
        check_var(parser, var_types=_BaseParserDeclarationForRegistries, var_name='parser')
        self.parser = parser

    def __getattr__(self, item):
        # Redirect anything that is not implemented here to the inner object
        # this is called only if the attribute was not found the usual way

        # easy version of the dynamic proxy just to save time :)
        # see http://code.activestate.com/recipes/496741-object-proxying/ for "the answer"
        objfs = object.__getattribute__(self, 'obj_on_fs_to_parse')
        if hasattr(objfs, item):
            return getattr(objfs, item)
        else:
            raise AttributeError('\'' + self.__class__.__name__ + '\' object has no attribute \'' + item + '\'')

    def get_singlefile_path(self):
        """
        Delegates to the inner PersistedObject
        We have to implement this explicitly because it is an abstract method in the parent class
        :return:
        """
        return self.obj_on_fs_to_parse.get_singlefile_path()

    def get_singlefile_encoding(self):
        """
        Delegates to the inner PersistedObject
        We have to implement this explicitly because it is an abstract method in the parent class
        :return:
        """
        return self.obj_on_fs_to_parse.get_singlefile_encoding()

    def get_multifile_children(self) -> Dict[str, Any]:
        """
        Delegates to the inner PersistedObject
        We have to implement this explicitly because it is an abstract method in the parent class
        :return:
        """
        return self.obj_on_fs_to_parse.get_multifile_children()

    def __str__(self):
        return get_parsing_plan_log_str(self.obj_on_fs_to_parse, self.obj_type, False, self.parser)

    def get_pretty_type_str(self) -> str:
        return get_pretty_type_str(self.obj_type)

    def execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Called to parse the object as described in this parsing plan, using the provided arguments for the parser.
        * Exceptions are caught and wrapped into ParsingException
        * If result does not match expected type, an error is thrown

        :param logger: the logger to use during parsing (optional: None is supported)
        :param options: a dictionary of option sets. Each option set is identified with an id in the dictionary.
        :return:
        """
        try:
            res = self._execute(logger, options)
        except Exception as e:
            raise ParsingException.create_for_caught_error(self.parser, self.obj_type, self.obj_on_fs_to_parse, e,
                                                           options)

        # Check that the returned parsed object has the correct type
        if res is not None:
            if robust_isinstance(res, self.obj_type):
                return res

        # wrong type : error
        raise ParsingException.create_for_wrong_result_type(self.parser, self.obj_type, self.obj_on_fs_to_parse,
                                                            res, options)

    @abstractmethod
    def _execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementing classes should perform the parsing here, possibly using custom methods of self.parser.

        :param logger:
        :param options:
        :return:
        """
        pass


class Parser(_BaseParserDeclarationForRegistries):
    """
    Represents the API that any parser should implement to be usable.

    A parser is basically
    * (1) a declaration (= a _BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor in _BaseParserDeclarationForRegistries for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.

    Important note: as this class shows, it is not mandatory for a Parser to implement any actual parsing methods,
    it is up to the ParsingPlan implementation. The single entry-point method called by the user to parse something is
    ParsingPlan.execute(...). It may seem counter-intuitive and harder to extend, but it allows users to debug
    recursive parsing plans a lot more easily.

    This class is meant for parser *usage*. In order to *implement* parsers, users should not extend this class but
    rather extend 'AnyParser' or any of its subclasses such as 'SingleFileParser', 'MultiFileParser', or
    'SingleFileParsingFunction'.
    """

    # TODO split 'parsingplan factory' concept from 'single/multi file parser' > Distinct interfaces ?
    # That would make the rootparser clearer

    def get_id_for_options(self):
        """
        Default implementation : the id to use in the options is the class name
        :return:
        """
        return self.__class__.__name__

    def options_hints(self):
        """
        Returns a string representing the options available for this parser
        :return:
        """
        return self.get_id_for_options() + ': No declared option'

    def _get_applicable_options(self, options: Dict[str, Dict[str, Any]]):
        """
        Returns the options that are applicable to this particular parser, from the full map of options.
        It first uses 'get_id_for_options()' to know the id of this parser, and then simply extracts the contents of
        the options corresponding to this id, or returns an empty dict().

        :param options: a dictionary parser_id > options
        :return:
        """
        return get_options_for_id(options, self.get_id_for_options())

    @abstractmethod
    def create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                            options: Dict[str, Dict[str, Any]]) -> ParsingPlan[T]:
        """
        Creates a parsing plan to parse the given filesystem object into the given desired_type.
        Implementing classes may wish to support additional parameters.

        :param desired_type: the type of object that should be created as the output of parsing plan execution.
        :param filesystem_object: the persisted object that should be parsed
        :param logger: an optional logger to log all parsing plan creation and execution information
        :param options: a dictionary additional implementation-specific parameters (one dict per parser id).
        Implementing classes may use 'self._get_applicable_options()' to get the options that are of interest for this
        parser.
        :return:
        """
        pass