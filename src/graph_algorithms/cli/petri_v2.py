"""Punto de entrada de línea de comandos para el análisis de cobertura de una red de Petri."""

import argparse
from pathlib import Path

from graph_algorithms.petri import PetriNet
from graph_algorithms.petri_v2 import (
    CoverabilityGraph,
    CoverabilityTree,
    OmegaMarking,
    TreeNode,
    add_child,
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
from graph_algorithms.render import render_coverability_graph, render_coverability_tree


def format_tree(tree: CoverabilityTree) -> list[str]:
    """Indented outline of the tree, one line per node, depth first."""
    lines: list[str] = []
    pending = [(tree.nodes[0], 0)]
    while pending:
        node, depth = pending.pop()
        arc = f"--{node.transition}--> " if node.transition else ""
        line = f"{'  ' * depth}{arc}{vertex_name(node.id)} {format_marking(node.marking)}"
        if node.duplicate_of is not None:
            line += f"  duplicado de {vertex_name(node.duplicate_of)}"
        lines.append(line)
        pending.extend((child, depth + 1) for child in reversed(tree.children(node.id)))
    return lines


def node_omega_lines(
    places: tuple[str, ...], nodes: tuple[TreeNode, ...] | list[TreeNode], node: TreeNode
) -> list[str]:
    """One line per acceleration of `node`: the ancestor it covers and the places turned to ω."""
    lines = []
    for acceleration in node.accelerations:
        ancestor = nodes[acceleration.ancestor]
        pumped = ", ".join(places[p] for p in acceleration.places)
        lines.append(
            f"{vertex_name(node.id)} cubre a su ancestro {vertex_name(ancestor.id)} "
            f"{format_marking(ancestor.marking)}: {pumped} -> ω"
        )
    return lines


def format_omegas(tree: CoverabilityTree) -> list[str]:
    """One line per acceleration in the whole tree."""
    return [line for node in tree.nodes for line in node_omega_lines(tree.places, tree.nodes, node)]


def format_bounds(places: tuple[str, ...], bounds: dict[str, int | None]) -> list[str]:
    return [
        f"{place}: "
        + ("no acotado (ω)" if bounds[place] is None else f"acotado (cota {bounds[place]})")
        for place in places
    ]


def format_components(graph: CoverabilityGraph, components: list[list[int]]) -> list[str]:
    terminal = {tuple(component) for component in terminal_components(graph, components)}
    lines = []
    for i, component in enumerate(components, start=1):
        markings = ", ".join(
            f"{vertex_name(v)} {format_marking(graph.markings[v])}" for v in component
        )
        tags = [
            tag
            for tag, applies in (
                ("cíclica", is_cyclic_component(graph, component)),
                ("terminal", tuple(component) in terminal),
            )
            if applies
        ]
        suffix = f"  [{', '.join(tags)}]" if tags else ""
        lines.append(f"CFC {i}: {markings}{suffix}")
    return lines


QUIT = "q"
BACK = "r"
PROMPT = f"Disparar transición ({BACK} = regresar, {QUIT} = salir): "


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
    exists is a duplicate leaf, after which the exploration stays at the parent. `r` goes back to
    the parent so that other branches can be explored; the tree is redrawn at every step.
    """
    root = TreeNode(0, net.initial_marking, None, None, None, ())
    nodes = [root]
    first_with_marking: dict[OmegaMarking, int] = {root.marking: root.id}
    current = root
    rendered = ""

    while True:
        tree = CoverabilityTree(net.places, net.transitions, tuple(nodes))
        dead = {
            node.id
            for node in nodes
            if not node.is_duplicate and not net.enabled_transitions(node.marking)
        }
        rendered = render_coverability_tree(tree, current=current.id, dead=dead).render(
            output, format=image_format, cleanup=True
        )
        path = " -> ".join(vertex_name(node.id) for node in tree.path_to(current.id))
        print(f"\nNodo actual: {vertex_name(current.id)} {format_marking(current.marking)}")
        print(f"  Camino desde la raíz: {path}")
        print(f"  Árbol escrito en {rendered}")

        enabled = net.enabled_transitions(current.marking)
        if enabled:
            print(f"  Transiciones habilitadas: {', '.join(enabled)}")
        elif current.parent is None:
            print("  Marcado muerto: ninguna transición habilitada desde el inicio")
            break
        else:
            print("  Marcado muerto: ninguna transición habilitada")

        choice = read_choice()
        if choice is None or choice == QUIT:
            break
        if choice == BACK:
            if current.parent is None:
                print("  Ya estás en la raíz")
            else:
                current = nodes[current.parent]
        elif choice in enabled:
            child = add_child(net, nodes, first_with_marking, current, choice)
            print(
                f"  {choice}: {format_marking(current.marking)} -> {format_marking(child.marking)}"
                f"  [{vertex_name(child.id)}]"
            )
            for line in node_omega_lines(net.places, nodes, child):
                print(f"  Omega nuevo: {line}")
            if child.duplicate_of is None:
                current = child
            else:
                print(
                    f"  Duplicado de {vertex_name(child.duplicate_of)}: no se expande, "
                    f"se regresa a {vertex_name(current.id)}"
                )
        elif choice in net.transitions:
            print(f"  {choice} no está habilitada")
        elif choice:
            print(f"  transición desconocida {choice!r}")

    tree = CoverabilityTree(net.places, net.transitions, tuple(nodes))
    duplicates = sum(node.is_duplicate for node in nodes)
    print(f"\nÁrbol construido: {len(nodes)} nodos, {duplicates} duplicados (no se expanden)")
    for line in format_tree(tree):
        print(f"  {line}")
    omegas = format_omegas(tree)
    print(f"Omegas: {len(omegas) or 'ninguno'}")
    for line in omegas:
        print(f"  {line}")
    print(f"Último árbol escrito en {rendered}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analiza una red de Petri con su árbol de cobertura de Karp-Miller: construye "
        "el árbol y el grafo de cobertura, encuentra los omegas, las componentes fuertemente "
        "conexas y el acotamiento de cada lugar, y dibuja el árbol y el grafo con Graphviz."
    )
    parser.add_argument("input", type=Path, help="archivo con las secciones pre, post y marking")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="ruta de salida sin extensión; se agregan '_arbol' y '_grafo' "
        "(por defecto: output/<nombre del archivo>)",
    )
    parser.add_argument("-f", "--format", default="svg", choices=["svg", "png", "pdf"])
    parser.add_argument(
        "-i",
        "--interactivo",
        action="store_true",
        help="modo interactivo: elige la transición a disparar en cada paso y se construye "
        "el árbol de cobertura poco a poco (se redibuja '<salida>_arbol' en cada paso)",
    )
    args = parser.parse_args(argv)

    net = PetriNet.from_text(args.input.read_text())
    output = args.output or Path("output") / args.input.stem
    if args.interactivo:
        explore(net, output.with_name(f"{output.name}_arbol"), args.format)
        return

    tree = build_coverability_tree(net)
    graph = build_coverability_graph(tree)
    components = coverability_components(graph)
    bounds = place_bounds(graph)

    print(f"Lugares: {', '.join(net.places)}")
    print(f"Transiciones: {', '.join(net.transitions)}")
    print(f"Marcado inicial: {format_marking(net.initial_marking)}")

    duplicates = sum(node.is_duplicate for node in tree.nodes)
    print(
        f"\nÁrbol de cobertura: {len(tree.nodes)} nodos, {duplicates} duplicados (no se expanden)"
    )
    for line in format_tree(tree):
        print(f"  {line}")

    omegas = format_omegas(tree)
    print(f"\nOmegas: {len(omegas) or 'ninguno'}")
    for line in omegas:
        print(f"  {line}")

    print(f"\nGrafo de cobertura: {len(graph.markings)} marcados, {len(graph.edges)} arcos")
    for vertex, marking in graph.markings.items():
        print(f"  {vertex_name(vertex)} {format_marking(marking)}")

    noun = (
        "Componente fuertemente conexa"
        if len(components) == 1
        else "Componentes fuertemente conexas"
    )
    print(f"\n{noun}: {len(components)}")
    for line in format_components(graph, components):
        print(f"  {line}")
    dead = dead_markings(graph)
    if dead:
        print(
            "  Marcados muertos (sin transiciones habilitadas): "
            + ", ".join(vertex_name(v) for v in dead)
        )
    else:
        print("  Marcados muertos: ninguno")

    print("\nAcotamiento")
    for line in format_bounds(net.places, bounds):
        print(f"  {line}")
    print(f"  La red es acotada: {'sí' if is_bounded(bounds) else 'no'}")
    print(f"  La red es segura (1-acotada): {'sí' if is_safe(bounds) else 'no'}")
    if not is_bounded(bounds):
        unbounded = ", ".join(p for p, bound in bounds.items() if bound is None)
        print(f"  Lugares no acotados: {unbounded}")

    tree_path = output.with_name(f"{output.name}_arbol")
    graph_path = output.with_name(f"{output.name}_grafo")
    rendered_tree = render_coverability_tree(tree).render(
        tree_path, format=args.format, cleanup=True
    )
    rendered_graph = render_coverability_graph(graph, components).render(
        graph_path, format=args.format, cleanup=True
    )
    print(f"\nÁrbol escrito en {rendered_tree}")
    print(f"Grafo escrito en {rendered_graph}")
