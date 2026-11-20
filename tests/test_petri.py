import pytest

from graph_algorithms.petri import PetriNet

PRODUCER_CONSUMER = """
# comment line
pre
       t1 t2 t3
p1     1  0  0
p2     0  1  0   # trailing comment
p3     0  0  1

post
       t1 t2 t3
p1     0  0  1
p2     1  0  0
p3     0  1  0

marking
1 0 0
"""

# Both transitions move tokens from p1 to p2 with weights: t1 takes 2 and gives 1,
# t2 takes 1 and gives 2, so they compete for the tokens of p1.
WEIGHTED = """
marking
3 0
post
0 0
1 2
pre
2 1
0 0
"""


def test_from_text_with_names_and_comments():
    net = PetriNet.from_text(PRODUCER_CONSUMER)

    assert net.places == ("p1", "p2", "p3")
    assert net.transitions == ("t1", "t2", "t3")
    assert net.pre == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert net.post == ((0, 0, 1), (1, 0, 0), (0, 1, 0))
    assert net.initial_marking == (1, 0, 0)


def test_from_text_without_names_and_any_section_order():
    net = PetriNet.from_text(WEIGHTED)

    assert net.places == ("p1", "p2")
    assert net.transitions == ("t1", "t2")
    assert net.pre == ((2, 1), (0, 0))
    assert net.post == ((0, 0), (1, 2))
    assert net.initial_marking == (3, 0)


def test_names_can_be_given_in_only_one_matrix():
    net = PetriNet.from_text(
        """
        pre
            go
        a   1
        b   0
        post
        0
        1
        marking
        1 0
        """
    )

    assert net.places == ("a", "b")
    assert net.transitions == ("go",)


@pytest.mark.parametrize(
    ("text", "error"),
    [
        pytest.param("pre\n1\npost\n1\n", "missing section: marking", id="missing-section"),
        pytest.param("1 0\npre\n1\n", "line 1: expected a section", id="data-before-section"),
        pytest.param(
            "pre\n1\npre\n1\npost\n1\nmarking\n1\n", "line 3: duplicate pre", id="duplicate"
        ),
        pytest.param("pre\npost\n1\nmarking\n1\n", "pre section is empty", id="empty-matrix"),
        pytest.param(
            "pre\n1 0\n1\npost\n1 0\n1 0\nmarking\n1 0\n",
            "line 3: expected 2 values, got 1",
            id="short-row",
        ),
        pytest.param(
            "pre\n1 0\npost\n1\nmarking\n1\n", "pre is 1x2 but post is 1x1", id="shape-mismatch"
        ),
        pytest.param(
            "pre\n-1\npost\n1\nmarking\n1\n",
            "line 2: expected a non-negative integer, got '-1'",
            id="negative-weight",
        ),
        pytest.param(
            "pre\n1\npost\n1\nmarking\n1.5\n",
            "line 6: expected a non-negative integer, got '1.5'",
            id="non-integer-marking",
        ),
        pytest.param(
            "pre\n1\npost\n1\nmarking\n1 0\n", "line 6: expected 1 values, got 2", id="marking-size"
        ),
        pytest.param(
            "pre\n1\npost\n1\nmarking\n1\n0\n",
            "marking section must be a single line",
            id="marking-lines",
        ),
        pytest.param(
            "pre\na 1\n0\npost\n1\n1\nmarking\n1 1\n",
            "line 3: either every pre row has a place name or none",
            id="partial-row-names",
        ),
        pytest.param(
            "pre\nx x\n1 0\npost\n1 0\nmarking\n1\n",
            "transition names must be unique",
            id="duplicate-names",
        ),
        pytest.param(
            "pre\nx\n1\npost\ny\n1\nmarking\n1\n",
            "pre and post name different transitions",
            id="mismatched-names",
        ),
    ],
)
def test_from_text_rejects_malformed_input(text, error):
    with pytest.raises(ValueError, match=error):
        PetriNet.from_text(text)


def test_constructor_validates_shapes():
    with pytest.raises(ValueError, match="post must be a 1x1 matrix"):
        PetriNet(("p",), ("t",), ((1,),), ((1, 0),), (0,))


def test_enabled_transitions_respect_weights():
    net = PetriNet.from_text(WEIGHTED)

    assert net.enabled_transitions((3, 0)) == ["t1", "t2"]
    assert net.enabled_transitions((1, 0)) == ["t2"]
    assert net.enabled_transitions((0, 5)) == []


def test_fire_consumes_pre_and_produces_post():
    net = PetriNet.from_text(WEIGHTED)

    assert net.fire((3, 0), "t1") == (1, 1)
    assert net.fire((3, 0), "t2") == (2, 2)


@pytest.mark.parametrize(
    ("transition", "error"),
    [
        pytest.param("t1", "transition 't1' is not enabled", id="not-enabled"),
        pytest.param("t9", "unknown transition 't9'", id="unknown"),
    ],
)
def test_fire_rejects_invalid_transitions(transition, error):
    net = PetriNet.from_text(WEIGHTED)

    with pytest.raises(ValueError, match=error):
        net.fire((1, 0), transition)


def test_firing_sequence_cycles_back_to_initial_marking():
    net = PetriNet.from_text(PRODUCER_CONSUMER)
    marking = net.initial_marking
    enabled_per_step = []
    for transition in ["t1", "t2", "t3"]:
        enabled_per_step.append(net.enabled_transitions(marking))
        marking = net.fire(marking, transition)

    assert enabled_per_step == [["t1"], ["t2"], ["t3"]]
    assert marking == net.initial_marking


def test_firing_sequence_reaches_deadlock():
    net = PetriNet.from_text(WEIGHTED)
    marking = net.initial_marking
    for transition in ["t1", "t2"]:
        marking = net.fire(marking, transition)

    assert marking == (0, 3)
    assert net.enabled_transitions(marking) == []
