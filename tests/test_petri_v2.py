from pathlib import Path

import pytest

from graph_algorithms.cli.petri_v2 import format_omegas, format_tree, main
from graph_algorithms.petri import PetriNet
from graph_algorithms.petri_v2 import (
    OMEGA,
    accelerate,
    build_coverability_graph,
    build_coverability_tree,
    coverability_components,
    dead_markings,
    format_marking,
    is_bounded,
    is_safe,
    place_bounds,
    terminal_components,
)
from graph_algorithms.render import render_coverability_graph, render_coverability_tree

EXAMPLES = Path(__file__).parent.parent / "examples"

# `arrive` keeps idle and adds a job to the queue, `serve` moves a job to done: both the queue
# and done are unbounded, and done only becomes omega one level below the queue.
UNBOUNDED = """
pre
        arrive serve
idle      1      0
queue     0      1
done      0      0
post
        arrive serve
idle      1      0
queue     1      0
done      0      1
marking
1 0 0
"""

# Two-slot buffer: bounded by 2, three markings in a single cycle.
BUFFER = """
pre
        put get
free     1   0
full     0   1
post
        put get
free     0   1
full     1   0
marking
2 0
"""

# `a` then `b` leads to a deadlock; `c` loops on the initial marking.
DEADLOCK = """
pre
      a b c
p     1 0 1
q     0 1 0
post
      a b c
p     0 0 1
q     1 0 0
marking
1 0
"""


def test_tree_of_a_bounded_net_has_no_omega_and_marks_duplicates():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))

    assert [(n.id, n.marking, n.parent, n.transition, n.duplicate_of) for n in tree.nodes] == [
        (0, (2, 0), None, None, None),
        (1, (1, 1), 0, "put", None),
        (2, (0, 2), 1, "put", None),
        (3, (2, 0), 1, "get", 0),
        (4, (1, 1), 2, "get", 1),
    ]
    assert all(not node.accelerations for node in tree.nodes)


def test_duplicates_are_leaves():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))

    for node in tree.nodes:
        if node.is_duplicate:
            assert tree.children(node.id) == []


def test_omega_appears_when_a_marking_covers_an_ancestor():
    tree = build_coverability_tree(PetriNet.from_text(UNBOUNDED))

    markings = {node.id: node.marking for node in tree.nodes}
    assert markings[1] == (1, OMEGA, 0)  # arrive from (1, 0, 0): queue grew
    assert markings[3] == (1, OMEGA, OMEGA)  # serve: done grew over the root, queue stays omega
    arrive = tree.nodes[1]
    assert [(a.ancestor, a.places) for a in arrive.accelerations] == [(0, (1,))]
    assert [(a.ancestor, a.places) for a in tree.nodes[3].accelerations] == [(0, (2,))]


def test_omega_arithmetic_keeps_omega():
    net = PetriNet.from_text(UNBOUNDED)

    assert net.fire((1, OMEGA, 0), "serve") == (1, OMEGA, 1)
    assert net.is_enabled((1, OMEGA, 0), "serve")


def test_accelerate_compares_with_every_ancestor_until_nothing_changes():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))
    root, middle = tree.nodes[0], tree.nodes[1]

    # (2, 2) covers (2, 0) in `full`, which becomes omega; (2, ω) then covers (1, 1) in `free`.
    marking, accelerations = accelerate((2, 2), [root, middle])

    assert marking == (OMEGA, OMEGA)
    assert [(a.ancestor, a.places) for a in accelerations] == [(0, (1,)), (1, (0,))]
    # An equal marking is not strictly greater: nothing changes.
    assert accelerate((2, 0), [root]) == ((2, 0), [])


def test_graph_merges_duplicates_into_arcs_to_the_original_node():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))

    graph = build_coverability_graph(tree)

    assert graph.markings == {0: (2, 0), 1: (1, 1), 2: (0, 2)}
    assert graph.edges == ((0, "put", 1), (1, "put", 2), (1, "get", 0), (2, "get", 1))


