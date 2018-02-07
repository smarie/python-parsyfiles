from collections import Mapping, ItemsView, ValuesView, MutableSet, MutableSequence, Sequence, OrderedDict
from io import TextIOBase
from logging import Logger
from typing import Dict, Any, List, Union, Type, Set, Tuple, Callable, AbstractSet

from parsyfiles import GLOBAL_CONFIG
from parsyfiles.converting_core import Converter, ConverterFunction
from parsyfiles.filesystem_mapping import PersistedObject, FolderAndFilesStructureError
from parsyfiles.parsing_core import SingleFileParserFunction, AnyParser, MultiFileParser, ParsingPlan, T
from parsyfiles.parsing_registries import ParserFinder, ConversionFinder
from parsyfiles.type_inspection_tools import _extract_collection_base_type, get_pretty_type_str, get_base_generic_type, \
    is_collection
from parsyfiles.var_checker import check_var


# ---- Redundant with read csv with one column... => removed -----
# def read_list_from_properties(desired_type: Type[dict], file_object: TextIOBase,
#                               logger: Logger, *args, **kwargs) -> List[str]:
#     """
#     Reads a text file into a list of string lines
#     :param desired_type:
#     :param file_object:
#     :param logger:
#     :param args:
#     :param kwargs:
#     :return:
#     """
#     return [line_str for line_str in file_object]


def read_dict_or_list_from_json(desired_type: Type[dict], file_object: TextIOBase,
                                logger: Logger, conversion_finder: ConversionFinder, **kwargs) -> Dict[str, Any]:
    """
    Helper method to read a dictionary from a .json file using json library
    :param file_object:
    :return:
    """
    # lazy import in order not to force use of jprops
    import json
    res = json.load(file_object)

    # convert if required
    return ConversionFinder.convert_collection_values_according_to_pep(res, desired_type, conversion_finder, logger, **kwargs)


class DictOfDict(Dict[str, Dict[str, Any]]):
    """
    Represents a dictionary of dictionaries. We can't use an alias here otherwise 'dict' would be considered a
    subclass of 'DictOfDict'
    """
    pass


class SetFacadeForDict(MutableSet, set):
    """
    A set facade for an inner dictionary. The set contains the dict values. set inheritance is is actually only here to
    be sure that the framework checks for type pass  correctly ; MutableSequence completely hides the method
    implementations in set
    """

    def __init__(self, inner_dict):
        check_var(inner_dict, var_types=dict, var_name='inner_dict')
        self._inner_dict = inner_dict

    def __contains__(self, x):
        return x in self._inner_dict.values()

    def __repr__(self, *args, **kwargs):
        # maybe rather check if underlying dict is loaded and in this case dont load all ?
        return repr(set(self._inner_dict.values()))

    def __len__(self):
        return len(self._inner_dict)

    def __iter__(self):
        return iter(self._inner_dict.values())

    def add(self, value):
        raise NotImplementedError('This set is read-only')

    def discard(self, value):
        raise NotImplementedError('This set is read-only')


class _KeySortedSequenceFacadeForDict(MutableSequence):
    """
    A sequence (list/tuple) facade for an inner dictionary. The sequence contains the dict values in alphabetical order
    of the keys.
    """

    def __init__(self, inner_dict):
        check_var(inner_dict, var_types=dict, var_name='inner_dict')
        self._inner_dict = inner_dict

    def __getitem__(self, index):
        # the key is the corresponding item in the list of keys, taken in alphabetical order
        key = sorted(self._inner_dict.keys())[index]
        return self._inner_dict[key]

    def __len__(self):
        return len(self._inner_dict)

    def insert(self, index, value):
        raise NotImplementedError('This sequence is read-only')

    def __setitem__(self, index, value):
        raise NotImplementedError('This sequence is read-only')

    def __delitem__(self, index):
        raise NotImplementedError('This sequence is read-only')


