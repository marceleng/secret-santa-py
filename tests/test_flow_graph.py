import unittest
from secret_santa.flow_graph import FlowEdge, FlowGraph

class FlowGrahTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_correct_flow_value(self):
        #        3     3
        # 2┌──►A───►B────┐
        #  │        ▲    │
        #  │        │    ▼
        # src       │   dst◄┐
        #  │        │    ▲  │
        #  │        │   1│  │3
        #  └──►C───►D────┘  │
        # 3      4  │       │
        #           └──────►E
        #           2
        edges = [
            FlowEdge("src", "A", 2),
            FlowEdge("src", "C", 3),
            FlowEdge("A", "B", 3),
            FlowEdge("C", "D", 4),
            FlowEdge("B", "dst", 3),
            FlowEdge("D", "B", 1),
            FlowEdge("D", "dst", 1),
            FlowEdge("D", "E", 2),
            FlowEdge("E", "dst", 3),
        ]

        graph = FlowGraph(edges, "src", "dst")
        flow = graph.compute_largest_flow()
        self.assertEqual(flow.value, 5, 'incorrect flow value')

    def test_no_path_returns_zero(self):
        edges = [
            FlowEdge("src", "A", 1),
            FlowEdge("A", "B", 1),
            FlowEdge("C", "B", 1),
            FlowEdge("C", "dst", 1)
        ]

        graph = FlowGraph(edges, "src", "dst")
        flow = graph.compute_largest_flow()
        self.assertDictEqual(flow.graph, {"src": {}, "A" : {}, "C": {}}, 'Flow di')
        self.assertEqual(flow.value, 0, 'Flow value is not zero when no path')
