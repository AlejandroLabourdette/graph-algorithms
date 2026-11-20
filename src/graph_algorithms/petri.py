"""Place/transition Petri nets and the token game."""

import re
from dataclasses import dataclass

type Marking = tuple[int, ...]

SECTIONS = ("pre", "post", "marking")

_INTEGER = re.compile(r"-?\d+")


def _is_integer(token: str) -> bool:
    return _INTEGER.fullmatch(token) is not None


def _parse_count(token: str, line_number: int) -> int:
    if not _is_integer(token) or int(token) < 0:
        raise ValueError(f"line {line_number}: expected a non-negative integer, got {token!r}")
    return int(token)


def _check_unique(names: list[str], what: str) -> None:
    if len(set(names)) != len(names):
        raise ValueError(f"{what} names must be unique")


@dataclass(frozen=True)
class _Matrix:
    places: list[str] | None
    transitions: list[str] | None
    rows: list[list[int]]


def _parse_matrix(section: str, lines: list[tuple[int, list[str]]]) -> _Matrix:
    """Parse a places x transitions matrix with optional header and row labels.

    The first line is a header of transition names when none of its tokens is an
    integer. A row starts with a place name when its first token is not an
    integer; either every row is labelled or none is.
    """
    if not lines:
        raise ValueError(f"{section} section is empty")

    transitions: list[str] | None = None
    if not any(_is_integer(token) for token in lines[0][1]):
        transitions = lines.pop(0)[1]
        _check_unique(transitions, "transition")
        if not lines:
            raise ValueError(f"{section} section has no rows")

    labelled = [not _is_integer(row[0]) for _, row in lines]
    if any(labelled) and not all(labelled):
        line_number = lines[labelled.index(not labelled[0])][0]
        raise ValueError(f"line {line_number}: either every {section} row has a place name or none")
    places: list[str] | None = None
    if all(labelled):
        places = [row[0] for _, row in lines]
        _check_unique(places, "place")
        lines = [(line_number, row[1:]) for line_number, row in lines]

    width = len(transitions) if transitions is not None else len(lines[0][1])
    rows: list[list[int]] = []
    for line_number, row in lines:
        if len(row) != width:
            raise ValueError(f"line {line_number}: expected {width} values, got {len(row)}")
        rows.append([_parse_count(token, line_number) for token in row])
    return _Matrix(places, transitions, rows)


def _merge_names(
    pre: list[str] | None, post: list[str] | None, size: int, prefix: str, what: str
) -> tuple[str, ...]:
    if pre is not None and post is not None and pre != post:
        raise ValueError(f"pre and post name different {what}: {pre} != {post}")
    names = pre or post
    return tuple(names) if names is not None else tuple(f"{prefix}{i}" for i in range(1, size + 1))


@dataclass(frozen=True)
class PetriNet:
    """Place/transition net given by its Pre and Post matrices and an initial marking.

    `pre[p][t]` is the number of tokens transition `t` consumes from place `p`
    and `post[p][t]` the number it produces into it. Places and transitions are
    referred to by name; markings are tuples indexed like `places`.
    """

    places: tuple[str, ...]
    transitions: tuple[str, ...]
    pre: tuple[tuple[int, ...], ...]
    post: tuple[tuple[int, ...], ...]
    initial_marking: Marking

    def __post_init__(self) -> None:
        _check_unique(list(self.places), "place")
        _check_unique(list(self.transitions), "transition")
        places, transitions = len(self.places), len(self.transitions)
        for name, matrix in (("pre", self.pre), ("post", self.post)):
            if len(matrix) != places or any(len(row) != transitions for row in matrix):
                raise ValueError(f"{name} must be a {places}x{transitions} matrix")
            if any(value < 0 for row in matrix for value in row):
                raise ValueError(f"{name} values must be non-negative")
        self._check_marking(self.initial_marking)

    def _check_marking(self, marking: Marking) -> None:
        if len(marking) != len(self.places):
            raise ValueError(
                f"marking has {len(marking)} values but the net has {len(self.places)} places"
            )
        if any(tokens < 0 for tokens in marking):
            raise ValueError("marking values must be non-negative")

    def _transition_index(self, transition: str) -> int:
        try:
            return self.transitions.index(transition)
        except ValueError:
            raise ValueError(f"unknown transition {transition!r}") from None

    def is_enabled(self, marking: Marking, transition: str) -> bool:
        """A transition is enabled when every place holds the tokens it consumes."""
        t = self._transition_index(transition)
        return all(tokens >= row[t] for tokens, row in zip(marking, self.pre, strict=True))

    def enabled_transitions(self, marking: Marking) -> list[str]:
        self._check_marking(marking)
        return [t for t in self.transitions if self.is_enabled(marking, t)]

    def fire(self, marking: Marking, transition: str) -> Marking:
        """Return the marking reached by firing `transition`: `M - Pre[:, t] + Post[:, t]`."""
        self._check_marking(marking)
        if not self.is_enabled(marking, transition):
            raise ValueError(f"transition {transition!r} is not enabled")
        t = self._transition_index(transition)
        return tuple(
            tokens - pre[t] + post[t]
            for tokens, pre, post in zip(marking, self.pre, self.post, strict=True)
        )

    @classmethod
    def from_text(cls, text: str) -> PetriNet:
        """Parse a net from `pre`, `post` and `marking` sections.

        Each section starts with its keyword alone on a line. `pre` and `post` are
        matrices of non-negative integers with a row per place and a column per
        transition, each with an optional header line of transition names and
        optional place names at the start of every row. Names default to `p1..pn`
        and `t1..tm`. `marking` is a single line with the initial tokens of every
        place. Blank lines and anything after `#` are ignored.
        """
        sections: dict[str, list[tuple[int, list[str]]]] = {}
        current: list[tuple[int, list[str]]] | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            tokens = line.split("#", 1)[0].split()
            if not tokens:
                continue
            if len(tokens) == 1 and tokens[0].lower() in SECTIONS:
                section = tokens[0].lower()
                if section in sections:
                    raise ValueError(f"line {line_number}: duplicate {section} section")
                current = sections[section] = []
            elif current is None:
                raise ValueError(f"line {line_number}: expected a section ({', '.join(SECTIONS)})")
            else:
                current.append((line_number, tokens))

        missing = [section for section in SECTIONS if section not in sections]
        if missing:
            raise ValueError(f"missing section: {', '.join(missing)}")

        pre = _parse_matrix("pre", sections["pre"])
        post = _parse_matrix("post", sections["post"])
        if len(pre.rows) != len(post.rows) or len(pre.rows[0]) != len(post.rows[0]):
            raise ValueError(
                f"pre is {len(pre.rows)}x{len(pre.rows[0])} "
                f"but post is {len(post.rows)}x{len(post.rows[0])}"
            )

        marking_lines = sections["marking"]
        if len(marking_lines) != 1:
            raise ValueError("marking section must be a single line")
        line_number, tokens = marking_lines[0]
        if len(tokens) != len(pre.rows):
            raise ValueError(
                f"line {line_number}: expected {len(pre.rows)} values, got {len(tokens)}"
            )
        marking = tuple(_parse_count(token, line_number) for token in tokens)

        return cls(
            places=_merge_names(pre.places, post.places, len(pre.rows), "p", "places"),
            transitions=_merge_names(
                pre.transitions, post.transitions, len(pre.rows[0]), "t", "transitions"
            ),
            pre=tuple(map(tuple, pre.rows)),
            post=tuple(map(tuple, post.rows)),
            initial_marking=marking,
        )
