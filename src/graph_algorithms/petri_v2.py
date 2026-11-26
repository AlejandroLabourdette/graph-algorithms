"""Karp-Miller coverability tree and graph of a Petri net.

The coverability tree is a finite abstraction of the (possibly infinite) reachability set of a
Petri net. Places that can grow without bound are marked with omega (`OMEGA`), which stands for
"arbitrarily many tokens". From the tree we derive the coverability graph, its strongly
connected components and the boundedness of every place.
"""

import math
from collections import deque
from dataclasses import dataclass

from graph_algorithms.graph import DirectedGraph
from graph_algorithms.petri import PetriNet
from graph_algorithms.tarjan import strongly_connected_components

# Omega behaves like an infinite number of tokens: omega >= n, omega - n = omega, omega + n = omega.
OMEGA = math.inf

type Tokens = int | float
type OmegaMarking = tuple[Tokens, ...]


def format_tokens(tokens: Tokens) -> str:
    return "ω" if tokens == OMEGA else str(tokens)


def format_marking(marking: OmegaMarking) -> str:
    return "(" + ", ".join(map(format_tokens, marking)) + ")"


@dataclass(frozen=True)
class Acceleration:
    """Places turned into omega because a new marking strictly covers an ancestor's marking."""

    ancestor: int
    places: tuple[int, ...]


@dataclass(frozen=True)
class TreeNode:
    """A node of the coverability tree.

    `parent` and `transition` describe the arc that created the node (both None for the root).
    A node whose marking already appears in an earlier node has `duplicate_of` set to that
    node's id and is a leaf: it is not expanded.
    """

    id: int
    marking: OmegaMarking
    parent: int | None
    transition: str | None
    duplicate_of: int | None
    accelerations: tuple[Acceleration, ...]

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None


@dataclass(frozen=True)
class CoverabilityTree:
    """Karp-Miller coverability tree; node ids are creation order (breadth first)."""

    places: tuple[str, ...]
    transitions: tuple[str, ...]
    nodes: tuple[TreeNode, ...]

    def children(self, node_id: int) -> list[TreeNode]:
        return [node for node in self.nodes if node.parent == node_id]

    def path_to(self, node_id: int) -> list[TreeNode]:
        """Nodes from the root to `node_id`, both included."""
        path: list[TreeNode] = []
        current: int | None = node_id
        while current is not None:
            node = self.nodes[current]
            path.append(node)
            current = node.parent
        path.reverse()
        return path


def accelerate(
    marking: OmegaMarking, ancestors: list[TreeNode]
) -> tuple[OmegaMarking, list[Acceleration]]:
    """Replace by omega every place in which `marking` grows over an ancestor.

    `marking` is compared with each marking on the path from the root. When it covers an
    ancestor's marking (>= in every place) and differs from it, the places where it is strictly
    greater can be pumped as often as we like, so they become omega. Turning places into omega
    can make `marking` cover further ancestors, so the comparison repeats until nothing changes.
    """
    accelerations: list[Acceleration] = []
    changed = True
    while changed:
        changed = False
        for ancestor in ancestors:
            old = ancestor.marking
            if marking == old or not all(
                new >= before for new, before in zip(marking, old, strict=True)
            ):
                continue
            pumped = tuple(
                p
                for p, (new, before) in enumerate(zip(marking, old, strict=True))
                if new > before and new != OMEGA
            )
            if pumped:
                marking = tuple(OMEGA if p in pumped else n for p, n in enumerate(marking))
                accelerations.append(Acceleration(ancestor.id, pumped))
                changed = True
    return marking, accelerations


def add_child(
    net: PetriNet,
    nodes: list[TreeNode],
    first_with_marking: dict[OmegaMarking, int],
    parent: TreeNode,
    transition: str,
) -> TreeNode:
    """Fire `transition` from `parent` and append the resulting node to `nodes`.

    The new marking is compared with the path from the root to introduce omegas
    (`accelerate`). If it already appears in a node created earlier the child is a duplicate;
    otherwise it is registered in `first_with_marking`.
    """
    marking = net.fire(parent.marking, transition)
    marking, accelerations = accelerate(marking, _path(nodes, parent))
    duplicate_of = first_with_marking.get(marking)
    child = TreeNode(len(nodes), marking, parent.id, transition, duplicate_of, tuple(accelerations))
    nodes.append(child)
    if duplicate_of is None:
        first_with_marking[marking] = child.id
    return child