def test_components_of_the_coverability_graph():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(UNBOUNDED)))

    components = coverability_components(graph)

    # Each marking is its own component (the graph only moves "forward" through the omegas).
    assert sorted(components) == [[0], [1], [3]]
    assert terminal_components(graph, components) == [[3]]


def test_buffer_is_a_single_cyclic_component():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(BUFFER)))

    components = coverability_components(graph)

    assert len(components) == 1
    assert sorted(components[0]) == [0, 1, 2]


def test_dead_markings_and_terminal_components():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(DEADLOCK)))

    components = coverability_components(graph)

    assert dead_markings(graph) == [3]
    assert terminal_components(graph, components) == [[3]]


def test_bounds_of_a_bounded_net():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(BUFFER)))

    bounds = place_bounds(graph)

    assert bounds == {"free": 2, "full": 2}
    assert is_bounded(bounds)
    assert not is_safe(bounds)


def test_bounds_of_an_unbounded_net():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(UNBOUNDED)))

    bounds = place_bounds(graph)

    assert bounds == {"idle": 1, "queue": None, "done": None}
    assert not is_bounded(bounds)
    assert not is_safe(bounds)


def test_safe_net():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(DEADLOCK)))

    assert is_safe(place_bounds(graph))


def test_format_marking_writes_omega():
    assert format_marking((1, OMEGA, 0)) == "(1, ω, 0)"


def test_cli_text_helpers():
    tree = build_coverability_tree(PetriNet.from_text(UNBOUNDED))

    assert format_tree(tree)[:3] == [
        "M0 (1, 0, 0)",
        "  --arrive--> M1 (1, ω, 0)",
        "    --arrive--> M2 (1, ω, 0)  duplicado de M1",
    ]
    assert format_omegas(tree) == [
        "M1 cubre a su ancestro M0 (1, 0, 0): queue -> ω",
        "M3 cubre a su ancestro M0 (1, 0, 0): done -> ω",
    ]


def test_render_tree_shows_omegas_duplicates_and_dead_nodes():
    tree = build_coverability_tree(PetriNet.from_text(DEADLOCK))
    source = render_coverability_tree(tree).source
    lines = {
        line.strip().split(" [")[0]: line for line in source.splitlines() if " [label=<" in line
    }

    assert "penwidth=3" in lines["M0"]  # root
    assert "= M0" in lines["M2"] and "dashed" in lines["M2"]  # duplicate of the root
    assert "muerto" in lines["M3"] and "#e53935" in lines["M3"]
    edges = [line.strip() for line in source.splitlines() if "->" in line]
    assert edges[0].startswith("M0 -> M1 [label=a")

    omega_source = render_coverability_tree(
        build_coverability_tree(PetriNet.from_text(UNBOUNDED))
    ).source
    assert "(1, ω, 0)" in omega_source and "#ffe0b2" in omega_source


def test_render_graph_draws_cyclic_components_as_clusters_and_dashes_other_arcs():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(DEADLOCK)))
    components = coverability_components(graph)

    source = render_coverability_graph(graph, components).source

    # M0 has a self-loop (c) so it is a cluster; M1 and the dead M3 are single plain nodes.
    assert source.count("subgraph cluster_") == 1
    assert 'label="CFC' in source
    edges = {
        line.strip().split(" [")[0] + " " + line.split("label=")[1].split()[0]: line
        for line in source.splitlines()
        if "->" in line
    }
    assert "dashed" in edges["M0 -> M1 a"]
    assert "dashed" in edges["M1 -> M3 b"]
    assert "dashed" not in edges["M0 -> M0 c"]


