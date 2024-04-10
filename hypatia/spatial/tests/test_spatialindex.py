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
from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from types import GeneratorType

from shapely import Point, wkt
from shapely.geometry.base import BaseGeometry

from hypatia.field import FieldIndex
from hypatia.spatial import SpatialIndex
from shapely.geometry import box

from hypatia.spatial.tests.belgium_simple import provinces, geometries
from hypatia.util import ResultSet

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

    def test_ctor_callback_discriminator(self):
        def _discriminator(obj, default):
            """ """

        index = self._makeOne(discriminator=_discriminator)
        self.assertTrue(index.discriminator is _discriminator)

    def test_ctor_string_discriminator(self):
        index = self._makeOne(discriminator="abc")
        self.assertEqual(index.discriminator, "abc")

    def test_ctor_invalid_discriminator(self):
        self.assertRaises(ValueError, self._makeOne, discriminator=1)

    def test_discriminator(self):
        @dataclass
        class Item:
            bounds: BaseGeometry

        index = self._makeOne(discriminator="bounds")
        index.index_doc(1, Item(bounds=box(5, 5, 25, 25)))
        self.assertEqual(index.document_repr(1), "(5.0, 5.0, 25.0, 25.0)")

    def test_index_doc_value_is_marker(self):
        index = self._makeOne()
        # this should never be raised
        index.unindex_doc = lambda *arg, **kw: 0 / 1
        index.index_doc(1, _marker)
        self.assertTrue(1 in index._not_indexed)
        index.index_doc(1, _marker)
        self.assertTrue(1 in index._not_indexed)

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
        self.assertEqual(len(index._tree.search((5, 5, 25, 25))), 1)

    def test_index_doc_count(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.docids_count(), 1)

    def test_index_indexed(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(2, box(6, 6, 26, 26))
        self.assertEqual(set(index.indexed()), {1, 2})

    def test_index_doc_existing_same_value(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 1)
        self.assertIn(1, index._rev_index)
        self.assertEqual(len(index._tree.search((5, 5, 25, 25))), 1)

    def test_index_doc_new_same_value(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        index.index_doc(2, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 2)
        self.assertIn(1, index._rev_index)
        self.assertIn(2, index._rev_index)
        self.assertEqual(len(index._tree.search((5, 5, 25, 25))), 2)

    def test_index_none_value(self):
        index: SpatialIndex = self._makeOne(discriminator="frogs")
        index.index_doc(1, {"notfrogs": None})
        self.assertEqual(index.docids_count(), 0)
        self.assertCountEqual(index.not_indexed(), [1])

    def test_index_not_geometry(self):
        index: SpatialIndex = self._makeOne()
        self.assertRaises(
            ValueError, index.index_doc, 1, "this thing is not a geometry"
        )

    def test_index_after_none_value(self):
        index: SpatialIndex = self._makeOne(discriminator="frogs")
        index.index_doc(1, {"notfrogs": None})
        self.assertEqual(index.docids_count(), 0)
        self.assertCountEqual(index.not_indexed(), [1])

        @dataclass
        class Item:
            frogs: BaseGeometry

        index.index_doc(1, Item(box(5, 5, 25, 25)))
        self.assertEqual(index.docids_count(), 1)
        self.assertCountEqual(index.not_indexed(), [])

    def test_unindex_doc(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.indexed_count(), 1)
        index.unindex_doc(1)
        self.assertEqual(index.indexed_count(), 0)
        self.assertNotIn(1, index._rev_index)
        self.assertEqual(len(index._tree.search((5, 5, 25, 25))), 0)

    def test_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(index.intersection((0, 0, 100, 100)), [1])

    def test_not_intersection(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(index.intersection((100, 100, 200, 200)), [])

    def test_bounds(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertEqual(index.bounds(), (5, 5, 25, 25))

    def test_apply_invalid_predicate(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertRaises(ValueError, index.apply, box(0, 0, 100, 100), "notapredicate")

    def test_applyIntersects(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(index.applyIntersects(box(0, 0, 100, 100)), [1])
        self.assertCountEqual(index.applyIntersects(box(0, 0, 100, 100)), [1])

    def test_intersects_execute(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertCountEqual(
            index.intersects(box(0, 0, 100, 100)).execute().all(), [1]
        )

    def test_intersects_str(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertTrue(
            str(index.intersects(box(0, 0, 100, 100))).startswith(
                "<POLYGON ((100 0, 100 100, 0 100, 0 0, 100 0))> intersects"
                " <hypatia.spatial.SpatialIndex object at"
            )
        )

    def test_knn(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(0, 0, 0, 0))
        index.index_doc(2, box(9, 9, 9, 9))
        index.index_doc(3, box(12, 12, 12, 12))
        index.index_doc(4, box(13, 14, 19, 11))

        res = index.knn(Point(0, 0), count=1000, max_distance=12.6)
        self.assertIsInstance(res, GeneratorType)
        self.assertEqual(next(res), (0, 1))

    def test_applyNear(self):

        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(0, 0, 0, 0))
        index.index_doc(2, box(9, 9, 9, 9))
        index.index_doc(3, box(12, 12, 12, 12))
        index.index_doc(4, box(13, 14, 19, 11))

        res = index.applyNear(Point(0, 0), count=1000, max_distance=12.6)

        self.assertIsInstance(res, index.family.IF.Set)

        self.assertListEqual(list(res), [1])

    def test_near_execute(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(0, 0, 0, 0))
        index.index_doc(2, box(9, 9, 9, 9))
        index.index_doc(3, box(12, 12, 12, 12))
        index.index_doc(4, box(13, 14, 19, 11))

        res = index.near(Point(0, 0), count=1000, max_distance=12.6).execute()

        self.assertIsInstance(res, ResultSet)

        self.assertListEqual(list(res), [1])

    def test_knn_index_resultset(self):
        """
        Search and sort on a knn index, no other indexes in query
        """
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(0, 0, 0, 0))
        index.index_doc(2, box(13, 14, 19, 11))
        index.index_doc(3, box(9, 9, 9, 9))
        index.index_doc(4, box(12, 12, 12, 12))

        near_args = (Point(0, 0), 1000)

        doc_ids, sort_index = index.knn_index(*near_args)
        self.assertIsInstance(doc_ids, index.family.IF.Set)
        self.assertIsInstance(sort_index, FieldIndex)

        self.assertEqual(len(doc_ids), 4)

        res = ResultSet(doc_ids, numids=len(doc_ids), resolver=None).sort(sort_index)
        self.assertListEqual(list(res.all()), [1, 3, 4, 2])

    def test_knn_index_execute(self):
        """
        Add knn search to a query against other indexes and sort by the distance to items
        found via knn.
        """
        @dataclass
        class Thing:
            docid: int
            geometry: BaseGeometry
            age: int

        things = [
            Thing(1, geometry=box(0, 0, 0, 0), age=10),
            Thing(2, geometry=box(13, 14, 19, 11), age=8),
            Thing(3, geometry=box(9, 9, 9, 9), age=7),
            Thing(4, geometry=box(12, 12, 12, 12), age=8),
        ]

        geometry: SpatialIndex = SpatialIndex("geometry")
        age: FieldIndex = FieldIndex("age")
        for thing in things:
            geometry.index_doc(thing.docid, thing)
            age.index_doc(thing.docid, thing)

        doc_ids, sort_index = geometry.knn_index(Point(0, 0), 1000)

        res = age.eq(8).execute().intersect(doc_ids).sort(sort_index)
        self.assertListEqual(list(res.all()), [4, 2])

    def test_near_str(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertTrue(
            re.match(
                r"<POINT \(0 100\)> near <hypatia.spatial.SpatialIndex object at 0x[0-9a-f]+>",
                str(index.near(Point(0, 100))),
            )
        )

    def test_near_str_with_count(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        self.assertTrue(
            re.match(
                r"<POINT \(0 100\)> near <hypatia.spatial.SpatialIndex object at 0x[0-9a-f]+>, count=10",
                str(index.near(Point(0, 100), count=10)),
            )
        )

    def test_near_str_with_max_distance(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        print(index.near(Point(0, 100), max_distance=5))
        self.assertTrue(
            re.match(
                r"<POINT \(0 100\)> near <hypatia.spatial.SpatialIndex object at 0x[0-9a-f]+>, max_distance=5\.000000",
                str(index.near(Point(0, 100), max_distance=5)),
            )
        )

    def test_near_str_with_count_and_max_distance(self):
        index: SpatialIndex = self._makeOne()
        index.index_doc(1, box(5, 5, 25, 25))
        print(index.near(Point(0, 100), max_distance=5))
        self.assertTrue(
            re.match(
                r"<POINT \(0 100\)> near <hypatia.spatial.SpatialIndex object at 0x[0-9a-f]+>, count=10, max_distance=5\.000000",
                str(index.near(Point(0, 100), count=10, max_distance=5)),
            )
        )

    def test_commit(self):
        """
        Test the tree survives being committed and reopened
        """
        import ZODB, ZODB.FileStorage, transaction

        fs = tempfile.NamedTemporaryFile()

        storage = ZODB.FileStorage.FileStorage(fs.name)
        db = ZODB.DB(storage)
        connection = db.open()
        root = connection.root

        index: SpatialIndex = self._makeOne(discriminator="bounds")
        root.index = index

        @dataclass
        class Item:
            bounds: BaseGeometry

        for i in range(20):
            index.index_doc(i, Item(bounds=box(5, 5, 25, 25)))

        transaction.commit()
        self.assertEqual(index.document_repr(1), "(5.0, 5.0, 25.0, 25.0)")
        self.assertCountEqual(
            index.intersection((0, 0, 100, 100)),
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
            root.index.intersection((0, 0, 100, 100)),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        )

    def test_belgium(self):
        """
        Test with some real world geometries
        """

        within = (
            ("Antwerp", (4.400278, 51.217778), "Antwerp"),
            ("Ghent", (3.725278, 51.053611), "East Flanders"),
        )

        # simplified geometries mean the touching provinces are not
        # all of the ones touching in realty
        touches = {"Walloon Brabant": ("Liège", "Namur")}

        @dataclass
        class Region:
            name: str
            geometry: BaseGeometry

        index: SpatialIndex = self._makeOne(discriminator="geometry")
        for idx, geometry in enumerate(geometries):
            index.index_doc(idx, Region(provinces[idx], wkt.loads(geometry)))

        self.assertEqual(index.indexed_count(), len(provinces))

        for city, coordinates, province in within:
            self.assertCountEqual(
                index.apply(Point(*coordinates), "within"), [provinces.index(province)]
            )

        for province, neighbours in touches.items():
            self.assertCountEqual(
                index.apply(index._rev_index.get(provinces.index(province)), "touches"),
                [provinces.index(province) for province in neighbours],
            )