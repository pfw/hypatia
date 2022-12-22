from __future__ import annotations

import unittest
from pprint import pprint
from random import random, randint

import math

from shapely.geometry import box
from shapely.wkt import loads

from ..rbush import BBox, RBush, Node


def arr_to_bbox(key: int, bounds):
    return BBox(key, *bounds)


data = [
    arr_to_bbox(idx, v)
    for idx, v in enumerate(
        [
            [0, 0, 0, 0],
            [10, 10, 10, 10],
            [20, 20, 20, 20],
            [25, 0, 25, 0],
            [35, 10, 35, 10],
            [45, 20, 45, 20],
            [0, 25, 0, 25],
            [10, 35, 10, 35],
            [20, 45, 20, 45],
            [25, 25, 25, 25],
            [35, 35, 35, 35],
            [45, 45, 45, 45],
            [50, 0, 50, 0],
            [60, 10, 60, 10],
            [70, 20, 70, 20],
            [75, 0, 75, 0],
            [85, 10, 85, 10],
            [95, 20, 95, 20],
            [50, 25, 50, 25],
            [60, 35, 60, 35],
            [70, 45, 70, 45],
            [75, 25, 75, 25],
            [85, 35, 85, 35],
            [95, 45, 95, 45],
            [0, 50, 0, 50],
            [10, 60, 10, 60],
            [20, 70, 20, 70],
            [25, 50, 25, 50],
            [35, 60, 35, 60],
            [45, 70, 45, 70],
            [0, 75, 0, 75],
            [10, 85, 10, 85],
            [20, 95, 20, 95],
            [25, 75, 25, 75],
            [35, 85, 35, 85],
            [45, 95, 45, 95],
            [50, 50, 50, 50],
            [60, 60, 60, 60],
            [70, 70, 70, 70],
            [75, 50, 75, 50],
            [85, 60, 85, 60],
            [95, 70, 95, 70],
            [50, 75, 50, 75],
            [60, 85, 60, 85],
            [70, 95, 70, 95],
            [75, 75, 75, 75],
            [85, 85, 85, 85],
            [95, 95, 95, 95],
        ]
    )
]

emptyData = [
    arr_to_bbox(idx, v)
    for idx, v in enumerate(
        [
            [-math.inf, -math.inf, math.inf, math.inf],
            [-math.inf, -math.inf, math.inf, math.inf],
            [-math.inf, -math.inf, math.inf, math.inf],
            [-math.inf, -math.inf, math.inf, math.inf],
            [-math.inf, -math.inf, math.inf, math.inf],
            [-math.inf, -math.inf, math.inf, math.inf],
        ]
    )
]


def some_data(n):
    data = []
    for i in range(n):
        data.append(BBox(key=i, min_x=i, min_y=i, max_x=i, max_y=i))
    return data


