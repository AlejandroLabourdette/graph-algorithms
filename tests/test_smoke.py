import graphviz

import graph_algorithms


def test_package_imports():
    assert graph_algorithms.__doc__


def test_graphviz_renders(tmp_path):
    graph = graphviz.Graph()
    graph.edge("a", "b")
    output = graph.render(tmp_path / "smoke", format="svg")
    assert (tmp_path / "smoke.svg").exists(), output
