from pathlib import Path

import pytest

from graph_algorithms.cli.petri_cover import format_omegas, format_tree, main
from graph_algorithms.petri import PetriNet
from graph_algorithms.petri_cover import (
    OMEGA,
    TreeBuilder,
    TreeNode,
    accelerate,
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
)
from graph_algorithms.render import render_petri_net
from graph_algorithms.render_cover import render_coverability_graph, render_coverability_tree

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


def test_children_come_from_an_index_in_creation_order():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))

    assert [child.id for child in tree.children(1)] == [2, 3]
    assert tree.children(4) == []
    assert tree.path_to(4)[0].id == 0 and [n.id for n in tree.path_to(4)] == [0, 1, 2, 4]


def test_omega_appears_when_a_marking_covers_an_ancestor():
    tree = build_coverability_tree(PetriNet.from_text(UNBOUNDED))

    markings = {node.id: node.marking for node in tree.nodes}
    assert markings[1] == (1, OMEGA, 0)  # arrive from (1, 0, 0): queue grew
    assert markings[3] == (1, OMEGA, OMEGA)  # serve: done grew, queue stays omega
    assert [(a.ancestor, a.places) for a in tree.nodes[1].accelerations] == [(0, (1,))]
    # M3 covers both M1 and the root: the nearest ancestor, M1, is the one reported.
    assert [(a.ancestor, a.places) for a in tree.nodes[3].accelerations] == [(1, (2,))]


def test_omega_arithmetic_keeps_omega():
    net = PetriNet.from_text(UNBOUNDED)

    assert net.fire((1, OMEGA, 0), "serve") == (1, OMEGA, 1)
    assert net.is_enabled((1, OMEGA, 0), "serve")


def test_accelerate_scans_from_the_nearest_ancestor():
    root = TreeNode(0, (2, 0), None, None, None, ())
    middle = TreeNode(1, (1, 1), 0, "put", None, ())

    # (2, 2) covers (1, 1) in both places: the nearest ancestor makes both of them omega.
    marking, accelerations = accelerate((2, 2), [root, middle])

    assert marking == (OMEGA, OMEGA)
    assert [(a.ancestor, a.places) for a in accelerations] == [(1, (0, 1))]
    # An equal marking is not strictly greater: nothing changes.
    assert accelerate((2, 0), [root]) == ((2, 0), [])


def test_accelerate_repeats_until_nothing_changes():
    far = TreeNode(0, (1, 0), None, None, None, ())
    near = TreeNode(1, (0, 5), 0, "t", None, ())

    # (1, 3) does not cover (0, 5), but it covers (1, 0): place 1 becomes omega, and then
    # (1, ω) covers (0, 5) in place 0.
    marking, accelerations = accelerate((1, 3), [far, near])

    assert marking == (OMEGA, OMEGA)
    assert [(a.ancestor, a.places) for a in accelerations] == [(0, (1,)), (1, (0,))]


def test_tree_builder_remembers_the_children_it_creates():
    builder = TreeBuilder(PetriNet.from_text(BUFFER))
    root = builder.root

    assert builder.child(root, "put") is None
    child = builder.add_child(root, "put")

    assert builder.child(root, "put") is child
    assert child.marking == (1, 1) and child.parent == 0
    assert [node.id for node in builder.tree().nodes] == [0, 1]


def test_graph_merges_duplicates_into_arcs_to_the_original_node():
    tree = build_coverability_tree(PetriNet.from_text(BUFFER))

    graph = build_coverability_graph(tree)

    assert graph.markings == {0: (2, 0), 1: (1, 1), 2: (0, 2)}
    assert graph.edges == ((0, "put", 1), (1, "put", 2), (1, "get", 0), (2, "get", 1))
    assert graph.successors(1) == [2, 0]
    assert graph.successors(2) == [1]


def test_graph_knows_its_self_loops():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(UNBOUNDED)))

    assert graph.self_loops == {1, 3}


def test_components_of_the_coverability_graph():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(UNBOUNDED)))

    components = coverability_components(graph)

    # Each marking is its own component (the graph only moves "forward" through the omegas),
    # numbered from the initial marking to the terminal component.
    assert components == [[0], [1], [3]]
    assert [is_cyclic_component(graph, c) for c in components] == [False, True, True]
    assert terminal_components(graph, components) == [[3]]


def test_buffer_is_a_single_cyclic_component():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(BUFFER)))

    components = coverability_components(graph)

    assert len(components) == 1
    assert sorted(components[0]) == [0, 1, 2]
    assert is_cyclic_component(graph, components[0])


def test_dead_markings_and_terminal_components():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(DEADLOCK)))

    components = coverability_components(graph)

    assert dead_markings(graph) == [3]
    assert terminal_components(graph, components) == [[3]]