def rand_box(key: int, size: float | int | None = None):
    W = 700
    if not size:
        size = randint(W // 8, W // 3)
    x = random() * (W - size)
    y = random() * (W - size)
    return BBox(
        key=key, min_x=x, min_y=y, max_x=x + size * random(), max_y=y + size * random()
    )


def generate(count, size):
    return [rand_box(size) for i in range(count)]


class TestRBush(unittest.TestCase):
    def test_default_max_entries(self):
        tree = RBush()
        tree.load(some_data(9))
        self.assertEqual(tree.data.height, 1)

        tree = RBush()
        tree.load(some_data(10))
        self.assertEqual(tree.data.height, 2)

    def test_custom_max_entries(self):
        tree = RBush(4)
        tree.load(some_data(9))
        self.assertEqual(tree.data.height, 2)

    def test_custom_node_type(self):
        class MyNode(Node):
            ...

        class MyRBush(RBush):
            node_type = MyNode

        tree = MyRBush()
        self.assertIsInstance(tree.data, MyNode)

    def test_bulk_load(self):
        tree = RBush(4)
        tree.load(data)
        self.assertCountEqual(data, tree.all())

    def test_load_uses_standard_insertion_when_given_a_low_number_of_items(self):
        tree = RBush(8)
        tree.load(data)
        tree.load(data[0:3])

        tree2 = RBush(8)
        tree2.load(data)
        tree2.insert(data[0])
        tree2.insert(data[1])
        tree2.insert(data[2])

        self.assertEqual(tree.to_dict(), tree2.to_dict())

    def test_load_does_nothing_if_loading_empty_data(self):
        tree = RBush()
        tree.load([])

        tree2 = RBush()
        self.assertEqual(tree.to_dict(), tree2.to_dict())

    def test_load_handles_the_insertion_of_maxEntries_plus_2_empty_bboxes(self):
        tree = RBush(4)
        tree.load(emptyData)

        self.assertEqual(tree.data.height, 2)
        self.assertCountEqual(tree.all(), emptyData)

    def test_load_properly_splits_tree_root_when_merging_trees_of_the_same_height(self):
        tree = RBush(4)
        tree.load(data)
        tree.load(data)

        self.assertEqual(tree.data.height, 4)
        self.assertCountEqual(tree.all(), data + data)

    def test_load_properly_merges_data_of_smaller_or_bigger_tree_heights(self):
        smaller = some_data(10)
        tree = RBush(4)
        tree.load(data)
        tree.load(smaller)

        tree2 = RBush(4)
        tree2.load(smaller)
        tree2.load(data)

        self.assertEqual(tree.data.height, tree2.data.height)

        self.assertCountEqual(tree.all(), data + smaller)
        self.assertCountEqual(tree2.all(), data + smaller)

    def test_search_finds_matching_points_in_the_tree_given_a_bbox(self):
        tree = RBush(4)
        tree.load(data)
        result = tree.search((40, 20, 80, 70))

        self.assertCountEqual(
            result,
            [
                arr_to_bbox(key, v)
                for key, v in [
                    (14, [70, 20, 70, 20]),
                    (21, [75, 25, 75, 25]),
                    (11, [45, 45, 45, 45]),
                    (36, [50, 50, 50, 50]),
                    (37, [60, 60, 60, 60]),
                    (38, [70, 70, 70, 70]),
                    (5, [45, 20, 45, 20]),
                    (29, [45, 70, 45, 70]),
                    (39, [75, 50, 75, 50]),
                    (18, [50, 25, 50, 25]),
                    (19, [60, 35, 60, 35]),
                    (20, [70, 45, 70, 45]),
                ]
            ],
        )

    def test_search_returns_an_empty_array_if_nothing_found(self):
        tree = RBush(4)
        tree.load(data)
        result = tree.search((200, 200, 210, 210))
        self.assertCountEqual(result, [])

    def test_all_returns_all_points_in_the_tree(self):
        self.maxDiff = None
        tree = RBush(4)
        tree.load(data)
        self.assertCountEqual(tree.all(), data)

        self.assertCountEqual(tree.search((0, 0, 100, 100)), data)

    def test_insert_adds_an_item_to_an_existing_tree_correctly(self):
        items = [
            arr_to_bbox(idx, v)
            for idx, v in enumerate(
                [
                    [0, 0, 0, 0],
                    [1, 1, 1, 1],
                    [2, 2, 2, 2],
                    [3, 3, 3, 3],
                    [1, 1, 2, 2],
                ]
            )
        ]
        tree = RBush(4)
        tree.load(items[0:3])

        tree.insert(items[3])
        self.assertEqual(tree.data.height, 1)

        tree.insert(items[4])
        self.assertEqual(tree.data.height, 2)
        self.assertCountEqual(tree.all(), items)

    def test_insert_forms_a_valid_tree_if_items_are_inserted_one_by_one(self):
        tree = RBush(4)
        # insert individually twice to trigger all branches in choose shub
        for i in range(2):
            for item in data:
                tree.insert(item)

        tree2 = RBush(4)
        tree2.load(data)
        tree2.load(data)

        self.assertLessEqual(tree.data.height - tree2.data.height, 1)
        self.assertCountEqual(tree.all(), tree2.all())

    def test_remove_removes_items_correctly(self):
        tree = RBush(4)
        tree.load(data)

        tree.remove(data[0])
        tree.remove(data[1])
        tree.remove(data[2])

        tree.remove(data[-1])
        tree.remove(data[-2])
        tree.remove(data[-3])

        self.assertCountEqual(data[3:-3], tree.all())

    def test_remove_does_nothing_if_nothing_found(self):
        tree = RBush()
        tree.load(data)

        tree2 = RBush()
        tree2.load(data)
        tree2.remove(arr_to_bbox(1232, [10, 20, 10, 20]))

        self.assertCountEqual(tree.all(), tree2.all())

    def test_remove_brings_the_tree_to_a_clear_state_when_removing_everything_one_by_one(
        self,
    ):
        tree = RBush(4)
        tree.load(data)

        for item in data:
            tree.remove(item)

        tree2 = RBush(4)
        self.assertCountEqual(tree.all(), tree2.all())

    def test_clear_should_clear_all_the_data_in_the_tree(self):
        tree = RBush(4)
        tree.load(data)
        tree.clear()

        tree2 = RBush(4)

        self.assertCountEqual(tree.all(), tree2.all())

    def test_quickselect_more_than_600(self):
        tree = RBush()
        tree.load(generate(1000, None))

