import threading
from abc import abstractmethod
from io import TextIOBase
from logging import Logger, DEBUG
from typing import Union, Type, Callable, Dict, Any, Set

from parsyfiles import GLOBAL_CONFIG
from parsyfiles.converting_core import get_options_for_id
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
                          options: Dict[str, Dict[str, Any]]) -> T:
        """
        Method that should be overriden by your implementing class. It will be called by
        (_BaseParsingPlan).execute

        :param desired_type:
        :param file_path:
        :param encoding:
        :param options:
        :return:
        """
        pass

    @abstractmethod
    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, ParsingPlan], logger: Logger,
                         options: Dict[str, Dict[str, Any]]) -> T:
        """
        First parse all children from the parsing plan, then calls _build_object_from_parsed_children

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param options:
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
                 logger: Logger, accept_union_types: bool = False):
        """
        Constructor like in PersistedObject, but with an additional logger.

        :param object_type:
        :param obj_on_filesystem:
        :param parser:
        :param logger:
        """
        super(_BaseParsingPlan, self).__init__(object_type, obj_on_filesystem, parser,
                                               accept_union_types=accept_union_types)

        # -- logger
        check_var(logger, var_types=Logger, var_name='logger', enforce_not_none=False)
        self.logger = logger

    # flag used for create_parsing_plan logs (to prevent recursive print messages)
    thrd_locals = threading.local()

    def execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Overrides the parent method to add log messages.

        :param logger: the logger to use during parsing (optional: None is supported)
        :param options:
        :return:
        """
        in_root_call = False
        if logger is not None:
            # log only for the root object, not for the children that will be created by the code below
            if not hasattr(_BaseParsingPlan.thrd_locals, 'flag_exec') \
                    or _BaseParsingPlan.thrd_locals.flag_exec == 0:
                # print('Executing Parsing Plan for ' + str(self))
                logger.debug('Executing Parsing Plan for [{location}]'
                             ''.format(location=self.obj_on_fs_to_parse.get_pretty_location(append_file_ext=False)))
                _BaseParsingPlan.thrd_locals.flag_exec = 1
                in_root_call = True

        # Common log message
        logger.debug('(P) ' + get_parsing_plan_log_str(self.obj_on_fs_to_parse, self.obj_type,
                                                       log_only_last=not in_root_call, parser=self.parser))

        try:
            res = super(_BaseParsingPlan, self).execute(logger, options)
            if logger.isEnabledFor(DEBUG):
                logger.info('(P) {loc} -> {type} SUCCESS !'
                            ''.format(loc=self.obj_on_fs_to_parse.get_pretty_location(
                    blank_parent_part=not GLOBAL_CONFIG.full_paths_in_logs,
                    compact_file_ext=True),
                    type=get_pretty_type_str(self.obj_type)))
            else:
                logger.info('SUCCESS parsed [{loc}] as a [{type}] successfully. Parser used was [{parser}]'
                            ''.format(loc=self.obj_on_fs_to_parse.get_pretty_location(compact_file_ext=True),
                                      type=get_pretty_type_str(self.obj_type),
                                      parser=str(self.parser)))
            if in_root_call:
                # print('Completed parsing successfully')
                logger.debug('Completed parsing successfully')
            return res

        finally:
            # remove threadlocal flag if needed
            if in_root_call:
                _BaseParsingPlan.thrd_locals.flag_exec = 0

    def _execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of the parent class method.
        Checks that self.parser is a _BaseParser, and calls the appropriate parsing method.

        :param logger:
        :param options:
        :return:
        """
        if isinstance(self.parser, _BaseParser):
            if (not self.is_singlefile) and self.parser.supports_multifile():
                return self.parser._parse_multifile(self.obj_type, self.obj_on_fs_to_parse,
                                                    self._get_children_parsing_plan(), logger, options)

            elif self.is_singlefile and self.parser.supports_singlefile():
                return self.parser._parse_singlefile(self.obj_type, self.get_singlefile_path(),
                                                     self.get_singlefile_encoding(), logger, options)
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
    * (1) a declaration (= a _BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.

    This class extends _BaseParser to add recursivity to the parsing plan creation step. It also adds logging
    capabilities in the parent 'create_parsing_plan' method.

    So what remains to the implementation ?
    * This class extends _BaseParserDeclarationForRegistries. So you may call its super constructor to declare the
    parser capabilities (see _BaseParserDeclarationForRegistries.__init__ for details)
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
                     logger: Logger, accept_union_types: bool = False):
            """
            Constructor with recursive construction of all children parsing plan. The plan for all children is then
            stored in a field, so that _get_children_parsing_plan may get it later (it was a parent method to implement)

            :param object_type:
            :param obj_on_filesystem:
            :param parser:
            :param logger:
            """

            # -- super
            super(AnyParser._RecursiveParsingPlan, self).__init__(object_type, obj_on_filesystem, parser, logger,
                                                                  accept_union_types=accept_union_types)

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

    # note: it is normal that signature does not match parent (additional option).
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
            logger.debug('Building a parsing plan to parse [{location}] into a {type}'
                         ''.format(location=filesystem_object.get_pretty_location(append_file_ext=False),
                                   type=get_pretty_type_str(desired_type)))
            AnyParser.thrd_locals.flag_init = 1
            in_root_call = True

        # -- create the parsing plan
        try:
            pp = self._create_parsing_plan(desired_type, filesystem_object, logger, log_only_last=(not _main_call))
        finally:
            # remove threadlocal flag if needed
            if in_root_call:
                AnyParser.thrd_locals.flag_init = 0

        # -- log success only if in root call
        if in_root_call:
            # print('Parsing Plan created successfully')
            logger.debug('Parsing Plan created successfully')

        # -- finally return
        return pp

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                             log_only_last: bool = False):
        """
        Adds a log message and creates a recursive parsing plan.

        :param desired_type:
        :param filesystem_object:
        :param logger:
        :param log_only_last: a flag to only log the last part of the file path (default False)
        :return:
        """
        logger.debug('(B) ' + get_parsing_plan_log_str(filesystem_object, desired_type,
                                                       log_only_last=log_only_last, parser=self))
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
    * (1) a declaration (= a _BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.
    """

    def __init__(self, supported_exts: Set[str], supported_types: Set[Type], can_chain: bool = True,
                 is_able_to_parse_func: Callable[[bool, Type[Any]], bool] = None):
        """
        Constructor, with
        * a mandatory set of supported extensions
        * an optional set of supported object types (otherwise the parser supports any object type)

        :param supported_exts: mandatory list of supported singlefile extensions ('.txt', '.json' ...)
        :param supported_types: mandatory list of supported object types that may be parsed
        :param can_chain: a boolean (default True) indicating if converters can be appended at the end of this
        parser to create a chain. Dont change this except if it really can never make sense.
        :param is_able_to_parse_func: an optional custom function to allow parsers to reject some types. This function
        signature should be my_func(strict_mode, desired_type) -> bool
        """
        # -- check that we are really a singlefile parser
        if supported_exts is not None and MULTIFILE_EXT in supported_exts:
            raise ValueError('Cannot create a SingleFileParser supporting multifile extensions ! Use AnyParser to '
                             'support both, or MultiFileParser to support MultiFile')
        # -- call super
        super(SingleFileParser, self).__init__(supported_types=supported_types, supported_exts=supported_exts,
                                               can_chain=can_chain, is_able_to_parse_func=is_able_to_parse_func)

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
                         logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of the parent method : since this is a singlefile parser, this is not implemented.

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param options:
        :return:
        """
        raise Exception('Not implemented since this is a SingleFileParser')


class MultiFileParser(AnyParser):
    """
    Represents parser able to parse multifiles only (not singlefiles).

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a _BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.
    """

    def __init__(self, supported_types: Set[Type[T]], can_chain: bool = True,
                 is_able_to_parse_func: Callable[[bool, Type[Any]], bool] = None):
        """
        Constructor, with a mandatory list of supported object types

        :param supported_types: mandatory list of supported object types that may be parsed
        :param can_chain: a boolean (default True) indicating if converters can be appended at the end of this
        parser to create a chain. Dont change this except if it really can never make sense.
        :param is_able_to_parse_func: an optional custom function to allow parsers to reject some types. This function
        signature should be my_func(strict_mode, desired_type) -> bool
        """
        super(MultiFileParser, self).__init__(supported_types=supported_types, supported_exts={MULTIFILE_EXT},
                                              can_chain=can_chain, is_able_to_parse_func=is_able_to_parse_func)

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of the parent method : since this is a multifile parser, this is not implemented.

        :param desired_type:
        :param file_path:
        :param encoding:
        :param logger:
        :param options:
        :return:
        """
        raise Exception('Not implemented since this is a MultiFileParser')


