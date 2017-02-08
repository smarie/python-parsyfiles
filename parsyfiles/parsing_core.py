import threading
from abc import abstractmethod
from io import TextIOBase
from logging import Logger
from typing import Union, Type, Callable, Dict, Any, Set

from parsyfiles.filesystem_mapping import MULTIFILE_EXT, PersistedObject
from parsyfiles.parsing_core_api import Parser, T, ParsingPlan, get_parsing_plan_log_str
from parsyfiles.type_inspection_tools import get_pretty_type_str
from parsyfiles.var_checker import check_var


class _InvalidParserException(Exception):
    """
    Exception raised whenever a ParsingPlan tries to be executed or created with a parser that is not compliant with
    the underlying file object format (multifile, singlefile) and/or the expected parser type. This should not happen
    except if the implementation code for parser registries or for parser is wrong > not part of public api.
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(_InvalidParserException, self).__init__(contents)

    @staticmethod
    def create(parser: Parser, obj: PersistedObject = None):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param parser:
        :param obj:
        :return:
        """
        if obj is not None:
            return _InvalidParserException('Error ' + str(obj) + ' cannot be parsed using ' + str(parser) + ' since '
                                           + ' this parser does not support ' + obj.get_pretty_file_mode())
        else:
            return _InvalidParserException('Error this parser is neither SingleFile nor MultiFile !')


class _BaseParser(Parser):
    """
    Abstract utility class of parsers able to produce a parsing plan for singlefile and multifile parsing.
    This class defines the two abstract methods _parse_singlefile and _parse_multifile for the parser.
    """

    @abstractmethod
    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          *args, **kwargs) -> T:
        """
        Method that should be overriden by your implementing class. It will be called by
        (_BaseParsingPlan).execute

        :param desired_type:
        :param file_path:
        :param encoding:
        :param args:
        :param kwargs:
        :return:
        """
        pass

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
        pass


