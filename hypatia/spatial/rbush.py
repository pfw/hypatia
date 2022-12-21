from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from operator import attrgetter
from typing import Callable

from persistent import Persistent
from persistent.list import PersistentList
from shapely.geometry.base import BaseGeometry
from shapely import prepare


@dataclass(order=True, eq=True)
class BBox:
    key: int

    # TODO - remove the geometry from the tree, just store in the index
    geometry: BaseGeometry = field(compare=False)

    min_x: int | float = field(init=False)
    min_y: int | float = field(init=False)
    max_x: int | float = field(init=False)
    max_y: int | float = field(init=False)

    def __post_init__(self):
        # TODO - don't take geometry
        self.min_x, self.min_y, self.max_x, self.max_y = self.geometry.bounds
        prepare(self.geometry)

    # TODO - prepare when loaded from ZODB, __setstate__???


# TODO - can become a subclass of BBox when geometry is removed
@dataclass
class Node:
    children: list[BBox | Node] = field(default_factory=PersistentList)
    height: int = field(default=1)
    leaf: bool = field(default=True)

    min_x: int | float = field(default=math.inf)
    min_y: int | float = field(default=math.inf)
    max_x: int | float = field(default=-math.inf)
    max_y: int | float = field(default=-math.inf)


def splice(items, start, end):
    """
    Emulate JS splice, returns what was replaced and
    updates the items in place
    :param items:
    :param start:
    :param end:
    :return:
    """
    removed = items[start:end]
    items[start:end] = []
    return removed


def intersects(a: BBox | Node, b: BBox | Node) -> bool:
    # TODO - check for BBox which spans the antimeridian
    return (
        b.min_x <= a.max_x
        and b.min_y <= a.max_y
        and b.max_x >= a.min_x
        and b.max_y >= a.min_y
    )


def contains(a: BBox | Node, b: BBox | Node) -> bool:
    return (
        a.min_x <= b.min_x
        and a.min_y <= b.min_y
        and b.max_x <= a.max_x
        and b.max_y <= a.max_y
    )


def intersection_area(a: BBox | Node, b: BBox | Node) -> float:
    min_x = max(a.min_x, b.min_x)
    min_y = max(a.min_y, b.min_y)
    max_x = min(a.max_x, b.max_x)
    max_y = min(a.max_y, b.max_y)

    return max(0, max_x - min_x) * max(0, max_y - min_y)


def enlarged_area(a: BBox | Node, b: BBox | Node) -> float:
    return (max(b.max_x, a.max_x) - min(b.min_x, a.min_x)) * (
        max(b.max_y, a.max_y) - min(b.min_y, a.min_y)
    )


def bbox_area(a: BBox | Node) -> float:
    return (a.max_x - a.min_x) * (a.max_y - a.min_y)


def bbox_margin(a: BBox | Node) -> float:
    return (a.max_x - a.min_x) + (a.max_y - a.min_y)


def extend(a: BBox | Node, b: BBox | Node):
    a.min_x = min(a.min_x, b.min_x)
    a.min_y = min(a.min_y, b.min_y)
    a.max_x = max(a.max_x, b.max_x)
    a.max_y = max(a.max_y, b.max_y)


def multi_select(items: list[BBox], left: int, right: int, n: int, compare: Callable):
    """
    sort an array so that items come in groups of n unsorted items, with groups sorted between each other;
    combines selection algorithm with binary divide & conquer approach
    """
    stack = [left, right]
    while len(stack):
        right = stack.pop()
        left = stack.pop()
        if (right - left) <= n:
            continue
        mid = left + math.ceil((right - left) / n / 2) * n
        quickselect(items, mid, left, right, compare)
        stack.extend([left, mid, mid, right])


