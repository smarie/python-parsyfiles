import threading
from abc import abstractmethod
from io import TextIOBase
from logging import Logger
from typing import TypeVar, Generic, Union, Type, Callable, Dict, Any, Set, Tuple

from parsyfiles.converting_core import get_validated_types
from parsyfiles.filesystem_mapping import EXT_SEPARATOR, MULTIFILE_EXT, PersistedObject
from parsyfiles.type_inspection_tools import get_pretty_type_str
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
    for ext in extensions:
        check_extension(ext, allow_multifile=allow_multifile)


def check_extension(extension: str, allow_multifile: bool = False):
    """
    Utility method to check that the provided extension is valid

    :param extension:
    :param allow_multifile:
    :return:
    """

    # Extension should either be 'multifile' or start with EXT_SEPARATOR and contain only one EXT_SEPARATOR
    check_var(extension, var_types=str, var_name='extension')

    if (extension.startswith(EXT_SEPARATOR) and extension.count(EXT_SEPARATOR) == 1) \
            or (allow_multifile and extension is MULTIFILE_EXT):
        # ok
        pass
    else:
        raise ValueError('\'extension\' should start with \'' + EXT_SEPARATOR + '\' and contain not other '
                         'occurence of \'' + EXT_SEPARATOR + '\'' + (', or be equal to \'' + MULTIFILE_EXT + '\' (for '
                         'multifile object parsing)' if allow_multifile else ''))

def parser_is_able_to_parse(supported_types_of_parser: Set[Type[Any]], desired_type_of_output: Type[Any],
                            supported_exts_of_parser: Set[str], desired_ext_to_parse: str, strict: bool):
    """
    Utility method to check if a parser is able to parse a given extension and a given type given its supported
    extensions and types, either in
    * strict mode (desired_type must be one of the supported ones, or supported types should be [Any]
    * inference mode (non-strict) : desired_type may be a parent class of one the parser is able to produce

    None

    :param supported_types_of_parser:
    :param desired_type_of_output:
    :param supported_exts_of_parser:
    :param desired_ext_to_parse:
    :param strict:
    :return: a first boolean indicating if there was a match, and a second boolean indicating if that match was
    strict (or None if no match)
    """

    if desired_ext_to_parse is None and desired_type_of_output is None:
        return True, None

    if desired_ext_to_parse is not None:
        check_var(desired_ext_to_parse, var_types=str, var_name='desired_ext_to_parse')
        if desired_ext_to_parse not in supported_exts_of_parser:
            # ** no match on extension - no need to go further
            return False, None

    if desired_type_of_output is None:
        # ** only extension match is required - ok.
        return True, None

    # extension matches and type is not None

    # ** check type match
    check_var(desired_type_of_output, var_types=type, var_name='desired_type_of_output')
    check_var(strict, var_types=bool, var_name='strict')

    # either the parser is able to parse Anything, or the match is exact
    if (Any in supported_types_of_parser) or (desired_type_of_output in supported_types_of_parser):
        return True, True  # exact match

    # non-strict match : if the parser is able to parse a subclass of the desired type, it is ok
    elif (not strict) \
            and any(issubclass(supported, desired_type_of_output) for supported in supported_types_of_parser):
        return True, False  # approx match

    # no match
    else:
        return False, None  # no match


class _BaseParserDeclaration(Generic[T]):
    """
    Represents the base API to declare a parser. Since this does not integrate the ability to parse or create parsing
    plans, it should not be extended by users. Please rather extend AnyParser or any of its subclasses.
    """

    def __init__(self, supported_types: Set[Type], supported_exts: Set[str] = None):
        """
        Constructor for a parser supporting both singlefile and multifile, with a mandatory list of supported object
        types (use {Any} or {object} for parsers able to parse any type).
        Note: if you wish to only implement singlefile or multifile, use SingleFileParser or MultiFileParser classes.

        :param supported_types: a list of supported object types that may be parsed, or None for parsers able to parse
        any object type
        """

        self.supported_types = get_validated_types(supported_types, 'supported_types')

        #self.supports_singlefile = True
        #self.supports_multifile = True

        supported_exts = supported_exts or []
        check_var(supported_exts, var_types=set, var_name='supported_exts')
        check_extensions(supported_exts, allow_multifile=True)
        self.supported_exts = supported_exts

    def __str__(self):
        return 'Parser for ' + str([get_pretty_type_str(typ) for typ in self.supported_types]) \
               + ' for extensions ' + str(self.supported_exts)

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version that will be offered in
        # str()
        return self.__str__()

    def is_generic(self):
        return (Any in self.supported_types)

    def is_able_to_parse(self, desired_type: Type[Any], desired_ext: str, strict: bool) -> Tuple[bool, bool]:
        """
        Utility method to check if a parser is able to parse a given type, either in
        * strict mode (desired_type must be one of the supported ones, or the parser should be generic)
        * inference mode (non-strict) : desired_type may be a parent class of one the parser is able to produce

        :param desired_type:
        :param desired_ext:
        :param strict:
        :return: a first boolean indicating if there was a match, and a second boolean indicating if that match was
        strict (or None if no match)
        """
        return parser_is_able_to_parse(self.supported_types, desired_type, self.supported_exts, desired_ext, strict)

    def supports_singlefile(self):
        return (len(self.supported_exts) > 1) or (MULTIFILE_EXT not in self.supported_exts)

    def supports_multifile(self):
        return MULTIFILE_EXT in self.supported_exts

    # REMOVED - it is clearer to use the supported_types fields directly.
    # def supports_object_type(self, type_to_parse: Type[T]) -> bool:
    #     """
    #     Method used to check if a parser supports a given object type.
    #
    #     :param type_to_parse: the type to check
    #     :return:
    #     """
    #     if self.supported_types:
    #         return type_to_parse in self.supported_types
    #     else:
    #         return True


