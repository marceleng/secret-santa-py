from dataclasses import InitVar, dataclass, field
from .player import Player


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