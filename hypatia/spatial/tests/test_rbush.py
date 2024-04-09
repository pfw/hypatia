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
        class MyNode(Node): ...

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


knn_data = [
    arr_to_bbox(idx, v)
    for idx, v in enumerate(
        [
            [87, 55, 87, 56],
            [38, 13, 39, 16],
            [7, 47, 8, 47],
            [89, 9, 91, 12],
            [4, 58, 5, 60],
            [0, 11, 1, 12],
            [0, 5, 0, 6],
            [69, 78, 73, 78],
            [56, 77, 57, 81],
            [23, 7, 24, 9],
            [68, 24, 70, 26],
            [31, 47, 33, 50],
            [11, 13, 14, 15],
            [1, 80, 1, 80],
            [72, 90, 72, 91],
            [59, 79, 61, 83],
            [98, 77, 101, 77],
            [11, 55, 14, 56],
            [98, 4, 100, 6],
            [21, 54, 23, 58],
            [44, 74, 48, 74],
            [70, 57, 70, 61],
            [32, 9, 33, 12],
            [43, 87, 44, 91],
            [38, 60, 38, 60],
            [62, 48, 66, 50],
            [16, 87, 19, 91],
            [5, 98, 9, 99],
            [9, 89, 10, 90],
            [89, 2, 92, 6],
            [41, 95, 45, 98],
            [57, 36, 61, 40],
            [50, 1, 52, 1],
            [93, 87, 96, 88],
            [29, 42, 33, 42],
            [34, 43, 36, 44],
            [41, 64, 42, 65],
            [87, 3, 88, 4],
            [56, 50, 56, 52],
            [32, 13, 35, 15],
            [3, 8, 5, 11],
            [16, 33, 18, 33],
            [35, 39, 38, 40],
            [74, 54, 78, 56],
            [92, 87, 95, 90],
            [12, 97, 16, 98],
            [76, 39, 78, 40],
            [16, 93, 18, 95],
            [62, 40, 64, 42],
            [71, 87, 71, 88],
            [60, 85, 63, 86],
            [39, 52, 39, 56],
            [15, 18, 19, 18],
            [91, 62, 94, 63],
            [10, 16, 10, 18],
            [5, 86, 8, 87],
            [85, 85, 88, 86],
            [44, 84, 44, 88],
            [3, 94, 3, 97],
            [79, 74, 81, 78],
            [21, 63, 24, 66],
            [16, 22, 16, 22],
            [68, 97, 72, 97],
            [39, 65, 42, 65],
            [51, 68, 52, 69],
            [61, 38, 61, 42],
            [31, 65, 31, 65],
            [16, 6, 19, 6],
            [66, 39, 66, 41],
            [57, 32, 59, 35],
            [54, 80, 58, 84],
            [5, 67, 7, 71],
            [49, 96, 51, 98],
            [29, 45, 31, 47],
            [31, 72, 33, 74],
            [94, 25, 95, 26],
            [14, 7, 18, 8],
            [29, 0, 31, 1],
            [48, 38, 48, 40],
            [34, 29, 34, 32],
            [99, 21, 100, 25],
            [79, 3, 79, 4],
            [87, 1, 87, 5],
            [9, 77, 9, 81],
            [23, 25, 25, 29],
            [83, 48, 86, 51],
            [79, 94, 79, 95],
            [33, 95, 33, 99],
            [1, 14, 1, 14],
            [33, 77, 34, 77],
            [94, 56, 98, 59],
            [75, 25, 78, 26],
            [17, 73, 20, 74],
            [11, 3, 12, 4],
            [45, 12, 47, 12],
            [38, 39, 39, 39],
            [99, 3, 103, 5],
            [41, 92, 44, 96],
            [79, 40, 79, 41],
            [29, 2, 29, 4],
        ]
    )
]

pyth_data = [
    arr_to_bbox(idx, v)
    for idx, v in enumerate(
        [[0, 0, 0, 0], [9, 9, 9, 9], [12, 12, 12, 12], [13, 14, 19, 11]]
    )
]


class TestRBushKNN(unittest.TestCase):

    def test_finds_n_neighbours(self):
        tree = RBush()
        tree.load(knn_data)

        result = tree.knn((40, 40), 10)
        self.assertEqual(
            [list(r[1].bounds()) for r in result],
            [
                [38, 39, 39, 39],
                [35, 39, 38, 40],
                [34, 43, 36, 44],
                [29, 42, 33, 42],
                [48, 38, 48, 40],
                [31, 47, 33, 50],
                [34, 29, 34, 32],
                [29, 45, 31, 47],
                [39, 52, 39, 56],
                [57, 36, 61, 40],
            ],
        )

    def test_does_not_throw_if_requesting_too_many_items(self):
        tree = RBush()
        tree.load(knn_data)
        result = tree.knn((40, 40), 1000)

        self.assertEqual(len(result), len(knn_data))

    def test_finds_all_neighbours_for_max_distance(self):
        tree = RBush()
        tree.load(knn_data)
        result = tree.knn((40, 40), 0, 10)
        self.assertEqual(
            [list(r[1].bounds()) for r in result],
            [
                [38, 39, 39, 39],
                [35, 39, 38, 40],
                [34, 43, 36, 44],
                [29, 42, 33, 42],
                [48, 38, 48, 40],
                [31, 47, 33, 50],
                [34, 29, 34, 32],
            ],
        )

    def test_finds_n_neighbours_for_max_distance(self):
        tree = RBush()
        tree.load(knn_data)
        result = tree.knn((40, 40), 1, 10)
        self.assertEqual([list(r[1].bounds()) for r in result], [[38, 39, 39, 39]])

    def test_does_not_throw_if_requesting_too_many_items_for_max_distance(self):
        tree = RBush()
        tree.load(knn_data)
        result = tree.knn((40, 40), 1000, 10)
        self.assertEqual(
            [list(r[1].bounds()) for r in result],
            [
                [38, 39, 39, 39],
                [35, 39, 38, 40],
                [34, 43, 36, 44],
                [29, 42, 33, 42],
                [48, 38, 48, 40],
                [31, 47, 33, 50],
                [34, 29, 34, 32],
            ],
        )

    def test_verify_max_distance_excludes_items_to_far_away(self):
        """
        in order to adhere to pythagoras theorem a^2+b^2=c^2
        """
        tree = RBush()
        tree.load(pyth_data)
        result = tree.knn((0, 0), 1000, 12.6)
        self.assertEqual([list(r[1].bounds()) for r in result], [[0, 0, 0, 0]])
    def test_verify_max_distance_includes_all_items_within_range(self):
        """
        in order to adhere to pythagoras theorem a^2+b^2=c^2
        """
        tree = RBush()
        tree.load(pyth_data)
        result = tree.knn((0, 0), 1000, 12.8)
        self.assertEqual([list(r[1].bounds()) for r in result], [[0,0,0,0],[9,9,9,9]])
