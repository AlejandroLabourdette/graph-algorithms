"""Graphviz rendering of graphs and their components."""

import graphviz

from graph_algorithms.graph import DirectedGraph

# (cluster background, node fill, border) triples, cycled across components.
PALETTE = [
    ("#e3f2fd", "#90caf9", "#1e88e5"),
    ("#fce4ec", "#f48fb1", "#d81b60"),
    ("#e8f5e9", "#a5d6a7", "#43a047"),
    ("#fff3e0", "#ffcc80", "#fb8c00"),
    ("#ede7f6", "#b39ddb", "#5e35b1"),
    ("#e0f7fa", "#80deea", "#00acc1"),
    ("#f9fbe7", "#e6ee9c", "#c0ca33"),
    ("#efebe9", "#bcaaa4", "#6d4c41"),
]

INTER_COMPONENT_EDGE_COLOR = "#9e9e9e"


def render_components(
    graph: DirectedGraph,
    components: list[list[str]],
) -> graphviz.Digraph:
    """Build a Graphviz digraph that draws each component as a labelled cluster.

    Edges inside a component are solid and use the component color; edges
    between components are dashed and gray.
    """
    component_of = {vertex: i for i, component in enumerate(components) for vertex in component}

    dot = graphviz.Digraph(name="components")
    dot.attr(
        rankdir="LR",
        nodesep="0.5",
        ranksep="0.9",
        dpi="150",
    )
    # Same size for every vertex, wide enough for the longest name (in inches).
    longest_name = max((len(vertex) for vertex in graph.vertices), default=1)
    node_width = max(0.5, 0.12 * longest_name + 0.2)
    dot.attr(
        "node",
        shape="circle",
        style="filled",
        fontname="Helvetica",
        penwidth="1.5",
        width=f"{node_width:.2f}",
        fixedsize="true",
    )
    dot.attr("edge", arrowsize="0.8", penwidth="1.3")

    for i, component in enumerate(components):
        background, fill, border = PALETTE[i % len(PALETTE)]
        with dot.subgraph(name=f"cluster_{i}") as cluster:
            cluster.attr(
                label=f"SCC {i + 1}",
                labeljust="l",
                labelloc="b",
                style="rounded,filled",
                fillcolor=background,
                color=border,
                fontcolor=border,
                fontname="Helvetica-Bold",
                fontsize="13",
                penwidth="2",
                margin="18",
            )
            for vertex in component:
                cluster.node(vertex, fillcolor=fill, color=border)

    for source, target in graph.edges:
        if source == target:
            # A blank label makes Graphviz reserve room for the loop, which otherwise
            # touches the cluster border.
            border = PALETTE[component_of[source] % len(PALETTE)][2]
            dot.edge(source, target, color=border, label=" ")
        elif component_of[source] == component_of[target]:
            border = PALETTE[component_of[source] % len(PALETTE)][2]
            dot.edge(source, target, color=border)
        else:
            dot.edge(source, target, color=INTER_COMPONENT_EDGE_COLOR, style="dashed")

    return dot
