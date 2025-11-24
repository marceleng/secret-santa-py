from collections import defaultdict, deque
from dataclasses import dataclass, field
from random import shuffle
from sys import maxsize
from typing import Hashable, List, Tuple, Union

Node = Hashable
Graph = defaultdict[Node, dict[Node, int]]


@dataclass
class FlowEdge:
    src: Node
    dst: Node
    capacity: int


@dataclass
class _ResidualFlow:
    rate: int = field(default=maxsize)
    edges: List[Tuple[Node, Node]] = field(default_factory=list)

    def add_edge(self, edge: FlowEdge):
        self.rate = min(self.rate, edge.capacity)
        self.edges.append((edge.src, edge.dst))


@dataclass
class Flow:
    value: int
    graph: Graph


@dataclass
class FlowGraph:
    edges: List[FlowEdge]
    source: Node
    sink: Node
    internal_graph: Graph = field(
        init=False,
        default_factory=lambda: defaultdict(dict))

    def __post_init__(self):
        for edge in self.edges:
            self.internal_graph[edge.src][edge.dst] = edge.capacity
            self.internal_graph[edge.dst][edge.src] = 0

    def compute_largest_flow(self) -> Flow:
        flow: Graph = defaultdict(dict)
        value = 0
        for edge in self.edges:
            flow[edge.src][edge.dst] = 0
        while residual_flow := self._find_residual_flow():
            self._apply_residual_flow(residual_flow, flow)
            value += residual_flow.rate

        # CleanUp empty edges
        for src in flow.keys():
            flow[src] = {dst: rate for dst, rate in flow[src].items() if rate > 0}
        return Flow(value, flow)

    def _find_residual_flow(self) -> Union[_ResidualFlow, None]:
        to_visit: deque[Node] = deque()
        prev_node: dict[Node, Node] = dict()

        to_visit.append(self.source)
        prev_node[self.source] = None

        while to_visit:
            cur_node = to_visit.popleft()
            if cur_node is self.sink:
                return self._reconstruct_flow_from_prev_dict(prev_node)
            else:
                next_nodes = [node for node in self.internal_graph[cur_node].keys()
                                if node not in prev_node and self.internal_graph[cur_node][node] > 0]

                shuffle(next_nodes)
                for node in next_nodes:
                    prev_node[node] = cur_node
                    to_visit.append(node)

        return None

    def _reconstruct_flow_from_prev_dict(self, prev_node_mapping: dict[Node, Node]) -> _ResidualFlow:
        flow = _ResidualFlow()
        dst = self.sink
        while dst is not self.source:
            src = prev_node_mapping[dst]
            flow.add_edge(FlowEdge(
                src=src,
                dst=dst,
                capacity=self.internal_graph[src][dst]
            ))
            dst = src
        return flow

    def _apply_residual_flow(
            self,
            residual_flow: _ResidualFlow,
            flow: Union[Graph, None] = None
    ) -> Union[Graph, None]:
        for (src, dst) in residual_flow.edges:
            self.internal_graph[src][dst] -= residual_flow.rate
            self.internal_graph[dst][src] += residual_flow.rate

            if flow:
                if dst in flow[src]:
                    flow[src][dst] += residual_flow.rate
                elif src in flow[dst]:
                    flow[dst][src] -= residual_flow.rate
                else:
                    raise ValueError("Residual flow has unknown edge")
