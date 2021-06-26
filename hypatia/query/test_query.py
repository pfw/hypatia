import pytest as pytest


class ComparatorTestBase:
    def _makeOne(self, index, value):
        return self._getTargetClass()(index, value)


class TestQuery:
    def _makeOne(self):
        from . import Query as cls

        return cls()

    def test_and(self):
        from . import And

        a = self._makeOne()
        b = self._makeOne()
        result = a & b
        assert isinstance(result, And)
        assert result.queries[0] == a
        assert result.queries[1] == b

    def test_and_query_should_not_change_after_optimize(self):
        from . import And, Or, Eq, Any

        states_query = Or(Eq("states", "published"), Eq("states", "archived"))
        query = And(states_query, Eq("content_types", "event"))
        op = query._optimize()
        assert isinstance(op, And)
        assert isinstance(op.queries[0], Any)
        assert isinstance(op.queries[1], Eq)
        assert op.queries[0].index == "states"
        assert op.queries[0]._value == ["published", "archived"]
        assert op.queries[1].index == "content_types"
        assert op.queries[1]._value == "event"
        # and_query should not have been modified
        # this is needed because query optimization can be more aggressive than
        # just replace Or(Eq, Eq) by Any. Here is an example:
        # reusable_query = And(Any1, Any3, Any4)
        # query = Or(And(Any1, Any2), reusable_query)
        # An optimization can be a factorization like this:
        # And(Any1, Or(Any2, And(Any3, Any4)))
        # We don't want reusable_query to be equal to And(Any3, Any4) now,
        # because it can be used in another query later...
        assert isinstance(query.queries[0], Or)
        assert isinstance(query.queries[1], Eq)

    def test_or_query_should_not_change_after_optimize(self):
        from . import And, Or, Eq, All

        states_query = And(Eq("states", "published"), Eq("states", "archived"))
        query = Or(states_query, Eq("content_types", "event"))
        op = query._optimize()
        assert isinstance(op, Or)
        assert isinstance(op.queries[0], All)
        assert isinstance(op.queries[1], Eq)
        assert op.queries[0].index == "states"
        assert op.queries[0]._value == ["published", "archived"]
        assert op.queries[1].index == "content_types"
        assert op.queries[1]._value == "event"
        assert isinstance(query.queries[0], And)
        assert isinstance(query.queries[1], Eq)

    def test_and_type_error(self):
        a = self._makeOne()
        with pytest.raises(TypeError) as e:
            assert a.__and__(2)

    def test_or(self):
        from . import Or

        a = self._makeOne()
        b = self._makeOne()
        result = a | b
        assert isinstance(result, Or)
        assert result.queries[0] == a
        assert result.queries[1] == b

    def test_or_type_error(self):
        a = self._makeOne()
        with pytest.raises(TypeError) as e:
            assert a.__or__(2)

    def test_iter_children(self):
        a = self._makeOne()
        assert a.iter_children() == ()

    def test_print_tree(self):
        from . import Query

        class Derived(Query):
            def __init__(self, name):
                self.name = name
                self.children = []

            def __str__(self):
                return self.name

            def iter_children(self):
                return self.children

        import sys

        if sys.version_info[0] >= 3:  # pragma NO COVER
            from io import StringIO
        else:  # pragma NO COVER
            from io import BytesIO as StringIO
        a = Derived("A")
        b = Derived("B")
        c = Derived("C")
        a.children.append(b)
        a.children.append(c)

        buf = StringIO()
        a.print_tree(buf)
        assert buf.getvalue() == "A\n  B\n  C\n"