class KeySortedListFacadeForDict(_KeySortedSequenceFacadeForDict, list):
    """
    list inheritance is actually only here to be sure that the framework checks for type pass
    correctly ; MutableSequence completely hides the method implementations in list
    """
    def __repr__(self, *args, **kwargs):
        # maybe rather check if underlying dict is loaded and in this case dont load all ?
        return repr(list(self))


class KeySortedTupleFacadeForDict(_KeySortedSequenceFacadeForDict, tuple):
    """
    tuple inheritance is actually only here to be sure that the framework checks for type pass
    correctly ; MutableSequence completely hides the method implementations in tuple
    """
    def __repr__(self, *args, **kwargs):
        # maybe rather check if underlying dict is loaded and in this case dont load all ?
        return repr(tuple(self))


class LazyDictionary(dict):
    """
    A dictionary that loads items lazily. It is read-only and relies on code from collections.Mapping for proper
    implementation for values() and items().
    """

    class ReadOnlyDictProxy(Mapping):
        """
        A read-only proxy for a dictionary
        """
        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            return self._data[key]

        def __len__(self):
            return len(self._data)

        def __iter__(self):
            return iter(self._data)

    def __init__(self, lazyloadable_keys: List[str], loading_method: Callable[[str], Any]):
        """
        Constructor with a list of keys for which the value can actually be loaded later (when needed) from a
        loading_method.

        :param lazyloadable_keys:
        :param loading_method:
        """
        # initialize the inner dictionary
        self.inner_dict = OrderedDict()
        self.inner_dict_readonly_wrapper = LazyDictionary.ReadOnlyDictProxy(self.inner_dict)

        # store the list of loadable keys
        check_var(lazyloadable_keys, var_types=list, var_name='initial_keys')
        self.lazyloadable_keys = lazyloadable_keys

        # loading method
        check_var(loading_method, var_types=Callable, var_name='loading_method')
        self.loading_method = loading_method

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if len(self.inner_dict) == len(self):
            return self.inner_dict.__repr__()
        else:
            return 'LazyDictionary - not entirely loaded yet. Keys: ' + str(self.lazyloadable_keys)

    def __contains__(self, item):
        return self.lazyloadable_keys.__contains__(item)

    def keys(self):
        return OrderedDict.fromkeys(self.lazyloadable_keys).keys()

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, name):
        """
        Implementation of the "lazyness" / cache mechanism
        :param name:
        :return:
        """
        if name in self.inner_dict.keys():
            # already retrieved: return the cached value
            return self.inner_dict[name]

        elif name in self.lazyloadable_keys:
            # not yet retrieved: load the value
            val = self.loading_method(name)
            # remember it for next time
            self.inner_dict[name] = val
            return val
        else:
            # unknown key: error as usual
            raise KeyError(name)

    def __len__(self):
        return len(self.lazyloadable_keys)

    def __iter__(self):
        return iter(self.lazyloadable_keys)

    def items(self):
        "implementation of a view, from collections.Mapping"
        return ItemsView(self)

    def values(self):
        "implementation of a view, from collections.Mapping"
        return ValuesView(self)

    def __getattr__(self, name):
        return getattr(self.inner_dict_readonly_wrapper, name)


