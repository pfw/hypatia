from typing import MutableMapping, MutableSet

from BTrees.Length import Length
from persistent import Persistent
from zope.interface import implementer

from hypatia.interfaces import IIndex
from hypatia.spatial.rbush import RBush, BBox
from hypatia.util import BaseIndexMixin

from shapely.geometry.base import BaseGeometry

_marker = []


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

        self.reset()

    def reset(self):
        self._tree = RBush()
        self._rev_index = self.family.IO.BTree()
        self._not_indexed = self.family.IF.TreeSet()
        self._num_docs = Length(0)

    def document_repr(self, docid, default=None):
        result: BBox = self._rev_index.get(docid, default)
        if result is not default:
            return repr((result.min_x, result.min_y, result.max_x, result.max_y))
        return default

    def indexed(self):
        return self._rev_index.keys()

    def not_indexed(self):
        return self._not_indexed

    def index_doc(self, docid: int, geometry: BaseGeometry):
        """Inserts object with bounds into this index."""
        # TODO
        # value = self.discriminate(value, _marker)

        if docid in self._rev_index:
            return
        bbox = BBox(docid, geometry)
        self._tree.insert(bbox)
        self._rev_index[docid] = bbox
        # increment doc count
        self._num_docs.change(1)

    def unindex_doc(self, docid):
        """Deletes an item from this index"""
        try:
            bbox = self._rev_index.pop(docid)
        except KeyError:
            # docid was not indexed
            return
        self._tree.remove(bbox)
        # increment doc count
        self._num_docs.change(-1)

    def docids_count(self):
        return len(self._rev_index)

    def intersection(self, coordinates):
        """Returns all docids which are within the given bounds."""
        for bbox in self._tree.search(coordinates):
            yield bbox.key

    def bounds(self):
        node = self._tree.data
        return node.min_x, node.min_y, node.max_x, node.max_y
