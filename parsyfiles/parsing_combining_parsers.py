import traceback
from collections import Mapping
from io import StringIO, TextIOBase
from logging import Logger, DEBUG
from typing import Type, Dict, Any, List, Iterable, Union, Tuple

from parsyfiles.global_config import GLOBAL_CONFIG
from parsyfiles.converting_core import Converter, T, S, ConversionChain, AnyObject
from parsyfiles.filesystem_mapping import PersistedObject
from parsyfiles.parsing_core import AnyParser
from parsyfiles.parsing_core_api import get_parsing_plan_log_str, Parser, ParsingPlan, ParsingException
from parsyfiles.type_inspection_tools import get_pretty_type_str, get_base_generic_type
from parsyfiles.var_checker import check_var


class DelegatingParsingPlan(ParsingPlan[T]):
    """
    A wrapper for a parsing plan.
    """

    # noinspection PyMissingConstructor
    def __init__(self, pp):
        # -- explicitly DONT use base constructor : we are just a proxy
        # super(CascadingParser.ActiveParsingPlan, self).__init__()
        self.pp = pp

    def __str__(self):
        return str(self.pp) + ' (proxy)'

    def execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        return self.pp.execute(logger, options)

    def _execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        return self.pp._execute(logger, options)

    def _get_children_parsing_plan(self) -> Dict[str, ParsingPlan]:
        return self.pp._get_children_parsing_plan()

    def __getattr__(self, item):
        # Redirect anything that is not implemented here to the underlying parsing plan.
        # this is called only if the attribute was not found the usual way

        # easy version of the dynamic proxy just to save time :)
        # see http://code.activestate.com/recipes/496741-object-proxying/ for "the answer"
        pp = object.__getattribute__(self, 'pp')
        if hasattr(pp, item):
            return getattr(pp, item)
        else:
            raise AttributeError('\'' + self.__class__.__name__ + '\' object has no attribute \'' + item + '\'')


