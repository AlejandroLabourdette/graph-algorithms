import pytest

from graph_algorithms.graph import DirectedGraph
from graph_algorithms.tarjan import strongly_connected_components

# Directed graph from CLRS figure 22.9, as two-letter "uv" edges.
CLRS_EDGES = "ab bc be bf cd cg dc dh ea ef fg gf gh hh".split()


def graph_from_edges(*edges: str, vertices: str = "") -> DirectedGraph:
    graph = DirectedGraph()
    for vertex in vertices:
        graph.add_vertex(vertex)
    for edge in edges:
        graph.add_edge(edge[0], edge[1])
    return graph


def as_sets(components: list[list[str]]) -> set[frozenset[str]]:
    return {frozenset(component) for component in components}


@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        pytest.param(DirectedGraph(), [], id="empty"),
        pytest.param(graph_from_edges(vertices="a"), ["a"], id="single-vertex"),
        pytest.param(graph_from_edges("aa"), ["a"], id="self-loop"),
        pytest.param(graph_from_edges("ab", "bc", "ac"), ["a", "b", "c"], id="dag"),
        pytest.param(graph_from_edges("ab", "bc", "cd", "da"), ["abcd"], id="cycle"),
        pytest.param(
            graph_from_edges("ab", "ba", "cd", "dc", vertices="e"),
            ["ab", "cd", "e"],
            id="disconnected",
        ),
        pytest.param(graph_from_edges(*CLRS_EDGES), ["abe", "cd", "fg", "h"], id="clrs"),
    ],
)
def test_strongly_connected_components(graph, expected):
    components = strongly_connected_components(graph)

    assert as_sets(components) == {frozenset(component) for component in expected}


def test_components_partition_vertices_in_reverse_topological_order():
    graph = graph_from_edges(*CLRS_EDGES)

    components = strongly_connected_components(graph)

    flattened = [vertex for component in components for vertex in component]
    assert sorted(flattened) == sorted(graph.vertices)

    position = {vertex: i for i, component in enumerate(components) for vertex in component}
    for source, target in graph.edges:
        assert position[target] <= position[source]


def test_deep_graph_does_not_hit_recursion_limit():
    size = 100_000
    graph = DirectedGraph()
    for i in range(size - 1):
        graph.add_edge(str(i), str(i + 1))

    chain = strongly_connected_components(graph)
    assert len(chain) == size

    graph.add_edge(str(size - 1), "0")
    cycle = strongly_connected_components(graph)
    assert len(cycle) == 1
    assert len(cycle[0]) == size