class RBush(Persistent):
    node_type: Node = Node
    _max_entries: int = 9

    def __init__(self, max_entries: int | None = None):
        if max_entries:
            self._max_entries: int = max(4, max_entries)
        self._min_entries: int = max(2, math.ceil(self._max_entries * 0.4))
        self.data: Node = self.node_type()

    def clear(self):
        self.data = self.node_type()

    def all(
        self, node: Node | BBox | None = None, result: list | None = None
    ) -> list[BBox]:
        if not node:
            node = self.data
        if result is None:
            result = []

        nodes_to_search = []
        while node:
            if node.leaf:
                result.extend(node.children)
            else:
                nodes_to_search.extend(node.children)

            node = nodes_to_search.pop() if len(nodes_to_search) else None

        return result

    # TODO - take bounds not a a geometry and not exact option
    def search(self, geometry: BaseGeometry, exact=False) -> list[BBox]:
        prepare(geometry)  # TODO - don't prepare
        bbox = BBox(-1, geometry)

        node = self.data
        result = []

        if not intersects(bbox, node):
            return result

        nodes_to_search: list[BBox] = []

        while node:
            for child in node.children:

                if intersects(bbox, child):
                    if node.leaf:
                        result.append(child)
                    elif contains(bbox, child):
                        self.all(child, result)
                    else:
                        nodes_to_search.append(child)
            node = nodes_to_search.pop() if nodes_to_search else None

        # TODO - move this to the index so that we don't store the full geometry in the tree
        # intersect the full geometries
        if exact:
            exact_intersects = geometry.intersects([r.geometry for r in result])
            return [r for idx, r in enumerate(result) if exact_intersects[idx]]
        else:
            return result

    def dist_bbox(self, node: Node, k: int, p: int, dest_node: Node | None = None):
        """
        min bounding rectangle of node children from k to p-1
        """
        if dest_node is None:
            dest_node = self.node_type()

        dest_node.min_x = math.inf
        dest_node.min_y = math.inf
        dest_node.max_x = -math.inf
        dest_node.max_y = -math.inf

        for i in range(k, p):
            child = node.children[i]
            extend(dest_node, child)

        return dest_node

    def calc_bbox(self, node: Node):
        """
        calculate node's bbox from bboxes of its children
        """
        return self.dist_bbox(node, 0, len(node.children), node)

    def _split_root(self, node: Node, new_node: Node):
        # split root node
        self.data = self.node_type(children=PersistentList([node, new_node]))
        self.data.height = node.height + 1
        self.data.leaf = False
        self.calc_bbox(self.data)

    def _choose_subtree(self, bbox: BBox, node: Node, level, path: list) -> Node:
        while True:
            path.append(node)

            if node.leaf or len(path) - 1 == level:
                break

            min_area = math.inf
            min_enlargement = math.inf
            target_node: BBox | None = None

            for child in node.children:
                area = bbox_area(child)
                enlargement = enlarged_area(bbox, child) - area

                # choose entry with the least area enlargement
                if enlargement < min_enlargement:
                    min_enlargement = enlargement
                    min_area = area if area < min_area else min_area
                    target_node = child

                elif enlargement == min_enlargement:
                    # otherwise choose one with the smallest area
                    if area < min_area:
                        min_area = area
                        target_node = child

            node = target_node or node.children[0]

        return node

    def _all_dist_margin(self, node: Node, m: int, M: int, compare: Callable) -> float:
        """
        total margin of all possible split distributions where each node is at least m full
        """
        node.children.sort(key=compare)

        left_bbox = self.dist_bbox(node, 0, m)
        right_bbox = self.dist_bbox(node, M - m, M)
        margin = bbox_margin(left_bbox) + bbox_margin(right_bbox)
        for i in range(m, M - m):
            child = node.children[i]
            extend(left_bbox, child)
            margin += bbox_margin(left_bbox)

        for i in range(M - m - 1, m - 1, -1):

            child = node.children[i]
            extend(right_bbox, child)
            margin += bbox_margin(right_bbox)

        return margin

    def _choose_split_axis(self, node: Node, m, M):
        x_margin = self._all_dist_margin(node, m, M, attrgetter("min_x"))
        y_margin = self._all_dist_margin(node, m, M, attrgetter("min_y"))

        # if total distributions margin value is minimal for x, sort by min_x,
        # otherwise it's already sorted by min_y
        if x_margin < y_margin:
            node.children.sort(key=attrgetter("min_x"))

    def _choose_split_index(self, node: Node, m: int, M: int) -> int:
        index: int | None = None
        min_overlap = math.inf
        min_area = math.inf

        for i in range(m, M - m + 1):
            bbox1 = self.dist_bbox(node, 0, i)
            bbox2 = self.dist_bbox(node, i, M)

            overlap = intersection_area(bbox1, bbox2)
            area = bbox_area(bbox1) + bbox_area(bbox2)

            # choose distribution with minimum overlap
            if overlap < min_overlap:
                min_overlap = overlap
                index = i

                min_area = area if area < min_area else min_area

            elif overlap == min_overlap:
                # otherwise choose distribution with minimum area
                if area < min_area:
                    min_area = area
                    index = i

        return index or M - m

    def _split(self, insert_path: list[Node], level: int):
        """
        split overflowed node into two
        """
        node = insert_path[level]
        M = len(node.children)
        m = self._min_entries

        self._choose_split_axis(node, m, M)

        split_index = self._choose_split_index(node, m, M)

        new_node = self.node_type(
            children=splice(
                node.children,
                split_index,
                split_index + len(node.children) - split_index,
            )
        )
        new_node.height = node.height
        new_node.leaf = node.leaf

        self.calc_bbox(node)
        self.calc_bbox(new_node)

        if level:
            insert_path[level - 1].children.append(new_node)
        else:
            self._split_root(node, new_node)

    def _adjust_parent_bboxes(self, bbox: BBox, path: list[Node], level: int):
        # adjust bboxes along the given tree path
        for i in range(level, -1, -1):
            extend(path[i], bbox)

    def _insert(self, item: BBox | Node, level: int):

        insert_path: list[Node] = []

        # find the best node for accommodating the item, saving all nodes along the path too
        node = self._choose_subtree(item, self.data, level, insert_path)

        # put the item into the node
        node.children.append(item)
        extend(node, item)

        # split on node overflow; propagate upwards if necessary
        while level >= 0:
            if len(insert_path[level].children) > self._max_entries:
                self._split(insert_path, level)
                level -= 1
            else:
                no_peephole_opt = None  # a bare break isn't found by coverage
                break

        # adjust bboxes along the insertion path
        self._adjust_parent_bboxes(item, insert_path, level)

    def insert(self, item: BBox):
        if item:
            self._insert(item, self.data.height - 1)

    def _build(self, items: list, left: int, right: int, height: int):
        N = right - left + 1
        M = self._max_entries

        if N <= M:
            # reached leaf level; return leaf
            node = self.node_type(children=items[left : right + 1])
            self.calc_bbox(node)
            return node

        if not height:
            # target height of the bulk-loaded tree
            height = math.ceil(math.log(N) / math.log(M))

            # target number of root entries to maximize storage utilization
            M = math.ceil(N / math.pow(M, height - 1))

        node = self.node_type()
        node.leaf = False
        node.height = height

        # split the items into M mostly square tiles
        N2 = math.ceil(N / M)
        N1 = N2 * math.ceil(math.sqrt(M))

        multi_select(items, left, right, N1, attrgetter("min_x"))

        for i in list(range(left, right + 1, N1)):
            right2 = min(i + N1 - 1, right)

            multi_select(items, i, right2, N2, attrgetter("min_y"))

            for j in list(range(i, right2 + 1, N2)):
                right3 = min(j + N2 - 1, right2)

                # pack each entry recursively
                node.children.append(self._build(items, j, right3, height - 1))

        self.calc_bbox(node)

        return node

    def load(self, data: list[BBox]):
        if not (data and len(data)):
            return self

        if len(data) < self._min_entries:
            for item in data:
                self.insert(item)
            return self

        data = data[:]  # copy data as the load process messes with it
        # recursively build the tree with the given data from scratch using OMT algorithm
        node = self._build(data, 0, len(data) - 1, 0)

        if not len(self.data.children):
            # save as is if tree is empty
            self.data = node

        elif self.data.height == node.height:
            # split root if trees have the same height
            self._split_root(self.data, node)
        else:
            if self.data.height < node.height:
                # swap trees if inserted one is bigger
                self.data, node = node, self.data

            # insert the small tree into the large tree at appropriate level
            self._insert(node, self.data.height - node.height - 1)

    def _condense(self, path: list[Node]):
        # go through the path, removing empty nodes and updating bboxes
        for i in range(len(path) - 1, -1, -1):

            if len(path[i].children) == 0:
                if i > 0:
                    siblings = path[i - 1].children
                    index = siblings.index(path[i])
                    splice(siblings, index, index + 1)

                else:
                    self.clear()

            else:
                self.calc_bbox(path[i])

    def remove(self, item: BBox):
        node = self.data
        path: list[Node] = []
        indexes: list[int] = []

        i: int | None = None
        parent: Node | None = None
        going_up: bool = False

        # depth-first iterative tree traversal
        while node or len(path):

            if not node:  # go up
                node = path.pop()
                try:
                    parent = path[-1]
                except IndexError:
                    parent = None
                i = indexes.pop()
                going_up = True

            if node.leaf:  # check current node
                if item in node.children:
                    index = node.children.index(item)
                    # item found, remove the item and condense tree upwards
                    node.children[index : index + 1] = []
                    path.append(node)
                    self._condense(path)
                    return self

            if not going_up and not node.leaf and contains(node, item):  # go down
                path.append(node)
                indexes.append(i)
                i = 0
                parent = node
                node = node.children[0]

            elif parent:  # go right
                i += 1
                try:
                    node = parent.children[i]
                except IndexError:
                    node = None
                going_up = False

            else:
                node = None  # nothing found

        return self

    def to_dict(self):
        """
        Create a nested dict from the root node
        :return: node hierarchy as a dictionary
        """
        return asdict(self.data)


