"""Command line entry point for Tarjan's strongly connected components."""

import argparse
from pathlib import Path

from graph_algorithms.graph import DirectedGraph
from graph_algorithms.render import render_components
from graph_algorithms.tarjan import strongly_connected_components


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Find the strongly connected components of a directed graph with "
        "Tarjan's algorithm and render them with Graphviz."
    )
    parser.add_argument("input", type=Path, help="adjacency matrix file of 0s and 1s")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path without extension (default: output/<input name>)",
    )
    parser.add_argument("-f", "--format", default="svg", choices=["svg", "png", "pdf"])
    args = parser.parse_args(argv)

    graph = DirectedGraph.from_adjacency_matrix(args.input.read_text())
    components = strongly_connected_components(graph)

    print(f"{len(components)} strongly connected components:")
    for i, component in enumerate(components, start=1):
        print(f"  SCC {i}: {', '.join(component)}")

    output = args.output or Path("output") / args.input.stem
    rendered = render_components(graph, components).render(output, format=args.format, cleanup=True)
    print(f"Graph written to {rendered}")
