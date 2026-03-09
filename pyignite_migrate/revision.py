import types

from pyignite_migrate.errors import RevisionError


class Revision:
    """Represents a single migration revision in the DAG."""

    def __init__(
        self,
        revision: str,
        down_revision: str | None,
        description: str = "",
        module: types.ModuleType | None = None,
    ):
        self.revision = revision
        self.down_revision = down_revision
        self.description = description
        self.module = module
        self.nextrev: frozenset[str] = frozenset()

    @property
    def is_base(self) -> bool:
        return self.down_revision is None

    @property
    def is_head(self) -> bool:
        return len(self.nextrev) == 0

    def __repr__(self) -> str:
        return f"<Revision {self.revision!r} -> {self.down_revision!r}>"


class RevisionMap:
    """Builds and manages the directed acyclic graph of revisions."""

    def __init__(self, revisions: list[Revision]):
        self._revisions: dict[str, Revision] = {}

        for rev in revisions:
            if rev.revision in self._revisions:
                raise RevisionError(f"Duplicate revision ID: {rev.revision}")
            self._revisions[rev.revision] = rev

        self._build_nextrev_links()
        self._validate()

    def get_revision(self, rev_id: str) -> Revision:
        if rev_id not in self._revisions:
            raise RevisionError(f"Revision not found: {rev_id!r}")
        return self._revisions[rev_id]

    def check_revision(self, rev_id: str) -> None:
        """Raise RevisionError if the revision does not exist."""
        if rev_id not in self._revisions:
            raise RevisionError(f"Revision not found: {rev_id!r}")

    def get_heads(self) -> list[str]:
        return sorted(rev.revision for rev in self._revisions.values() if rev.is_head)

    def get_upgrade_path(
        self,
        current: str | None,
        target: str,
    ) -> list[Revision]:
        topo_order = self._topological_sort()

        if current is None:
            start_idx = -1
        else:
            if current not in self._revisions:
                raise RevisionError(f"Current revision not found: {current!r}")
            start_idx = topo_order.index(current)

        if target not in self._revisions:
            raise RevisionError(f"Target revision not found: {target!r}")
        end_idx = topo_order.index(target)

        if end_idx <= start_idx:
            raise RevisionError(
                f"Target {target!r} is not ahead of current {current!r}"
            )

        path_ids = topo_order[start_idx + 1 : end_idx + 1]

        ancestors = self._get_ancestors(target)
        if current is not None:
            ancestors -= self._get_ancestors(current)
            ancestors.discard(current)
        ancestors.add(target)

        return [self._revisions[rev_id] for rev_id in path_ids if rev_id in ancestors]

    def get_downgrade_path(
        self,
        current: str,
        target: str | None,
    ) -> list[Revision]:
        topo_order = self._topological_sort()

        if current not in self._revisions:
            raise RevisionError(f"Current revision not found: {current!r}")
        current_idx = topo_order.index(current)

        if target is None:
            target_idx = -1
        else:
            if target not in self._revisions:
                raise RevisionError(f"Target revision not found: {target!r}")
            target_idx = topo_order.index(target)

        if target_idx >= current_idx:
            raise RevisionError(f"Target {target!r} is not behind current {current!r}")

        path_ids = topo_order[target_idx + 1 : current_idx + 1]

        ancestors = self._get_ancestors(current)
        ancestors.add(current)
        if target is not None:
            ancestors -= self._get_ancestors(target)
            ancestors.discard(target)

        return [
            self._revisions[rev_id]
            for rev_id in reversed(path_ids)
            if rev_id in ancestors
        ]

    def get_all_revisions(self) -> list[Revision]:
        topo = self._topological_sort()
        return [self._revisions[rev_id] for rev_id in topo]

    def is_empty(self) -> bool:
        return len(self._revisions) == 0

    def _build_nextrev_links(self) -> None:
        children: dict[str, set[str]] = {rev_id: set() for rev_id in self._revisions}
        for rev in self._revisions.values():
            if rev.down_revision is not None and rev.down_revision in children:
                children[rev.down_revision].add(rev.revision)

        for rev_id, child_set in children.items():
            self._revisions[rev_id].nextrev = frozenset(child_set)

    def _validate(self) -> None:
        for rev in self._revisions.values():
            if (
                rev.down_revision is not None
                and rev.down_revision not in self._revisions
            ):
                raise RevisionError(
                    f"Revision {rev.revision!r} references unknown "
                    f"down_revision {rev.down_revision!r}"
                )
        self._topological_sort()

    def _topological_sort(self) -> list[str]:
        in_degree: dict[str, int] = {rev_id: 0 for rev_id in self._revisions}
        for rev in self._revisions.values():
            if rev.down_revision is not None:
                in_degree[rev.revision] += 1

        queue = sorted(rev_id for rev_id, deg in in_degree.items() if deg == 0)
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            rev = self._revisions[current]
            for child_id in sorted(rev.nextrev):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
            queue.sort()

        if len(result) != len(self._revisions):
            raise RevisionError("Cycle detected in revision graph")

        return result

    def _get_ancestors(self, rev_id: str) -> set[str]:
        result: set[str] = set()
        current = self._revisions[rev_id].down_revision
        while current is not None:
            result.add(current)
            current = self._revisions[current].down_revision
        return result
