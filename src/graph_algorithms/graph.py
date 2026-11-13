"""Directed graph data structure."""

from collections.abc import Iterator


class DirectedGraph:
    """Directed graph backed by an insertion-ordered adjacency list."""

    def __init__(self) -> None:
        self._adjacency: dict[str, list[str]] = {}

    def add_vertex(self, vertex: str) -> None:
        self._adjacency.setdefault(vertex, [])

    def add_edge(self, source: str, target: str) -> None:
        self.add_vertex(source)
        self.add_vertex(target)
        self._adjacency[source].append(target)

    @property
    def vertices(self) -> list[str]:
        return list(self._adjacency)

    @property
    def edges(self) -> Iterator[tuple[str, str]]:
        for source, targets in self._adjacency.items():
            for target in targets:
                yield source, target

    def successors(self, vertex: str) -> list[str]:
        return self._adjacency[vertex]

    def __len__(self) -> int:
        return len(self._adjacency)

    @classmethod
    def from_adjacency_matrix(cls, text: str) -> DirectedGraph:
        """Parse a graph from a whitespace-separated adjacency matrix of 0s and 1s.

        Row `i` lists the edges leaving vertex `i`: a 1 in column `j` is an edge
        `i -> j`, so a 1 on the diagonal is a self-loop. An optional first line
        names the vertices; it is recognised because it contains a non-numeric
        token, so names cannot all be numbers. Without it, vertices are named
        `1..n`. Blank lines and anything after `#` are ignored.
        """
        lines = [
            (line_number, tokens)
            for line_number, line in enumerate(text.splitlines(), start=1)
            if (tokens := line.split("#", 1)[0].split())
        ]

        names: list[str] | None = None
        if lines and not all(token.isdigit() for token in lines[0][1]):
            names = lines.pop(0)[1]
            if len(set(names)) != len(names):
                raise ValueError("vertex names must be unique")

        size = len(lines)
        if names is None:
            names = [str(i) for i in range(1, size + 1)]
        elif len(names) != size:
            raise ValueError(f"header names {len(names)} vertices but the matrix has {size} rows")

        graph = cls()
        for name in names:
            graph.add_vertex(name)
        for source, (line_number, row) in zip(names, lines, strict=True):
            if len(row) != size:
                raise ValueError(f"line {line_number}: expected {size} values, got {len(row)}")
            for target, value in zip(names, row, strict=True):
                if value not in ("0", "1"):
                    raise ValueError(f"line {line_number}: expected 0 or 1, got {value!r}")
                if value == "1":
                    graph.add_edge(source, target)
        return graph
