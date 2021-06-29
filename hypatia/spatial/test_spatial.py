from dataclasses import dataclass

import numpy as np
import pygeos
import pytest
from pygeos.creation import box
from pygeos import STRtree

from hypatia.spatial import SpatialIndex

_marker = object()


class Test_SpatialIndex:
    def _getTargetClass(self):
        from . import SpatialIndex

        return SpatialIndex

    def _makeOne(self, discriminator=None, family=None):
        def _discriminator(obj, default):
            if obj is _marker:
                return default
            return obj

        if discriminator is None:
            discriminator = _discriminator
        return self._getTargetClass()(discriminator=discriminator, family=family)

    def test_document_repr(self):
        index = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert index.document_repr(1) == repr(index.to_wkb(box(5, 5, 25, 25)))
        assert index.document_repr(50, True) is True

    def test_class_conforms_to_IIndexInjection(self):
        from zope.interface.verify import verifyClass
        from hypatia.interfaces import IIndexInjection

        verifyClass(IIndexInjection, self._getTargetClass())

    def test_instance_conforms_to_IIndexInjection(self):
        from zope.interface.verify import verifyObject
        from hypatia.interfaces import IIndexInjection

        verifyObject(IIndexInjection, self._makeOne())

    def test_class_conforms_to_IIndex(self):
        from zope.interface.verify import verifyClass
        from hypatia.interfaces import IIndex

        verifyClass(IIndex, self._getTargetClass())

    def test_instance_conforms_to_IIndex(self):
        from zope.interface.verify import verifyObject
        from hypatia.interfaces import IIndex

        verifyObject(IIndex, self._makeOne())

    def test_ctor_defaults(self):
        import BTrees

        index: SpatialIndex = self._makeOne()
        assert index.family is BTrees.family64
        assert index.indexed_count() == 0

        assert not hasattr(index, "_v_rtree")

    def test_ctor_explicit_family(self):
        import BTrees

        index = self._makeOne(family=BTrees.family32)
        assert index.family is BTrees.family32

    def test_index_doc_new(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert index.indexed_count() == 1
        assert 1 in index._rev_index

    def test_index_doc_existing_same_value(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(1, box(5, 5, 25, 25))
        assert index.indexed_count() == 1

    def test_index_doc_not_geometry(self):
        index: SpatialIndex = self._makeOne()
        with pytest.raises(ValueError):
            index.index_doc(1, (5, 5, 25, 25))

    def test_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert list(index.intersects(box(0, 0, 100, 100))) == [1]

    def test_not_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert list(index.intersects(box(100, 100, 200, 200))) == []

    def test_apply_intersects(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert (
            list(
                index.apply(
                    box(0, 0, 100, 100),
                    "intersects",
                )
            )
            == [1]
        )

    def test_apply_not_intersects(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert (
            list(
                index.apply(
                    box(0, 0, 1, 1),
                    "intersects",
                )
            )
            == []
        )

    def test_unindex_doc_new(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.unindex_doc(1)
        assert index.indexed_count() == 0
        assert 1 not in index._rev_index
        assert len(index.tree.geometries) == index.indexed_count()

    def test_reset(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        assert isinstance(index.tree, STRtree)
        assert hasattr(index, "_v_rtree")
        index.reset()
        assert not hasattr(index, "_v_rtree")
        assert index.indexed_count() == 0
        assert 1 not in index._rev_index
        assert len(index.tree.geometries) == 0

    def test_index_many_points(self):
        index: SpatialIndex = self._makeOne()
        points = pygeos.points(np.arange(1000), np.arange(1000))
        for i in range(1000):
            index.index_doc(i, points[i])

        index.intersects(box(2, 2, 4, 4))

    def test_tree_invalidation(self):
        from ZODB import MappingStorage, DB
        import transaction
        from pygeos.lib import Geometry

        storage = MappingStorage.MappingStorage()
        db = DB(storage)
        connection = db.open()
        root = connection.root

        @dataclass
        class Thing:
            geom: Geometry

        index: SpatialIndex = SpatialIndex("geom")
        root.index = index
        index.index_doc(1, Thing(geom=box(5, 5, 25, 25)))
        assert list(index.intersects(box(0, 0, 200, 200))) == [1]
        assert hasattr(index, "_v_rtree")

        index.index_doc(2, Thing(geom=box(5, 5, 25, 25)))
        assert not hasattr(index, "_v_rtree")
        transaction.commit()

        connection2 = db.open()
        root2 = connection2.root
        index2: SpatialIndex = root2.index
        assert not hasattr(index2, "_v_rtree")
        assert list(index2.intersects(box(0, 0, 200, 200))) == [1, 2]
        assert hasattr(index2, "_v_rtree")

        index.index_doc(3, Thing(geom=box(6, 6, 25, 25)))
        assert not hasattr(index, "_v_rtree")
        assert hasattr(index2, "_v_rtree")

        assert list(index.intersects(box(0, 0, 200, 200))) == [1, 2, 3]
        assert list(index2.intersects(box(0, 0, 200, 200))) == [1, 2]
