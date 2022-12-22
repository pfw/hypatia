from __future__ import annotations
from typing import MutableMapping, MutableSet, Any, Sequence

from BTrees.Length import Length
from persistent import Persistent
from zope.interface import implementer

from .._compat import string_types
from ..interfaces import IIndex
from ..util import BaseIndexMixin
from ..query import Comparator

from .rbush import RBush, BBox

from shapely.geometry.base import BaseGeometry
from shapely import prepare, is_prepared

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
        discriminator,  # TODO - add!!
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

    def bounds(self):
        node = self._tree.data
        return node.min_x, node.min_y, node.max_x, node.max_y

    def apply(self, geometry: BaseGeometry, predicate="intersects"):
        results = self._tree.search(geometry.bounds)
        geometries = []
        for bbox in self._tree.search(geometry.bounds):
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


class Intersects(Comparator):
    """Intersects query."""

    def _apply(self, names):
        return self.index.applyIntersects(self._get_value(names))

    def __str__(self):
        return "%r intersects %s" % (self._value, self.index)
