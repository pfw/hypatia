from typing import Any

from ..field import FieldIndex

from zope.interface import implementer

from .. import interfaces

from pygeos import STRtree
from pygeos.lib import Geometry
from pygeos.io import to_wkt, from_wkt, to_wkb, from_wkb

_marker = []


@implementer(
    interfaces.IIndex,
    interfaces.IIndexStatistics,
)
class SpatialIndex(FieldIndex):
    _v_rtree: STRtree
    _v_geometries_idx_to_key: dict

    def to_wkb(self, geometry):
        return to_wkb(geometry, output_dimension=2)

    def reset(self):
        super().reset()
        if hasattr(self, "_v_rtree"):
            tree = self._v_rtree
            del tree
            delattr(self, "_v_rtree")
            delattr(self, "_v_geometries_idx_to_key")

    def discriminate(self, obj, default):
        geometry = super().discriminate(obj, default)
        if not isinstance(geometry, Geometry):
            raise ValueError("Not a pygeos geometry")
        return self.to_wkb(geometry)

    def index_doc(self, docid: int, value: Any):
        super().index_doc(docid, value)
        self.destroy_tree()

    def destroy_tree(self):
        if hasattr(self, "_v_rtree"):
            tree = self._v_rtree
            del tree
            delattr(self, "_v_rtree")
            delattr(self, "_v_geometries_idx_to_key")

    @property
    def tree(self):
        """
        Build a pygeos strtree from the items in this index
        """
        if not hasattr(self, "_v_rtree"):
            geometries = []
            self._v_geometries_idx_to_key = {}
            for idx, (key, geometry) in enumerate(self._rev_index.items()):
                geometries.append(from_wkb(geometry=geometry))
                self._v_geometries_idx_to_key[idx] = key
            self._v_rtree = STRtree(geometries)
        return self._v_rtree

    def apply(self, geometry: Geometry, predictate="intersects"):
        return self.family.IF.Set(
            [
                self._v_geometries_idx_to_key[idx]
                for idx in self.tree.query(geometry, predicate=predictate)
            ]
        )

    def intersects(self, geometry: Geometry):
        return self.apply(geometry=geometry, predictate="intersects")