class MultifileCollectionParser(MultiFileParser):
    """
    This class is able to read any collection type as long as they are PEP484 specified (Dict, List, Set, Tuple), from
     multifile objects. It simply inspects the required type to find the base type expected for items of the collection,
     and relies on a ParserFinder to parse each of them before creating the final collection.
    """
    def __init__(self, parser_finder: ParserFinder):
        """
        Constructor. The parser_finder will be used to find the most appropriate parser to parse each item of the
        collection
        :param parser_finder:
        """
        # prevent chaining with converters. Indeed otherwise the information about the inner collection type will not
        # be known, therefore it will be impossible to parse the multifile children
        super(MultifileCollectionParser, self).__init__(supported_types={Dict, List, Set, Tuple}, can_chain=False)
        self.parser_finder = parser_finder

    def __str__(self):
        return 'Multifile Collection parser (' + str(self.parser_finder) + ')'
        #(based on \'' + str(self.parser_finder) + '\' to find the parser for each item)'

    # def is_able_to_parse(self, desired_type: Type[Any], desired_ext: str, strict: bool):
    #     if desired_type is None:
    #         return True, True
    #     else:
    #         if is_collection(desired_type):
    #             return True, True
    #         else:
    #             return False, None
    #         # try:
    #         #     subtype, key_type = _extract_collection_base_type(desired_type)
    #         #     return True, True
    #         # except:
    #         #     return False, None

    def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[Any],
                                                 logger: Logger) -> Dict[str, Any]:
        """
        Simply inspects the required type to find the base type expected for items of the collection,
        and relies on the ParserFinder to find the parsing plan

        :param obj_on_fs:
        :param desired_type:
        :param logger:
        :return:
        """
        # nb of file children
        n_children = len(obj_on_fs.get_multifile_children())

        # first extract base collection type
        subtypes, key_type = _extract_collection_base_type(desired_type)

        if isinstance(subtypes, tuple):
            # -- check the tuple length
            if n_children != len(subtypes):
                raise FolderAndFilesStructureError.create_for_multifile_tuple(obj_on_fs, len(subtypes),
                                                                              len(obj_on_fs.get_multifile_children()))
        else:
            # -- repeat the subtype n times
            subtypes = [subtypes] * n_children

        # -- for each child create a plan with the appropriate parser
        children_plan = OrderedDict()
        # use sorting for reproducible results in case of multiple errors
        for (child_name, child_fileobject), child_typ in zip(sorted(obj_on_fs.get_multifile_children().items()),
                                                           subtypes):
            # -- use the parserfinder to find the plan
            t, child_parser = self.parser_finder.build_parser_for_fileobject_and_desiredtype(child_fileobject, 
                                                                                             child_typ, logger)
            children_plan[child_name] = child_parser.create_parsing_plan(t, child_fileobject, logger,
                                                                         _main_call=False)

        return children_plan

    def options_hints(self):
        return self.get_id_for_options() + ': \n' \
               ' -- \'lazy_parsing\': a boolean indicating if parsing should be done later, when the item is actually ' \
               'used. \n' + \
               ' -- \'background_parsing\': not implemented yet'

    def _parse_multifile(self, desired_type: Type[Union[Dict, List, Set, Tuple]], obj: PersistedObject,
                         parsing_plan_for_children: Dict[str, ParsingPlan], logger: Logger,
                         options: Dict[str, Dict[str, Any]]) \
            -> Union[Dict, List, Set, Tuple]:
        """
        Options may contain a section with id 'MultifileCollectionParser' containing the following options:
        * lazy_parsing: if True, the method will return immediately without parsing all the contents. Instead, the
        returned collection will perform the parsing the first time an item is required.
        * background_parsing: if True, the method will return immediately while a thread parses all the contents in
        the background. Note that users cannot set both lazy_parsing and background_parsing to True at the same time

        :param desired_type:
        :param obj:
        :param parsing_plan_for_children:
        :param logger:
        :param options:
        :return:
        """

        # first get the options and check them
        lazy_parsing = False
        background_parsing = False

        opts = self._get_applicable_options(options)
        for opt_key, opt_val in opts.items():
            if opt_key is 'lazy_parsing':
                lazy_parsing = opt_val
            elif opt_key is 'background_parsing':
                background_parsing = opt_val
            else:
                raise Exception('Invalid option in MultiFileCollectionParser : ' + opt_key)

        check_var(lazy_parsing, var_types=bool, var_name='lazy_parsing')
        check_var(background_parsing, var_types=bool, var_name='background_parsing')

        if lazy_parsing and background_parsing:
            raise ValueError('lazy_parsing and background_parsing cannot be set to true at the same time')

        if lazy_parsing:
            # build a lazy dictionary
            results = LazyDictionary(sorted(list(parsing_plan_for_children.keys())),
                                     loading_method=lambda x: parsing_plan_for_children[x].execute(logger, options))
            # logger.debug('Assembling a ' + get_pretty_type_str(desired_type) + ' from all children of ' + str(obj)
            #             + ' (lazy parsing: children will be parsed when used) ')
            logger.debug('(P) {loc} : lazy parsing ON, children will be parsed only if/when used'.format(
                loc=obj.get_pretty_location(blank_parent_part=(not GLOBAL_CONFIG.full_paths_in_logs),
                                            compact_file_ext=True)))

        elif background_parsing:
            # -- TODO create a thread to perform the parsing in the background
            raise ValueError('Background parsing is not yet supported')

        else:
            # Parse right now
            results = OrderedDict()

            # parse all children according to their plan
            # -- use key-based sorting on children to lead to reproducible results
            # (in case of multiple errors, the same error will show up first everytime)
            for child_name, child_plan in sorted(parsing_plan_for_children.items()):
                results[child_name] = child_plan.execute(logger, options)
            # logger.debug('Assembling a ' + get_pretty_type_str(desired_type) + ' from all parsed children of '
            #             + str(obj))

        if issubclass(desired_type, list):
            # return a list facade
            return KeySortedListFacadeForDict(results)
        elif issubclass(desired_type, tuple):
            # return a tuple facade
            return KeySortedTupleFacadeForDict(results)
        elif issubclass(desired_type, set):
            # return a set facade
            return SetFacadeForDict(results)
        elif issubclass(desired_type, dict):
            # return the dict directly
            return results
        else:
            raise TypeError('Cannot build the desired collection out of the multifile children: desired type is not '
                            'supported: ' + get_pretty_type_str(desired_type))


