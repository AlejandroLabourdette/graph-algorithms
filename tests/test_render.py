from graph_algorithms.cli.tarjan import main
from graph_algorithms.graph import DirectedGraph
from graph_algorithms.render import render_components
from graph_algorithms.tarjan import strongly_connected_components


def build_graph() -> DirectedGraph:
    return DirectedGraph.from_adjacency_matrix(
        """
        a b c d
        0 1 0 0
        1 0 1 0
        0 0 1 0
        0 0 0 0
        """
    )


def test_each_component_is_a_labelled_cluster():
    graph = build_graph()
    components = strongly_connected_components(graph)

    source = render_components(graph, components).source

    assert source.count("subgraph cluster_") == len(components) == 3
    for i in range(1, len(components) + 1):
        assert f'label="SCC {i}"' in source
    for vertex in graph.vertices:
        assert f"\t\t{vertex} [" in source


def test_only_inter_component_edges_are_dashed():
    graph = build_graph()
    components = strongly_connected_components(graph)

    source = render_components(graph, components).source
    edge_lines = [line.strip() for line in source.splitlines() if "->" in line]

    dashed = [line.split(" [")[0] for line in edge_lines if "dashed" in line]
    assert dashed == ["b -> c"]


def test_cli_renders_image(tmp_path, capsys):
    input_file = tmp_path / "graph.txt"
    input_file.write_text("0 1 0\n1 0 1\n0 0 0\n")

    main([str(input_file), "-o", str(tmp_path / "out"), "-f", "svg"])

    assert (tmp_path / "out.svg").read_text().startswith("<?xml")
    assert "2 strongly connected components" in capsys.readouterr().out