class InvalidParserException(Exception):
    """
    Raised whenever a ParsingPlan tries to be created with a parser that is not compliant with the underlying file
    object format (multifile, singlefile)
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(InvalidParserException, self).__init__(contents)

    @staticmethod
    def create(parser: _BaseParserDeclaration[T], obj: PersistedObject = None):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param obj:
        :return:
        """
        if obj is not None:
            return InvalidParserException('Error ' + str(obj) + ' cannot be parsed using ' + str(parser) + ' since '
                                          + ' this parser does not support ' + obj.get_pretty_file_mode())
        else:
            return InvalidParserException('Error this parser is neither SingleFile nor MultiFile !')


class ParsingException(Exception):
    """
    Raised whenever parsing fails
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
    def create_for_caught_error(parser: _BaseParserDeclaration[T], desired_type: Type[T], obj: PersistedObject,
                                caught: Exception, *args, **kwargs):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param desired_type:
        :param obj:
        :param caught:
        :param args:
        :param kwargs:
        :return:
        """
        try:
            typ = get_pretty_type_str(desired_type)
        except:
            typ = str(desired_type)

        return ParsingException('Error while parsing ' + str(obj) + ' as a ' + typ + ' with parser \''
                                + str(parser) + '\' using args=(' + str(args) + ') and kwargs=(' + str(kwargs)
                                + ') : caught \n  ' + str(caught.__class__.__name__) + ' : ' + str(caught))\
            .with_traceback(caught.__traceback__) # 'from e' was hiding the inner traceback. This is much better for debug

    @staticmethod
    def create_for_wrong_result_type(parser: _BaseParserDeclaration[T], desired_type: Type[T], obj: PersistedObject,
                                     result: T, *args, **kwargs):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param desired_type:
        :param obj:
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        return ParsingException('Error while parsing ' + str(obj) + ' as a ' + str(desired_type) + ' with parser \''
                                + str(parser) + '\' using args=(' + str(args) + ') and kwargs=(' + str(kwargs)
                                + ') : parser returned ' + str(result) + ' of type ' + str(type(result))
                                + ' which is not an instance of ' + str(desired_type))

    @staticmethod
    def create_for_wrong_result_type_multifile(desired_type: Type[T], parser: _BaseParserDeclaration[T], result: T,
                                               multifile_location: str):
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


def get_parsing_plan_log_str(obj_on_fs_to_parse, desired_type, parser):
    return str(obj_on_fs_to_parse) + ' > ' + get_pretty_type_str(desired_type) + ' ------- using ' + str(parser)


class _ParsingPlanElement(Generic[T], PersistedObject):
    """
    Represents the association between a parser and a persisted object to parse a given type.
    A parsing plan element may be executed to perform the parsing action.
    """
    def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject, parser: _BaseParserDeclaration[T]):
        """
        Creates a parsing plan, from an object's type, an object's files, and a parser.

        :param object_type:
        :param obj_on_filesystem:
        :param parser:
        """
        # DONT CALL SUPER INIT, since we wrap/proxy an existing object

        # check and apply defaults
        # -- object_type
        check_var(object_type, var_types=type, var_name='object_type')
        self.obj_type = object_type
        # -- obj_files
        check_var(obj_on_filesystem, var_types=PersistedObject, var_name='obj_on_filesystem')
        self.obj_on_fs_to_parse = obj_on_filesystem
        # -- parser
        check_var(parser, var_types=_BaseParserDeclaration, var_name='parser')
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
        return self.obj_on_fs_to_parse.get_singlefile_path()

    def get_singlefile_encoding(self):
        return self.obj_on_fs_to_parse.get_singlefile_encoding()

    def get_multifile_children(self) -> Dict[str, Any]:
        return self.obj_on_fs_to_parse.get_multifile_children()

    def __str__(self):
        return get_parsing_plan_log_str(self.obj_on_fs_to_parse, self.obj_type, self.parser)

    def get_pretty_type_str(self) -> str:
        return get_pretty_type_str(self.obj_type)

    def execute(self, logger: Logger, *args, **kwargs) -> T:
        """
        Called to parse the object as described in this parsing plan, using the provided arguments for the parser.
        * Exceptions are caught and wrapped into ParsingException
        * If result does not match expected type, an error is thrown

        :param logger: the logger to use during parsing (optional: None is supported)
        :param args:
        :param kwargs:
        :return:
        """
        try:
            res = self._execute(logger, *args, **kwargs)
        except Exception as e:
            raise ParsingException.create_for_caught_error(self.parser, self.obj_type, self.obj_on_fs_to_parse,
                                                           e, *args, **kwargs)

        # Check that the returned parsed object has the correct type
        if res is not None and isinstance(res, self.obj_type):
            return res
        else:
            # wrong type : error
            raise ParsingException.create_for_wrong_result_type(self.parser, self.obj_type, self.obj_on_fs_to_parse,
                                                                res, *args, **kwargs)

    @abstractmethod
    def _execute(self, logger: Logger, *args, **kwargs) -> T:
        pass