class _BaseParsingPlan(ParsingPlan[T]):
    """
    Defines abstract parsing plan objects for _BaseParsers. It
    * adds log information to the parent execute() method
    * relies on the singlefile and multifile parsing methods of _BaseParser to implement the inner _execute() method.
    * defines the _get_children_parsing_plan method that should be implemented by multifile parsers
    """

    def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject, parser: _BaseParser,
                 logger: Logger):
        """
        Constructor like in PersistedObject, but with an additional logger.

        :param object_type:
        :param obj_on_filesystem:
        :param parser:
        :param logger:
        """
        super(_BaseParsingPlan, self).__init__(object_type, obj_on_filesystem, parser)

        # -- logger
        check_var(logger, var_types=Logger, var_name='logger', enforce_not_none=False)
        self.logger = logger

    # flag used for create_parsing_plan logs (to prevent recursive print messages)
    thrd_locals = threading.local()

    def execute(self, logger: Logger, *args, **kwargs) -> T:
        """
        Overrides the parent method to add log messages.

        :param logger: the logger to use during parsing (optional: None is supported)
        :param args:
        :param kwargs:
        :return:
        """
        in_root_call = False
        if logger is not None:
            # log only for the root object, not for the children that will be created by the code below
            if not hasattr(_BaseParsingPlan.thrd_locals, 'flag_exec') \
                    or _BaseParsingPlan.thrd_locals.flag_exec == 0:
                # print('Executing Parsing Plan for ' + str(self))
                logger.info('Executing Parsing Plan for ' + str(self))
                _BaseParsingPlan.thrd_locals.flag_exec = 1
                in_root_call = True

        # Common log message
        logger.info('Parsing ' + str(self))

        try:
            res = super(_BaseParsingPlan, self).execute(logger, *args, **kwargs)
            if in_root_call:
                # print('Completed parsing successfully')
                logger.info('Completed parsing successfully')
            return res

        finally:
            # remove threadlocal flag if needed
            if in_root_call:
                _BaseParsingPlan.thrd_locals.flag_exec = 0

    def _execute(self, logger: Logger, *args, **kwargs) -> T:
        """
        Implementation of the parent class method.
        Checks that self.parser is a _BaseParser, and calls the appropriate parsing method

        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        if isinstance(self.parser, _BaseParser):
            if (not self.is_singlefile) and self.parser.supports_multifile():
                return self.parser._parse_multifile(self.obj_type, self.obj_on_fs_to_parse,
                                                    self._get_children_parsing_plan(), logger, *args, **kwargs)

            elif self.is_singlefile and self.parser.supports_singlefile():
                return self.parser._parse_singlefile(self.obj_type, self.get_singlefile_path(),
                                                     self.get_singlefile_encoding(), logger, *args, **kwargs)
            else:
                raise _InvalidParserException.create(self.parser, self.obj_on_fs_to_parse)
        else:
            raise TypeError('Parser attached to this _BaseParsingPlan is not a ' + str(_BaseParser))

    @abstractmethod
    def _get_children_parsing_plan(self) -> Dict[str, ParsingPlan]:
        pass


class AnyParser(_BaseParser):
    """
    Base class for any parser implementation wishing to implement *both* singlefile and multifile parsing. Users wishing
    to implement parsers *only for singlefile* or *only for multifile* should rather extend SingleFileParser or
    MultiFileParser respectively, or one of their subclasses such as SingleFileParserFunction.

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.

    This class extends _BaseParser to add recursivity to the parsing plan creation step. It also adds logging
    capabilities in the parent 'create_parsing_plan' method.

    So what remains to the implementation ?
    * This class extends BaseParserDeclarationForRegistries. So you may call its super constructor to declare the
    parser capabilities (see BaseParserDeclarationForRegistries.__init__ for details)
    * This class extends _BaseParser. So 2 parsing methods should be implemented : '_parse_singlefile' and
    '_parse_multifile'.
    * This class implements _BaseParser._create_parsing_plan by creating recursive parsing plans. These recursive
    parsing plans rely on an additional function to implement, '_get_parsing_plan_for_multifile_children'.
    """

    class _RecursiveParsingPlan(_BaseParsingPlan[T]):
        """
        Represents a parsing plan that is recursive : at creation time, it will query the parsing plans for all
        children. This enables to then implement the parent '_get_children_parsing_plan' method by just getting the
        stored field.
        """

        def __init__(self, object_type: Type[T], obj_on_filesystem: PersistedObject, parser: _BaseParser,
                     logger: Logger):
            """
            Constructor with recursive construction of all children parsing plan. The plan for all children is then
            stored in a field, so that _get_children_parsing_plan may get it later (it was a parent method to implement)

            :param object_type:
            :param obj_on_filesystem:
            :param parser:
            :param logger:
            """

            # -- super
            super(AnyParser._RecursiveParsingPlan, self).__init__(object_type, obj_on_filesystem, parser, logger)

            try:
                # -- if singlefile, nothing to do
                if self.obj_on_fs_to_parse.is_singlefile and parser.supports_singlefile():
                    pass

                # -- if multifile, get the parsing plan for children
                elif (not self.obj_on_fs_to_parse.is_singlefile) and parser.supports_multifile():
                    if isinstance(parser, AnyParser):
                        self._children_parsing_plan = parser._get_parsing_plan_for_multifile_children(self.obj_on_fs_to_parse,
                                                                                                      object_type,
                                                                                                      logger=logger)
                    else:
                        raise TypeError('Parser attached to this _BaseParsingPlan is not a ' + str(AnyParser))
                else:
                    raise _InvalidParserException.create(self.parser, self.obj_on_fs_to_parse)

            except Exception as e:
                raise e.with_traceback(e.__traceback__)

        def _get_children_parsing_plan(self) -> Dict[str, ParsingPlan]:
            """
            Implementation of the parent method by just getting the field built at init time.
            :return:
            """
            return self._children_parsing_plan

    # flag used for create_parsing_plan logs (to prevent recursive print messages)
    thrd_locals = threading.local()

    def create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                            _main_call: bool = True):
        """
        Implements the abstract parent method by using the recursive parsing plan impl. Subclasses wishing to produce
        their own parsing plans should rather override _create_parsing_plan in order to benefit from this same log msg.

        :param desired_type:
        :param filesystem_object:
        :param logger:
        :param _main_call: internal parameter for recursive calls. Should not be changed by the user.
        :return:
        """
        in_root_call = False

        # -- log msg only for the root call, not for the children that will be created by the code below
        if _main_call and (not hasattr(AnyParser.thrd_locals, 'flag_init') or AnyParser.thrd_locals.flag_init == 0):
            # print('Building a parsing plan to parse ' + str(filesystem_object) + ' into a ' +
            #      get_pretty_type_str(desired_type))
            logger.info('Building a parsing plan to parse ' + str(filesystem_object) + ' into a ' +
                        get_pretty_type_str(desired_type))
            AnyParser.thrd_locals.flag_init = 1
            in_root_call = True

        # -- create the parsing plan
        try:
            pp = self._create_parsing_plan(desired_type, filesystem_object, logger)
        finally:
            # remove threadlocal flag if needed
            if in_root_call:
                AnyParser.thrd_locals.flag_init = 0

        # -- log success only if in root call
        if in_root_call:
            # print('Parsing Plan created successfully')
            logger.info('Parsing Plan created successfully')

        # -- finally return
        return pp

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger):
        """
        Adds a log message and creates a recursive parsing plan.

        :param desired_type:
        :param filesystem_object:
        :param logger:
        :return:
        """
        logger.info(get_parsing_plan_log_str(filesystem_object, desired_type, self))
        return AnyParser._RecursiveParsingPlan(desired_type, filesystem_object, self, logger)

    @abstractmethod
    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                 logger: Logger) -> Dict[str, ParsingPlan[T]]:
        """
        This method is called by the _RecursiveParsingPlan when created.
        Implementing classes should return a dictionary containing a ParsingPlan for each child they plan to parse
        using this framework. Note that for the files that will be parsed using a parsing library it is not necessary to
        return a ParsingPlan.

        In other words, implementing classes should return here everything they need for their implementation of
        _parse_multifile to succeed. Indeed during parsing execution, the framework will call their _parse_multifile
        method with that same dictionary as an argument (argument name is 'parsing_plan_for_children', see _BaseParser).

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """
        pass


class SingleFileParser(AnyParser):
    """
    Represents parser able to parse singlefiles only (not multifiles).

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.
    """

    def __init__(self, supported_exts: Set[str], supported_types: Set[Type[T]]):
        """
        Constructor, with
        * a mandatory set of supported extensions
        * an optional set of supported object types (otherwise the parser supports any object type)

        :param supported_exts: mandatory list of supported singlefile extensions ('.txt', '.json' ...)
        :param supported_types: mandatory list of supported object types that may be parsed
        """
        # -- check that we are really a singlefile parser
        if supported_exts is not None and MULTIFILE_EXT in supported_exts:
            raise ValueError('Cannot create a SingleFileParser supporting multifile extensions ! Use AnyParser to '
                             'support both, or MultiFileParser to support MultiFile')
        # -- call super
        super(SingleFileParser, self).__init__(supported_types=supported_types, supported_exts=supported_exts)

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Implementation of the parent method : since this is a singlefile parser, this is not implemented.

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """
        raise Exception('Not implemented since this is a SingleFileParser')

    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan],
                         logger: Logger, *args, **kwargs) -> T:
        """
        Implementation of the parent method : since this is a singlefile parser, this is not implemented.

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        raise Exception('Not implemented since this is a SingleFileParser')


class MultiFileParser(AnyParser):
    """
    Represents parser able to parse multifiles only (not singlefiles).

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.
    """

    def __init__(self, supported_types: Set[Type[T]]):
        """
        Constructor, with a mandatory list of supported object types

        :param supported_types: mandatory list of supported object types that may be parsed
        """
        super(MultiFileParser, self).__init__(supported_types=supported_types, supported_exts={MULTIFILE_EXT})

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          *args, **kwargs) -> T:
        """
        Implementation of the parent method : since this is a multifile parser, this is not implemented.

        :param desired_type:
        :param file_path:
        :param encoding:
        :param logger:
        :param args:
        :param kwargs:
        :return:
        """
        raise Exception('Not implemented since this is a MultiFileParser')


# aliases used in SingleFileParserFunction
ParsingMethodForStream = Callable[[Type[T], TextIOBase, Logger], T]
ParsingMethodForFile = Callable[[Type[T], str, str, Logger], T]


class CaughtTypeError(Exception):
    """
    Raised whenever a TypeError is caught during SingleFileParserFunction's parser function execution
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


