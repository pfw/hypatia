import unittest


class TestBadResults(unittest.TestCase):
    def _makeOne(self, resultset):
        from hypatia.exc import BadResults

        return BadResults([1, 2, 3])

    def test_it(self):
        inst = self._makeOne([1, 2, 3])
        assert inst.resultset == [1, 2, 3]


class TestUnsortable(unittest.TestCase):
    def _makeOne(self, docids):
        from hypatia.exc import Unsortable

        return Unsortable(docids)

    def test___repr__(self):
        inst = self._makeOne([1, 2, 3])
        assert repr(inst) == "[1, 2, 3]"

    def test___str__(self):
        inst = self._makeOne([1, 2, 3])
        assert str(inst) == "[1, 2, 3]"