class TestComparator(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Comparator

        return Comparator

    def test_ctor(self):
        inst = self._makeOne("index", "val")
        assert inst.index == "index"
        assert inst._value == "val"

    def test_eq(self):
        inst = self._makeOne("index", "val")
        assert inst == self._makeOne("index", "val")

    def test_execute(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        rs = inst.execute()
        assert rs["query"] == inst
        assert rs["names"] == None
        assert rs["resolver"] == None

    def test_flush(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        inst.flush(True)
        assert index.flushed == True

    def test_execute_withargs(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        rs = inst.execute(optimize=False, names={"a": 1}, resolver=True)
        assert rs["query"] == inst
        assert rs["names"] == {"a": 1}
        assert rs["resolver"] == True


class TestContains(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Contains

        return Contains

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.contains == "val"

    def test_apply_w_name(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, Name("foo"))
        result = inst._apply({"foo": "val"})
        assert result == "val"
        assert index.contains == "val"

    def test_apply_w_missing_name(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, Name("foo"))
        with pytest.raises(NameError) as e:
            assert inst._apply({})

    def test_to_str(self):
        inst = self._makeOne("index", "val")
        assert str(inst) == "'val' in index"

    def test_negate(self):
        from . import NotContains

        inst = self._makeOne("index", "val")
        assert inst.negate() == NotContains("index", "val")

    def test_not_equal_to_another_type(self):
        from . import NotContains

        inst = self._makeOne("index", "val")
        assert inst != NotContains("index", "val")


class TestNotContains(ComparatorTestBase):
    def _getTargetClass(self):
        from . import NotContains

        return NotContains

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.not_contains == "val"

    def test_to_str(self):
        inst = self._makeOne("index", "val")
        assert str(inst) == "'val' not in index"

    def test_negate(self):
        from . import Contains

        inst = self._makeOne("index", "val")
        assert inst.negate() == Contains("index", "val")


class TestEq(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Eq

        return Eq

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.eq == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index == 'val'"

    def test_negate(self):
        from . import NotEq

        inst = self._makeOne("index", "val")
        assert inst.negate() == NotEq("index", "val")

    def test_not_equal_to_another_type(self):
        from . import NotEq

        inst = self._makeOne("index", "val")
        assert inst != NotEq("index", "val")


class TestNotEq(ComparatorTestBase):
    def _getTargetClass(self):
        from . import NotEq

        return NotEq

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.not_eq == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index != 'val'"

    def test_negate(self):
        from . import Eq

        inst = self._makeOne("index", "val")
        assert inst.negate() == Eq("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Eq

        inst = self._makeOne("index", "val")
        assert inst != Eq("index", "val")


class TestGt(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Gt

        return Gt

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.gt == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index > 'val'"

    def test_negate(self):
        from . import Le

        inst = self._makeOne("index", "val")
        assert inst.negate() == Le("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Ge

        inst = self._makeOne("index", "val")
        assert inst != Ge("index", "val")


class TestLt(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Lt

        return Lt

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.lt == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index < 'val'"

    def test_negate(self):
        from . import Ge

        inst = self._makeOne("index", "val")
        assert inst.negate() == Ge("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Ge

        inst = self._makeOne("index", "val")
        assert inst != Ge("index", "val")


class TestGe(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Ge

        return Ge

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.ge == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index >= 'val'"

    def test_negate(self):
        from . import Lt

        inst = self._makeOne("index", "val")
        assert inst.negate() == Lt("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Lt

        inst = self._makeOne("index", "val")
        assert inst != Lt("index", "val")


class TestLe(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Le

        return Le

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.le == "val"

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, "val")
        assert str(inst) == "index <= 'val'"

    def test_negate(self):
        from . import Gt

        inst = self._makeOne("index", "val")
        assert inst.negate() == Gt("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Lt

        inst = self._makeOne("index", "val")
        assert inst != Lt("index", "val")


class TestAll(ComparatorTestBase):
    def _getTargetClass(self):
        from . import All

        return All

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.all == "val"

    def test_to_str(self):
        inst = self._makeOne("index", [1, 2, 3])
        assert str(inst) == "index in all([1, 2, 3])"

    def test_negate(self):
        from . import NotAll

        inst = self._makeOne("index", "val")
        assert inst.negate() == NotAll("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Any

        inst = self._makeOne("index", "val")
        assert inst != Any("index", "val")


class TestNotAll(ComparatorTestBase):
    def _getTargetClass(self):
        from . import NotAll

        return NotAll

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.all == "val"

    def test_to_str(self):
        inst = self._makeOne("index", [1, 2, 3])
        assert str(inst) == "index not in all([1, 2, 3])"

    def test_negate(self):
        from . import All

        inst = self._makeOne("index", "val")
        assert inst.negate() == All("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Any

        inst = self._makeOne("index", "val")
        assert inst != Any("index", "val")


class TestAny(ComparatorTestBase):
    def _getTargetClass(self):
        from . import Any

        return Any

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.any == "val"

    def test_apply_with_list(self):
        index = DummyIndex()
        inst = self._makeOne(index, ["one", "two"])
        result = inst._apply(None)
        assert result == ["one", "two"]
        assert index.any == ["one", "two"]

    def test_apply_with_tuple(self):
        index = DummyIndex()
        inst = self._makeOne(index, ("one", "two"))
        result = inst._apply(None)
        assert result == ("one", "two")
        assert index.any == ("one", "two")

    def test_apply_with_names(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, [Name("foo"), Name("bar")])
        result = inst._apply(names={"foo": "one", "bar": "two"})
        assert result == ["one", "two"]
        assert index.any == ["one", "two"]

    def test_apply_with_names_in_tuple(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, (Name("foo"), Name("bar")))
        result = inst._apply(names={"foo": "one", "bar": "two"})
        assert result == ("one", "two")
        assert index.any == ("one", "two")

    def test_to_str(self):
        inst = self._makeOne("index", [1, 2, 3])
        assert str(inst) == "index in any([1, 2, 3])"

    def test_negate(self):
        from . import NotAny

        inst = self._makeOne("index", "val")
        assert inst.negate() == NotAny("index", "val")

    def test_not_equal_to_another_type(self):
        from . import NotAny

        inst = self._makeOne("index", "val")
        assert inst != NotAny("index", "val")


class TestNotAny(ComparatorTestBase):
    def _getTargetClass(self):
        from . import NotAny

        return NotAny

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "val")
        result = inst._apply(None)
        assert result == "val"
        assert index.not_any == "val"

    def test_to_str(self):
        inst = self._makeOne("index", [1, 2, 3])
        assert str(inst) == "index not in any([1, 2, 3])"

    def test_negate(self):
        from . import Any

        inst = self._makeOne("index", "val")
        assert inst.negate() == Any("index", "val")

    def test_not_equal_to_another_type(self):
        from . import Any

        inst = self._makeOne("index", "val")
        assert inst != Any("index", "val")


class TestInRange(ComparatorTestBase):
    def _getTargetClass(self):
        from . import InRange

        return InRange

    def _makeOne(self, index, begin, end, begin_exclusive=False, end_exclusive=False):
        return self._getTargetClass()(index, begin, end, begin_exclusive, end_exclusive)

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "begin", "end")
        result = inst._apply(None)
        assert result == ("begin", "end", False, False)
        assert index.range == ("begin", "end", False, False)

    def test_apply_w_names(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, Name("foo"), Name("bar"))
        result = inst._apply({"foo": "begin", "bar": "end"})
        assert result == ("begin", "end", False, False)
        assert index.range == ("begin", "end", False, False)

    def test_apply_w_names_missing(self):
        from . import Name

        index = DummyIndex()
        inst = self._makeOne(index, Name("foo"), Name("bar"))
        with pytest.raises(NameError) as e:
            assert inst._apply({})
        with pytest.raises(NameError) as e:
            assert inst._apply({"foo": "begin"})

    def test_apply_exclusive(self):
        index = DummyIndex()
        inst = self._makeOne(index, "begin", "end", True, True)
        result = inst._apply(None)
        assert result == ("begin", "end", True, True)
        assert index.range == ("begin", "end", True, True)

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, 0, 5)
        assert str(inst) == "0 <= index <= 5"

    def test_to_str_exclusive(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, 0, 5, True, True)
        assert str(inst) == "0 < index < 5"

    def test_from_gtlt(self):
        from . import Ge
        from . import Le

        index = DummyIndex("index")
        gt = Ge(index, 0)
        lt = Le(index, 5)
        inst = self._getTargetClass().fromGTLT(gt, lt)
        assert str(inst) == "0 <= index <= 5"

    def test_from_gtlt_exclusive(self):
        from . import Gt
        from . import Lt

        index = DummyIndex("index")
        gt = Gt(index, 0)
        lt = Lt(index, 5)
        inst = self._getTargetClass().fromGTLT(gt, lt)
        assert str(inst) == "0 < index < 5"

    def test_negate(self):
        from . import NotInRange

        inst = self._makeOne("index", "begin", "end")
        assert inst.negate() == NotInRange("index", "begin", "end")

    def test_not_equal_to_another_type(self):
        inst = self._makeOne("index", "begin", "end")
        assert inst != object()


class TestNotInRange(ComparatorTestBase):
    def _getTargetClass(self):
        from . import NotInRange

        return NotInRange

    def _makeOne(self, index, begin, end, begin_exclusive=False, end_exclusive=False):
        return self._getTargetClass()(index, begin, end, begin_exclusive, end_exclusive)

    def test_apply(self):
        index = DummyIndex()
        inst = self._makeOne(index, "begin", "end")
        result = inst._apply(None)
        assert result == ("begin", "end", False, False)
        assert index.not_range == ("begin", "end", False, False)

    def test_apply_exclusive(self):
        index = DummyIndex()
        inst = self._makeOne(index, "begin", "end", True, True)
        result = inst._apply(None)
        assert result == ("begin", "end", True, True)
        assert index.not_range == ("begin", "end", True, True)

    def test_to_str(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, 0, 5)
        assert str(inst) == "not(0 <= index <= 5)"

    def test_to_str_exclusive(self):
        index = DummyIndex("index")
        inst = self._makeOne(index, 0, 5, True, True)
        assert str(inst) == "not(0 < index < 5)"

    def test_negate(self):
        from . import InRange

        inst = self._makeOne("index", "begin", "end")
        assert inst.negate() == InRange("index", "begin", "end")

    def test_not_equal_to_another_type(self):
        inst = self._makeOne("index", "begin", "end")
        assert inst != object()


class BoolOpTestBase:
    def _makeOne(self, left, right):
        return self._getTargetClass()(left, right)


class TestBoolOp(BoolOpTestBase):
    def _getTargetClass(self):
        from . import BoolOp as cls

        return cls

    def _makeDummyQuery(self, values):
        return DummyQuery(values, index=DummyIndex())

    def test_iter_children(self):
        class Dummy(object):
            pass

        left, right = Dummy(), Dummy()
        o = self._makeOne(left, right)
        assert list(o.iter_children()) == [left, right]

    def test_flush(self):
        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        inst = self._makeOne(left, right)
        inst.flush(True)
        assert left.flushed == True
        assert right.flushed == True


class TestOr(BoolOpTestBase):
    def _getTargetClass(self):
        from . import Or as cls

        return cls

    def test_to_str(self):
        o = self._makeOne(None, None)
        assert str(o) == "Or"

    def test_apply(self):
        left = DummyQuery(set([1, 2]))
        right = DummyQuery(set([3, 4]))
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set([1, 2, 3, 4])
        assert left.applied
        assert right.applied
        assert left.unioned == None
        assert right.unioned == (left.results, right.results)

    def test_apply_left_empty(self):
        left = DummyQuery(set())
        right = DummyQuery(set([3, 4]))
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set([3, 4])
        assert left.applied
        assert right.applied
        assert left.unioned == None
        assert right.unioned == (left.results, right.results)

    def test_apply_right_empty(self):
        left = DummyQuery(set([1, 2]))
        right = DummyQuery(set())
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set([1, 2])
        assert left.applied
        assert right.applied
        assert left.unioned == None
        assert right.unioned == (left.results, right.results)

    def test_negate(self):
        from . import And

        left = DummyQuery("foo")
        right = DummyQuery("bar")
        o = self._makeOne(left, right)
        neg = o.negate()
        assert isinstance(neg, And)
        left, right = neg.queries
        assert left.negated
        assert right.negated


class TestAnd(BoolOpTestBase):
    def _getTargetClass(self):
        from . import And as cls

        return cls

    def test_to_str(self):
        o = self._makeOne(None, None)
        assert str(o) == "And"

    def test_apply(self):
        left = DummyQuery(set([1, 2, 3]))
        right = DummyQuery(set([3, 4, 5]))
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set([3])
        assert left.applied
        assert right.applied
        assert left.intersected == None
        assert right.intersected == (left.results, right.results)

    def test_apply_left_empty(self):
        left = DummyQuery(set([]))
        right = DummyQuery(set([3, 4, 5]))
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set()
        assert left.applied
        assert right.applied is False
        assert left.intersected == None
        assert right.intersected == None

    def test_apply_right_empty(self):
        left = DummyQuery(set([1, 2, 3]))
        right = DummyQuery(set())
        o = self._makeOne(left, right)
        o.family = DummyFamily()
        assert o._apply(None) == set()
        assert left.applied
        assert right.applied
        assert left.intersected == None
        assert right.intersected == None

    def test_negate(self):
        from . import Or

        left = DummyQuery("foo")
        right = DummyQuery("bar")
        o = self._makeOne(left, right)
        neg = o.negate()
        assert isinstance(neg, Or)
        left, right = neg.queries
        assert left.negated
        assert right.negated


class TestBoolOpExecute:
    def _makeDummyQuery(self, values):
        return DummyQuery(values, index=DummyIndex())

    def test_execute(self):
        from . import Or

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        inst = Or(left, right)
        rs = inst.execute(names={"a": 1})
        assert rs["names"] == {"a": 1}
        assert rs["query"] == inst

    def test_execute_first(self):
        from . import Or
        from . import And

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        o = Or(left, right)
        third = self._makeDummyQuery({"boo": 21})
        a = And(o, third)
        rs = a.execute()
        assert rs["query"] == a

    def test_execute_second(self):
        from . import Or
        from . import And

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        o = Or(left, right)
        third = self._makeDummyQuery({"soap": 22})
        a = And(third, o)
        rs = a.execute()
        assert rs["query"] == a

    def test_execute_both(self):
        from . import And

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        a = And(left, right)
        rs = a.execute()
        assert rs["query"] == a

    def test_execute_none(self):
        from . import Or
        from . import And

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        o = Or(left, right)
        third = self._makeDummyQuery({"boo": 21})
        fourth = self._makeDummyQuery({"soap": 22})
        o2 = Or(third, fourth)
        a = And(o, o2)
        rs = a.execute()
        assert rs["query"] == a

    def test_execute_withargs(self):
        from . import Or

        left = self._makeDummyQuery({"foo": 11})
        right = self._makeDummyQuery({"bar": 12})
        inst = Or(left, right)
        rs = inst.execute(optimize=False, names={"a": 1}, resolver=True)
        assert rs["query"] == inst
        assert rs["names"] == {"a": 1}
        assert rs["resolver"] == True

    def test_execute_no_queries(self):
        from . import Or

        inst = Or()
        with pytest.raises(ValueError):
            inst.execute(optimize=False, names={"a": 1}, resolver=True)

    def test_execute_no_query_has_an_index(self):
        from . import Or

        class Dummy(object):
            def iter_children(self):
                return ()

        inst = Or(Dummy())
        with pytest.raises(ValueError):
            inst.execute(optimize=False, names={"a": 1}, resolver=True)


class TestNot(BoolOpTestBase):
    def _makeOne(self, query):
        from . import Not as cls

        return cls(query)

    def test_to_str(self):
        o = self._makeOne(None)
        assert str(o) == "Not"

    def test_apply(self):
        query = DummyQuery("foo")
        o = self._makeOne(query)
        assert o._apply(None) == "foo"
        assert query.negated
        assert query.applied

    def test_negate(self):
        query = DummyQuery("foo")
        o = self._makeOne(query)
        assert o.negate() == query

    def test_iter_children(self):
        query = DummyQuery("foo")
        o = self._makeOne(query)
        assert list(o.iter_children()) == [query]

    def test_execute(self):
        index = DummyIndex()
        query = DummyQuery("foo", index=index)
        inst = self._makeOne(query)
        rs = inst.execute()
        assert rs["query"] == query
        assert rs["names"] == None
        assert rs["resolver"] == None

    def test_execute_withargs(self):
        index = DummyIndex()
        query = DummyQuery("foo", index=index)
        inst = self._makeOne(query)
        rs = inst.execute(optimize=False, names={"a": 1}, resolver=True)
        assert rs["query"] == inst
        assert rs["names"] == {"a": 1}
        assert rs["resolver"] == True

    def test_flush(self):
        index = DummyIndex()
        query = DummyQuery("foo", index=index)
        inst = self._makeOne(query)
        inst.flush(True)
        assert query.flushed == True


class TestName:
    def _makeOne(self):
        from . import Name as cls

        return cls("foo")

    def test_to_str(self):
        o = self._makeOne()
        assert str(o) == "Name('foo')"

    def test_eq(self):
        o1 = self._makeOne()
        o2 = self._makeOne()
        assert o1 is not o2
        assert o1 == o2
        assert o1 != "foo"


class Test_parse_query:
    def _call_fut(self, expr):
        from . import parse_query as fut

        indexes = {}

        class Catalog(object):
            def __getitem__(self, name):
                index = indexes.get(name)
                if index is None:
                    index = DummyIndex(name)
                    indexes[name] = index
                return index

        catalog = Catalog()
        return fut(expr, catalog)

    def test_not_an_expression(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("a = 1")

    def test_multiple_expressions(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("a == 1\nb == 2\n")

    def test_unhandled_operator(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("a ^ b")

    def test_non_string_index_name(self):
        # == is not commutative in this context, sorry.
        with pytest.raises(ValueError) as e:
            assert self._call_fut("1 == a")

    def test_bad_operand_for_set_operation(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("(a == 1) | 2")
        with pytest.raises(ValueError) as e:
            assert self._call_fut("1 | (b == 2)")

    def test_bad_operand_for_bool_operation(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("1 or 2")

    def test_bad_comparator_chaining(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("1 < 2 > 3")
        with pytest.raises(ValueError) as e:
            assert self._call_fut("x == y == z")

    def test_bad_func_call(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("a in foo(bar)")

    def test_wrong_number_or_args_for_any(self):
        with pytest.raises(ValueError) as e:
            assert self._call_fut("a in any(1, 2)")

    def test_num(self):
        assert self._call_fut("1") == 1
        assert self._call_fut("1.1") == 1.1

    def test_str(self):
        assert self._call_fut('"foo"') == "foo"

    def test_list(self):
        assert self._call_fut("[1, 2, 3]") == [1, 2, 3]

    def test_tuple(self):
        from . import Name

        assert self._call_fut("(a, b, c)") == (Name("a"), Name("b"), Name("c"))

    def test_dotted_name(self):
        assert self._call_fut("a.foo").id == "a.foo"

    def test_dotted_names(self):
        assert self._call_fut("a.foo.bar").id == "a.foo.bar"

    def test_eq(self):
        from . import Eq

        eq = self._call_fut("a.foo == 1")
        assert isinstance(eq, Eq)
        assert eq.index.name == "a.foo"
        assert eq._value == 1

    def test_not_eq(self):
        from . import NotEq

        not_eq = self._call_fut("a != 'one'")
        assert isinstance(not_eq, NotEq)
        assert not_eq.index.name == "a"
        assert not_eq._value == "one"

    def test_lt(self):
        from . import Lt
        from . import Name

        lt = self._call_fut("a < foo")
        assert isinstance(lt, Lt)
        assert lt.index.name == "a"
        assert lt._value == Name("foo")

    def test_le(self):
        from . import Le

        le = self._call_fut("a <= 4")
        assert isinstance(le, Le)
        assert le.index.name == "a"
        assert le._value == 4

    def test_gt(self):
        from . import Gt

        gt = self._call_fut("b > 2")
        assert isinstance(gt, Gt)
        assert gt.index.name == "b"
        assert gt._value == 2

    def test_ge(self):
        from . import Ge

        ge = self._call_fut("a >= 5")
        assert isinstance(ge, Ge)
        assert ge.index.name == "a"
        assert ge._value == 5

    def test_contains(self):
        from . import Contains

        contains = self._call_fut("6 in a")
        assert isinstance(contains, Contains)
        assert contains.index.name == "a"
        assert contains._value == 6

    def test_not_contains(self):
        from . import NotContains

        contains = self._call_fut("6 not in a")
        assert isinstance(contains, NotContains)
        assert contains.index.name == "a"
        assert contains._value == 6

    def test_range_exclusive_exclusive(self):
        from . import InRange

        comp = self._call_fut("0 < a < 5")
        assert isinstance(comp, InRange)
        assert comp.index.name == "a"
        assert comp._start == 0
        assert comp._end == 5
        assert comp.start_exclusive
        assert comp.end_exclusive

    def test_range_exclusive_inclusive(self):
        from . import InRange

        comp = self._call_fut("0 < a <= 5")
        assert isinstance(comp, InRange)
        assert comp.index.name == "a"
        assert comp._start == 0
        assert comp._end == 5
        assert comp.start_exclusive
        assert comp.end_exclusive is False

    def test_range_inclusive_exclusive(self):
        from . import InRange

        comp = self._call_fut("0 <= a < 5")
        assert isinstance(comp, InRange)
        assert comp.index.name == "a"
        assert comp._start == 0
        assert comp._end == 5
        assert comp.start_exclusive is False
        assert comp.end_exclusive

    def test_range_inclusive_inclusive(self):
        from . import InRange

        comp = self._call_fut("0 <= a <= 5")
        assert isinstance(comp, InRange)
        assert comp.index.name == "a"
        assert comp._start == 0
        assert comp._end == 5
        assert comp.start_exclusive is False
        assert comp.end_exclusive is False

    def test_not_in_range(self):
        from . import NotInRange

        comp = self._call_fut("not(0 < a < 5)")
        assert isinstance(comp, NotInRange)
        assert comp.index.name == "a"
        assert comp._start == 0
        assert comp._end == 5
        assert comp.start_exclusive
        assert comp.end_exclusive

    def test_or(self):
        from . import Eq
        from . import Or

        op = self._call_fut("(a == 1) | (b == 2)")
        assert isinstance(op, Or)
        query = op.queries[0]
        assert isinstance(query, Eq)
        assert query.index.name == "a"
        assert query._value == 1
        query = op.queries[1]
        assert isinstance(query, Eq)
        assert query.index.name == "b"
        assert query._value == 2

    def test_or_with_bool_syntax(self):
        from . import NotEq
        from . import Or

        op = self._call_fut("a != 1 or b != 2")
        assert isinstance(op, Or)
        query = op.queries[0]
        assert isinstance(query, NotEq)
        assert query.index.name == "a"
        assert query._value == 1
        query = op.queries[1]
        assert isinstance(query, NotEq)
        assert query.index.name == "b"
        assert query._value == 2

    def test_any(self):
        from . import Any

        op = self._call_fut("a == 1 or a == 2 or a == 3")
        assert isinstance(op, Any), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_better_any(self):
        from . import Any

        op = self._call_fut("a in any([1, 2, 3])")
        assert isinstance(op, Any), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_any_with_name(self):
        from . import Any
        from . import Name

        op = self._call_fut("a in any(foo)")
        assert isinstance(op, Any), op
        assert op.index.name == "a"
        assert op._value == Name("foo")

    def test_any_with_names(self):
        from . import Any
        from . import Name

        op = self._call_fut("a in any([foo, bar])")
        assert isinstance(op, Any), op
        assert op.index.name == "a"
        assert op._value == [Name("foo"), Name("bar")]

    def test_not_any(self):
        from . import NotAny

        op = self._call_fut("not(a == 1 or a == 2 or a == 3)")
        assert isinstance(op, NotAny), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_better_not_any(self):
        from . import NotAny

        op = self._call_fut("a not in any([1, 2, 3])")
        assert isinstance(op, NotAny), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_and(self):
        from . import Eq
        from . import And

        op = self._call_fut("(a == 1) & (b == 2)")
        assert isinstance(op, And)
        query = op.queries[0]
        assert isinstance(query, Eq)
        assert query.index.name == "a"
        assert query._value == 1
        query = op.queries[1]
        assert isinstance(query, Eq)
        assert query.index.name == "b"
        assert query._value == 2

    def test_and_with_bool_syntax(self):
        from . import Eq
        from . import And

        op = self._call_fut("a == 1 and b == 2")
        assert isinstance(op, And)
        query = op.queries[0]
        assert isinstance(query, Eq)
        assert query.index.name == "a"
        assert query._value == 1
        query = op.queries[1]
        assert isinstance(query, Eq)
        assert query.index.name == "b"
        assert query._value == 2

    def test_all(self):
        from . import All

        op = self._call_fut("a == 1 and a == 2 and a == 3")
        assert isinstance(op, All), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_better_all(self):
        from . import All

        op = self._call_fut("a in all([1, 2, 3])")
        assert isinstance(op, All), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_not_all(self):
        from . import NotAll

        op = self._call_fut("not(a == 1 and a == 2 and a == 3)")
        assert isinstance(op, NotAll), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_better_not_all(self):
        from . import NotAll

        op = self._call_fut("a not in all([1, 2, 3])")
        assert isinstance(op, NotAll), op
        assert op.index.name == "a"
        assert op._value == [1, 2, 3]

    def test_all_with_or(self):
        # Regression test for earlier bug where:
        #   a == 1 or a == 2 and a == 3
        # was transformed into:
        #   a any [1, 2, 3]
        from . import All
        from . import Eq
        from . import Or

        op = self._call_fut("a == 1 or a == 2 and a == 3")
        assert isinstance(op, Or)
        assert isinstance(op.queries[0], Eq)
        assert isinstance(op.queries[1], All)
        assert op.queries[1].index.name == "a"
        assert op.queries[1]._value == [2, 3]

    def test_convert_gtlt_to_range(self):
        from . import InRange

        op = self._call_fut("a < 1 and a > 0")
        assert isinstance(op, InRange)
        assert op._start == 0
        assert op._end == 1
        assert op.start_exclusive == True
        assert op.end_exclusive == True

    def test_convert_ltgt_to_range(self):
        from . import InRange

        op = self._call_fut("a > 0 and a < 1")
        assert isinstance(op, InRange)
        assert op._start == 0
        assert op._end == 1
        assert op.start_exclusive == True
        assert op.end_exclusive == True

    def test_convert_gtlt_to_not_in_range(self):
        from . import NotInRange

        op = self._call_fut("a < 0 or a > 1")
        assert isinstance(op, NotInRange)
        assert op._start == 0
        assert op._end == 1
        assert op.start_exclusive == False
        assert op.end_exclusive == False

    def test_convert_ltgt_to_not_in_range(self):
        from . import NotInRange

        op = self._call_fut("a > 1 or a < 0")
        assert isinstance(op, NotInRange)
        assert op._start == 0
        assert op._end == 1
        assert op.start_exclusive == False
        assert op.end_exclusive == False

    def test_convert_gtlt_child_left_nephew_left(self):
        from . import Eq
        from . import And
        from . import InRange

        op = self._call_fut("a > 0 and (a < 5 and b == 7)")
        assert isinstance(op, And)
        assert isinstance(op.queries[0], InRange)
        assert isinstance(op.queries[1], Eq)

    def test_strange_gtlt_child_left_nephew_right(self):
        from . import Eq
        from . import And
        from . import InRange

        op = self._call_fut("a > 0 and (b == 7 and a < 5)")
        assert isinstance(op, And)
        assert isinstance(op.queries[0], InRange)
        assert isinstance(op.queries[1], Eq)

    def test_convert_gtlt_child_right_nephew_left(self):
        from . import Eq
        from . import Gt
        from . import And
        from . import InRange

        op = self._call_fut("a >= -1 and b == 2 and c > 3 and a <= 1")
        assert isinstance(op, And)
        assert isinstance(op.queries[0], InRange)
        assert isinstance(op.queries[1], Eq)
        assert isinstance(op.queries[2], Gt)

    def test_convert_gtlt_both_descendants(self):
        from . import Eq
        from . import Gt
        from . import And
        from . import InRange

        op = self._call_fut("b == 2 and a > -1 and (a <= 1 and c > 3)")
        assert isinstance(op, And)
        assert isinstance(op.queries[0], Eq)
        assert isinstance(op.queries[1], InRange)
        assert isinstance(op.queries[2], Gt)

    def test_convert_gtlt_both_descendants_multiple_times(self):
        from . import And
        from . import InRange

        op = self._call_fut(
            "(a > 0 and b > 0 and c > 0) and (a < 5 and b < 5 and c < 5)"
        )
        assert isinstance(op, And)
        assert isinstance(op.queries[0], InRange)
        assert isinstance(op.queries[1], InRange)
        assert isinstance(op.queries[2], InRange)

    def test_dont_convert_gtlt_to_range_with_or_spread_out(self):
        from . import Gt
        from . import Lt
        from . import And
        from . import Or

        op = self._call_fut("a > 0 and b > 0 or a < 5 and b < 5")
        assert isinstance(op, Or)
        assert isinstance(op.queries[0], And)
        assert isinstance(op.queries[0].queries[0], Gt)
        assert isinstance(op.queries[0].queries[1], Gt)
        assert isinstance(op.queries[1], And)
        assert isinstance(op.queries[1].queries[0], Lt)
        assert isinstance(op.queries[1].queries[1], Lt)


class DummyIndex(object):
    def __init__(self, name=None):
        self.name = name

    def flush(self, value):
        self.flushed = value

    def applyContains(self, value):
        self.contains = value
        return value

    def applyNotContains(self, value):
        self.not_contains = value
        return value

    def applyEq(self, value):
        self.eq = value
        return value

    def applyNotEq(self, value):
        self.not_eq = value
        return value

    def applyGt(self, value):
        self.gt = value
        return value

    def applyLt(self, value):
        self.lt = value
        return value

    def applyGe(self, value):
        self.ge = value
        return value

    def applyLe(self, value):
        self.le = value
        return value

    def applyAny(self, value):
        self.any = value
        return value

    def applyNotAny(self, value):
        self.not_any = value
        return value

    def applyAll(self, value):
        self.all = value
        return value

    def applyInRange(self, start, end, start_exclusive, end_exclusive):
        self.range = (start, end, start_exclusive, end_exclusive)
        return self.range

    def applyNotInRange(self, start, end, start_exclusive, end_exclusive):
        self.not_range = (start, end, start_exclusive, end_exclusive)
        return self.not_range

    def qname(self):
        return str(self.name)

    def resultset_from_query(self, query, names=None, resolver=None):
        return {"query": query, "names": names, "resolver": resolver}


class DummyFamily(object):
    @property
    def IF(self):
        return self

    def Set(self):
        return set()


class DummyQuery(object):
    applied = False
    negated = False
    flushed = False
    intersected = None
    unioned = None

    def __init__(self, results, index=None):
        self.results = results
        self.index = index

    def _apply(self, names):
        self.applied = True
        return self.results

    def negate(self):
        self.negated = True
        return self

    def _optimize(self):
        return self

    def flush(self, value):
        self.flushed = value

    def intersect(self, theset, names):
        result = self._apply(names)
        if (not theset) or (not result):
            return result
        self.intersected = (theset, result)
        return theset & result

    def union(self, theset, names):
        result = self._apply(names)
        self.unioned = (theset, result)
        return theset | result