class SingleFileParserFunction(SingleFileParser): #metaclass=ABCMeta
    """
    Represents a parser for singlefiles relying on a parser_function.

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.

    Two kind of parser_function may be provided as implementations:
    * if streaming_mode=True (default), this class handles opening and closing the file, and parser_function should
    have a signature such as my_func(desired_type: Type[T], opened_file: TextIOBase, *args, **kwargs) -> T
    * if streaming_mode=False, this class does not handle opening and closing the file. parser_function should be a
    my_func(desired_type: Type[T], file_path: str, encoding: str, *args, **kwargs) -> T
    """

    def __init__(self, parser_function: Union[ParsingMethodForStream, ParsingMethodForFile],
                 supported_types: Set[Type[T]], supported_exts: Set[str], streaming_mode: bool = True):
        """
        Constructor from a parser function , a mandatory set of supported types, and a mandatory set of supported
        extensions.

        Two kind of parser_function may be provided as implementations:
        * if streaming_mode=True (default), this class handles opening and closing the file, and parser_function should
        have a signature such as my_func(desired_type: Type[T], opened_file: TextIOBase, *args, **kwargs) -> T
        * if streaming_mode=False, this class does not handle opening and closing the file. parser_function should be a
        my_func(desired_type: Type[T], file_path: str, encoding: str, *args, **kwargs) -> T

        :param parser_function:
        :param streaming_mode: an optional boolean (default True) indicating if the function should be called with an
        open stream or with a file path
        :param supported_types: mandatory set of supported types, or {
        :param supported_exts: mandatory set of supported singlefile extensions ('.txt', '.json' ...)
        """
        super(SingleFileParserFunction, self).__init__(supported_types=supported_types, supported_exts=supported_exts)

        # -- check the function
        # TODO check the function signature to prevent TypeErrors to happen (and then remove the catch block below)
        check_var(parser_function, var_types=Callable, var_name='parser_function')
        self._parser_func = parser_function

        # -- check the streaming mode
        check_var(streaming_mode, var_types=bool, var_name='streaming_mode')
        self._streaming_mode = streaming_mode

    def __str__(self):
        return '<' + self._parser_func.__name__ + '(' + ('stream' if self._streaming_mode else 'file') + ' mode)>'

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
                raise CaughtTypeError.create(self._parser_func, e)

            finally:
                if file_stream is not None:
                    # Close the File in any case
                    file_stream.close()

        else:
            # the parsing function will open the file itself
            return self._parser_func(desired_type, file_path, encoding, logger, *args, **kwargs)
