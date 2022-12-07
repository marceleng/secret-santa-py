import itertools
from dataclasses import dataclass, field, InitVar
from itertools import product
from typing import Tuple
from random import shuffle


@dataclass(order=False, frozen=True)
class Player:
    name: str
    email: str


Edge = Tuple[Player, Player]


@dataclass(order=False)
class Incompatibility:
    fst: Player = field(init=False)
    snd: Player = field(init=False)
    fst_init: InitVar[Player]
    snd_init: InitVar[Player]

    def __post_init__(self, fst_init, snd_init):
        if fst_init == snd_init:
            raise RuntimeError("Should not have same players")
        if hash(fst_init) < hash(snd_init):
            self.fst = fst_init
            self.snd = snd_init
        else:
            self.fst = snd_init
            self.snd = fst_init

    def __hash__(self):
        return hash((self.fst, self.snd))


@dataclass(order=False)
class GiftGraph:
    players: set[Player]
    incompatibilities: set[Incompatibility]
    assignments: dict[Player, Player] = field(default_factory=dict)

    def __post_init__(self):
        while len(self.assignments) != len(self.players):
            self.assignments = dict()
            initial_graph = self._build_initial_graph()
            self._build_assignments(initial_graph)

    def _is_invalid_edge(self, edge: Edge) -> bool:
        (fst, snd) = edge
        return fst == snd or Incompatibility(fst, snd) in self.incompatibilities

    def _build_initial_graph(self) -> list[Edge]:
        ret = list(itertools.filterfalse(self._is_invalid_edge, product(self.players, self.players)))
        shuffle(ret)  # randomize graph
        return ret

    def _build_assignments(self, initial_graph: list[Edge]):
        assigned_dst: set[Player] = set()
        for (src, dst) in initial_graph:
            if src not in self.assignments and dst not in assigned_dst:
                self.assignments[src] = dst
                assigned_dst.add(dst)
            if len(assigned_dst) == len(self.players):
                break