# aliases used in SingleFileParserFunction
ParsingMethodForStream = Callable[[Type[T], TextIOBase, Logger], T]
ParsingMethodForFile = Callable[[Type[T], str, str, Logger], T]
parsing_method_stream_example_signature_str = 'def my_parse_fun(desired_type: Type[T], stream: TextIOBase, ' \
                                              'logger: Logger, **kwargs) -> T'
parsing_method_file_example_signature_str = 'def my_parse_fun(desired_type: Type[T], path: str, encoding: str, ' \
                                            'logger: Logger, **kwargs) -> T'


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
              'Note that the parsing function signature should be ' + parsing_method_stream_example_signature_str \
              + ' (streaming=True) or ' + parsing_method_file_example_signature_str + ' (streaming=False).' \
              'Caught error message is : ' + caught.__class__.__name__ + ' : ' + str(caught)
        return CaughtTypeError(msg).with_traceback(caught.__traceback__)


class SingleFileParserFunction(SingleFileParser): #metaclass=ABCMeta
    """
    Represents a parser for singlefiles relying on a parser_function.

    Reminder from 'Parser' parent class: a parser is basically
    * (1) a declaration (= a _BaseParserDeclarationForRegistries) of supported object types and supported file
    extensions. It is possible to declare that a parser is able to parse Any type (typically, a pickle parser). It is
    also possible to declare a custom function telling if a specific object type is supported, in order to accept most
    types but not all. See constructor for details.
    * (2) a factory able to create ParsingPlan[T] objects on demand in order to parse files into objects of type T.

    Two kind of parser_function may be provided as implementations:
    * if streaming_mode=True (default), this class handles opening and closing the file, and parser_function should
    have a signature such as my_func(desired_type: Type[T], opened_file: TextIOBase, logger: Logger, **kwargs) -> T
    * if streaming_mode=False, this class does not handle opening and closing the file. parser_function should be a
    my_func(desired_type: Type[T], file_path: str, encoding: str, logger: Logger, **kwargs) -> T
    """

    def __init__(self, parser_function: Union[ParsingMethodForStream, ParsingMethodForFile],
                 supported_types: Set[Type[T]], supported_exts: Set[str], streaming_mode: bool = True,
                 custom_name: str = None, function_args: dict = None, option_hints: Callable[[], str] = None):
        """
        Constructor from a parser function , a mandatory set of supported types, and a mandatory set of supported
        extensions.

        Two kind of parser_function may be provided as implementations:
        * if streaming_mode=True (default), this class handles opening and closing the file, and parser_function should
        have a signature such as my_func(desired_type: Type[T], opened_file: TextIOBase, **kwargs) -> T
        * if streaming_mode=False, this class does not handle opening and closing the file. parser_function should be a
        my_func(desired_type: Type[T], file_path: str, encoding: str, **kwargs) -> T

        :param parser_function:
        :param streaming_mode: an optional boolean (default True) indicating if the function should be called with an
        open stream or with a file path
        :param supported_types: mandatory set of supported types, or {
        :param supported_exts: mandatory set of supported singlefile extensions ('.txt', '.json' ...)
        :param function_args: kwargs that will be passed to the function at every call
        :param option_hints: an optional method returning a string containing the options descriptions
        """
        super(SingleFileParserFunction, self).__init__(supported_types=supported_types, supported_exts=supported_exts)

        # -- check the custom name
        check_var(custom_name, var_types=str, var_name='custom_name', enforce_not_none=False)
        self._custom_name = custom_name

        # -- check the function
        # TODO check the function signature to prevent TypeErrors to happen (and then remove the catch block below in _parse_singlefile)
        check_var(parser_function, var_types=Callable, var_name='parser_function')
        self._parser_func = parser_function

        # -- check the streaming mode
        check_var(streaming_mode, var_types=bool, var_name='streaming_mode')
        self._streaming_mode = streaming_mode

        # -- remember the static args values
        check_var(function_args, var_types=dict, var_name='function_args', enforce_not_none=False)
        self.function_args = function_args

        # -- option hints
        check_var(option_hints, var_types=Callable, var_name='option_hints', enforce_not_none=False)
        self._option_hints_func = option_hints

    def __str__(self):
        if self._custom_name:
            return '<' + self._custom_name + '>'
        else:
            if self.function_args is None:
                return '<' + self._parser_func.__name__ + '>'
            else:
                return '<' + self._parser_func.__name__ + '(' + str(self.function_args) + ')>'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def get_id_for_options(self):
        return self._custom_name or self._parser_func.__name__

    def options_hints(self):
        """
        Returns a string representing the options available for this converter
        :return:
        """
        return self.get_id_for_options() + ': ' \
               + ('No declared option' if self._option_hints_func is None else self._option_hints_func())

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          options: Dict[str, Dict[str, Any]]) -> T:
        """
        Relies on the inner parsing function to parse the file.
        If _streaming_mode is True, the file will be opened and closed by this method. Otherwise the parsing function
        will be responsible to open and close.

        :param desired_type:
        :param file_path:
        :param encoding:
        :param options:
        :return:
        """
        opts = get_options_for_id(options, self.get_id_for_options())

        if self._streaming_mode:

            # We open the stream, and let the function parse from it
            file_stream = None
            try:
                # Open the file with the appropriate encoding
                file_stream = open(file_path, 'r', encoding=encoding)

                # Apply the parsing function
                if self.function_args is None:
                    return self._parser_func(desired_type, file_stream, logger, **opts)
                else:
                    return self._parser_func(desired_type, file_stream, logger, **self.function_args, **opts)

            except TypeError as e:
                raise CaughtTypeError.create(self._parser_func, e)

            finally:
                if file_stream is not None:
                    # Close the File in any case
                    file_stream.close()

        else:
            # the parsing function will open the file itself
            if self.function_args is None:
                return self._parser_func(desired_type, file_path, encoding, logger, **opts)
            else:
                return self._parser_func(desired_type, file_path, encoding, logger, **self.function_args, **opts)
