import unittest

_marker = object()


class TestCatalog(unittest.TestCase):
    def _getTargetClass(self):
        from . import Catalog

        return Catalog

    def _makeOne(self, family=_marker):
        klass = self._getTargetClass()
        if family is _marker:
            return klass()
        return klass(family)

    def test_klass_provides_ICatalog(self):
        klass = self._getTargetClass()
        from zope.interface.verify import verifyClass
        from ..interfaces import ICatalog

        verifyClass(ICatalog, klass)

    def test_inst_provides_ICatalog(self):
        from zope.interface.verify import verifyObject
        from ..interfaces import ICatalog

        inst = self._makeOne()
        verifyObject(ICatalog, inst)

    def test_ctor_defaults(self):
        from BTrees import family64

        catalog = self._makeOne()
        assert catalog.family is family64

    def test_ctor_explicit_family(self):
        from BTrees import family32

        catalog = self._makeOne(family32)
        assert catalog.family is family32

    def test_reset(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog["name"] = idx
        catalog.reset()
        assert idx.cleared == True

    def test_index_doc(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog["name"] = idx
        catalog.index_doc(1, "value")
        assert idx.docid == 1
        assert idx.value == "value"

    def test_index_doc_nonint_docid(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog["name"] = idx
        with pytest.raises(ValueError):
            catalog.index_doc("abc", "value")

    def test_reindex_doc(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog["name"] = idx
        catalog.reindex_doc(1, "value")
        assert idx.reindexed_docid == 1
        assert idx.reindexed_ob == "value"

    def test_unindex_doc(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog["name"] = idx
        catalog.unindex_doc(1)
        assert idx.unindexed == 1


class TestCatalogQuery(unittest.TestCase):
    def _makeOne(self, catalog, family=None):
        from . import CatalogQuery

        return CatalogQuery(catalog, family=family)

    def _makeCatalog(self, family=None):
        from . import Catalog

        return Catalog(family=family)

    def test_with_alternate_family(self):
        from BTrees import family32

        search = self._makeOne(None, family=family32)
        assert search.family == family32

    def test_sort(self):
        import BTrees

        IFSet = BTrees.family64.IF.Set
        catalog = self._makeCatalog()
        c1 = IFSet([1, 2, 3, 4, 5])
        idx1 = DummyIndex(c1)
        catalog["name1"] = idx1
        q = self._makeOne(catalog)
        numdocs, result = q.sort(c1, sort_index="name1", limit=1)
        assert numdocs == 1
        assert idx1.limit == 1


from ..interfaces import IIndex
from zope.interface import implementer
import pytest


@implementer(IIndex)
class DummyIndex(object):

    value = None
    docid = None
    limit = None
    sort_type = None

    def __init__(self, *arg, **kw):
        self.arg = arg
        self.kw = kw

    def index_doc(self, docid, value):
        self.docid = docid
        self.value = value
        return value

    def unindex_doc(self, docid):
        self.unindexed = docid

    def reset(self):
        self.cleared = True

    def reindex_doc(self, docid, object):
        self.reindexed_docid = docid
        self.reindexed_ob = object

    def apply(self, query):
        return self.arg[0]

    def apply_intersect(self, query, docids):  # pragma: no cover
        if docids is None:
            return self.arg[0]
        L = []
        for docid in self.arg[0]:
            if docid in docids:
                L.append(docid)
        return L

    def sort(self, results, reverse=False, limit=None, sort_type=None):
        self.limit = limit
        self.sort_type = sort_type
        if reverse:
            return ["sorted3", "sorted2", "sorted1"]
        return ["sorted1", "sorted2", "sorted3"]
