"""Graphviz rendering of coverability trees and coverability graphs of Petri nets."""

import html

import graphviz

from graph_algorithms.petri_cover import (
    OMEGA,
    CoverabilityGraph,
    CoverabilityTree,
    OmegaMarking,
    dead_markings,
    format_marking,
    is_cyclic_component,
    vertex_name,
)
from graph_algorithms.render import ARC_COLOR, PALETTE, PLACE_COLORS

OMEGA_COLORS = ("#ffe0b2", "#fb8c00")
DEAD_COLOR = "#e53935"
DUPLICATE_COLOR = "#9e9e9e"
CURRENT_COLOR = "#2e7d32"


def _marking_label(vertex: str, marking: OmegaMarking, note: str = "") -> str:
    """HTML-like label with the node name above its marking and an optional note below."""
    text = f"{html.escape(vertex)}<BR/>{html.escape(format_marking(marking))}"
    if note:
        text += f'<BR/><FONT POINT-SIZE="10">{html.escape(note)}</FONT>'
    return f"<{text}>"


def _marking_node_colors(marking: OmegaMarking) -> tuple[str, str]:
    """(fill, border) of a marking node: orange when some place is omega."""
    return OMEGA_COLORS if OMEGA in marking else PLACE_COLORS


def _places_title(places: tuple[str, ...]) -> str:
    return f"places = ({', '.join(places)})"


def render_coverability_tree(
    tree: CoverabilityTree,
    current: int | None = None,
    dead: set[int] | None = None,
) -> graphviz.Digraph:
    """Build a Graphviz digraph of the coverability tree.

    Every tree node shows its id and marking; arcs are labelled with the fired transition.
    Nodes with an omega are orange, duplicates are dashed gray leaves that name the node they
    repeat, and dead nodes (no transition enabled) have a red border. The root is drawn with a
    thick border and `current`, when given, with a thick green one.

    `dead` lists the ids of the dead nodes. By default they are the nodes that were not
    expanded and are not duplicates, which is right for a finished tree but not for a tree
    that is still being explored, where the caller passes the dead nodes it knows.
    """
    if dead is None:
        expanded = {node.parent for node in tree.nodes}
        dead = {node.id for node in tree.nodes if not node.is_duplicate and node.id not in expanded}

    dot = graphviz.Digraph(name="coverability_tree")
    dot.attr(
        rankdir="TB",
        nodesep="0.4",
        ranksep="0.6",
        dpi="150",
        label=_places_title(tree.places),
        labelloc="t",
        fontname="Helvetica-Bold",
        fontsize="14",
    )
    dot.attr("node", shape="box", style="rounded,filled", fontname="Helvetica", penwidth="1.5")
    dot.attr("edge", arrowsize="0.8", penwidth="1.3", color=ARC_COLOR, fontname="Helvetica")

    for node in tree.nodes:
        fill, border = _marking_node_colors(node.marking)
        attributes = {"fillcolor": fill, "color": border}
        notes = []
        if node.duplicate_of is not None:
            notes.append(f"= {vertex_name(node.duplicate_of)}")
            attributes.update(
                fillcolor="#f5f5f5", color=DUPLICATE_COLOR, style="rounded,dashed,filled"
            )
        elif node.id in dead:
            attributes["color"] = DEAD_COLOR
            notes.append("dead")
        if node.parent is None:
            attributes["penwidth"] = "3"
        if node.id == current:
            attributes.update(color=CURRENT_COLOR, penwidth="4")
            notes.append("current")
        dot.node(
            vertex_name(node.id),
            label=_marking_label(vertex_name(node.id), node.marking, ", ".join(notes)),
            **attributes,
        )

    for node in tree.nodes:
        if node.parent is not None and node.transition is not None:
            dot.edge(vertex_name(node.parent), vertex_name(node.id), label=node.transition)

    return dot


def render_coverability_graph(
    graph: CoverabilityGraph,
    components: list[list[int]],
) -> graphviz.Digraph:
    """Build a Graphviz digraph of the coverability graph with its strongly connected components.

    Every cyclic component (several markings, or one marking with a self-loop) is drawn as a
    labelled cluster. Markings with an omega are orange, markings where no transition is
    enabled have a red border and the initial marking has a thick border. Parallel arcs are
    merged into one arc labelled with all their transitions; arcs between components are dashed.
    """
    component_of = {vertex: i for i, component in enumerate(components) for vertex in component}
    dead = set(dead_markings(graph))

    dot = graphviz.Digraph(name="coverability_graph")
    dot.attr(
        rankdir="LR",
        nodesep="0.5",
        ranksep="0.9",
        dpi="150",
        label=_places_title(graph.places),
        labelloc="t",
        fontname="Helvetica-Bold",
        fontsize="14",
    )
    dot.attr("node", shape="box", style="rounded,filled", fontname="Helvetica", penwidth="1.5")
    dot.attr("edge", arrowsize="0.8", penwidth="1.3", color=ARC_COLOR, fontname="Helvetica")

    def add_marking(target: graphviz.Digraph, vertex: int) -> None:
        marking = graph.markings[vertex]
        fill, border = _marking_node_colors(marking)
        attributes = {"fillcolor": fill, "color": DEAD_COLOR if vertex in dead else border}
        if vertex == graph.initial:
            attributes["penwidth"] = "3"
        target.node(
            vertex_name(vertex),
            label=_marking_label(vertex_name(vertex), marking, "dead" if vertex in dead else ""),
            **attributes,
        )

    clustered: set[int] = set()
    for i, component in enumerate(components):
        if not is_cyclic_component(graph, component):
            continue
        background, _, border = PALETTE[i % len(PALETTE)]
        clustered.update(component)
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
                add_marking(cluster, vertex)
    for vertex in graph.markings:
        if vertex not in clustered:
            add_marking(dot, vertex)

    # Parallel arcs (same source and target) are drawn as one arc with all their labels, so that
    # several self-loops on a marking do not stack on top of each other.
    arcs: dict[tuple[int, int], list[str]] = {}
    for source, transition, target in graph.edges:
        arcs.setdefault((source, target), []).append(transition)
    for (source, target), transitions in arcs.items():
        style = "solid" if component_of[source] == component_of[target] else "dashed"
        dot.edge(
            vertex_name(source), vertex_name(target), label=", ".join(transitions), style=style
        )

    return dot
