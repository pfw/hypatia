##############################################################################
#
# Copyright (c) 2002 Zope Foundation and Contributors.
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
"""N-Best index tests
"""
from unittest import TestCase

import pytest as pytest

from . import NBest


class Test_NBest:
    def test_Constructor(self):
        with pytest.raises(ValueError):
            NBest(0)
        with pytest.raises(ValueError):
            NBest(-1)

        for n in range(1, 11):
            nb = NBest(n)
            assert len(nb) == 0
            assert nb.capacity() == n

    def test_One(self):
        nb = NBest(1)
        nb.add("a", 0)
        assert nb.getbest() == [("a", 0)]

        nb.add("b", 1)
        assert len(nb) == 1
        assert nb.capacity() == 1
        assert nb.getbest() == [("b", 1)]

        nb.add("c", -1)
        assert len(nb) == 1
        assert nb.capacity() == 1
        assert nb.getbest() == [("b", 1)]

        nb.addmany([("d", 3), ("e", -6), ("f", 5), ("g", 4)])
        assert len(nb) == 1
        assert nb.capacity() == 1
        assert nb.getbest() == [("f", 5)]

    def test_Many(self):
        import random

        inputs = [(-i, i) for i in range(50)]

        reversed_inputs = list(reversed(inputs[:]))

        # Test the N-best for a variety of n (1, 6, 11, ... 50).
        for n in range(1, len(inputs) + 1, 5):
            expected = list(reversed(inputs[-n:]))

            random_inputs = inputs[:]
            random.shuffle(random_inputs)

            for source in inputs, reversed_inputs, random_inputs:
                # Try feeding them one at a time.
                nb = NBest(n)
                for item, score in source:
                    nb.add(item, score)
                assert len(nb) == n
                assert nb.capacity() == n
                assert nb.getbest() == expected

                # And again in one gulp.
                nb = NBest(n)
                nb.addmany(source)
                assert len(nb) == n
                assert nb.capacity() == n
                assert nb.getbest() == expected

                for i in range(1, n + 1):
                    assert nb.pop_smallest() == expected[-i]
                with pytest.raises(IndexError):
                    nb.pop_smallest()

    def test_AllSameScore(self):
        inputs = [(i, 0) for i in range(10)]
        for n in range(1, 12):
            nb = NBest(n)
            nb.addmany(inputs)
            outputs = nb.getbest()
            assert outputs == inputs[: len(outputs)]
