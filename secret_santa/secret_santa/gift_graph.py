from collections import defaultdict
from enum import Enum
import itertools
from dataclasses import dataclass, field, InitVar
from itertools import product
from typing import Tuple
from random import randbytes, shuffle
from .player import Player
from .incompatibility import Incompatibility
from secret_santa.flow_graph.flow_graph import Flow, FlowGraph, FlowEdge

_Edge = Tuple[Player, Player]


def forbidden_pairs(incompatibilities: set[Incompatibility]) -> set[_Edge]:
    """All the (gifter, giftee) pairs ruled out, whether one-way or reciprocal."""
    return {pair for inc in incompatibilities for pair in inc.forbidden_pairs()}


class GiftAssignmentError(Exception):
    """Raised when a valid gift assignment cannot be found."""
    pass


class _PlayerDirection(Enum):
    GIFTER = 0
    GIFTEE = 1


@dataclass(order=False, frozen=True)
class _DirectedPlayer:
    player: Player
    direction: _PlayerDirection
    # Random field to ensure random order on graph BFS
    _randomizer: bytes = field(init=False,
                               default_factory=lambda: randbytes(4))


@dataclass(order=False)
class NGiftGraph:
    players: set[Player]
    incompatibilities: set[Incompatibility]
    number_of_gifts: int = field(default=1)
    allow_2cycles: bool = field(default=True)
    # Attempts are cheap (well under a millisecond for a family-sized group), and with
    # allow_2cycles=False a single attempt can succeed only a few percent of the time.
    max_attempts: int = field(default=1000)
    assignments: defaultdict[Player, set[Player]] = field(init=False)
    flow_graph: FlowGraph = field(init=False)

    def __post_init__(self):
        expected_gifts = len(self.players) * self.number_of_gifts
        is_correct_flow = False
        attempts = 0
        while not is_correct_flow and attempts < self.max_attempts:
            attempts += 1
            self.assignments = defaultdict(set)
            flow_graph = self._build_flow_graph()
            flow = flow_graph.compute_largest_flow()
            # The max flow value does not depend on the random exploration order,
            # so a short flow means no assignment exists: retrying is pointless.
            if flow.value < expected_gifts:
                raise GiftAssignmentError(
                    f"No valid assignment exists: only {flow.value} of the {expected_gifts} "
                    f"required gifts can be assigned. Check the number of gifts and the incompatibilities.")
            is_correct_flow = self._extract_assignments_from_flow(flow)
        
        if not is_correct_flow:
            raise GiftAssignmentError(f"Could not find a valid solution after {self.max_attempts} attempts")

    def _extract_assignments_from_flow(self, flow: Flow) -> bool:
        for src in flow.graph:
            if src == "src":
                continue
            for dst in flow.graph[src]:
                if dst == "sink":
                    continue
                
                self.assignments[src.player].add(dst.player)
                if not self.allow_2cycles and src.player in self.assignments[dst.player]:
                    return False
        return True
    def _build_flow_graph(self) -> FlowGraph:
        graph_source = "src"
        graph_sink = "sink"
        flow_edges: list[FlowEdge] = []

        gifters = list(map(lambda p: _DirectedPlayer(p, _PlayerDirection.GIFTER), self.players))
        giftees = list(map(lambda p: _DirectedPlayer(p, _PlayerDirection.GIFTEE), self.players))

        # Edges source -> gifter
        flow_edges.extend(map(
            lambda gifter: FlowEdge(graph_source, gifter, self.number_of_gifts),
            gifters))

        # Edges giftee -> sink
        flow_edges.extend(map(
            lambda giftee: FlowEdge(giftee, graph_sink, self.number_of_gifts),
            giftees))

        # Edges gifter -> giftee
        forbidden = forbidden_pairs(self.incompatibilities)
        for (src, dst) in product(gifters, giftees):
            if src.player != dst.player and (src.player, dst.player) not in forbidden:
                flow_edges.append(
                    FlowEdge(src, dst, 1)
                )
        return FlowGraph(flow_edges, graph_source, graph_sink)

    def verify_assignments(self):
        """Check that the assignments satisfy every rule; raise GiftAssignmentError otherwise."""
        gifts_received: defaultdict[Player, int] = defaultdict(int)
        forbidden = forbidden_pairs(self.incompatibilities)
        for src in self.players:
            dsts = self.assignments.get(src, set())
            if len(dsts) != self.number_of_gifts:
                raise GiftAssignmentError(
                    f"{src.name} gives {len(dsts)} gifts instead of {self.number_of_gifts}")
            for dst in dsts:
                if dst == src:
                    raise GiftAssignmentError(f"{src.name} is assigned to themselves")
                if (src, dst) in forbidden:
                    raise GiftAssignmentError(f"{src.name} is assigned to incompatible {dst.name}")
                if not self.allow_2cycles and src in self.assignments.get(dst, set()):
                    raise GiftAssignmentError(f"{src.name} and {dst.name} are assigned to each other")
                gifts_received[dst] += 1

        for player in self.players:
            if gifts_received[player] != self.number_of_gifts:
                raise GiftAssignmentError(
                    f"{player.name} receives {gifts_received[player]} gifts instead of {self.number_of_gifts}")


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

    def _is_invalid_edge(self, edge: _Edge) -> bool:
        (fst, snd) = edge
        return fst == snd or edge in forbidden_pairs(self.incompatibilities)

    def _build_initial_graph(self) -> list[_Edge]:
        ret = list(itertools.filterfalse(self._is_invalid_edge, product(self.players, self.players)))
        shuffle(ret)  # randomize graph
        return ret

    def _build_assignments(self, initial_graph: list[_Edge]):
        assigned_dst: set[Player] = set()
        for (src, dst) in initial_graph:
            if src not in self.assignments and dst not in assigned_dst:
                self.assignments[src] = dst
                assigned_dst.add(dst)
            if len(assigned_dst) == len(self.players):
                break

    def print_assignment(self, player):
        print("{} is gifting {}".format(player.name, self.assignments[player].name))

    def print_all_assignments(self):
        for player in self.players:
            self.print_assignment(player)