import math


def swap(arr, i, j):
    """
    Swap two elements in an array, as a function purely to
    reduce visual clutter in the code above
    """
    arr[i], arr[j] = arr[j], arr[i]


def compare_l(getval, a, b):
    """
    Call a custom function to get a value to use to compare objects
    """
    return getval(a) - getval(b)


def quickselect(arr, k, left, right, getval):
    while right > left:
        if right - left > 600:
            n = right - left + 1
            m = k - left + 1
            z = math.log(n)
            s = 0.5 * math.exp(2 * z / 3)
            d = -1 if m - n / 2 < 0 else 1
            sd = 0.5 * math.sqrt(z * s * (n - s) / n) * d
            new_left = max(left, math.floor(k - m * s / n + sd))
            new_right = min(right, math.floor(k + (n - m) * s / n + sd))
            quickselect(arr, k, new_left, new_right, getval)

        t = arr[k]
        i = left
        j = right

        swap(arr, left, k)
        if compare_l(getval, arr[right], t) > 0:
            swap(arr, left, right)

        while i < j:
            swap(arr, i, j)
            i = i + 1
            j = j - 1
            while compare_l(getval, arr[i], t) < 0:
                i = i + 1
            while compare_l(getval, arr[j], t) > 0:
                j = j - 1

        if compare_l(getval, arr[left], t) == 0:
            swap(arr, left, j)
        else:
            j = j + 1
            swap(arr, j, right)

        if j <= k:
            left = j + 1
        if k <= j:
            right = j - 1
