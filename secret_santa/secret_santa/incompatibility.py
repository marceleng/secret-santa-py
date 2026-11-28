from dataclasses import InitVar, dataclass, field
from .player import Player


@dataclass(order=False)
class Incompatibility:
    fst: Player = field(init=False)
    snd: Player = field(init=False)
    fst_init: InitVar[Player]
    snd_init: InitVar[Player]
    # True: only fst gifting snd is forbidden; snd may still gift fst.
    one_way: bool = False

    def __post_init__(self, fst_init, snd_init):
        if fst_init == snd_init:
            raise RuntimeError("Should not have same players")
        # A reciprocal pair is stored in a canonical order, so that (a, b) == (b, a).
        if self.one_way or hash(fst_init) < hash(snd_init):
            self.fst = fst_init
            self.snd = snd_init
        else:
            self.fst = snd_init
            self.snd = fst_init

    def __hash__(self):
        return hash((self.fst, self.snd, self.one_way))

    def forbidden_pairs(self) -> set[tuple[Player, Player]]:
        """The (gifter, giftee) pairs this incompatibility rules out."""
        if self.one_way:
            return {(self.fst, self.snd)}
        return {(self.fst, self.snd), (self.snd, self.fst)}