class BaseParser(_BaseParserDeclaration[T]):
    """
    Represents a parser able to produce a parsing plan for singlefile and multifile parsing.
    Note that for multifile parsing the parsing plan is expected to have a way to get the parsing plans for each child
    element
    """
    class ParsingPlan(_ParsingPlanElement[T]):
        """
        A Parsing plan for _BaseParsers.
        When executed, it relies on the singlefile and multifile parsing methods of the BaseParser
        """

        def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject, parser: _BaseParserDeclaration[T],
                     logger: Logger):
            super(BaseParser.ParsingPlan, self).__init__(object_type, obj_on_filesystem, parser)

            # -- logger
            check_var(logger, var_types=Logger, var_name='logger', enforce_not_none=False)
            self.logger = logger

        # flag used for create_parsing_plan logs (to prevent recursive print messages)
        thrd_locals = threading.local()

        def execute(self, logger: Logger, *args, **kwargs) -> T:
            """
            Called to parse the object as described in this parsing plan, using the provided arguments for the parser.

            This method adds log messages to what the parent does.

            :param logger: the logger to use during parsing (optional: None is supported)
            :param args:
            :param kwargs:
            :return:
            """
            in_root_call = False
            if logger is not None:
                # log only for the root object, not for the children that will be created by the code below
                if not hasattr(BaseParser.ParsingPlan.thrd_locals, 'flag_exec') \
                        or BaseParser.ParsingPlan.thrd_locals.flag_exec == 0:
                    #print('Executing Parsing Plan for ' + str(self))
                    logger.info('Executing Parsing Plan for ' + str(self))
                    BaseParser.ParsingPlan.thrd_locals.flag_exec = 1
                    in_root_call = True

            # Common log message
            logger.info('Parsing ' + str(self))

            try:
                res = super(BaseParser.ParsingPlan, self).execute(logger, *args, **kwargs)
                if in_root_call:
                    #print('Completed parsing successfully')
                    logger.info('Completed parsing successfully')
                return res

            finally:
                # remove threadlocal flag if needed
                if in_root_call:
                    BaseParser.ParsingPlan.thrd_locals.flag_exec = 0

        def _execute(self, logger: Logger, *args, **kwargs) -> T:
            if isinstance(self.parser, BaseParser):
                if (not self.is_singlefile) and self.parser.supports_multifile():
                    return self.parser._parse_multifile(self.obj_type, self.obj_on_fs_to_parse,
                                                        self._get_children_parsing_plan(), logger, *args, **kwargs)

                elif self.is_singlefile and self.parser.supports_singlefile():
                    return self.parser._parse_singlefile(self.obj_type, self.get_singlefile_path(),
                                                         self.get_singlefile_encoding(), logger, *args, **kwargs)
                else:
                    raise InvalidParserException.create(self.parser, self.obj_on_fs_to_parse)
            else:
                raise TypeError('Parser attached to this ParsingPlan is not a ' + str(BaseParser))

        @abstractmethod
        def _get_children_parsing_plan(self) -> Dict[str, _ParsingPlanElement]:
            pass

    def size(self):
        # as opposed to parsing chains..
        return 1

    @abstractmethod
    def create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                            in_rootcall: bool) \
        -> ParsingPlan[T]:
        """
        Creates a parsing plan to parse the given filesystem object into the given desired_type

        :param desired_type:
        :param filesystem_object:
        :param logger:
        :return:
        """
        pass

    @abstractmethod
    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          *args, **kwargs) -> T:
        """
        Method that should be overriden by your implementing class. It will be called by
        (BaseParser.ParsingPlan).execute

        :param desired_type:
        :param file_path:
        :param encoding:
        :param args:
        :param kwargs:
        :return:
        """
        pass

        # @abstractmethod
        # def _parse(self, desired_type: Type[T], obj: PersistedObject, *args, **kwargs) -> T:
        #     """
        #     Implementing classes should implement this method to perform the parsing.
        #
        #     :param desired_type: the desired type of object that should be produced by the parser
        #     :param obj: the persisted object to parse. It may be singlefile or multifile
        #     :param args: optional arguments for the parsing method
        #     :param kwargs: optional keyword arguments for the parsing method
        #     :return:
        #     """
        #     pass

    @abstractmethod
    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, ParsingPlan],
                         logger: Logger, *args, **kwargs) -> T:
        """
        First parse all children from the parsing plan, then calls _build_object_from_parsed_children

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        # # first parse all children according to their plan
        # parsed_children = {child_name: child_plan.parse_object(logger, *args, **kwargs)
        #                    for child_name, child_plan in parsing_plan_for_children.items()}
        #
        # # finally build the resulting object
        # return self._build_object_from_parsed_children(desired_type, obj, parsed_children, logger, *args, **kwargs)
        pass


class AnyParser(BaseParser[T]):
    """
    Represents any parser. A parser may support singlefiles, multifiles, or both (default). Users wishing to extend
    only one of them should rather extend SingleFileParser or MuliFileParser.

    A set of supported object types has to be provided. Use {Any} to declare ability to parse any object type.

    This class can be typed with PEP484 if the supported object type(s) is known
    (e.g. AnyParser[Any], AnyParser[Union[str, int]], etc.)
    """

    class _RecursiveParsingPlan(BaseParser.ParsingPlan[T]):
        """
        Represents a parsing plan that is recursive : at creation time, it will query the parsing plan for all children.
        It also adds some logging to that constructor step.
        """

        def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject, parser: BaseParser[T],
                     logger: Logger):

            # -- super
            super(AnyParser._RecursiveParsingPlan, self).__init__(object_type, obj_on_filesystem, parser, logger)

            try:
                # if singlefile, nothing else to do
                if self.obj_on_fs_to_parse.is_singlefile and parser.supports_singlefile():
                    pass

                # if multifile, prepare the parsing plan for children
                elif (not self.obj_on_fs_to_parse.is_singlefile) and parser.supports_multifile():
                    if isinstance(parser, AnyParser):
                        # we have to create the parsing plan for file children and save it
                        # children = self.obj_on_fs_to_parse.get_multifile_children()
                        self._children_parsing_plan = parser._get_parsing_plan_for_multifile_children(self.obj_on_fs_to_parse,
                                                                                                      object_type,
                                                                                                      logger=logger)
                    else:
                        raise TypeError('Parser attached to this ParsingPlan is not a ' + str(AnyParser))
                else:
                    raise InvalidParserException.create(self.parser, self.obj_on_fs_to_parse)

            except Exception as e:
                # if logger is not None:
                #     # log the object that was being built, just for consistency of log messages
                #     logger.info(str(obj_on_filesystem) + ' > ' + get_pretty_type_str(object_type))
                raise e.with_traceback(e.__traceback__)

        def _get_children_parsing_plan(self) -> Dict[str, _ParsingPlanElement]:
            return self._children_parsing_plan

    # flag used for create_parsing_plan logs (to prevent recursive print messages)
    thrd_locals = threading.local()

    def create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                            in_rootcall: bool = True):
        """
        Implements the abstract parent method by using the recursive parsing plan impl.
        :param desired_type:
        :param filesystem_object:
        :param logger:
        :return:
        """
        in_root_call= False

        # print only for the root call, not for the children that will be created by the code below
        if in_rootcall and (not hasattr(AnyParser.thrd_locals, 'flag_init') or AnyParser.thrd_locals.flag_init == 0):
            #print('Building a parsing plan to parse ' + str(filesystem_object) + ' into a ' +
            #      get_pretty_type_str(desired_type))
            logger.info('Building a parsing plan to parse ' + str(filesystem_object) + ' into a ' +
                  get_pretty_type_str(desired_type))
            AnyParser.thrd_locals.flag_init = 1
            in_root_call = True

        # create it
        try:
            pp = self._create_parsing_plan(desired_type, filesystem_object, logger)
        finally:
            # remove threadlocal flag if needed
            if in_root_call:
                AnyParser.thrd_locals.flag_init = 0

        # log success only in root call
        if in_root_call:
            #print('Parsing Plan created successfully')
            logger.info('Parsing Plan created successfully')

        return pp

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger):
        """
        Subclasses may wish to override this if needed.
        :param desired_type:
        :param filesystem_object:
        :param logger:
        :return:
        """
        logger.info(get_parsing_plan_log_str(filesystem_object, desired_type, self))
        return AnyParser._RecursiveParsingPlan(desired_type, filesystem_object, self, logger)


    @abstractmethod
    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                 logger: Logger) -> Dict[str, BaseParser.ParsingPlan[Any]]:
        """
        Implementing classes should create a ParsingPlan for each child. This plan will be executed in
        _parse_multifile before _build_object_from_parsed_children is finally called.

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """
        pass

    # def execute_parsing_plan(self, parsing_plan: _ParsingPlanElement[T], logger: Logger, *args, **kwargs) -> T:
    #     """
    #     Called to parse the object as described in the given parsing plan, using the provided arguments for the parser.
    #     This method actually only redirects to the parsing plan.
    #     This method checks that 'self' is actually the parser in the parsing plan.
    #
    #     :param parsing_plan: a parsing plan created with create_parsing_plan
    #     :param logger: the logger to use during parsing (optional: None is supported)
    #     :param args:
    #     :param kwargs:
    #     :return:
    #     """
    #     if parsing_plan.parser is self:
    #         return parsing_plan.execute(logger, *args, **kwargs)
    #     else:
    #         raise ValueError('The parser associated to this parsing plan is different from this object. This is '
    #                          'probably a mistake. If not, please use the \'execute\' method directly on the parsing '
    #                          'plan to avoid confusion.')


