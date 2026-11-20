from pathlib import Path

import pytest

from graph_algorithms.cli.petri import main
from graph_algorithms.petri import PetriNet
from graph_algorithms.render import render_petri_net

EXAMPLES = Path(__file__).parent.parent / "examples"

NET = """
pre
       a  b
p      2  1
q      0  0
post
       a  b
p      0  0
q      3  0
marking
3 0
"""


def feed_input(monkeypatch, *answers: str) -> None:
    remaining = iter(answers)

    def fake_input(prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


def test_render_petri_net_draws_places_transitions_and_weights():
    net = PetriNet.from_text(NET)

    source = render_petri_net(net, (1, 0), last_fired="a").source

    assert 'place_p [label=<p<BR/><FONT POINT-SIZE="18">●</FONT>>' in source
    assert 'place_q [label=<q<BR/><FONT POINT-SIZE="18"> </FONT>>' in source
    edges = [line.strip() for line in source.splitlines() if "->" in line]
    assert edges == [
        "place_p -> transition_a [label=2]",
        'place_p -> transition_b [label=""]',
        "transition_a -> place_q [label=3]",
    ]
    transition_lines = {
        line.strip().split(" [")[0]: line for line in source.splitlines() if "shape=box" in line
    }
    assert "#eeeeee" in transition_lines["transition_a"]  # disabled
    assert "penwidth=3" in transition_lines["transition_a"]  # last fired
    assert "#a5d6a7" in transition_lines["transition_b"]  # enabled


def test_render_petri_net_writes_large_counts_as_numbers():
    net = PetriNet.from_text(NET)

    assert '<FONT POINT-SIZE="18">12</FONT>' in render_petri_net(net, (12, 0)).source


def test_cli_fires_chosen_transitions_until_deadlock(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "net.txt"
    input_file.write_text(NET)
    feed_input(monkeypatch, "zzz", "a", "a", "b")

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Enabled transitions: a, b" in out
    assert "unknown transition 'zzz'" in out
    assert "a is not enabled" in out
    assert "Marking: p=0 q=3" in out
    assert "Deadlock: no transition is enabled" in out
    assert "Firing sequence: a b" in out
    assert (tmp_path / "out.svg").read_text().startswith("<?xml")


@pytest.mark.parametrize("answer", ["q", None], ids=["quit", "eof"])
def test_cli_stops_when_user_quits(tmp_path, monkeypatch, capsys, answer):
    input_file = tmp_path / "net.txt"
    input_file.write_text(NET)
    feed_input(monkeypatch, *([answer] if answer else []))

    main([str(input_file), "-o", str(tmp_path / "out")])

    out = capsys.readouterr().out
    assert "Step 1" not in out
    assert "Firing sequence: (empty)" in out


@pytest.mark.parametrize("example", sorted(EXAMPLES.glob("petri*.txt")), ids=lambda path: path.name)
def test_examples_render(example, tmp_path, monkeypatch):
    feed_input(monkeypatch)

    main([str(example), "-o", str(tmp_path / example.stem)])

    assert (tmp_path / f"{example.stem}.svg").exists()
