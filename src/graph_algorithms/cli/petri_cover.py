"""Command line entry point for the coverability analysis of a Petri net."""

import argparse
from pathlib import Path

from graph_algorithms.petri import PetriNet
from graph_algorithms.petri_cover import (
    CoverabilityGraph,
    CoverabilityTree,
    OmegaMarking,
    TreeBuilder,
    TreeNode,
    build_coverability_graph,
    build_coverability_tree,
    coverability_components,
    dead_markings,
    format_marking,
    is_bounded,
    is_cyclic_component,
    is_safe,
    place_bounds,
    terminal_components,
    vertex_name,
)
from graph_algorithms.render import render_petri_net
from graph_algorithms.render_cover import render_coverability_graph, render_coverability_tree


def format_tree(tree: CoverabilityTree) -> list[str]:
    """Indented outline of the tree, one line per node, depth first."""
    lines: list[str] = []
    pending = [(tree.nodes[0], 0)]
    while pending:
        node, depth = pending.pop()
        arc = f"--{node.transition}--> " if node.transition else ""
        line = f"{'  ' * depth}{arc}{vertex_name(node.id)} {format_marking(node.marking)}"
        if node.duplicate_of is not None:
            line += f"  duplicate of {vertex_name(node.duplicate_of)}"
        lines.append(line)
        pending.extend((child, depth + 1) for child in reversed(tree.children(node.id)))
    return lines


def node_omega_lines(tree: CoverabilityTree, node: TreeNode) -> list[str]:
    """One line per acceleration of `node`: the ancestor it covers and the places turned to ω."""
    lines = []
    for acceleration in node.accelerations:
        ancestor = tree.nodes[acceleration.ancestor]
        pumped = ", ".join(tree.places[p] for p in acceleration.places)
        lines.append(
            f"{vertex_name(node.id)} covers its ancestor {vertex_name(ancestor.id)} "
            f"{format_marking(ancestor.marking)}: {pumped} -> ω"
        )
    return lines


def format_omegas(tree: CoverabilityTree) -> list[str]:
    """One line per acceleration in the whole tree."""
    return [line for node in tree.nodes for line in node_omega_lines(tree, node)]


def format_bounds(places: tuple[str, ...], bounds: dict[str, int | None]) -> list[str]:
    return [
        f"{place}: " + ("unbounded (ω)" if bounds[place] is None else f"{bounds[place]}-bounded")
        for place in places
    ]


def format_components(graph: CoverabilityGraph, components: list[list[int]]) -> list[str]:
    """One line per component, numbered in topological order (SCC 1 holds the initial marking)."""
    terminal = {tuple(component) for component in terminal_components(graph, components)}
    lines = []
    for i, component in enumerate(components, start=1):
        markings = ", ".join(
            f"{vertex_name(v)} {format_marking(graph.markings[v])}" for v in component
        )
        tags = [
            tag
            for tag, applies in (
                ("cyclic", is_cyclic_component(graph, component)),
                ("terminal", tuple(component) in terminal),
            )
            if applies
        ]
        suffix = f"  [{', '.join(tags)}]" if tags else ""
        lines.append(f"SCC {i}: {markings}{suffix}")
    return lines


def write_net(
    net: PetriNet,
    output: Path,
    image_format: str,
    marking: OmegaMarking | None = None,
    last_fired: str | None = None,
) -> str:
    """Draw the net itself and return the path of the image.

    The net is drawn at `marking` (default: the initial marking), which may contain omegas, with
    `last_fired` highlighted.
    """
    return render_petri_net(
        net, net.initial_marking if marking is None else marking, last_fired
    ).render(output.with_name(f"{output.name}_net"), format=image_format, cleanup=True)


QUIT = "q"
BACK = "r"
PROMPT = f"Fire transition ({BACK} = back, {QUIT} = quit): "


def read_choice() -> str | None:
    """Read the user's answer; None means end of input."""
    try:
        return input(PROMPT).strip()
    except EOFError, KeyboardInterrupt:
        print()
        return None


