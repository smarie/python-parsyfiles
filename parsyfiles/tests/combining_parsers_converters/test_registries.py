from collections import OrderedDict
from logging import Logger
from random import shuffle
from typing import Generic, TypeVar, Dict, Type, Any
from unittest import TestCase

from parsyfiles.converting_core import AnyObject
from parsyfiles.filesystem_mapping import MULTIFILE_EXT, PersistedObject
from parsyfiles.parsing_core import SingleFileParserFunction, MultiFileParser, AnyParser, T, _BaseParsingPlan
from parsyfiles.parsing_registries import ParserCache
from parsyfiles.type_inspection_tools import get_pretty_type_str


class TestParserRegistry(TestCase):
    """ This class tests the capabilities of parser registry to create all possible combinations in the
    right order """

    def setUp(self):
        """
        This setup function defines
        * the classes that will be used in the whole test class.
        * file extensions associated to one or several classes
        * parsers

        :return:
        """
        # defines the classes
        A, B, C, D = self.define_types()
        self.A, self.B, self.C, self.D,  = A, B, C, D
        self.all_types = {A, B, C, D, AnyObject}

        # create all combinations of file extensions
        all_a_exts, all_b_exts, all_c_exts, all_d_exts, all_extensions = self.define_file_extensions()
        self.all_extensions = all_extensions

        # defines the parsers
        self.all_parsers_for_a = set()
        self.all_parsers_for_b = set()
        self.all_parsers_for_c = set()
        self.all_parsers_for_d = set()
        self.all_parsers_generic = set()

        # *********** Specific SingleFile ************
        # -- one type
        def parse_a():
            pass

        def parse_b():
            pass

        def parse_c():
            pass

        def parse_d():
            pass

        a_parser_single = SingleFileParserFunction(parse_a, supported_types={A},
                                                   supported_exts=set(all_a_exts))
        b_parser_single = SingleFileParserFunction(parse_b, supported_types={B}, supported_exts=set(all_b_exts))
        c_parser_single = SingleFileParserFunction(parse_c, supported_types={C}, supported_exts=set(all_c_exts))
        d_parser_single = SingleFileParserFunction(parse_d, supported_types={D}, supported_exts=set(all_d_exts))
        parsers_specific_singlefile_onetype = [a_parser_single, b_parser_single, c_parser_single, d_parser_single]
        self.all_parsers_for_a.add(a_parser_single)
        self.all_parsers_for_b.add(b_parser_single)
        self.all_parsers_for_c.add(c_parser_single)
        self.all_parsers_for_d.add(d_parser_single)

        # -- several types
        def parse_a_or_d():
            pass

        def parse_b_or_c():
            pass

        ad_parser_single = SingleFileParserFunction(parse_a_or_d, supported_types={A, D},
                                                    supported_exts=set(all_a_exts).union(all_d_exts))
        bc_parser_single = SingleFileParserFunction(parse_b_or_c, supported_types={B, C},
                                                    supported_exts=set(all_b_exts).union(all_c_exts))
        parsers_specific_singlefile_severaltypes = [ad_parser_single, bc_parser_single]
        self.all_parsers_for_a.add(ad_parser_single)
        self.all_parsers_for_b.add(bc_parser_single)
        self.all_parsers_for_c.add(bc_parser_single)
        self.all_parsers_for_d.add(ad_parser_single)

        # ******** Specific Multifile ************
        class DummyMultifileParser(MultiFileParser):

            def __init__(self, supported_types):
                super(DummyMultifileParser, self).__init__(supported_types)

            def __str__(self):
                return 'MultifileParser for ' + str([get_pretty_type_str(typ) for typ in self.supported_types]) \
                       + 'for ' + str(self.supported_exts)

            def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                         logger: Logger) -> Dict[str, _BaseParsingPlan[Any]]:
                pass

            def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                                 parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan], logger: Logger,
                                 options: Dict[str, Dict[str, Any]]) -> T:
                pass

        # -- one type
        a_parser_multi = DummyMultifileParser(supported_types={A})
        b_parser_multi = DummyMultifileParser(supported_types={B})
        c_parser_multi = DummyMultifileParser(supported_types={C})
        d_parser_multi = DummyMultifileParser(supported_types={D})
        parsers_specific_multifile_onetype = [a_parser_multi, b_parser_multi, c_parser_multi, d_parser_multi]
        self.all_parsers_for_a.add(a_parser_multi)
        self.all_parsers_for_b.add(b_parser_multi)
        self.all_parsers_for_c.add(c_parser_multi)
        self.all_parsers_for_d.add(d_parser_multi)

        # -- several types
        bd_parser_multi = DummyMultifileParser(supported_types={B, D})
        ac_parser_multi = DummyMultifileParser(supported_types={A, C})
        parsers_specific_multifile_severaltypes = [bd_parser_multi, ac_parser_multi]
        self.all_parsers_for_a.add(ac_parser_multi)
        self.all_parsers_for_b.add(bd_parser_multi)
        self.all_parsers_for_c.add(ac_parser_multi)
        self.all_parsers_for_d.add(bd_parser_multi)

        # ******** Specific BOTH **************
        class DummyParser(AnyParser):

            def __init__(self, supported_types, supported_exts):
                super(DummyParser, self).__init__(supported_types=supported_types,
                                                  supported_exts=supported_exts)

            def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                         logger: Logger) -> Dict[str, _BaseParsingPlan[Any]]:
                pass

            def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                                 parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan], logger: Logger,
                                 options: Dict[str, Dict[str, Any]]) -> T:
                pass

            def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger,
                                  options: Dict[str, Dict[str, Any]]) -> T:
                pass

        # -- one type
        a_parser_both = DummyParser(supported_types={A}, supported_exts=set(all_a_exts))
        b_parser_both = DummyParser(supported_types={B}, supported_exts=set(all_b_exts))
        c_parser_both = DummyParser(supported_types={C}, supported_exts=set(all_c_exts))
        d_parser_both = DummyParser(supported_types={D}, supported_exts=set(all_d_exts))
        parsers_specific_bothfile_onetype = [a_parser_both, b_parser_both, c_parser_both, d_parser_both]
        self.all_parsers_for_a.add(a_parser_both)
        self.all_parsers_for_b.add(b_parser_both)
        self.all_parsers_for_c.add(c_parser_both)
        self.all_parsers_for_d.add(d_parser_both)

        # -- several types
        abc_parser_both = DummyParser(supported_types={A, B, C},
                                      supported_exts=set(all_a_exts).union(all_b_exts).union(
                                          all_c_exts))
        acd_parser_both = DummyParser(supported_types={A, C, D},
                                      supported_exts=set(all_a_exts).union(all_c_exts).union(
                                          all_d_exts))
        parsers_specific_bothfile_severaltypes = [abc_parser_both, acd_parser_both]
        self.all_parsers_for_a = self.all_parsers_for_a.union({abc_parser_both, acd_parser_both})
        self.all_parsers_for_b.add(abc_parser_both)
        self.all_parsers_for_c = self.all_parsers_for_c.union({abc_parser_both, acd_parser_both})
        self.all_parsers_for_d.add(acd_parser_both)

        # ******** GENERIC *******
        def parse_any():
            pass

        any_parser_singlefile = SingleFileParserFunction(parse_any, supported_types={AnyObject},
                                                         supported_exts=set(all_d_exts))
        parsers_generic_singlefile = [any_parser_singlefile]

        any_parser_multifile = DummyMultifileParser(supported_types={AnyObject})
        parsers_generic_multifile = [any_parser_multifile]

        any_parser_bothfile = DummyParser(supported_types={AnyObject}, supported_exts=set(all_a_exts))
        parsers_generic_bothfile = [any_parser_bothfile]

        self.all_parsers_generic = self.all_parsers_generic.union(set(parsers_generic_singlefile)) \
                                                           .union(set(parsers_generic_multifile)) \
                                                           .union(set(parsers_generic_bothfile))

        self.all_parsers_lists = [parsers_specific_singlefile_onetype,
                                  parsers_specific_singlefile_severaltypes,
                                  parsers_specific_multifile_onetype,
                                  parsers_specific_multifile_severaltypes,
                                  parsers_specific_bothfile_onetype,
                                  parsers_specific_bothfile_severaltypes,
                                  parsers_generic_singlefile,
                                  parsers_generic_multifile,
                                  parsers_generic_bothfile]

        self.all_parsers = {A: self.all_parsers_for_a,
                            B: self.all_parsers_for_b,
                            C: self.all_parsers_for_c,
                            D: self.all_parsers_for_d,
                            AnyObject: self.all_parsers_generic}

    def define_types(self):
        """
        Defines the types that will be used in the tests. It defines
         * 2 classes with inheritance: A and B inheriting from A
         * 2 'generic' classes (in the sense of the typing module) with inheritance :  C[Y] and
         D[Z, Y] inheriting from C[Y]
        :return:
        """
        # 2 simple classes with inheritance
        class A(object):
            pass

        class B(A):
            pass

        # 2 generic classes with inheritance
        Y = TypeVar('Y')
        Z = TypeVar('Z')

        class C(Generic[Y]):
            pass

        class D(Generic[Z, Y], C[Y]):
            pass

        return A, B, C, D

    def define_file_extensions(self):
        """
        Defines a couple file extensions, that will be used in the whole test class.
        They are defined by doing all the 1-, 2-, 3-, and 4- combinations of a,b,c,d.
        This method returns lists containing all extensions containing 'a', all extensions containing 'b', etc.

        '.a', '.b', '.c', '.d', 'ab', 'ac', 'ad' ..., '.abc', '.bcd', ... '.abcd'
        :return:
        """
        all_a_extensions = []
        all_b_extensions = []
        all_c_extensions = []
        all_d_extensions = []
        all_extensions = {MULTIFILE_EXT}
        for a in [False, True]:
            for b in [False, True]:
                for c in [False, True]:
                    for d in [False, True]:
                        ext = '.'
                        if a:
                            ext += 'a'
                        if b:
                            ext += 'b'
                        if c:
                            ext += 'c'
                        if d:
                            ext += 'd'
                        print(ext)
                        if a or b or c or d:
                            all_extensions.add(ext)
                        if a:
                            all_a_extensions.append(ext)
                        if b:
                            all_b_extensions.append(ext)
                        if c:
                            all_c_extensions.append(ext)
                        if d:
                            all_d_extensions.append(ext)
        return all_a_extensions, all_b_extensions, all_c_extensions, all_d_extensions, all_extensions

    def create_shuffled_registry(self):
        """ Creates an instance of ParserCache """
        r = ParserCache()
        all = [p for sublist in self.all_parsers_lists for p in sublist]
        shuffle(all)
        for p in all:
            r.register_parser(p)
        return r

    def test_a_all_extensions_and_types_are_present(self):
        """
        Asserts that all the file extensions are in get_all_supported_exts().
        Asserts that all types are in get_all_supported_types()
        :return:
        """
        for i in range(1,10):
            r = self.create_shuffled_registry()

            # first assert that all extensions are here
            self.assertEquals(r.get_all_supported_exts(), self.all_extensions)

            # then that all types are here
            self.assertEquals(r.get_all_supported_types(), self.all_types)

    def test_b_capabilities_equal_query_strict(self):
        """
        Tests that, for all parser registry queries that can be done,
        * the order of the parsers returned by `find_all_matching_parsers` is correct for all categories. That is, it
        is consistent with the one returned in `get_capabilities_by_ext`
        * there are no duplicates

        This test is done in 'strict' mode
        :return:
        """
        self._capabilities_equal_query(True)

    def test_c_capabilities_equal_query_nonstrict(self):
        """
        Tests that, for all parser registry queries that can be done,
        * the order of the parsers returned by `find_all_matching_parsers` is correct for all categories. That is, it
        is consistent with the one returned in `get_capabilities_by_ext`
        * there are no duplicates

        This test is done in 'non-strict' mode (a parser that is able to parse a subclass of what we want is retained)
        :return:
        """
        self._capabilities_equal_query(False)

    def _capabilities_equal_query(self, strict):
        """
        Tests that, for all parser registry queries that can be done,
        * the order of the parsers returned by `find_all_matching_parsers` is correct for all categories. That is, it
        is consistent with the one returned in `get_capabilities_by_ext`
        * there are no duplicates
        :param strict:
        :return:
        """
        for i in range(1, 10):
            r = self.create_shuffled_registry()

            capabilities_by_ext = r.get_capabilities_by_ext(strict_type_matching=strict)

            # consistency check : each entry should reflect the value returned by find_parsers
            for ext in capabilities_by_ext.keys():
                for typ in capabilities_by_ext[ext].keys():
                    print('Asserting (' + ('' if strict else 'non-') + 'strict mode) type='
                          + get_pretty_type_str(typ) + ' ext=' + ext)

                    # query
                    matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match \
                        = r.find_all_matching_parsers(strict, desired_type=typ, required_ext=ext)
                    matching_parsers = matching[0] + matching[1] + matching[2]

                    # capabilities
                    capa = []
                    if '1_exact_match' in capabilities_by_ext[ext][typ].keys():
                        capa = capa + capabilities_by_ext[ext][typ]['1_exact_match']
                    if '2_approx_match' in capabilities_by_ext[ext][typ].keys():
                        capa = capa + capabilities_by_ext[ext][typ]['2_approx_match']
                    if '3_generic' in capabilities_by_ext[ext][typ].keys():
                        capa = capa + capabilities_by_ext[ext][typ]['3_generic']

                    # asserts
                    self.assertEquals(capa, list(reversed(matching_parsers)))
                    # --remove duplicates
                    capa_no_dup = list(OrderedDict.fromkeys(capa))
                    self.assertEquals(capa_no_dup, list(reversed(matching_parsers)))

    def test_d_correct_parsers_in_order_strict(self):
        """
        Tests that the correct parsers are returned in the right order by find_all_matching_parsers for each queried
        type (A, B, C, D) whatever the file extension put in the query. This test is in STRICT mode.
        :return:
        """
        self._correct_parsers_in_order(True)

    def test_e_correct_parsers_in_order_nonstrict(self):
        """
        Tests that the correct parsers are returned in the right order by find_all_matching_parsers for each queried
        type (A, B, C, D) whatever the file extension put in the query. This test is in NON-STRICT mode.
        :return:
        """
        self._correct_parsers_in_order(False)

    def _correct_parsers_in_order(self, strict):
        """
        Tests that the correct parsers are returned in the right order by find_all_matching_parsers for each queried
        type (A, B, C, D) whatever the file extension put in the query.
         * For A, the reference is self.all_parsers_for_a (strict) and self.all_parsers_for_b (in non-strict mode)
         since B is a subcless of A
         * for B, the reference is self.all_parsers_for_b in both modes
         * For C, the reference is self.all_parsers_for_c (strict) and self.all_parsers_for_d (in non-strict mode)
         since D is a subcless of C
         * for D, the reference is self.all_parsers_for_d in both modes

        :return:
        """

        # do this 10 times with 10 reorderings of the registry
        for i in range(1, 10):
            r = self.create_shuffled_registry()

            typ = self.A
            if strict:
                self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_a)
            else:
                # B is a subclass of A, so all parsers providing A should be there too
                self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_a, self.all_parsers_for_b)

            typ = self.B
            self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_b)

            typ = self.C
            if strict:
                self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_c)
            else:
                # D is a subclass of C, so all parsers providing D should be there too
                self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_c, self.all_parsers_for_d)

            typ = self.D
            self._correct_parsers_in_order_specific_type(r, typ, self.all_parsers_for_d)

        pass

    def _correct_parsers_in_order_specific_type(self, parser_cache, typ, specific_parsers_strict,
                                                specific_parsers_non_strict = None):
        """
        Tests, for each extension available, that the find_all_matching_parsers query for type 'typ' and that extension
        returns the correct results.
         * generic parsers first (all the ones from self.all_parsers_generic that support that file extension)
         * then specific non-strict (if that list is provided)
         * then the specific strict (that list should be provided

        :param parser_cache:
        :param typ:
        :param specific_parsers_strict:
        :param specific_parsers_non_strict:
        :return:
        """
        strict = specific_parsers_non_strict is None

        for ext in self.all_extensions:
            print('Checking list of parsers returned for (' + ('' if strict else 'non-') + 'strict mode) type='
                  + get_pretty_type_str(typ) + ' ext=' + ext)
            matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match \
                = parser_cache.find_all_matching_parsers(strict=strict, desired_type=typ, required_ext=ext)

            # all generic should always be there, at the beginning
            print('First generic')
            generic = self.all_parsers_generic.copy()
            for g in self.all_parsers_generic:
                if ext not in g.supported_exts:
                    generic.remove(g)

            self.assertEquals(set(matching[0]), generic)

            if not strict:
                print('Then specific non-strict')
                specific_nonstrict = specific_parsers_non_strict.copy()
                for f in specific_parsers_non_strict:
                    if ext not in f.supported_exts:
                        specific_nonstrict.remove(f)
                # remove those that are actually strict
                for t in specific_parsers_strict:
                    if t in specific_nonstrict:
                        specific_nonstrict.remove(t)
                self.assertEquals(set(matching[1]), specific_nonstrict)

            # then all specific should support a
            print('Then specific strict')
            specific = specific_parsers_strict.copy()
            for s in specific_parsers_strict:
                if ext not in s.supported_exts:
                    specific.remove(s)

            self.assertEquals(set(matching[2]), specific)
