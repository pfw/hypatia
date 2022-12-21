##############################################################################
#
# Copyright (c) 2009 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Spatial Index Tests
"""
import tempfile
import unittest
from shapely.geometry import box

from hypatia.spatial import SpatialIndex

_marker = object()


class SpatialIndexTests(unittest.TestCase):
    def _getTargetClass(self):
        from .. import SpatialIndex

        return SpatialIndex

    def _makeOne(self, discriminator=_marker, family=None):
        def _discriminator(obj, default):
            if obj is _marker:
                return default
            return obj

        if discriminator is _marker:
            discriminator = _discriminator
        return self._getTargetClass()(discriminator=discriminator, family=family)

    def test_class_conforms_to_IIndex(self):
        from zope.interface.verify import verifyClass
        from hypatia.interfaces import IIndex

        verifyClass(IIndex, self._getTargetClass())

    def test_instance_conforms_to_IIndex(self):
        from zope.interface.verify import verifyObject
        from hypatia.interfaces import IIndex

        verifyObject(IIndex, self._makeOne())

    def test_document_repr(self):
        index = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.document_repr(1), "(5.0, 5.0, 25.0, 25.0)")
        self.assertEqual(index.document_repr(50, True), True)

    def test_explicit_family(self):
        import BTrees

        index = self._makeOne(family=BTrees.family32)
        assert index.family is BTrees.family32

    def test_index_doc_new(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 1)
        self.assertIn(1, index._rev_index)
        self.assertEqual(len(index._tree.search(box(5, 5, 25, 25))), 1)

    def test_index_doc_count(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.docids_count(), 1)

    def test_index_doc_existing_same_value(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 1)
        self.assertIn(1, index._rev_index)
        self.assertEqual(len(index._tree.search(box(5, 5, 25, 25))), 1)

    def test_index_doc_new_same_value(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(2, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 2)
        self.assertIn(1, index._rev_index)
        self.assertIn(2, index._rev_index)
        self.assertEqual(len(index._tree.search(box(5, 5, 25, 25))), 2)

    def test_unindex_doc(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 1)
        index.unindex_doc(1)
        self.assertEqual(index.indexed_count(), 0)
        self.assertNotIn(1, index._rev_index)
        self.assertEqual(len(index._tree.search(box(5, 5, 25, 25))), 0)

    def test_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(index.intersection(box(0, 0, 100, 100)), [1])

    def test_not_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(index.intersection(box(100, 100, 200, 200)), [])

    def test_bounds(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.bounds(), (5.0, 5.0, 25.0, 25.0))

    def test_commit(self):
        import ZODB, ZODB.FileStorage, transaction

        fs = tempfile.NamedTemporaryFile()

        storage = ZODB.FileStorage.FileStorage(fs.name)
        db = ZODB.DB(storage)
        connection = db.open()
        root = connection.root

        index: SpatialIndex = self._makeOne()
        root.index = index
        for i in range(20):
            index.index_doc(i, box(5, 5, 25, 25))

        transaction.commit()
        self.assertEqual(index.document_repr(1), "(5.0, 5.0, 25.0, 25.0)")
        self.assertCountEqual(
            index.intersection(box(0, 0, 100, 100)),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        )
        db.close()
        storage.close()

        # reopen
        storage = ZODB.FileStorage.FileStorage(fs.name)
        db = ZODB.DB(storage)
        connection = db.open()
        root = connection.root

        self.assertCountEqual(
            root.index.intersection(box(0, 0, 100, 100)),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        )