def explore(net: PetriNet, output: Path, image_format: str) -> None:
    """Build the coverability tree interactively, firing the transition the user chooses.

    The tree grows from the current node: each fired transition adds a child, omegas are
    introduced by comparing it with the path from the root, and a child whose marking already
    exists is a duplicate leaf, after which the exploration stays at the parent. Firing a
    transition that was already fired from the current node moves to the child that exists
    instead of adding another one. `r` goes back to the parent so that other branches can be
    explored. At every step the tree (`<output>_tree`) and the net (`<output>_net`, at the current
    marking with the transition that led to it highlighted) are redrawn.
    """
    builder = TreeBuilder(net)
    current = builder.root
    rendered = rendered_net = ""

    while True:
        tree = builder.tree()
        dead = {
            node.id
            for node in tree.nodes
            if not node.is_duplicate and not net.enabled_transitions(node.marking)
        }
        rendered = render_coverability_tree(tree, current=current.id, dead=dead).render(
            output.with_name(f"{output.name}_tree"), format=image_format, cleanup=True
        )
        rendered_net = write_net(net, output, image_format, current.marking, current.transition)
        path = " -> ".join(vertex_name(node.id) for node in tree.path_to(current.id))
        print(f"\nCurrent node: {vertex_name(current.id)} {format_marking(current.marking)}")
        print(f"  Path from the root: {path}")
        print(f"  Tree written to {rendered}")
        print(f"  Net written to {rendered_net}")

        enabled = net.enabled_transitions(current.marking)
        if enabled:
            print(f"  Enabled transitions: {', '.join(enabled)}")
        elif current.parent is None:
            print("  Dead marking: no transition is enabled from the start")
            break
        else:
            print("  Dead marking: no transition is enabled")

        choice = read_choice()
        if choice is None or choice == QUIT:
            break
        if choice == BACK:
            if current.parent is None:
                print("  Already at the root")
            else:
                current = tree.nodes[current.parent]
        elif choice in enabled:
            existing = builder.child(current, choice)
            child = existing or builder.add_child(current, choice)
            note = "  (already in the tree)" if existing else ""
            print(
                f"  {choice}: {format_marking(current.marking)} -> {format_marking(child.marking)}"
                f"  [{vertex_name(child.id)}]{note}"
            )
            if not existing:
                for line in node_omega_lines(builder.tree(), child):
                    print(f"  New omega: {line}")
            if child.duplicate_of is None:
                current = child
            else:
                print(
                    f"  Duplicate of {vertex_name(child.duplicate_of)}: not expanded, "
                    f"back to {vertex_name(current.id)}"
                )
        elif choice in net.transitions:
            print(f"  {choice} is not enabled")
        elif choice:
            print(f"  unknown transition {choice!r}")

    tree = builder.tree()
    duplicates = sum(node.is_duplicate for node in tree.nodes)
    print(f"\nTree built: {len(tree.nodes)} nodes, {duplicates} duplicates (not expanded)")
    for line in format_tree(tree):
        print(f"  {line}")
    omegas = format_omegas(tree)
    print(f"Omegas: {len(omegas) or 'none'}")
    for line in omegas:
        print(f"  {line}")
    print(f"Last tree written to {rendered}")
    print(f"Last net written to {rendered_net}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analyse a Petri net with its Karp-Miller coverability tree: build the tree "
        "and the coverability graph, find the omegas, the strongly connected components and "
        "the boundedness of every place, and render the tree and the graph with Graphviz."
    )
    parser.add_argument("input", type=Path, help="file with pre, post and marking sections")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path without extension; '_net', '_tree' and '_graph' are appended "
        "(default: output/<input name>)",
    )
    parser.add_argument("-f", "--format", default="svg", choices=["svg", "png", "pdf"])
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="build the tree step by step: choose the transition to fire at each step; "
        "'<output>_tree' and '<output>_net' are redrawn after every step",
    )
    args = parser.parse_args(argv)

    net = PetriNet.from_text(args.input.read_text())
    output = args.output or Path("output") / args.input.stem
    if args.interactive:
        explore(net, output, args.format)
        return

    tree = build_coverability_tree(net)
    graph = build_coverability_graph(tree)
    components = coverability_components(graph)
    bounds = place_bounds(graph)

    print(f"Places: {', '.join(net.places)}")
    print(f"Transitions: {', '.join(net.transitions)}")
    print(f"Initial marking: {format_marking(net.initial_marking)}")
    print(f"Petri net written to {write_net(net, output, args.format)}")

    duplicates = sum(node.is_duplicate for node in tree.nodes)
    print(f"\nCoverability tree: {len(tree.nodes)} nodes, {duplicates} duplicates (not expanded)")
    for line in format_tree(tree):
        print(f"  {line}")

    omegas = format_omegas(tree)
    print(f"\nOmegas: {len(omegas) or 'none'}")
    for line in omegas:
        print(f"  {line}")

    print(f"\nCoverability graph: {len(graph.markings)} markings, {len(graph.edges)} arcs")
    for vertex, marking in graph.markings.items():
        print(f"  {vertex_name(vertex)} {format_marking(marking)}")

    noun = "component" if len(components) == 1 else "components"
    print(f"\nStrongly connected {noun}: {len(components)}")
    for line in format_components(graph, components):
        print(f"  {line}")
    dead = dead_markings(graph)
    if dead:
        print("  Dead markings: " + ", ".join(vertex_name(v) for v in dead))
    else:
        print("  Dead markings: none")

    print("\nBoundedness")
    for line in format_bounds(net.places, bounds):
        print(f"  {line}")
    print(f"  Net is bounded: {'yes' if is_bounded(bounds) else 'no'}")
    print(f"  Net is safe (1-bounded): {'yes' if is_safe(bounds) else 'no'}")
    if not is_bounded(bounds):
        unbounded = ", ".join(p for p, bound in bounds.items() if bound is None)
        print(f"  Unbounded places: {unbounded}")

    tree_path = output.with_name(f"{output.name}_tree")
    graph_path = output.with_name(f"{output.name}_graph")
    rendered_tree = render_coverability_tree(tree).render(
        tree_path, format=args.format, cleanup=True
    )
    rendered_graph = render_coverability_graph(graph, components).render(
        graph_path, format=args.format, cleanup=True
    )
    print(f"\nTree written to {rendered_tree}")
    print(f"Graph written to {rendered_graph}")