# Dont propose this kind of conversion, as it is too 'special' and may vary depending the need
# def dict_to_list():


def list_to_set(desired_type: Type[T], contents_list: List[str], logger: Logger,
                conversion_finder: ConversionFinder, **kwargs) -> Set:

    # don't create a facade/proxy, since anyway we'll try to convert the values below
    res = set(contents_list)

    # convert if required
    return ConversionFinder.convert_collection_values_according_to_pep(res, desired_type, conversion_finder, logger,
                                                                       **kwargs)


def list_to_tuple(desired_type: Type[T], contents_list: List[str], logger: Logger,
                  conversion_finder: ConversionFinder, **kwargs) -> Tuple:

    # don't create a facade/proxy, since anyway we'll try to convert the values below
    res = tuple(contents_list)

    # convert if required
    return ConversionFinder.convert_collection_values_according_to_pep(res, desired_type, conversion_finder, logger,
                                                                       **kwargs)


def get_default_collection_parsers(parser_finder: ParserFinder, conversion_finder: ConversionFinder) -> List[AnyParser]:
    """
    Utility method to return the default parsers able to parse a dictionary from a file.
    :return:
    """
    return [SingleFileParserFunction(parser_function=read_dict_or_list_from_json,
                                     streaming_mode=True, custom_name='read_dict_or_list_from_json',
                                     supported_exts={'.json'},
                                     supported_types={dict, list},
                                     function_args={'conversion_finder': conversion_finder}),
            MultifileCollectionParser(parser_finder)
            ]


def get_default_collection_converters(conversion_finder: ConversionFinder) -> List[Union[Converter[Any, dict], Converter[dict, Any]]]:
    """
    Utility method to return the default converters associated to dict (from dict to other type,
    and from other type to dict)
    :return:
    """
    return [ConverterFunction(from_type=List, to_type=Set, conversion_method=list_to_set, custom_name='list_to_set',
                              function_args={'conversion_finder': conversion_finder}),
            ConverterFunction(from_type=List, to_type=Tuple, conversion_method=list_to_tuple,
                              custom_name='list_to_tuple', function_args={'conversion_finder': conversion_finder})]