class SingleFileParser(AnyParser[T]):
    """
    Represents any singlefile parser.
    Optionally a list of supported object types may be provided. Otherwise the parser is able to parse any object type.

    Implementing classes should override '_supports_singlefile_extension', and '_parse_singlefile'

    This class can be typed with PEP484 if the supported object type(s) is known
    (e.g. SingleFileParser[Any], SingleFileParser[Union[str, int]], etc.)
    """

    def __init__(self, supported_exts: Set[str], supported_types: Set[Type[T]], **kwargs):
        """
        Constructor, with
        * a mandatory list of supported extensions
        * an optional list of supported object types (otherwise the parser supports any object type)

        :param supported_exts: mandatory list of supported singlefile extensions ('.txt', '.json' ...)
        :param supported_types: mandatory list of supported object types that may be parsed
        """
        if supported_exts is not None and MULTIFILE_EXT in supported_exts:
            raise ValueError('Cannot create a SingleFileParser supporting multifile extensions ! Use AnyParser to '
                             'support both, or MultiFileParser to support MultiFile')
        super(SingleFileParser, self).__init__(supported_types=supported_types, supported_exts=supported_exts)

    # def supports_file_extension(self, ext_to_parse: str) -> bool:
    #     """
    #     if the object was build with an initial list of supported extensions, check if ext is in there. Otherwise
    #     returns True (the parser supports any extension).
    #     :param ext_to_parse:
    #     :return:
    #     """
    #     if self._supported_exts:
    #         return ext_to_parse in self._supported_exts
    #     else:
    #         return True

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        raise NotImplementedError('Not implemented since this is a SingleFileParser')

    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan],
                         logger: Logger, *args, **kwargs) -> T:
        raise NotImplementedError('Not implemented since this is a SingleFileParser')

    # def _parse(self, desired_type: Type[T], obj: PersistedObject, *args, **kwargs) -> T:
    #     """
    #     Implementation of the abstract method in AnyParser. This checks that the object is a single file, and
    #     redirects to _parse_singlefile with the appropriate arguments. Implementing classes should implement
    #     _parse_singlefile.
    #
    #     :param desired_type:
    #     :param obj:
    #     :param args:
    #     :param kwargs:
    #     :return:
    #     """
    #     if obj.is_singlefile:
    #         return self._parse_singlefile(desired_type, obj.get_file_path(), obj.get_file_encoding(), *args, **kwargs)
    #     else:
    #         raise NotImplementedError('This parser is not able to parse multifile objects. Found : ' + str(obj))



        # def supports_singlefile_extension(self, ext_to_parse: str) -> bool:
        #     """
        #     Method used to check if a parser supporting singlefiles supports a given file extension.
        #
        #     This method throws a NotImplementedError error if the parser does not support singlefiles. It redirects to
        #     _supports_singlefile_extension otherwise, so implementing classes dont need to override this one, only
        #     _supports_singlefile_extension
        #
        #     :param ext_to_parse: the extension to check
        #     :return:
        #     """
        #     if not self.supports_singlefiles:
        #         raise NotImplementedError('This parser is for multifiles only. Therefore it can not be called for '
        #                                   'singlefile parsing')
        #     else:
        #         return self._supports_singlefile_extension(ext_to_parse)

        # def _supports_singlefile_extension(self, ext: str) -> bool:
        #     """
        #     Method that should be overriden by your implementing class if it supports singlefiles.
        #     It will be called by supports_singlefile_extension.
        #
        #     :param ext:
        #     :return:
        #     """
        #     raise NotImplementedError('your singlefile parser should implement _supports_singlefile_extension')

        # def parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str = None) -> T:
        #     """
        #     Method used to parse a singlefile, if the parser supports singlefiles.
        #
        #     This method throws a NotImplementedError error if the parser does not support singlefiles. It redirects to
        #     _parse_singlefile otherwise, so implementing classes dont need to override this one, only
        #     _parse_singlefile.
        #
        #     Note that the resulting parsed object's type is checked after parsing.
        #
        #     :param desired_type:
        #     :param opened_file:
        #     :param file_path_for_error_msg:
        #     :return:
        #     """
        #     if self.supports_singlefiles:
        #
        #         # a few checks for the framework's sanity
        #         check_var(desired_type, var_types=type, var_name='desired_type')
        #         check_var(file_path, var_types=str, var_name='file_path')
        #         encoding = encoding or 'utf-8'
        #         check_var(encoding, var_types=str, var_name='encoding')
        #
        #         # Call the subclass implementation
        #         return self._parse_singlefile(desired_type, file_path, encoding)
        #
        #     else:
        #         raise NotImplementedError('This parser is for multifiles only. Therefore it can not be called for '
        #                                   'singlefile parsing')
