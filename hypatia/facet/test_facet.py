import unittest
import pytest

FACETS = [
    "price",
    "price:0-100",
    "price:100-500",
    "price:100-*",
    "color",
    "color:blue",
    "color:red",
    "size",
    "size:small",
    "size:medium",
    "size:large",
    "style",
    "style:gucci",
    "style:gucci:handbag",
    "style:gucci:dress",
]

_marker = object()


class TestCatalogFacetIndex:
    def _getTargetClass(self):
        from . import FacetIndex

        return FacetIndex

    def _makeOne(self, discriminator=None, facets=FACETS, family=_marker):
        def _discriminator(obj, default):
            return obj

        if discriminator is None:
            discriminator = _discriminator
        if family is _marker:
            return self._getTargetClass()(discriminator, facets)
        return self._getTargetClass()(discriminator, facets, family)

    def _populateIndex(self, idx):
        idx.index_doc(1, ["price:0-100", "color:blue", "style:gucci:handbag"])
        idx.index_doc(2, ["price:0-100", "color:blue", "style:gucci:dress"])
        idx.index_doc(3, ["price:0-100", "color:red", "color:blue", "style:gucci"])
        idx.index_doc(4, ["size:large"])

    def test_class_conforms_to_IIndex(self):
        from zope.interface.verify import verifyClass
        from ..interfaces import IIndex

        verifyClass(IIndex, self._getTargetClass())

    def test_instance_conforms_to_IIndex(self):
        from zope.interface.verify import verifyObject
        from ..interfaces import IIndex

        verifyObject(IIndex, self._makeOne())

    def test_document_repr(self):
        index = self._makeOne()
        self._populateIndex(index)
        assert "color:blue" in index.document_repr(1)
        assert index.document_repr(50, True) == True

    def test_ctor_defaults(self):
        from BTrees import family64

        index = self._makeOne()
        assert index.discriminator(self, index) is self
        assert list(index.facets) == sorted(FACETS)
        assert index.family is family64

    def test_ctor_explicit(self):
        from BTrees import family32

        OTHER_FACETS = ["foo", "foo:bar"]

        def _discriminator(obj, default):
            return default

        index = self._makeOne(_discriminator, OTHER_FACETS, family32)
        assert index.discriminator(self, index) is index
        assert list(index.facets) == OTHER_FACETS
        assert index.family is family32

    def test_ctor_string_discriminator(self):
        index = self._makeOne("facets")
        assert index.discriminator == "facets"

    def test_ctor_bad_discriminator(self):
        with pytest.raises(ValueError):
            self._makeOne(object())

    def test_index_doc_callback_discriminator(self):
        OTHER_FACETS = ["foo", "foo:bar", "foo:baz"]

        def _discrimintator(obj, default):
            return ["foo:bar"]

        index = self._makeOne(_discrimintator, OTHER_FACETS)
        index.index_doc(1, object())
        assert list(index._fwd_index["foo"]) == [1]
        assert list(index._fwd_index["foo:bar"]) == [1]
        assert list(index._rev_index[1]) == ["foo", "foo:bar"]

    def test_index_doc_string_discriminator(self):
        OTHER_FACETS = ["foo", "foo:bar", "foo:baz"]

        class Dummy:
            facets = ["foo:bar"]

        index = self._makeOne("facets", OTHER_FACETS)
        index.index_doc(1, Dummy())
        assert list(index._fwd_index["foo"]) == [1]
        assert list(index._fwd_index["foo:bar"]) == [1]
        assert list(index._rev_index[1]) == ["foo", "foo:bar"]

    def test_index_doc_missing_value_unindexes(self):
        OTHER_FACETS = ["foo", "foo:bar", "foo:baz"]

        class Dummy:
            pass

        dummy = Dummy()
        dummy.facets = ["foo:bar"]
        index = self._makeOne("facets", OTHER_FACETS)
        index.index_doc(1, dummy)
        del dummy.facets
        index.index_doc(1, dummy)
        assert not ("foo" in index._fwd_index)
        assert not ("foo:bar" in index._fwd_index)
        assert not (1 in index._rev_index)

    def test_index_doc_persistent_value_raises(self):
        from persistent import Persistent

        OTHER_FACETS = ["foo", "foo:bar", "foo:baz"]

        class Dummy:
            pass

        index = self._makeOne("facets", OTHER_FACETS)
        dummy = Dummy()
        dummy.facets = Persistent()
        with pytest.raises(ValueError):
            index.index_doc(1, dummy)

    def test_index_doc_unindexes_old_values(self):
        OTHER_FACETS = ["foo", "foo:bar", "foo:baz"]

        class Dummy:
            pass

        dummy = Dummy()
        dummy.facets = ["foo:bar"]
        index = self._makeOne("facets", OTHER_FACETS)
        index.index_doc(1, dummy)
        dummy.facets = ["foo:baz"]
        index.index_doc(1, dummy)
        assert list(index._fwd_index["foo"]) == [1]
        assert list(index._fwd_index["foo:baz"]) == [1]
        assert list(index._rev_index[1]) == ["foo", "foo:baz"]
        assert not ("foo:bar" in index._fwd_index)

    def test_search(self):
        index = self._makeOne()
        self._populateIndex(index)

        result = index.search(["color:blue", "color:red"])
        assert sorted(list(result)) == [3]
        result = index.search(["price"])
        assert sorted(list(result)) == [1, 2, 3]
        result = index.search(["price:0-100"])
        assert sorted(list(result)) == [1, 2, 3]
        result = index.search(["style:gucci"])
        assert sorted(list(result)) == [1, 2, 3]
        result = index.search(["style:gucci:handbag"])
        assert sorted(list(result)) == [1]
        result = index.search(["size"])
        assert sorted(list(result)) == [4]
        result = index.search(["size:large"])
        assert sorted(list(result)) == [4]
        result = index.search(["size:nonexistent"])
        assert sorted(list(result)) == []
        result = index.search(["nonexistent"])
        assert sorted(list(result)) == []

        index.unindex_doc(1)
        result = index.search(["price"])
        assert sorted(list(result)) == [2, 3]
        result = index.search(["price:0-100"])
        assert sorted(list(result)) == [2, 3]
        result = index.search(["style:gucci"])
        assert sorted(list(result)) == [2, 3]
        result = index.search(["style:gucci:handbag"])
        assert sorted(list(result)) == []

        index.unindex_doc(2)
        result = index.search(["price"])
        assert sorted(list(result)) == [3]
        result = index.search(["price:0-100"])
        assert sorted(list(result)) == [3]
        result = index.search(["style:gucci"])
        assert sorted(list(result)) == [3]

        index.unindex_doc(4)
        result = index.search(["size"])
        assert sorted(list(result)) == []
        result = index.search(["size:large"])
        assert sorted(list(result)) == []
        result = index.search(["size:nonexistent"])
        assert sorted(list(result)) == []
        result = index.search(["nonexistent"])
        assert sorted(list(result)) == []

    def test_counts(self):
        index = self._makeOne()
        self._populateIndex(index)

        search = ["price:0-100"]
        result = index.search(search)
        assert sorted(list(result)) == [1, 2, 3]
        counts = index.counts(result, search)
        assert counts["style"] == 3
        assert counts["style:gucci"] == 3
        assert counts["style:gucci:handbag"] == 1
        assert counts["style:gucci:dress"] == 1
        assert counts["color"] == 3
        assert counts["color:blue"] == 3
        assert counts["color:red"] == 1
        assert len(counts) == 7

        search = ["price:0-100", "color:red"]
        result = index.search(search)
        assert sorted(list(result)) == [3]
        counts = index.counts(result, search)
        assert counts["style"] == 1
        assert counts["style:gucci"] == 1
        assert counts["color:blue"] == 1
        assert len(counts) == 3

        search = ["size:large"]
        result = index.search(search)
        assert sorted(list(result)) == [4]
        counts = index.counts(result, search)
        assert counts == {}

        search = ["size"]
        result = index.search(search)
        assert sorted(list(result)) == [4]
        counts = index.counts(result, search)
        assert counts == {"size:large": 1}

    def test_indexed(self):
        index = self._makeOne()
        self._populateIndex(index)
        assert set(index.indexed()) == set((1, 2, 3, 4))

    def test_index_doc_missing_value_adds_to__not_indexed(self):
        def discriminator(obj, default):
            return default

        index = self._makeOne(discriminator)
        assert index.index_doc(20, 3) == None
        assert 20 in index._not_indexed

    def test_index_doc_with_value_removes_from__not_indexed(self):
        index = self._makeOne()
        index._not_indexed.add(20)
        assert index.index_doc(20, "foo") == "foo"
        assert not (20 in index._not_indexed)
