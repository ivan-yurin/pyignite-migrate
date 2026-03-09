import pytest

from pyignite_migrate.errors import RevisionError
from pyignite_migrate.revision import Revision, RevisionMap


class TestRevision:
    def test_is_base(self):
        rev = Revision("aaa", None)
        assert rev.is_base is True

    def test_is_not_base(self):
        rev = Revision("bbb", "aaa")
        assert rev.is_base is False

    def test_is_head_by_default(self):
        rev = Revision("aaa", None)
        assert rev.is_head is True

    def test_repr(self):
        rev = Revision("aaa", "bbb")
        assert "aaa" in repr(rev)
        assert "bbb" in repr(rev)


class TestRevisionMap:
    def test_empty(self):
        rev_map = RevisionMap([])
        assert rev_map.is_empty() is True
        assert rev_map.get_heads() == []
        assert rev_map.get_bases() == []

    def test_single_revision(self):
        r1 = Revision("aaa", None, "first")
        rev_map = RevisionMap([r1])
        assert rev_map.get_heads() == ["aaa"]
        assert rev_map.get_bases() == ["aaa"]

    def test_linear_chain(self):
        r1 = Revision("aaa", None, "first")
        r2 = Revision("bbb", "aaa", "second")
        r3 = Revision("ccc", "bbb", "third")
        rev_map = RevisionMap([r1, r2, r3])
        assert rev_map.get_heads() == ["ccc"]
        assert rev_map.get_bases() == ["aaa"]

    def test_duplicate_revision_raises(self):
        r1 = Revision("aaa", None)
        r2 = Revision("aaa", None)
        with pytest.raises(RevisionError, match="Duplicate"):
            RevisionMap([r1, r2])

    def test_broken_reference_raises(self):
        r1 = Revision("bbb", "missing")
        with pytest.raises(RevisionError, match="unknown"):
            RevisionMap([r1])

    def test_cycle_detection(self):
        r1 = Revision("aaa", "bbb")
        r2 = Revision("bbb", "aaa")
        with pytest.raises(RevisionError, match="Cycle"):
            RevisionMap([r1, r2])

    def test_get_revision(self):
        r1 = Revision("aaa", None, "first")
        rev_map = RevisionMap([r1])
        assert rev_map.get_revision("aaa").description == "first"

    def test_get_revision_not_found(self):
        rev_map = RevisionMap([])
        with pytest.raises(RevisionError, match="not found"):
            rev_map.get_revision("missing")

    def test_get_all_revisions_order(self):
        r1 = Revision("aaa", None, "first")
        r2 = Revision("bbb", "aaa", "second")
        r3 = Revision("ccc", "bbb", "third")
        rev_map = RevisionMap([r3, r1, r2])
        all_revs = rev_map.get_all_revisions()
        assert [r.revision for r in all_revs] == [
            "aaa",
            "bbb",
            "ccc",
        ]


class TestUpgradePath:
    def test_full_upgrade_from_base(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        r3 = Revision("ccc", "bbb")
        rev_map = RevisionMap([r1, r2, r3])

        path = rev_map.get_upgrade_path(None, "ccc")
        assert [r.revision for r in path] == [
            "aaa",
            "bbb",
            "ccc",
        ]

    def test_partial_upgrade(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        r3 = Revision("ccc", "bbb")
        rev_map = RevisionMap([r1, r2, r3])

        path = rev_map.get_upgrade_path("aaa", "ccc")
        assert [r.revision for r in path] == ["bbb", "ccc"]

    def test_upgrade_single_step(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        rev_map = RevisionMap([r1, r2])

        path = rev_map.get_upgrade_path("aaa", "bbb")
        assert [r.revision for r in path] == ["bbb"]

    def test_target_not_ahead_raises(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        rev_map = RevisionMap([r1, r2])

        with pytest.raises(RevisionError, match="not ahead"):
            rev_map.get_upgrade_path("bbb", "aaa")


class TestDowngradePath:
    def test_full_downgrade_to_base(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        r3 = Revision("ccc", "bbb")
        rev_map = RevisionMap([r1, r2, r3])

        path = rev_map.get_downgrade_path("ccc", None)
        assert [r.revision for r in path] == [
            "ccc",
            "bbb",
            "aaa",
        ]

    def test_partial_downgrade(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        r3 = Revision("ccc", "bbb")
        rev_map = RevisionMap([r1, r2, r3])

        path = rev_map.get_downgrade_path("ccc", "aaa")
        assert [r.revision for r in path] == ["ccc", "bbb"]

    def test_downgrade_single_step(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        rev_map = RevisionMap([r1, r2])

        path = rev_map.get_downgrade_path("bbb", "aaa")
        assert [r.revision for r in path] == ["bbb"]

    def test_target_not_behind_raises(self):
        r1 = Revision("aaa", None)
        r2 = Revision("bbb", "aaa")
        rev_map = RevisionMap([r1, r2])

        with pytest.raises(RevisionError, match="not behind"):
            rev_map.get_downgrade_path("aaa", "bbb")