# def organize_parsers(List[])


class MultiFileParser(AnyParser[T]):
    """
    Represents a multifile parser

    Implementing classes should override '_get_multifile_parsing_plan_for_children' and '_parse_multifile'

    This class can be typed with PEP484 if the supported object type(s) is known
    (e.g. MultiFileParser[Any], MultiFileParser[Union[str, int]], etc.)
    """

    def __init__(self, supported_types: Set[Type[T]], **kwargs):
        """
        Constructor, with
        * an optional list of supported object types (otherwise the parser supports any object type)

        :param supported_types: mandatory list of supported object types that may be parsed
        """
        super(MultiFileParser, self).__init__(supported_types=supported_types, supported_exts={MULTIFILE_EXT})
        # disable singlefile
        # self.supports_singlefile = False

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          *args, **kwargs) -> T:
        raise Exception('Not implemented since this is a MultiFileParser')

    # def _parse(self, desired_type: Type[T], obj: PersistedObject, *args, **kwargs) -> T:
    #     """
    #     Implementation of the abstract method in AnyParser. This checks that the object is a multifile, and
    #     redirects to _parse_multifile with the appropriate arguments. Implementing classes should implement
    #     _parse_multifile.
    #
    #     :param desired_type:
    #     :param obj:
    #     :param args:
    #     :param kwargs:
    #     :return:
    #     """
    #     if not obj.is_singlefile:
    #         return self._parse_multifile(desired_type, obj, *args, **kwargs)
    #     else:
    #         raise NotImplementedError('This parser is not able to parse singlefile objects. Found : ' + str(obj))

    # @abstractmethod
    # def _build_object_from_parsed_children(self, desired_type: Type[T], obj: PersistedObject,
    #                                        parsed_children: Dict[str, Any], logger: Logger, *args, **kwargs) -> T:
    #     """
    #     Method that should be overriden by your implementing class. It will be called by
    #     (_RecursiveParsingPlan).parse_object > (MultiFileParser)._parse_multifile > (yours)._build_object_from_parsed_children
    #
    #     :param desired_type:
    #     :param obj:
    #     :param parsing_plan_for_children:
    #     :param logger:
    #     :param args:
    #     :param kwargs:
    #     :return:
    #     """
    #     pass





    # def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
    #                       *args, **kwargs) -> T:
    #     """
    #     Implementation of AnyParser method, by delegation to the chain
    #     """
    #     if len(self._parsers_list) > 0:
    #         for parser in self._parsers_list:
    #             try:
    #                 return parser._parse_singlefile(desired_type, file_path, encoding, logger, *args, **kwargs)
    #             except Exception as e:
    #                 last_e = e
    #         # if we're here, we can raise at least the last exception.
    #         raise last_e.with_traceback(last_e.__traceback__)
    #     else:
    #         raise Exception('Empty parser list !')
    #
    # # the parser that has been selected in case of multifile. This is to prevent inconsistent behaviour.
    # active_mf_parsers = threading.local()
    #
    # def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
    #                                              logger: Logger) -> Dict[str, Any]:
    #     """
    #     Implementing classes should create an _RecursiveParsingPlan for each child. This plan will be executed in
    #     _parse_multifile before _build_object_from_parsed_children is finally called.
    #
    #     :param children:
    #     :param logger:
    #     :return:
    #     """
    #     # TO DO it would probably be better to return a 'union' of parsing plan ?
    #     # For the rare case where a parser would accept to create a parsing plan, and then realize at execution time
    #     # that it fails...
    #     #
    #     # Actually this can be prevented by asking all parser implementors to perform basic sanity checks in the
    #     # function creating the parsing plan.
    #     #
    #     # So here we will even be stricter : as soon as ne of the parsers accepts to parse, the remaining ones won't be
    #     # tried
    #
    #     if len(self._parsers_list) > 0:
    #         errors = dict()
    #         for parser in self._parsers_list:
    #             try:
    #                 pp = parser._get_parsing_plan_for_multifile_children(obj_on_fs, desired_type, logger)
    #                 # save the active parser
    #                 CascadingParser.active_mf_parsers.parser = parser
    #                 return pp
    #             except Exception as e:
    #                 errors[parser] = e
    #         raise CascadeError.create_for_parsing_plan_creation(self, parent_plan, errors)
    #     else:
    #         raise Exception('Empty parser list !')

    # def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
    #                      parsing_plan_for_children: Dict[str, _ParsingPlanElement],
    #                      logger: Logger, *args, **kwargs) -> T:
    #     if hasattr(CascadingParser.active_mf_parsers, 'parser') \
    #             and CascadingParser.active_mf_parsers.parser is not None:
    #         try:
    #             return CascadingParser.active_mf_parsers.parser._parse_multifile(desired_type, obj,
    #                                                         parsing_plan_for_children, logger, *args, **kwargs)
    #         finally:
    #             # reset the active parser
    #             CascadingParser.active_mf_parsers.parser = None
    #     else:
    #         raise Exception('No active multifile parser elected. _get_parsing_plan_for_multifile_children should'
    #                         ' run first')
        # if len(self._parsers_list) > 0:
        #     errors = []
        #     for parser in self._parsers_list:
        #         try:
        #             return parser._parse_multifile(desired_type, obj, parsing_plan_for_children, logger, *args, **kwargs)
        #         except Exception as e:
        #             last_e = e
        #     # if we're here, we can raise at least the last exception.
        #     raise last_e.with_traceback(last_e.__traceback__)
        # else:
        #     raise Exception('Empty parser list !')


