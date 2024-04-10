from __future__ import annotations

import math
from dataclasses import dataclass
from typing import MutableMapping, MutableSet, Any, Sequence, Optional, Iterable

from BTrees.Length import Length
from persistent import Persistent
from zope.interface import implementer

from .._compat import string_types
from ..field import FieldIndex
from ..interfaces import IIndex
from ..util import BaseIndexMixin
from ..query import Comparator

from .rbush import RBush, BBox

from shapely.geometry.base import BaseGeometry
from shapely import prepare, is_prepared, Point

_marker = []

PREDICATES = ("intersects", "overlaps", "within", "touches")


@implementer(IIndex)
class SpatialIndex(BaseIndexMixin, Persistent):
    """A spatial index. You can insert objects with their coordinates and later
    perform queries on the index.
    """

    _tree: RBush
    _rev_index: MutableMapping
    _not_indexed: MutableSet
    _num_docs: Length

    def __init__(
        self,
        discriminator,
        family=None,
    ):
        if family is not None:
            self.family = family
        if not callable(discriminator):
            if not isinstance(discriminator, string_types):
                raise ValueError("discriminator value must be callable or a " "string")
        self.discriminator = discriminator

        self.reset()

    def reset(self):
        self._tree = RBush()
        self._rev_index = self.family.IO.BTree()
        self._not_indexed = self.family.IF.TreeSet()
        self._num_docs = Length(0)

    def document_repr(self, docid, default=None):
        result: BaseGeometry = self._rev_index.get(docid, default)
        if result is not default:
            return repr(result.bounds)
        return default

    def indexed(self):
        return self._rev_index.keys()

    def not_indexed(self):
        return self._not_indexed

    def indexed_count(self):
        return self._num_docs.value

    def index_doc(self, docid: int, value: Any):
        """Inserts object with bounds into this index."""
        value = self.discriminate(value, _marker)
        if value is _marker or value is None:
            if not (docid in self._not_indexed):
                # unindex the previous value
                self.unindex_doc(docid)
                # Store docid in set of unindexed docids
                self._not_indexed.add(docid)
            return None

        if not isinstance(value, BaseGeometry):
            raise ValueError(f"Value not a geometry: {value}")

        bbox = BBox(docid, *value.bounds)

        if docid in self._not_indexed:
            # Remove from set of unindexed docs if it was in there.
            self._not_indexed.remove(docid)

        if docid in self._rev_index:
            # unindex doc if present, can be optimised to skip
            # if the item is unchanged from what is indexed
            self.unindex_doc(docid)
            self._tree.remove(bbox)

        self._tree.insert(bbox)
        self._rev_index[docid] = value
        # increment doc count
        self._num_docs.change(1)

    def unindex_doc(self, docid):
        """Deletes an item from this index"""
        try:
            geometry = self._rev_index.pop(docid)
        except KeyError:
            # docid was not indexed
            return
        self._tree.remove(BBox(docid, *geometry.bounds))
        # increment doc count
        self._num_docs.change(-1)

    def docids_count(self):
        return len(self._rev_index)

    def intersection(
        self,
        bounds: tuple[int | float, int | float, int | float, int | float],
    ):
        """
        Returns all docids which are within the given bounds but does NOT
        perform an exact match on the geometries
        """
        for bbox in self._tree.search(bounds):
            yield bbox.key

    def knn(
        self,
        point: Point,
        count: Optional[int] = None,
        max_distance: Optional[float] = None,
    ) -> Iterable[tuple[int, int]]:
        """
        Returns the nearest items within max_distance of the given point, not more than count docids.
        """
        for dist, bbox in self._tree.knn((point.x, point.y), count, max_distance):
            yield dist, bbox.key

    @dataclass
    class ByDistance:
        distance: float

    def knn_index(
        self,
        point: Point,
        count: Optional[int] = None,
        max_distance: Optional[float] = None,
    ) -> tuple[set[int], FieldIndex]:
        """
        Return ids and an index for sorting by distance.

        doc_ids, sort_index = root.index.knn_index(Point(149.05209129629245,-35.36327793337446), count=15)

        If there is only a query via distance then create a Result object with the result
        of a call to knn_index, eg:

        rs = ResultSet(ids=doc_ids, numids=len(doc_ids), resolver=None).sort(sort_index)


        If there is an existing ResultSet from a call to .execute() then intersect the doc_ids and sort, eg:

        rs.intersect(doc_ids).sort(sort_index)

        This can be done in a query with other indexes,eg

        other_index.eq(12).intersect(doc_ids).sort(sort_index)

        """
        sort_index = FieldIndex("distance")
        doc_ids = self.family.IF.Set()
        for dist, bbox in self._tree.knn((point.x, point.y), count, max_distance):
            doc_ids.add(bbox.key)
            sort_index.index_doc(bbox.key, self.ByDistance(dist))
        return doc_ids, sort_index

    def bounds(self):
        node = self._tree.data
        return node.min_x, node.min_y, node.max_x, node.max_y

    def apply(self, geometry: BaseGeometry, predicate="intersects"):
        prepare(geometry)  # prepare the search geometry
        results = []
        geometries = []
        for bbox in self._tree.search(geometry.bounds):
            results.append(bbox)
            geometries.append(self._rev_index[bbox.key])
            prepare(geometries[-1])

        if predicate not in PREDICATES:
            raise ValueError(f"Invalid predicate: {predicate}")

        by_predicate = getattr(geometry, predicate)(geometries)

        return self.family.IF.Set(
            [bbox.key for idx, bbox in enumerate(results) if by_predicate[idx]]
        )

    def applyIntersects(self, geometry: BaseGeometry):
        return self.apply(geometry)

    def intersects(self, value: BaseGeometry):
        return Intersects(self, value)

    def applyNear(
        self,
        point: Point,
        count: Optional[int] = None,
        max_distance: Optional[float | int] = None,
    ):
        return self.family.IF.Set(
            [
                bbox.key
                for dist, bbox in self._tree.knn(
                    (point.x, point.y), count, max_distance
                )
            ]
        )

    def near(
        self,
        point: Point,
        count: Optional[int] = None,
        max_distance: Optional[float] = None,
    ):
        return Near(self, point, count, max_distance)


class Intersects(Comparator):
    """Intersects query."""

    def _apply(self, names):
        return self.index.applyIntersects(self._get_value(names))

    def __str__(self):
        return "%r intersects %s" % (self._value, self.index)


class Near(Comparator):

    def __init__(self, index, value, count, max_distance):
        super().__init__(index, value)
        self.count = count
        self.max_distance = max_distance

    def _apply(self, names):
        return self.index.applyNear(
            self._get_value(names), count=self.count, max_distance=self.max_distance
        )

    def __str__(self):
        return "%r near %s%s%s" % (
            self._value,
            self.index,
            ", count=%d" % self.count if self.count else "",
            ", max_distance=%f" % self.max_distance if self.max_distance else "",
        )
