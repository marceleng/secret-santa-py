from dataclasses import dataclass


@dataclass(order=False, frozen=True)
class Player:
    name: str
    email: str
