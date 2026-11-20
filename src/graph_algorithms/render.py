"""Graphviz rendering of graphs, their components and Petri nets."""

import html

import graphviz

from graph_algorithms.graph import DirectedGraph
from graph_algorithms.petri import Marking, PetriNet

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


PLACE_COLORS = ("#e3f2fd", "#1e88e5")
ENABLED_TRANSITION_COLORS = ("#a5d6a7", "#43a047")
DISABLED_TRANSITION_COLORS = ("#eeeeee", "#9e9e9e")
LAST_FIRED_COLOR = "#fb8c00"
ARC_COLOR = "#616161"

# Tokens up to this count are drawn as dots; larger counts are written as a number.
MAX_TOKEN_DOTS = 4


def _place_label(place: str, tokens: int) -> str:
    """HTML-like label with the place name above its tokens."""
    marks = str(tokens) if tokens > MAX_TOKEN_DOTS else "●" * tokens
    return f'<{html.escape(place)}<BR/><FONT POINT-SIZE="18">{marks or " "}</FONT>>'


def render_petri_net(
    net: PetriNet,
    marking: Marking,
    last_fired: str | None = None,
) -> graphviz.Digraph:
    """Build a Graphviz digraph of `net` in `marking`.

    Places are circles holding their tokens, transitions are boxes: green when
    enabled, gray otherwise, with an orange border on `last_fired`. Arcs carry
    their weight when it is greater than one.
    """
    enabled = set(net.enabled_transitions(marking))

    dot = graphviz.Digraph(name="petri_net")
    dot.attr(
        rankdir="LR",
        nodesep="0.5",
        ranksep="0.7",
        dpi="150",
        label=f"M = ({', '.join(map(str, marking))})",
        labelloc="t",
        fontname="Helvetica-Bold",
        fontsize="14",
    )
    dot.attr("node", fontname="Helvetica", penwidth="1.5", style="filled")
    dot.attr("edge", arrowsize="0.8", penwidth="1.3", color=ARC_COLOR, fontname="Helvetica")

    fill, border = PLACE_COLORS
    # Same size for every place, wide enough for the longest name (in inches).
    longest_name = max((len(name) for name in net.places), default=1)
    place_width = max(0.75, 0.1 * longest_name + 0.25)
    for place, tokens in zip(net.places, marking, strict=True):
        dot.node(
            f"place_{place}",
            label=_place_label(place, tokens),
            shape="circle",
            width=f"{place_width:.2f}",
            fixedsize="true",
            fillcolor=fill,
            color=border,
        )

    for transition in net.transitions:
        fill, border = (
            ENABLED_TRANSITION_COLORS if transition in enabled else DISABLED_TRANSITION_COLORS
        )
        fired = transition == last_fired
        dot.node(
            f"transition_{transition}",
            label=transition,
            shape="box",
            height="0.4",
            fillcolor=fill,
            color=LAST_FIRED_COLOR if fired else border,
            penwidth="3" if fired else "1.5",
            fontcolor="black" if transition in enabled else border,
        )

    for p, place in enumerate(net.places):
        for t, transition in enumerate(net.transitions):
            if weight := net.pre[p][t]:
                dot.edge(
                    f"place_{place}",
                    f"transition_{transition}",
                    label=str(weight) if weight > 1 else "",
                )
            if weight := net.post[p][t]:
                dot.edge(
                    f"transition_{transition}",
                    f"place_{place}",
                    label=str(weight) if weight > 1 else "",
                )

    return dot
