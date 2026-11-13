import pytest

from graph_algorithms.graph import DirectedGraph


def test_from_edge_list_parses_edges_vertices_and_comments():
    graph = DirectedGraph.from_edge_list(
        """
        # comment line
        a b
        b c  # trailing comment

        d
        """
    )

    assert graph.vertices == ["a", "b", "c", "d"]
    assert list(graph.edges) == [("a", "b"), ("b", "c")]
    assert graph.successors("d") == []


def test_from_edge_list_rejects_malformed_line():
    with pytest.raises(ValueError, match="line 2"):
        DirectedGraph.from_edge_list("a b\na b c\n")


def test_parallel_edges_and_self_loops_are_kept():
    graph = DirectedGraph()
    graph.add_edge("a", "a")
    graph.add_edge("a", "b")
    graph.add_edge("a", "b")

    assert graph.successors("a") == ["a", "b", "b"]
    assert len(graph) == 2