#
# def _scan_multifile_children(self):
#     """
#     Utility method to fill the self.children field
#     :return:
#     """
#     if self.is_singlefile:
#         raise NotImplementedError('get_multifile_children does not mean anything on a singlefile object : a single file'
#                                   'object by definition has no children - check your code')
#     else:
#         if self.is_collection:
#             # the child items all have the same type, determined by the PEP484 typing annotation of this object
#             # --use sorting in order to lead to reproducible results in case of multiple errors
#             self.children = {name: _RecursiveParsingPlan(loc, self.subtype, logger=self.logger)
#                              for name, loc in sorted(self._contents_or_path.items())}
#         else:
#


#
# def _check_common_vars_core(obj: _RecursiveParsingPlan, lazy_parsing: bool = None, logger: IndentedLogger = None):
#     """
#     Utility method to check all these variables and apply defaults
#     :param obj:
#     :param lazy_parsing:
#     :param logger:
#     :return: lazy_parsing, logger
#     """
#     check_var(obj, var_types=_RecursiveParsingPlan, var_name='obj')
#
#     lazy_parsing = lazy_parsing or False
#     check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
#
#     logger = logger or IndentedLogger(TypedParsingChain.logger)
#     check_var(logger, var_types=IndentedLogger, var_name='logger')
#
#     return lazy_parsing, logger
#


