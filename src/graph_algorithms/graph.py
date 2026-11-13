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
    def from_edge_list(cls, text: str) -> DirectedGraph:
        """Parse a graph from text with one edge `u v` per line.

        A line with a single token declares an isolated vertex. Blank lines and
        anything after `#` are ignored.
        """
        graph = cls()
        for line_number, line in enumerate(text.splitlines(), start=1):
            tokens = line.split("#", 1)[0].split()
            match tokens:
                case []:
                    continue
                case [vertex]:
                    graph.add_vertex(vertex)
                case [source, target]:
                    graph.add_edge(source, target)
                case _:
                    raise ValueError(
                        f"line {line_number}: expected 'u v' or 'v', got {line.strip()!r}"
                    )
        return graph