def build_coverability_tree(net: PetriNet) -> CoverabilityTree:
    """Build the Karp-Miller coverability tree of `net`, breadth first.

    Every enabled transition of an expanded node creates a child (`add_child`). A child whose
    marking already appears in a node created earlier is a duplicate: it is kept in the tree as
    a leaf and is not expanded.
    """
    root = TreeNode(0, net.initial_marking, None, None, None, ())
    nodes = [root]
    first_with_marking: dict[OmegaMarking, int] = {root.marking: root.id}
    queue = deque([root.id])

    while queue:
        node = nodes[queue.popleft()]
        for transition in net.transitions:
            if not net.is_enabled(node.marking, transition):
                continue
            child = add_child(net, nodes, first_with_marking, node, transition)
            if not child.is_duplicate:
                queue.append(child.id)

    return CoverabilityTree(net.places, net.transitions, tuple(nodes))


def _path(nodes: list[TreeNode], node: TreeNode) -> list[TreeNode]:
    path = [node]
    while path[-1].parent is not None:
        path.append(nodes[path[-1].parent])
    path.reverse()
    return path


@dataclass(frozen=True)
class CoverabilityGraph:
    """Coverability graph: the tree with equal markings merged.

    Vertices are the tree nodes that are not duplicates (named after their node id) and
    `edges` are `(source, transition, target)` triples between those ids.
    """

    places: tuple[str, ...]
    markings: dict[int, OmegaMarking]
    edges: tuple[tuple[int, str, int], ...]
    initial: int = 0

    def successors(self, vertex: int) -> list[int]:
        return [target for source, _, target in self.edges if source == vertex]

    def to_directed_graph(self) -> DirectedGraph:
        graph = DirectedGraph()
        for vertex in self.markings:
            graph.add_vertex(vertex_name(vertex))
        for source, _, target in self.edges:
            graph.add_edge(vertex_name(source), vertex_name(target))
        return graph


def vertex_name(vertex: int) -> str:
    return f"M{vertex}"


def build_coverability_graph(tree: CoverabilityTree) -> CoverabilityGraph:
    """Merge the nodes of `tree` that share a marking into a graph."""
    markings = {node.id: node.marking for node in tree.nodes if not node.is_duplicate}
    edges = tuple(
        (node.parent, node.transition, node.duplicate_of if node.is_duplicate else node.id)
        for node in tree.nodes
        if node.parent is not None and node.transition is not None
    )
    return CoverabilityGraph(tree.places, markings, edges)


def coverability_components(graph: CoverabilityGraph) -> list[list[int]]:
    """Strongly connected components of the coverability graph (Tarjan), as vertex ids."""
    components = strongly_connected_components(graph.to_directed_graph())
    return [[int(name.removeprefix("M")) for name in component] for component in components]


def is_cyclic_component(graph: CoverabilityGraph, component: list[int]) -> bool:
    """A component is cyclic when it has several vertices or a vertex with a self-loop."""
    return len(component) > 1 or any(
        source == target for source, _, target in graph.edges if source == component[0]
    )


def terminal_components(graph: CoverabilityGraph, components: list[list[int]]) -> list[list[int]]:
    """Components with no arc leaving them: once reached, the net never leaves them."""
    terminal = []
    for component in components:
        members = set(component)
        if all(target in members for source, _, target in graph.edges if source in members):
            terminal.append(component)
    return terminal


def dead_markings(graph: CoverabilityGraph) -> list[int]:
    """Vertices without outgoing arcs: markings in which no transition is enabled."""
    with_successors = {source for source, _, _ in graph.edges}
    return [vertex for vertex in graph.markings if vertex not in with_successors]


def place_bounds(graph: CoverabilityGraph) -> dict[str, int | None]:
    """Bound of every place: the most tokens it ever holds, or None when it is unbounded.

    A place is unbounded exactly when omega appears in it in some marking of the graph.
    """
    bounds: dict[str, int | None] = {}
    for p, place in enumerate(graph.places):
        highest = max(marking[p] for marking in graph.markings.values())
        bounds[place] = None if highest == OMEGA else int(highest)
    return bounds


def is_bounded(bounds: dict[str, int | None]) -> bool:
    """A net is bounded when none of its places is unbounded."""
    return all(bound is not None for bound in bounds.values())


def is_safe(bounds: dict[str, int | None]) -> bool:
    """A net is safe (1-bounded) when no place ever holds more than one token."""
    return all(bound is not None and bound <= 1 for bound in bounds.values())