@pytest.mark.parametrize("example", sorted(EXAMPLES.glob("petri*.txt")), ids=lambda path: path.name)
def test_components_are_in_topological_order(example):
    net = PetriNet.from_text(example.read_text())
    graph = build_coverability_graph(build_coverability_tree(net))

    components = coverability_components(graph)

    index = {vertex: i for i, component in enumerate(components) for vertex in component}
    assert graph.initial in components[0]
    assert all(index[source] <= index[target] for source, _, target in graph.edges)
    assert sorted(index) == sorted(graph.markings)


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
        "    --arrive--> M2 (1, ω, 0)  duplicate of M1",
    ]
    assert format_omegas(tree) == [
        "M1 covers its ancestor M0 (1, 0, 0): queue -> ω",
        "M3 covers its ancestor M1 (1, ω, 0): done -> ω",
    ]


def test_render_tree_shows_omegas_duplicates_and_dead_nodes():
    tree = build_coverability_tree(PetriNet.from_text(DEADLOCK))
    source = render_coverability_tree(tree).source
    lines = {
        line.strip().split(" [")[0]: line for line in source.splitlines() if " [label=<" in line
    }

    assert "penwidth=3" in lines["M0"]  # root
    assert "= M0" in lines["M2"] and "dashed" in lines["M2"]  # duplicate of the root
    assert "dead" in lines["M3"] and "#e53935" in lines["M3"]
    edges = [line.strip() for line in source.splitlines() if "->" in line]
    assert edges[0].startswith("M0 -> M1 [label=a")

    omega_source = render_coverability_tree(
        build_coverability_tree(PetriNet.from_text(UNBOUNDED))
    ).source
    assert "(1, ω, 0)" in omega_source and "#ffe0b2" in omega_source


def test_render_tree_highlights_the_current_node_and_known_dead_nodes():
    tree = build_coverability_tree(PetriNet.from_text(DEADLOCK))

    source = render_coverability_tree(tree, current=1, dead=set()).source
    lines = {
        line.strip().split(" [")[0]: line for line in source.splitlines() if " [label=<" in line
    }

    assert "current" in lines["M1"] and "#2e7d32" in lines["M1"]
    assert "current" not in lines["M0"]
    assert "dead" not in source  # dead nodes are only the ones the caller passes


def test_render_graph_draws_cyclic_components_as_clusters_and_dashes_other_arcs():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(DEADLOCK)))
    components = coverability_components(graph)

    source = render_coverability_graph(graph, components).source

    # M0 has a self-loop (c) so it is a cluster; M1 and the dead M3 are single plain nodes.
    assert source.count("subgraph cluster_") == 1
    assert 'label="SCC 1"' in source
    edges = {
        line.strip().split(" [")[0] + " " + line.split("label=")[1].split()[0]: line
        for line in source.splitlines()
        if "->" in line
    }
    assert "dashed" in edges["M0 -> M1 a"]
    assert "dashed" in edges["M1 -> M3 b"]
    assert "dashed" not in edges["M0 -> M0 c"]


def test_render_graph_merges_parallel_arcs_into_one_labelled_arc():
    graph = build_coverability_graph(build_coverability_tree(PetriNet.from_text(UNBOUNDED)))
    components = coverability_components(graph)

    source = render_coverability_graph(graph, components).source

    # M3 has two self-loops, `arrive` and `serve`: one arc, labelled with both.
    loops = [line for line in source.splitlines() if "M3 -> M3" in line]
    assert len(loops) == 1
    assert 'label="arrive, serve"' in loops[0]