def test_cli_prints_the_analysis_and_writes_both_images(tmp_path, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(UNBOUNDED)

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Árbol de cobertura: 6 nodos, 3 duplicados (no se expanden)" in out
    assert "Omegas: 2" in out
    assert "queue: no acotado (ω)" in out
    assert "La red es acotada: no" in out
    assert "Lugares no acotados: queue, done" in out
    assert (tmp_path / "out_arbol.svg").read_text().startswith("<?xml")
    assert (tmp_path / "out_grafo.svg").read_text().startswith("<?xml")


def test_cli_reports_a_bounded_net(tmp_path, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Omegas: ninguno" in out
    assert "free: acotado (cota 2)" in out
    assert "La red es acotada: sí" in out
    assert "La red es segura (1-acotada): no" in out
    assert "Marcados muertos: ninguno" in out


@pytest.mark.parametrize("example", sorted(EXAMPLES.glob("petri*.txt")), ids=lambda path: path.name)
def test_examples_terminate_and_render(example, tmp_path):
    main([str(example), "-o", str(tmp_path / example.stem)])

    assert (tmp_path / f"{example.stem}_arbol.svg").exists()
    assert (tmp_path / f"{example.stem}_grafo.svg").exists()


def feed_input(monkeypatch, *answers: str) -> None:
    remaining = iter(answers)

    def fake_input(prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


def test_interactive_builds_the_tree_step_by_step(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(UNBOUNDED)
    feed_input(monkeypatch, "arrive", "arrive", "serve", "q")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Nodo actual: M0 (1, 0, 0)" in out
    assert "Transiciones habilitadas: arrive\n" in out  # serve needs a job in the queue
    assert "arrive: (1, 0, 0) -> (1, ω, 0)  [M1]" in out
    assert "Omega nuevo: M1 cubre a su ancestro M0 (1, 0, 0): queue -> ω" in out
    assert "Duplicado de M1: no se expande, se regresa a M1" in out
    assert "serve: (1, ω, 0) -> (1, ω, ω)  [M3]" in out
    assert "Omega nuevo: M3 cubre a su ancestro M0 (1, 0, 0): done -> ω" in out
    assert "Camino desde la raíz: M0 -> M1 -> M3" in out
    assert "Árbol construido: 4 nodos, 1 duplicados (no se expanden)" in out
    assert "Omegas: 2" in out
    assert (tmp_path / "out_arbol.svg").read_text().startswith("<?xml")
    assert not (tmp_path / "out_grafo.svg").exists()


def test_interactive_reports_invalid_choices_and_goes_back(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)
    feed_input(monkeypatch, "get", "zzz", "", "put", "r", "r")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "get no está habilitada" in out
    assert "transición desconocida 'zzz'" in out
    assert "Nodo actual: M1 (1, 1)" in out
    assert out.index("Nodo actual: M1 (1, 1)") < out.index("Ya estás en la raíz")
    assert "Árbol construido: 2 nodos, 0 duplicados (no se expanden)" in out


def test_interactive_marks_a_dead_marking_and_lets_the_user_leave(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(DEADLOCK)
    feed_input(monkeypatch, "a", "b", "q")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Nodo actual: M2 (0, 0)" in out
    assert "Marcado muerto: ninguna transición habilitada\n" in out
    source = (tmp_path / "out_arbol.svg").read_text()
    assert "muerto" in source


def test_interactive_ends_when_the_initial_marking_is_dead(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text("pre\nt\np 1\npost\nt\np 0\nmarking\n0\n")
    feed_input(monkeypatch)

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    assert "ninguna transición habilitada desde el inicio" in capsys.readouterr().out


def test_render_tree_highlights_the_current_node_and_known_dead_nodes():
    tree = build_coverability_tree(PetriNet.from_text(DEADLOCK))

    source = render_coverability_tree(tree, current=1, dead=set()).source
    lines = {
        line.strip().split(" [")[0]: line for line in source.splitlines() if " [label=<" in line
    }

    assert "actual" in lines["M1"] and "#2e7d32" in lines["M1"]
    assert "actual" not in lines["M0"]
    assert "muerto" not in source  # dead nodes are only the ones the caller passes
