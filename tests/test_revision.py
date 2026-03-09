import pytest

from pyignite_migrate.errors import RevisionError
from pyignite_migrate.revision import Revision, RevisionMap


class TestRevision:
    def test_repr(self):
        rev = Revision("0001", None)

        assert repr(rev) == "<Revision '0001' -> None>"


class TestRevisionMap:
    def test_duplicate_revision_id(self):
        revisions = [
            Revision("0001", None),
            Revision("0001", None),
        ]

        with pytest.raises(RevisionError, match="Duplicate revision ID"):
            RevisionMap(revisions)

    def test_unknown_down_revision(self):
        revisions = [
            Revision("0001", "9999"),
        ]

        with pytest.raises(RevisionError, match="references unknown down_revision"):
            RevisionMap(revisions)

    def test_cycle_detection(self):
        revisions = [
            Revision("0001", "0002"),
            Revision("0002", "0001"),
        ]

        with pytest.raises(RevisionError, match="Cycle detected"):
            RevisionMap(revisions)

    def test_get_revision_not_found(self):
        rev_map = RevisionMap([Revision("0001", None)])

        with pytest.raises(RevisionError, match="Revision not found"):
            rev_map.get_revision("9999")

    def test_check_revision_not_found(self):
        rev_map = RevisionMap([Revision("0001", None)])

        with pytest.raises(RevisionError, match="Revision not found"):
            rev_map.check_revision("9999")

    def test_upgrade_path_unknown_current(self):
        rev_map = RevisionMap([Revision("0001", None)])

        with pytest.raises(RevisionError, match="Current revision not found"):
            rev_map.get_upgrade_path("9999", "0001")

    def test_upgrade_path_unknown_target(self):
        rev_map = RevisionMap([Revision("0001", None)])

        with pytest.raises(RevisionError, match="Target revision not found"):
            rev_map.get_upgrade_path(None, "9999")

    def test_upgrade_path_target_not_ahead(self):
        revisions = [
            Revision("0001", None),
            Revision("0002", "0001"),
        ]
        rev_map = RevisionMap(revisions)

        with pytest.raises(RevisionError, match="not ahead of current"):
            rev_map.get_upgrade_path("0002", "0001")

    def test_upgrade_path_from_non_base(self):
        revisions = [
            Revision("0001", None),
            Revision("0002", "0001"),
            Revision("0003", "0002"),
        ]
        rev_map = RevisionMap(revisions)

        path = rev_map.get_upgrade_path("0001", "0003")

        assert [r.revision for r in path] == ["0002", "0003"]

    def test_downgrade_path_unknown_current(self):
        rev_map = RevisionMap([Revision("0001", None)])

        with pytest.raises(RevisionError, match="Current revision not found"):
            rev_map.get_downgrade_path("9999", None)

    def test_downgrade_path_unknown_target(self):
        revisions = [
            Revision("0001", None),
            Revision("0002", "0001"),
        ]
        rev_map = RevisionMap(revisions)

        with pytest.raises(RevisionError, match="Target revision not found"):
            rev_map.get_downgrade_path("0002", "9999")

    def test_downgrade_path_target_not_behind(self):
        revisions = [
            Revision("0001", None),
            Revision("0002", "0001"),
        ]
        rev_map = RevisionMap(revisions)

        with pytest.raises(RevisionError, match="not behind current"):
            rev_map.get_downgrade_path("0001", "0002")