#

        # def get_constructor_attributes_types(self):
        #     """
        #     :return: a dictionary {attr_name: attr_type} for all attributes of the object constructor
        #     (if it is not a collection)
        #     """
        #     if self.is_collection:
        #         raise NotImplementedError('Collection objects dont need to inspect their constructor attributes')
        #     else:
        #         return get_constructor_attributes_types(self.obj_type)


# aliases used in SingleFileParserFunction
ParsingMethodForStream = Callable[[Type[T], TextIOBase, Logger], T]
ParsingMethodForFile = Callable[[Type[T], str, str, Logger], T]


class CaughtTypeError(Exception):
    """
    Raised whenever a TypeError is caught during parser function execution
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
    def create(parser_func: Union[ParsingMethodForStream, ParsingMethodForFile], caught: Exception):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser_func:
        :param caught:
        :return:
        """
        msg = 'Caught TypeError while calling parsing function \'' + str(parser_func.__name__) + '\'. ' \
              'Note that the parsing function signature should be my_parse_func(type, stream, logger, *args, **kwargs).' \
              'Caught error message is : ' + caught.__class__.__name__ + ' : ' + str(caught)
        return CaughtTypeError(msg).with_traceback(caught.__traceback__)

class SingleFileParserFunction(SingleFileParser[T]): #metaclass=ABCMeta
    """
    Represents any parser for singlefiles, relying on a parser_function.

    As for any AnyParser, a list of supported types may be provided (by default the parser is declared to be
    able to parse objects of any types).

    As for any SingleFileParser, the list of supported file extensions may also be provided (by default the parser
    is declared to be able to parse any file extension - quite unrealistic :)).

    Two kind of parser_function may be provided as implementations:
    * if streaming_mode=True (default), this class handles opening and closing the file, and parser_function should
    have a signature such as my_func(desired_type: Type[T], opened_file: TextIOBase, *args, **kwargs) -> T
    * if streaming_mode=False, this class does not handle opening and closing the file. parser_function should be a
    my_func(desired_type: Type[T], file_path: str, encoding: str, *args, **kwargs) -> T

    This class can be typed with PEP484 if the supported object type(s) is known
    (e.g. SingleFileParserFunction[Any], SingleFileParserFunction[Union[str, int]], etc.)
    """

    def __init__(self, parser_function: Union[ParsingMethodForStream, ParsingMethodForFile],
                 supported_types: Set[Type[T]], supported_exts: Set[str], streaming_mode: bool = True,  ):
        """
        Constructor from a parser function , a mandatory list of supported types, and a mandatory list of supported
        extensions.

        :param parser_function:
        :param streaming_mode:
        :param supported_types:
        :param supported_exts: mandatory list of supported singlefile extensions ('.txt', '.json' ...)
        """
        super(SingleFileParserFunction, self).__init__(supported_types=supported_types, supported_exts=supported_exts)

        check_var(parser_function, var_types=Callable, var_name='parser_function')
        self._parser_func = parser_function

        check_var(streaming_mode, var_types=bool, var_name='streaming_mode')
        self._streaming_mode = streaming_mode

    def __str__(self):
        # return 'ParserFunc<' + self._parser_func.__name__ \
        #        + '(' + ('stream' if self._streaming_mode else 'file') + ' mode)>'
        return '<' + self._parser_func.__name__ + '(' + ('stream' if self._streaming_mode else 'file') + ' mode)>'
            #for '\
            #   + str([get_pretty_type_str(typ) for typ in self.supported_types]) + ' for extensions ' \
            #   + str(self.supported_exts)

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          *args, **kwargs) -> T:
        """
        Relies on the inner parsing function to parse the file.
        If _streaming_mode is True, the file will be opened and closed by this method. Otherwise the parsing function
        will be responsible to open and close.

        :param desired_type:
        :param file_path:
        :param encoding:
        :param args:
        :param kwargs:
        :return:
        """
        if self._streaming_mode:

            # We open the stream, and let the function parse from it
            file_stream = None
            try:
                # Open the file with the appropriate encoding
                file_stream = open(file_path, 'r', encoding=encoding)

                # Apply the parsing function
                return self._parser_func(desired_type, file_stream, logger, *args, **kwargs)

            except TypeError as e:
                # TODO check the function signature in the constructor to prevent this to happen
                raise CaughtTypeError.create(self._parser_func, e)
            finally:
                if file_stream is not None:
                    # Close the File in any case
                    file_stream.close()

        else:
            # the parsing function will open the file
            return self._parser_func(desired_type, file_path, encoding, logger, *args, **kwargs)