class DelegatingParser(AnyParser):
    """
    A parser that delegates all the parsing tasks to another implementation ; and therefore does not implement directly
    the corresponding parsing submethods, just the '_create_parsing_plan'
    """

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of AnyParser API with an exception
        """
        raise Exception('This should never happen, since this parser relies on underlying parsers')

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Implementation of AnyParser API
        """
        raise Exception('This should never happen, since this parser relies on underlying parsers')

    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan],
                         logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of AnyParser API
        """
        raise Exception('This should never happen, since this parser relies on underlying parsers')


def print_error_to_io_stream(err: Exception, io: TextIOBase, print_big_traceback : bool = True):
    """
    Utility method to print an exception's content to a stream

    :param err:
    :param io:
    :param print_big_traceback:
    :return:
    """
    if print_big_traceback:
        traceback.print_tb(err.__traceback__, file=io, limit=-GLOBAL_CONFIG.multiple_errors_tb_limit)
    else:
        traceback.print_tb(err.__traceback__, file=io, limit=-1)
    io.writelines('  ' + str(err.__class__.__name__) + ' : ' + str(err))


class CascadeError(ParsingException):
    """
    Raised whenever parsing failed for all parsers in a CascadingParser. This object provides an overview of errors
    caught in the multiple parsers
    """

    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(CascadeError, self).__init__(contents)

    @staticmethod
    def create_for_parsing_plan_creation(origin_parser: AnyParser, parent_plan: AnyParser._RecursiveParsingPlan[T],
                                         caught: Dict[AnyParser, Exception]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param origin_parser:
        :param parent_plan:
        :param caught:
        :return:
        """
        base_msg = 'Error while trying to build parsing plan to parse \'' + str(parent_plan.obj_on_fs_to_parse) \
                   + '\' : \n' \
                   + '   - required object type is \'' + get_pretty_type_str(parent_plan.obj_type) + '\' \n' \
                   + '   - cascading parser is : ' + str(origin_parser) + '\n'

        msg = StringIO()
        if len(list(caught.keys())) > 0:
            msg.writelines('   - parsers tried are : \n      * ')
            msg.writelines('\n      * '.join([str(p) for p in caught.keys()]))
            msg.writelines(' \n Caught the following exceptions: \n')

            for p, err in caught.items():
                msg.writelines('--------------- From ' + str(p) + ' caught: \n')
                print_error_to_io_stream(err, msg)
                msg.write('\n')

        return CascadeError(base_msg + msg.getvalue())

    @staticmethod
    def create_for_execution(origin_parser: AnyParser, parent_plan: AnyParser._RecursiveParsingPlan[T],
                             caught_exec: Dict[AnyParser, Exception]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param origin_parser:
        :param parent_plan:
        :param caught_exec:
        :return:
        """
        base_msg = 'Error while trying to execute parsing plan to parse \'' + str(parent_plan.obj_on_fs_to_parse) \
                   + '\' : \n' \
                   + '   - required object type is \'' + get_pretty_type_str(parent_plan.obj_type) + '\' \n' \
                   + '   - cascading parser is : ' + str(origin_parser) + '\n'

        msg = StringIO()
        if len(list(caught_exec.keys())) > 0:
            msg.writelines('   - parsers tried are : \n      * ')
            msg.writelines('\n      * '.join([str(p) for p in caught_exec.keys()]))
            msg.writelines(' \n Caught the following exceptions: \n')

            for p, err in caught_exec.items():
                msg.writelines('--------------- From ' + str(p) + ' caught: \n')
                print_error_to_io_stream(err, msg)
                msg.write('\n')

        return CascadeError(base_msg + msg.getvalue())


class CascadingParser(DelegatingParser):
    """
    Represents a cascade of parsers that are tried in order: the first parser is used, then if it fails the second is
    used, etc. If all parsers failed, a CascadeError is thrown in order to provide an overview of all errors.
    Note that before switching to another parser, a new parsing plan is rebuilt with that new parser.

    Finally note that this class can either be used to create a cascade of parsers for the same destination type, or
    for different destination types (for example in case of a Union)
    """
    def __init__(self, parsers: Union[Iterable[AnyParser], Dict[Type, Iterable[AnyParser]]] = None):
        """
        Constructor from an initial list of parsers
        :param parsers:
        """

        # -- init
        # explicitly DONT use base constructor
        # super(CascadingParser, self).__init__(supported_types=set(), supported_exts=set())
        self.configured = False
        self._parsers_list = []

        if parsers is not None:
            check_var(parsers, var_types=Iterable, var_name='parsers')
            if isinstance(parsers, Mapping):
                for typ, parser in parsers.items():
                    self.add_parser_to_cascade(parser, typ)
            else:
                for parser in parsers:
                    self.add_parser_to_cascade(parser)

    def __str__(self):
        if len(self._parsers_list) > 1:
            first_typ = self._parsers_list[0][0]
            if all([p[0] is None for p in self._parsers_list[1:]]):
                return "[Try '{first}' then '{rest}']" \
                       "".format(first=self._parsers_list[0][1],
                                 rest="' then '".join([str(p[1]) for p in self._parsers_list[1:]]) + ']')
            else:
                return "[Try '{first}' -> [{first_typ}] then {rest}]" \
                       "".format(first=self._parsers_list[0][1], first_typ=get_pretty_type_str(first_typ),
                                 rest=" then ".join(["'{p}' -> [{p_typ}]".format(p=p[1],
                                                                                 p_typ=get_pretty_type_str(p[0]))
                                                       for p in self._parsers_list[1:]]) + ']')
        elif len(self._parsers_list) == 1:
            # useless...
            return 'CascadingParser[' + str(self._parsers_list[0]) + ']'
        else:
            return 'CascadingParser[Empty]'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def add_parser_to_cascade(self, parser: AnyParser, typ: Type = None):
        """
        Adds the provided parser to this cascade. If this is the first parser, it will configure the cascade according
        to the parser capabilities (single and multifile support, extensions).
        Subsequent parsers will have to support the same capabilities at least, to be added.

        :param parser:
        :param typ:
        :return:
        """
        # the first parser added will configure the cascade
        if not self.configured:
            self.supported_exts = parser.supported_exts
            self.supported_types = parser.supported_types

        # check if new parser is compliant with previous ones
        if self.supports_singlefile():
            if not parser.supports_singlefile():
                raise ValueError(
                    'Cannot add this parser to this parsing cascade : it does not match the rest of the cascades '
                    'configuration (singlefile support)')

        if self.supports_multifile():
            if not parser.supports_multifile():
                raise ValueError(
                    'Cannot add this parser to this parsing cascade : it does not match the rest of the cascades '
                    'configuration (multifile support)')

        if AnyObject not in parser.supported_types:
            if typ is None:
                # in that case the expected types for this parser will be self.supported_types
                if AnyObject in self.supported_types:
                    raise ValueError(
                        'Cannot add this parser to this parsing cascade : it does not match the rest of the cascades '
                        'configuration (the cascade supports any type while the parser only supports '
                        + str(parser.supported_types) + ')')
                else:
                    missing_types = set(self.supported_types) - set(parser.supported_types)
                    if len(missing_types) > 0:
                        raise ValueError(
                            'Cannot add this parser to this parsing cascade : it does not match the rest of the '
                            'cascades configuration (supported types should at least contain the supported types '
                            'already in place. The parser misses type(s) ' + str(missing_types) + ')')
            else:
                if typ == AnyObject:
                    raise ValueError(
                        'Cannot add this parser to this parsing cascade : it does not match the expected type "Any", '
                        'it only supports ' + str(parser.supported_types))
                else:
                    if get_base_generic_type(typ) not in parser.supported_types:
                        raise ValueError(
                            'Cannot add this parser to this parsing cascade : it does not match the expected type ' +
                            str(typ) + ', it only supports ' + str(parser.supported_types))

        missing_exts = set(self.supported_exts) - set(parser.supported_exts)
        if len(missing_exts) > 0:
            raise ValueError(
                'Cannot add this parser to this parsing cascade : it does not match the rest of the cascades '
                'configuration (supported extensions should at least contain the supported extensions already in '
                'place. The parser misses extension(s) ' + str(missing_exts) + ')')

        # finally add it
        self._parsers_list.append((typ, parser))

    class ActiveParsingPlan(DelegatingParsingPlan[T]):
        """
        A wrapper for the currently active parsing plan, simply to provide a different string representation.
        """
        def __init__(self, pp, cascadeparser: 'CascadingParser'):
            # -- explicitly DONT use base constructor nor super
            DelegatingParsingPlan.__init__(self, pp)
            self.cascadeparser = cascadeparser

        def __str__(self):
            return str(self.pp) + ' (currently active parsing plan in ' + str(self.cascadeparser) + ')'

    class CascadingParsingPlan(ParsingPlan[T]):
        """
        Represents a parsing plan built by multiple parsers. It is at any time a proxy of the most appropriate parsing
        plan
        """

        def _execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
            raise NotImplementedError('This method is not implemented directly but through inner parsing plans. '
                                      'This should not be called normally')

        def __init__(self, desired_type: Type[T], obj_on_filesystem: PersistedObject, parser: AnyParser,
                     parser_list: List[Tuple[Type, Parser]], logger: Logger):

            # We accept that the desired type is a Union or a TypeVar
            # Indeed CascadingParser can both provide alternatives to the same type (no Union), 
            # or to different ones (Union)
            super(CascadingParser.CascadingParsingPlan, self).__init__(desired_type, obj_on_filesystem, parser,
                                                                       accept_union_types=True)

            # --parser list
            check_var(parser_list, var_types=list, var_name='parser_list', min_len=1)
            self.parser_list = parser_list

            # -- the variables that will contain the active parser and its parsing plan
            self.active_parser_idx = -1
            self.active_parsing_plan = None
            self.parsing_plan_creation_errors = dict()

            # -- activate the next one
            self.activate_next_working_parser(logger=logger)

        def activate_next_working_parser(self, already_caught_execution_errors: Dict[AnyParser, Exception] = None,
                                         logger: Logger = None):
            """
            Utility method to activate the next working parser. It iteratively asks each parser of the list to create
            a parsing plan, and stops at the first one that answers

            :param already_caught_execution_errors:
            :param logger:
            :return:
            """

            if (self.active_parser_idx+1) < len(self.parser_list):
                # ask each parser to create a parsing plan right here. Stop at the first working one
                for i in range(self.active_parser_idx+1, len(self.parser_list)):
                    typ, p = self.parser_list[i]
                    if i > 0:
                        # print('----- Rebuilding local parsing plan with next candidate parser:')
                        if logger is not None:
                            logger.info('Rebuilding local parsing plan with next candidate parser: ' + str(p))
                    try:
                        # -- try to rebuild a parsing plan with next parser, and remember it if is succeeds
                        self.active_parsing_plan = CascadingParser.ActiveParsingPlan(p.create_parsing_plan(
                            typ or self.obj_type, self.obj_on_fs_to_parse, self.logger, _main_call=False), self.parser)
                        self.active_parser_idx = i
                        if i > 0 and logger is not None:
                            logger.info('DONE Rebuilding local parsing plan for [{location}]. Resuming parsing...'
                                        ''.format(location=self.obj_on_fs_to_parse.get_pretty_location(
                                compact_file_ext=True)))
                        return

                    except Exception as e:
                        # -- log the error
                        msg = StringIO()
                        print_error_to_io_stream(e, msg, print_big_traceback=logger.isEnabledFor(DEBUG))
                        logger.warning('----- WARNING: Caught error while creating parsing plan with parser ' + str(p))
                        logger.warning(msg.getvalue())
                        # print('----- WARNING: Caught error while creating parsing plan with parser ' + str(p) + '.')
                        # print(msg.getvalue())
                        # (Note: we dont use warning because it does not show up in the correct order in the console)

                        # -- remember the error in order to create a CascadeError at the end in case of failure of all
                        self.parsing_plan_creation_errors[p] = e

            # no more parsers to try...
            if already_caught_execution_errors is None:
                raise CascadeError.create_for_parsing_plan_creation(self.parser, self,
                                                                    self.parsing_plan_creation_errors)
            else:
                caught = self.parsing_plan_creation_errors
                caught.update(already_caught_execution_errors)
                raise CascadeError.create_for_execution(self.parser, self, caught)

        def execute(self, logger: Logger, options: Dict[str, Dict[str, Any]]):
            """
            Delegates execution to currently active parser. In case of an exception, recompute the parsing plan and
            do it again on the next one.

            :param logger:
            :param options:
            :return:
            """
            if self.active_parsing_plan is not None:
                execution_errors = dict()
                while self.active_parsing_plan is not None:
                    try:
                        # -- try to execute current plan
                        return self.active_parsing_plan.execute(logger, options)

                    except Exception as e:
                        # -- log the error
                        if not logger.isEnabledFor(DEBUG):
                            logger.warning('ERROR while parsing [{location}] into a [{type}] using [{parser}]. '
                                           'Set log level to DEBUG for details'.format(
                                location=self.obj_on_fs_to_parse.get_pretty_location(compact_file_ext=True),
                                type=get_pretty_type_str(self.active_parsing_plan.obj_type),
                                parser=str(self.active_parsing_plan.parser), err_type=type(e).__name__, err=e))
                        else:
                            msg = StringIO()
                            print_error_to_io_stream(e, msg, print_big_traceback=logger.isEnabledFor(DEBUG))
                            logger.warning('  !! Caught error during execution !!')
                            logger.warning(msg.getvalue())
                        # print('----- WARNING: Caught error during execution : ')
                        # print(msg.getvalue())
                        # (Note: we dont use warning because it does not show up in the correct order in the console)

                        # -- remember the error in order to create a CascadeError at the end in case of failure of all
                        execution_errors[self.active_parsing_plan.parser] = e

                        # -- try to switch to the next parser of the cascade, if any
                        self.activate_next_working_parser(execution_errors, logger)

                caught = self.parsing_plan_creation_errors
                caught.update(execution_errors)
                raise CascadeError.create_for_execution(self.parser, self, caught)

            else:
                raise Exception('Cannot execute this parsing plan : empty parser list !')

    def _create_parsing_plan(self, desired_type: Type[T], filesystem_object: PersistedObject, logger: Logger,
                             log_only_last: bool = False) -> ParsingPlan[T]:
        """
        Creates a parsing plan to parse the given filesystem object into the given desired_type.
        This overrides the method in AnyParser, in order to provide a 'cascading' parsing plan

        :param desired_type:
        :param filesystem_object:
        :param logger:
        :param log_only_last: a flag to only log the last part of the file path (default False)
        :return:
        """
        # build the parsing plan
        logger.debug('(B) ' + get_parsing_plan_log_str(filesystem_object, desired_type,
                                                       log_only_last=log_only_last, parser=self))
        return CascadingParser.CascadingParsingPlan(desired_type, filesystem_object, self, self._parsers_list,
                                                    logger=logger)


class ParsingChain(AnyParser):
    """
    Represents a parsing chain made of a base parser and a list of converters.
    It creates a parsing plan as in AnyParser, but delegates the parsing methods of AnyParser to the base parser and
    then applies the converters
    """

    def __init__(self, base_parser: AnyParser, converter: Converter[S, T], strict: bool,
                 base_parser_chosen_dest_type: Type[S] = None):
        """
        Constructor from a base parser and a conversion chain.
        Even if the base parser is able to parse several types or even any type, at the moment converters only support
        *one* source type that cannot be 'any'. for this reason in this constructor the caller is expected to restrict
        the parser to a unique destination type explicitly

        :param base_parser:
        :param converter:
        :param strict:
        :param base_parser_chosen_dest_type
        """
        check_var(base_parser, var_types=AnyParser, var_name='base_parser')

        # Removed this check : in some cases, it makes sense
        # (for example use a generic parser to parse object A then convert A to B ; might be more convenient than using
        # the generic parser to parse B directly)
        #
        # if base_parser.is_generic():
        #     raise ValueError('Creating a parsing chain from a base parser able to parse any type is just pointless.')

        self._base_parser = base_parser

        # did the user explicitly restrict the destination type of the base parser ?
        if base_parser_chosen_dest_type is None:
            if len(base_parser.supported_types) != 1:
                raise ValueError('Cannot create a parsing chain from a parser that is able to parse several types '
                                 'without restricting it explicitly. Please set a value for '
                                 '\'base_parser_chosen_dest_type\'')
            else:
                # supported types = the parser's ones (that is, only 1)
                parser_out_type = next(iter(base_parser.supported_types))
        else:
            check_var(base_parser_chosen_dest_type, var_types=type, var_name='base_parser_chosen_dest_type')
            parser_out_type = base_parser_chosen_dest_type

        # set the converter
        check_var(converter, var_types=Converter, var_name='converter')
        if not converter.is_able_to_convert(strict=strict, from_type=parser_out_type, to_type=converter.to_type):
            raise ValueError('Cannot chain this parser and this converter : types are not consistent')

        self._converter = converter
        super(ParsingChain, self).__init__(supported_types={converter.to_type},
                                           supported_exts=base_parser.supported_exts)

        check_var(strict, var_types=bool, var_name='strict')
        self.strict = strict

    def __len__(self):
        return len(self._base_parser) + len(self._converter)

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
        # return 'ParsingChain<' + str(self._base_parser) + (' ' if len(self._converters_list) > 0 else '') + \
        #            ' '.join(['-> ' + str(converter) for converter in self._converters_list]) + '>'
        conv_str = str(self._converter)[1:-1] if isinstance(self._converter, ConversionChain) else str(self._converter)
        return '$' + str(self._base_parser) + ' => ' + conv_str + '$'

    def __repr__(self):
        # __repr__ is supposed to offer an unambiguous representation,
        # but pprint uses __repr__ so we'd like users to see the small and readable version
        return self.__str__()

    def options_hints(self):
        """
        Returns a string representing the options available for this parsing chain : it concatenates all options
        :return:
        """
        return self._base_parser.options_hints() + '\n' \
               + self._converter.options_hints()

    def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                          options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of AnyParser API
        """
        # first use the base parser to parse something compliant with the conversion chain
        first = self._base_parser._parse_singlefile(self._converter.from_type, file_path, encoding,
                                                    logger, options)

        # then apply the conversion chain
        return self._converter.convert(desired_type, first, logger, options)

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Implementation of AnyParser API
        """
        return self._base_parser._get_parsing_plan_for_multifile_children(obj_on_fs, self._converter.from_type, logger)
        # return self._base_parser._get_parsing_plan_for_multifile_children(obj_on_fs, desired_type, logger)

    def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, ParsingPlan],
                         logger: Logger, options: Dict[str, Dict[str, Any]]) -> T:
        """
        Implementation of AnyParser API
        """
        # first use the base parser
        # first = self._base_parser._parse_multifile(desired_type, obj, parsing_plan_for_children, logger, options)
        first = self._base_parser._parse_multifile(self._converter.from_type, obj, parsing_plan_for_children, logger,
                                                   options)

        # then apply the conversion chain
        return self._converter.convert(desired_type, first, logger, options)

    @staticmethod
    def are_worth_chaining(base_parser: Parser, to_type: Type[S], converter: Converter[S,T]) -> bool:
        """
        Utility method to check if it makes sense to chain this parser configured with the given to_type, with this
        converter.  It is an extension of ConverterChain.are_worth_chaining

        :param base_parser:
        :param to_type:
        :param converter:
        :return:
        """
        if isinstance(converter, ConversionChain):
            for conv in converter._converters_list:
                if not Parser.are_worth_chaining(base_parser, to_type, conv):
                    return False
            # all good
            return True
        else:
            return Parser.are_worth_chaining(base_parser, to_type, converter)