def test_cli_prints_the_analysis_and_writes_the_net_the_tree_and_the_graph(tmp_path, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(UNBOUNDED)

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Coverability tree: 6 nodes, 3 duplicates (not expanded)" in out
    assert "Omegas: 2" in out
    assert "queue: unbounded (ω)" in out
    assert "Net is bounded: no" in out
    assert "Unbounded places: queue, done" in out
    assert f"Petri net written to {tmp_path / 'out_net.svg'}" in out
    assert (tmp_path / "out_net.svg").read_text().startswith("<?xml")
    assert (tmp_path / "out_tree.svg").read_text().startswith("<?xml")
    assert (tmp_path / "out_graph.svg").read_text().startswith("<?xml")


def test_cli_reports_a_bounded_net(tmp_path, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Omegas: none" in out
    assert "free: 2-bounded" in out
    assert "Net is bounded: yes" in out
    assert "Net is safe (1-bounded): no" in out
    assert "Dead markings: none" in out


def test_cli_numbers_the_components_from_the_initial_marking(tmp_path, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(DEADLOCK)

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "SCC 1: M0 (1, 0)  [cyclic]" in out
    assert "SCC 2: M1 (0, 1)\n" in out
    assert "SCC 3: M3 (0, 0)  [terminal]" in out
    assert "Dead markings: M3" in out


@pytest.mark.parametrize("example", sorted(EXAMPLES.glob("petri*.txt")), ids=lambda path: path.name)
def test_examples_terminate_and_render(example, tmp_path):
    main([str(example), "-o", str(tmp_path / example.stem)])

    assert (tmp_path / f"{example.stem}_net.svg").exists()
    assert (tmp_path / f"{example.stem}_tree.svg").exists()
    assert (tmp_path / f"{example.stem}_graph.svg").exists()


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

    main([str(input_file), "--interactive", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Current node: M0 (1, 0, 0)" in out
    assert "Enabled transitions: arrive\n" in out  # serve needs a job in the queue
    assert "arrive: (1, 0, 0) -> (1, ω, 0)  [M1]" in out
    assert "New omega: M1 covers its ancestor M0 (1, 0, 0): queue -> ω" in out
    assert "Duplicate of M1: not expanded, back to M1" in out
    assert "serve: (1, ω, 0) -> (1, ω, ω)  [M3]" in out
    assert "New omega: M3 covers its ancestor M1 (1, ω, 0): done -> ω" in out
    assert "Path from the root: M0 -> M1 -> M3" in out
    assert "Tree built: 4 nodes, 1 duplicates (not expanded)" in out
    assert "Omegas: 2" in out
    assert f"  Net written to {tmp_path / 'out_net.svg'}" in out
    assert (tmp_path / "out_tree.svg").read_text().startswith("<?xml")
    assert "M = (1, ω, ω)" in (tmp_path / "out_net.svg").read_text()  # net at the last node
    assert not (tmp_path / "out_graph.svg").exists()


def test_interactive_reports_invalid_choices_and_goes_back(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)
    feed_input(monkeypatch, "get", "zzz", "", "put", "r", "r")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "get is not enabled" in out
    assert "unknown transition 'zzz'" in out
    assert "Current node: M1 (1, 1)" in out
    assert out.index("Current node: M1 (1, 1)") < out.index("Already at the root")
    assert "Tree built: 2 nodes, 0 duplicates (not expanded)" in out


def test_interactive_firing_a_transition_again_moves_to_the_existing_child(
    tmp_path, monkeypatch, capsys
):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)
    feed_input(monkeypatch, "put", "r", "put", "r", "put", "q")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    # The same `put` from M0 is fired three times but only creates one child.
    assert out.count("put: (2, 0) -> (1, 1)  [M1]") == 3
    assert out.count("(already in the tree)") == 2
    assert "Tree built: 2 nodes, 0 duplicates (not expanded)" in out
    source = (tmp_path / "out_tree.svg").read_text()
    assert source.count("<title>M0&#45;&gt;M1</title>") == 1


def test_interactive_marks_a_dead_marking_and_lets_the_user_leave(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(DEADLOCK)
    feed_input(monkeypatch, "a", "b", "q")

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Current node: M2 (0, 0)" in out
    assert "Dead marking: no transition is enabled\n" in out
    assert "dead" in (tmp_path / "out_tree.svg").read_text()


def test_interactive_ends_when_the_initial_marking_is_dead(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text("pre\nt\np 1\npost\nt\np 0\nmarking\n0\n")
    feed_input(monkeypatch)

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    assert "no transition is enabled from the start" in capsys.readouterr().out


def test_interactive_redraws_the_net_at_the_current_marking(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(BUFFER)
    net_file = tmp_path / "out_net.svg"
    seen = []

    def fake_input(prompt: str) -> str:
        seen.append(net_file.read_text())  # the net as drawn when the prompt is shown
        return ("put", "r", "q")[len(seen) - 1]

    monkeypatch.setattr("builtins.input", fake_input)

    main([str(input_file), "-i", "-o", str(tmp_path / "out")])

    assert "M = (2, 0)" in seen[0] and "#fb8c00" not in seen[0]  # initial marking, nothing fired
    assert "M = (1, 1)" in seen[1] and "#fb8c00" in seen[1]  # after `put`, `put` highlighted
    assert "M = (2, 0)" in net_file.read_text()  # back at the root
    assert "Last net written to" in capsys.readouterr().out


def test_net_drawing_writes_omega_instead_of_infinity():
    net = PetriNet.from_text(UNBOUNDED)

    source = render_petri_net(net, (1, OMEGA, 0)).source

    assert "M = (1, ω, 0)" in source
    assert 'POINT-SIZE="18">ω</FONT>' in source  # the queue place holds ω
    assert "inf" not in source
