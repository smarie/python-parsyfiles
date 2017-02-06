from logging import Logger
from random import shuffle
from typing import Generic, TypeVar, Dict, Type, Any
from unittest import TestCase

from sficopaf import PersistedObject, get_pretty_type_str, MULTIFILE_EXT
from sficopaf.parsing_core import SingleFileParserFunction, MultiFileParser, AnyParser, T, BaseParser
from sficopaf.parsing_registries import ParserCache


class TestParserRegistry(TestCase):

    def setUp(self):
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

        self.A = A
        self.B = B
        self.C = C
        self.D = D
        self.all_types = {A, B, C, D, Any}

        self.all_parsers_for_a = set()
        self.all_parsers_for_b = set()
        self.all_parsers_for_c = set()
        self.all_parsers_for_d = set()
        self.all_parsers_generic = set()

        # create all combinations of file extensions
        self.all_a_extensions = []
        all_b_extensions = []
        all_c_extensions = []
        all_d_extensions = []
        self.all_extensions = {MULTIFILE_EXT}
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
                            self.all_extensions.add(ext)
                        if a:
                            self.all_a_extensions.append(ext)
                        if b:
                            all_b_extensions.append(ext)
                        if c:
                            all_c_extensions.append(ext)
                        if d:
                            all_d_extensions.append(ext)

        # parsers

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

        a_parser_single = SingleFileParserFunction(parse_a, supported_types={A}, supported_exts=set(self.all_a_extensions))
        b_parser_single = SingleFileParserFunction(parse_b, supported_types={B}, supported_exts=set(all_b_extensions))
        c_parser_single = SingleFileParserFunction(parse_c, supported_types={C}, supported_exts=set(all_c_extensions))
        d_parser_single = SingleFileParserFunction(parse_d, supported_types={D}, supported_exts=set(all_d_extensions))
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
                                                    supported_exts=set(self.all_a_extensions).union(all_d_extensions))
        bc_parser_single = SingleFileParserFunction(parse_b_or_c, supported_types={B, C},
                                                    supported_exts=set(all_b_extensions).union(all_c_extensions))
        parsers_specific_singlefile_severaltypes = [ad_parser_single, bc_parser_single]
        self.all_parsers_for_a.add(ad_parser_single)
        self.all_parsers_for_b.add(bc_parser_single)
        self.all_parsers_for_c.add(bc_parser_single)
        self.all_parsers_for_d.add(ad_parser_single)

        # ******** Specific Multifile ************
        class DummyMultifileParser(MultiFileParser[T]):

            def __init__(self, supported_types):
                super(DummyMultifileParser, self).__init__(supported_types)

            def __str__(self):
                return 'MultifileParser for ' + str([get_pretty_type_str(typ) for typ in self.supported_types]) \
                       + 'for ' + str(self.supported_exts)

            def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                         logger: Logger) -> Dict[str, BaseParser.ParsingPlan[Any]]:
                pass

            def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                                 parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan], logger: Logger, *args,
                                 **kwargs) -> T:
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
        class DummyParser(AnyParser[T]):

            def __init__(self, supported_types, supported_exts):
                super(DummyParser, self).__init__(supported_types=supported_types,
                                                  supported_exts=supported_exts)

            def _get_parsing_plan_for_multifile_children(self, obj_on_fs: PersistedObject, desired_type: Type[T],
                                                         logger: Logger) -> Dict[str, BaseParser.ParsingPlan[Any]]:
                pass

            def _parse_multifile(self, desired_type: Type[T], obj: PersistedObject,
                                 parsing_plan_for_children: Dict[str, AnyParser._RecursiveParsingPlan], logger: Logger, *args,
                                 **kwargs) -> T:
                pass

            def _parse_singlefile(self, desired_type: Type[T], file_path: str, encoding: str, logger: Logger, *args,
                                  **kwargs) -> T:
                pass

        # -- one type
        a_parser_both = DummyParser(supported_types={A}, supported_exts=set(self.all_a_extensions))
        b_parser_both = DummyParser(supported_types={B}, supported_exts=set(all_b_extensions))
        c_parser_both = DummyParser(supported_types={C}, supported_exts=set(all_c_extensions))
        d_parser_both = DummyParser(supported_types={D}, supported_exts=set(all_d_extensions))
        parsers_specific_bothfile_onetype = [a_parser_both, b_parser_both, c_parser_both, d_parser_both]
        self.all_parsers_for_a.add(a_parser_both)
        self.all_parsers_for_b.add(b_parser_both)
        self.all_parsers_for_c.add(c_parser_both)
        self.all_parsers_for_d.add(d_parser_both)

        # -- several types
        abc_parser_both = DummyParser(supported_types={A, B, C},
                                      supported_exts=set(self.all_a_extensions).union(all_b_extensions).union(
                                          all_c_extensions))
        acd_parser_both = DummyParser(supported_types={A, C, D},
                                      supported_exts=set(self.all_a_extensions).union(all_c_extensions).union(
                                          all_d_extensions))
        parsers_specific_bothfile_severaltypes = [abc_parser_both, acd_parser_both]
        self.all_parsers_for_a = self.all_parsers_for_a.union({abc_parser_both, acd_parser_both})
        self.all_parsers_for_b.add(abc_parser_both)
        self.all_parsers_for_c = self.all_parsers_for_c.union({abc_parser_both, acd_parser_both})
        self.all_parsers_for_d.add(acd_parser_both)

        # ******** GENERIC *******
        def parse_any():
            pass

        any_parser_singlefile = SingleFileParserFunction(parse_any, supported_types={Any},
                                                         supported_exts=set(all_d_extensions))
        parsers_generic_singlefile = [any_parser_singlefile]

        any_parser_multifile = DummyMultifileParser(supported_types={Any})
        parsers_generic_multifile = [any_parser_multifile]

        any_parser_bothfile = DummyParser(supported_types={Any}, supported_exts=set(self.all_a_extensions))
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
                            Any: self.all_parsers_generic}

    def create_shuffled_registry(self):
        r = ParserCache()
        all = [p for sublist in self.all_parsers_lists for p in sublist]
        shuffle(all)
        for p in all:
            r.register_parser(p)
        return r

    def test_a_all_extensions_and_types_are_present(self):
        """
        assert that all extensions are in get_all_supported_exts()
        assert that all types are in get_all_supported_types()
        :return:
        """
        for i in range(1,10):
            r = self.create_shuffled_registry()

            # first assert that all extensions are here
            self.assertEquals(r.get_all_supported_exts(), self.all_extensions)

            # then that all types are here
            self.assertEquals(r.get_all_supported_types(), self.all_types)

    def test_b_capabilities_equal_query_strict(self):
        self._capabilities_equal_query(True)

    def test_c_capabilities_equal_query_nonstrict(self):
        self._capabilities_equal_query(False)

    def _capabilities_equal_query(self, strict):
        """
        for all queries that can be done
        - the order should be correct (specific then generic)
        - there should be no duplicate
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
                    matching, no_type_match_but_ext_match, no_ext_match_but_type_match, no_match \
                        = r.find_all_matching_parsers(strict, desired_type=typ, required_ext=ext)
                    matching_parsers = matching[0] + matching[1] + matching[2]
                    tst = capabilities_by_ext[ext][typ]['1_exact_match'] \
                          + capabilities_by_ext[ext][typ]['2_approx_match']\
                          + capabilities_by_ext[ext][typ]['3_generic']
                    self.assertEquals(tst, list(reversed(matching_parsers)))

    def test_d_correct_parsers_in_order_strict(self):
        self._correct_parsers_in_order(True)

    def test_e_correct_parsers_in_order_nonstrict(self):
        self._correct_parsers_in_order(False)

    def _correct_parsers_in_order(self, strict):
        """

        :return:
        """
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