'''
@dataclass
class NGiftGraph:
    giftNumber: int
    players: set[Player]
    incompatibilities: set[Incompatibility]
    subgraph: GiftGraph = field(init=False)
    nPlayers: dict[Player, set[Player]] = field(default_factory=dict)
    assignments: defaultdict[Player, set[Player]] = field(default_factory= lambda : defaultdict(set))

    def __post_init__(self):
        subgraphPlayers: set[Player] = set()
        subgraphIncompatibilites: set[Incompatibility] = set()

        #First we demultiply each player in n twins
        for player in self.players:
            self.nPlayers[player] = set([
                Player(name = '{} {}'.format(player.name,i), email= player.email)
                for i in range(self.giftNumber)
            ])
            subgraphPlayers.update(self.nPlayers[player])

            #Prevent assignment between twins
            subgraphIncompatibilites.update(itertools.combinations(self.nPlayers[player], 2))

        # Now we must apply all incompatibilites to all twins
        for incompatibility in self.incompatibilities:
            subgraphIncompatibilites.update(
                itertools.product(
                    self.nPlayers[incompatibility.fst],
                    self.nPlayers[incompatibility.snd]
                )
            )

        #print(subgraphPlayers)
        #print(subgraphIncompatibilites)
        self.subgraph = GiftGraph(players=subgraphPlayers, incompatibilities=subgraphIncompatibilites)
        self.subgraph.print_all_assignments()
        self._demultiplex_assignments()

    def _retrieve_original_player(self, subgraphPlayer: Player) -> Player:
        if not subgraphPlayer in self.subgraph.players:
            raise ValueError('Player is not a valid subgraph player')
        name = subgraphPlayer.name[:subgraphPlayer.name.rfind(' ')]
        ret = Player(name, email=subgraphPlayer.email)
        if not ret in self.players:
            raise RuntimeError("Player name is not in the mutiplexed player format - this should not happen")
        return ret

    def _demultiplex_assignments(self):
        for src, dst in self.subgraph.assignments.items():
            self.assignments[self._retrieve_original_player(src)] \
                .add(self._retrieve_original_player(dst))

    def verify_assignments(self):
        giftsPerAssignee: defaultdict[Player, int] = defaultdict(int)
        for src, assignment_arr in self.assignments.items():
            print("Verifying assignments for {}: {}".format(src.name, assignment_arr))
            assert(len(assignment_arr) is self.giftNumber) # Has right number of assignees
            for dst in assignment_arr:
                print("Verifying specific assignment: {} -> {}".format(src.name, dst.name))
                assert(src is not dst) # Is not self-assigned
                assert(Incompatibility(src, dst) not in self.incompatibilities) # Is not incompatible
                giftsPerAssignee[dst] += 1

        assert(len(giftsPerAssignee) == len(self.players)) #Everyone has gifts
        assert(set(giftsPerAssignee.values()) == {self.giftNumber}) #Everyone has the right number of gifts
'''
