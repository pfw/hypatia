import unittest
from .. import query


class _CatalogMaker(object):
    def _makeCatalog(self):
        from ..catalog import Catalog
        from ..field import FieldIndex
        from ..keyword import KeywordIndex
        from ..text import TextIndex

        catalog = Catalog()

        self.name = FieldIndex("name")
        self.title = FieldIndex("title")
        self.text = TextIndex("text")
        self.allowed = KeywordIndex("allowed")

        catalog["name"] = self.name
        catalog["title"] = self.title
        catalog["text"] = self.text
        catalog["allowed"] = self.allowed

        catalog.index_doc(1, Content("name1", "title1", "body one", ["a"]))
        catalog.index_doc(2, Content("name2", "title2", "body two", ["b"]))
        catalog.index_doc(3, Content("name3", "title3", "body three", ["c"]))
        catalog.index_doc(4, Content("name4", None, "body four", ["a", "b"]))
        catalog.index_doc(5, Content("name5", "title5", "body five", ["a", "b", "c"]))
        catalog.index_doc(6, Content("name6", "title6", "body six", ["d"]))

        return catalog


class CatalogQueryBase(_CatalogMaker):
    def get_query(self):
        raise NotImplementedError

    def test_it(self):
        from ..catalog import CatalogQuery

        catalog = self._makeCatalog()

        q = CatalogQuery(catalog)

        numdocs, result = q.query(
            self.get_query(), sort_index="name", limit=5, names=dict(body="body")
        )

        assert numdocs == 2
        assert list(result) == [4, 5]


class TestCatalogQueryWithCQE(unittest.TestCase, CatalogQueryBase):
    def get_query(self):
        return (
            "(allowed == 'a' and allowed == 'b' and "
            "(name == 'name1' or name == 'name2' or name == 'name3' or "
            "name == 'name4' or name == 'name5') and not(title == 'title3')) "
            "and body in text"
        )


class TestCatalogQueryWithPythonQueryObjects(CatalogQueryBase):
    def get_query(self):
        return (
            query.All(self.allowed, ["a", "b"])
            & query.Any(self.name, ["name1", "name2", "name3", "name4", "name5"])
            & query.Not(query.Eq(self.title, "title3"))
            & query.Contains(self.text, "body")
        )


class TestCatalogQueryWithPythonQueryObjectsUnionAndIntersection(
    _CatalogMaker,
):
    def _get_result(self, q):
        from ..catalog import CatalogQuery

        cq = CatalogQuery(self.catalog)

        numdocs, result = cq.query(
            q, sort_index="name", limit=5, names=dict(body="body")
        )
        return numdocs, result

    def test_union_both_left_and_right_nonempty(self):
        self.catalog = self._makeCatalog()
        q = query.All(self.allowed, ["a", "b"]) & query.Any(
            self.name, ["name1", "name2", "name3", "name4", "name5"]
        ) & query.Not(query.Eq(self.title, "title3")) | query.Contains(
            self.text, "body"
        )
        numdocs, result = self._get_result(q)
        assert numdocs == 5
        assert list(result) == [1, 2, 3, 4, 5]

    def test_union_left_nonempty_right_empty(self):
        self.catalog = self._makeCatalog()
        q = query.All(self.allowed, ["a", "b"]) & query.Any(
            self.name, ["name1", "name2", "name3", "name4", "name5"]
        ) & query.Not(query.Eq(self.title, "title3")) | query.Contains(
            self.text, "nope"
        )
        numdocs, result = self._get_result(q)
        assert numdocs == 2
        assert list(result) == [4, 5]

    def test_union_left_empty_right_nonempty(self):
        self.catalog = self._makeCatalog()
        q = query.Contains(self.text, "nope") | query.All(
            self.allowed, ["a", "b"]
        ) & query.Any(
            self.name, ["name1", "name2", "name3", "name4", "name5"]
        ) & query.Not(
            query.Eq(self.title, "title3")
        )
        numdocs, result = self._get_result(q)
        assert numdocs == 2
        assert list(result) == [4, 5]

    def test_intersection_left_nonempty_right_empty(self):
        self.catalog = self._makeCatalog()
        q = query.Contains(self.text, "body") & query.All(self.allowed, ["c", "d"])
        numdocs, result = self._get_result(q)
        assert numdocs == 0
        assert list(result) == []


class TestCatalogQueryWithIndexHelpers(CatalogQueryBase):
    def get_query(self):
        return (
            self.allowed.all(["a", "b"])
            & self.name.any(["name1", "name2", "name3", "name4", "name5"])
            & self.title.noteq("title3")
            & self.text.contains("body")
        )


class TestQueryExecution(_CatalogMaker):
    def test_it(self):
        self._makeCatalog()
        query = (
            self.allowed.all(["a", "b"])
            & self.name.any(["name1", "name2", "name3", "name4", "name5"])
            & self.title.noteq("title3")
            & self.text.contains("body")
        )
        resultset = query.execute().sort(self.name, limit=5)
        assert len(resultset) == 2
        assert list(resultset.ids) == [4, 5]


class TestFieldIndexResultSetSortStabilityGuarantee:
    def _makeCatalog(self):
        from ..catalog import Catalog
        from ..field import FieldIndex

        catalog = Catalog()

        name = FieldIndex("name")
        title = FieldIndex("title")

        catalog["name"] = name
        catalog["title"] = title

        catalog.index_doc(1, Content("name1", "title1", None, None))
        catalog.index_doc(2, Content("name2", "title1", None, None))
        catalog.index_doc(3, Content("name3", "title2", None, None))
        catalog.index_doc(4, Content("name4", "title2", None, None))
        catalog.index_doc(5, Content("name5", "title2", None, None))
        catalog.index_doc(6, Content("name6", "title3", None, None))

        return catalog

    def test_it(self):
        catalog = self._makeCatalog()
        name_index = catalog["name"]
        title_index = catalog["title"]
        query = name_index.any(["name6", "name5", "name4", "name3", "name2", "name1"])
        # first we sort by name, which will give us 1,2,3,4,5,6
        resultset = query.execute().sort(name_index)
        # then we sort the resulting result set by title; the ordering should
        # not change (even though some of the titles are identical, and might
        # be considered interchangeable) because the 2nd and subsequent sorts
        # of a result set are implicitly marked as stable.
        resultset = resultset.sort(title_index)
        assert len(resultset) == 6
        assert list(resultset.ids) == [1, 2, 3, 4, 5, 6]


class Content(object):
    def __init__(self, name, title, text, allowed):
        self.name = name
        if title:
            self.title = title
        self.text = text
        self.allowed = allowed