# def parse_object_with_parsing_chains(obj: _RecursiveParsingPlan, parsing_chains: Dict[str, TypedParsingChain[T]],
#                                      lazy_parsing: bool = None, logger: Logger = None):
#     """
#     Utility function to parse a singlefile or multifile object with a bunch of available parsing chains
#     (a [extension > parsing_chain] dictionary, where a special extension denotes a multifile).
#     This method throws NoParserFoundForObject if the object is present but not with an extension matching the ones
#     supported by the parsing chains
#
#     :param obj: the object to parse
#     :param parsing_chains:
#     :param lazy_parsing:
#     :param logger:
#     :return:
#     """
#
#     # 0. check all vars
#     # -- core
#     lazy_parsing, logger = _check_common_vars_core(obj, lazy_parsing=lazy_parsing, logger=logger)
#     # -- parsing chains
#     check_var(parsing_chains, var_types=dict, var_name='parsing_chains')
#
#     if len(parsing_chains) == 0:
#         # no parsing chain provided
#         raise NoParserFoundForObjectType.create(obj)
#     else:
#         # 1. Check what kind of object is present on the filesystem with this prefix, and check if it cab be read with
#         # the parsing chains provided.
#         if obj.is_singlefile and obj.ext in parsing_chains.keys():
#             # parse this file and add to the result
#             parsing_chain_to_use = parsing_chains[obj.ext]
#             log_parsing_info(logger, obj=obj, parser_name=str(parsing_chain_to_use), additional_details='')
#
#             return parse_single_file_with_parsing_chain(obj.get_file_path(), parsing_chain_to_use,
#                                                         encoding=obj.file_mapping_conf.encoding)
#
#         elif MULTIFILE_EXT in parsing_chains.keys():
#             # parse this file and add to the result
#             parsing_chain_to_use = parsing_chains[MULTIFILE_EXT]
#             log_parsing_info(logger, obj=obj, parser_name=str(parsing_chain_to_use), additional_details='')
#
#             return parse_multifile_with_parsing_chain(obj.location, obj.file_mapping_conf, parsing_chain_to_use)
#
#         else:
#             # there is a singlefile but not with the appropriate extension
#             # or
#             # there is a multifile, but there is no parsing chain for multifile
#             raise NoParserFoundForObjectExt.create(obj, parsing_chains.keys())

# def parse_single_file_with_parsing_chain(file_path: str, parsing_chain: TypedParsingChain[T],
#                                          encoding: str = None) -> T:
#     """
#     Utility function to parse a single-file object from the provided path, using the provided parsing chain. If an
#     error happens during parsing it will be wrapped into a ParsingException
#
#     :param file_path:
#     :param parsing_chain:
#     :param encoding:
#     :return:
#     """
#
#     check_var(file_path, var_types=str, var_name='file_path')
#     check_var(parsing_chain, var_types=TypedParsingChain, var_name='parsing_chain')
#     encoding = encoding or 'utf-8'
#     check_var(encoding, var_types=str, var_name='encoding')
#
#     f = None
#     try:
#         # Open the file with the appropriate encoding
#         f = open(file_path, 'r', encoding=encoding)
#
#         # Apply the parsing function
#         res = parsing_chain.parse_singlefile(f, file_path)
#
#     except Exception as e:
#         # Wrap into a ParsingException
#         raise ParsingException.create_for_caught_error(file_path, parsing_chain, encoding, e)
#     finally:
#         if f is not None:
#             # Close the File in any case
#             f.close()


# def parse_multifile_with_parsing_chain(file_prefix: str, file_mapping_conf: FileMappingConfiguration,
#                                        parsing_chain: TypedParsingChain[T]) -> T:
#     """
#     In this method the parsing chain is used to parse the multifile object file_prefix. Therefore the parsing chain
#     is responsible to open/close the files
#
#     :param file_prefix:
#     :param file_mapping_conf:
#     :param parsing_chain:
#     :return:
#     """
#     return parsing_chain.parse_multifile(file_prefix, file_mapping_conf)


# def parse_singlefile_object_with_parsers(obj: _RecursiveParsingPlan,
#                                          parsers: Dict[str, Union[Callable[[TextIOBase], T],
#                                                                   Callable[[str, FileMappingConfiguration], T]]],
#                                          logger: IndentedLogger):
#     """
#     Utility function to parse a singlefile object with a bunch of available parsers (a [extension > function] dictionary).
#     It will look if the file is present with a SINGLE supported extension, and parse with the associated parser if it
#     is the case.
#
#     :param obj:
#     :param parsers:
#     :param logger:
#     :return:
#     """
#
#     # First transform all parser functions into parsing chains
#     parsing_chains = {ext: TypedParsingChain(obj.obj_type, ext, parser_function) for ext, parser_function in parsers.items()}
#
#     # Then use the generic method with parsing chains
#     return parse_object_with_parsing_chains(obj, parsing_chains, logger=logger)


# def parse_single_file_object_with_parser_function(file_path:str, item_type: Type[T],
#                                                   parser_function:Callable[[TextIOBase], T],
#                                                   encoding:str= None, *args, **kwargs) -> T:
#     """
#     A function to execute a given parsing function on a file path while handling the close() properly.
#     Made public so that users may directly try with their parser functions on a single file.
#
#     :param file_path:
#     :param parser_function:
#     :param encoding:
#     :param args:
#     :param kwargs:
#     :return:
#     """
#     check_var(parser_function, var_types=Callable, var_name='parser_function')
#
#     ext = splitext(file_path)[1]
#
#     return parse_single_file_with_parsing_chain(file_path, TypedParsingChain(item_type, ext, parser_function),
#                                                 encoding=encoding, *args, **kwargs)


# def log_parsing_info(logger: Logger, obj: _RecursiveParsingPlan, parser_name: str, additional_details: str):
#     """
#     Utility method for logging information about a parsing operation that is starting
#
#     :param logger:
#     :param obj:
#     :param parser_name:
#     :param additional_details:
#     :return:
#     """
#     logger.info('Parsing ' + str(obj) + ' with ' + parser_name + '. ' + additional_details)
