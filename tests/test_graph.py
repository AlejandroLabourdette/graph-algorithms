import pytest

from graph_algorithms.graph import DirectedGraph


def test_from_adjacency_matrix_with_header_and_comments():
    graph = DirectedGraph.from_adjacency_matrix(
        """
        # comment line
        a b c d
        0 1 0 0
        0 0 1 0  # trailing comment

        0 0 1 0
        0 0 0 0
        """
    )

    assert graph.vertices == ["a", "b", "c", "d"]
    assert list(graph.edges) == [("a", "b"), ("b", "c"), ("c", "c")]
    assert graph.successors("d") == []


def test_from_adjacency_matrix_without_header_numbers_vertices():
    graph = DirectedGraph.from_adjacency_matrix("0 1\n1 0\n")

    assert graph.vertices == ["1", "2"]
    assert list(graph.edges) == [("1", "2"), ("2", "1")]


def test_from_adjacency_matrix_empty():
    assert len(DirectedGraph.from_adjacency_matrix("# nothing here\n")) == 0


@pytest.mark.parametrize(
    ("text", "error"),
    [
        pytest.param("0 1\n1\n", "line 2: expected 2 values, got 1", id="short-row"),
        pytest.param("0 1\n1 0\n0 0\n", "line 1: expected 3 values, got 2", id="not-square"),
        pytest.param("0 2\n1 0\n", "line 1: expected 0 or 1, got '2'", id="bad-value"),
        pytest.param("a b c\n0 1\n1 0\n", "header names 3 vertices", id="header-size"),
        pytest.param("a a\n0 1\n1 0\n", "vertex names must be unique", id="duplicate-names"),
    ],
)
def test_from_adjacency_matrix_rejects_malformed_input(text, error):
    with pytest.raises(ValueError, match=error):
        DirectedGraph.from_adjacency_matrix(text)


def test_parallel_edges_and_self_loops_are_kept():
    graph = DirectedGraph()
    graph.add_edge("a", "a")
    graph.add_edge("a", "b")
    graph.add_edge("a", "b")

    assert graph.successors("a") == ["a", "b", "b"]
    assert len(graph) == 2
