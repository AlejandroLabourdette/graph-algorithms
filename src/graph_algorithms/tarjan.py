"""Tarjan's strongly connected components algorithm."""

from collections.abc import Iterator

from graph_algorithms.graph import DirectedGraph


def strongly_connected_components(graph: DirectedGraph) -> list[list[str]]:
    """Return the strongly connected components of `graph` in O(V + E).

    Components are returned in the order Tarjan's algorithm emits them, which is
    a reverse topological order of the condensation: if there is an edge from
    component A to component B, then B appears before A.

    The depth-first search is iterative, so deep graphs do not hit Python's
    recursion limit.
    """
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    # Each frame is a vertex and the iterator over its remaining successors.
    call_stack: list[tuple[str, Iterator[str]]] = []

    def visit(vertex: str) -> None:
        index[vertex] = lowlink[vertex] = len(index)
        stack.append(vertex)
        on_stack.add(vertex)
        call_stack.append((vertex, iter(graph.successors(vertex))))

    for root in graph.vertices:
        if root in index:
            continue

        visit(root)
        while call_stack:
            vertex, successors = call_stack[-1]
            successor = next(successors, None)
            if successor is not None:
                if successor not in index:
                    visit(successor)
                elif successor in on_stack:
                    lowlink[vertex] = min(lowlink[vertex], index[successor])
                continue

            # All successors explored: return from `vertex`.
            call_stack.pop()
            if call_stack:
                parent = call_stack[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[vertex])

            if lowlink[vertex] == index[vertex]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == vertex:
                        break
                components.append(component)

    return components
