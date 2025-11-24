import unittest
from unittest.mock import patch, MagicMock
from secret_santa.secret_santa.gift_graph import NGiftGraph, GiftAssignmentError
from secret_santa.secret_santa.player import Player
from secret_santa.secret_santa.incompatibility import Incompatibility

class TestNGiftGraph(unittest.TestCase):

    def test_basic_assignment(self):
        """
        Scenario: 3 Players (A, B, C), 1 gift each.
        Verification:
        - Each player gives exactly 1 gift.
        - Each player receives exactly 1 gift.
        - No self-assignments.
        """
        p1 = Player("A", "a@example.com")
        p2 = Player("B", "b@example.com")
        p3 = Player("C", "c@example.com")
        players = {p1, p2, p3}
        incompatibilities = set()

        graph = NGiftGraph(players, incompatibilities, number_of_gifts=1)
        
        # Verify assignments
        graph.verify_assignments()
        
        # Additional manual checks
        for src, assignments in graph.assignments.items():
            self.assertEqual(len(assignments), 1)
            for dst in assignments:
                self.assertNotEqual(src, dst)
        
        # Check all players are gifters and giftees
        all_gifters = set(graph.assignments.keys())
        all_giftees = set()
        for assignments in graph.assignments.values():
            all_giftees.update(assignments)
            
        self.assertEqual(all_gifters, players)
        self.assertEqual(all_giftees, players)

    def test_incompatibility(self):
        """
        Scenario: 4 Players (A, B, C, D), 1 gift each. Incompatibility: A <-> B.
        Verification:
        - Assignments are valid.
        - A does NOT gift B.
        - B does NOT gift A.
        """
        p1 = Player("A", "a@example.com")
        p2 = Player("B", "b@example.com")
        p3 = Player("C", "c@example.com")
        p4 = Player("D", "d@example.com")
        players = {p1, p2, p3, p4}
        # A cannot gift B (and vice versa)
        incompatibilities = {Incompatibility(p1, p2)}

        graph = NGiftGraph(players, incompatibilities, number_of_gifts=1)
        
        graph.verify_assignments()
        
        # Check specific incompatibility
        if p1 in graph.assignments:
            self.assertNotIn(p2, graph.assignments[p1])
        if p2 in graph.assignments:
            self.assertNotIn(p1, graph.assignments[p2])

    def test_player_counts_multiple_gifts(self):
        """
        Scenario: 4 Players, 2 gifts each.
        Verification:
        - Each player gives exactly 2 gifts.
        - Each player receives exactly 2 gifts.
        - No self-assignments.
        """
        pa = Player("A", "a@example.com")
        pb = Player("B", "b@example.com")
        pc = Player("C", "c@example.com")
        pd = Player("D", "d@example.com")
        players = {pa, pb, pc, pd}
        incompatibilities = set()

        graph = NGiftGraph(players, incompatibilities, number_of_gifts=2)
        
        graph.verify_assignments()
        
        for src, assignments in graph.assignments.items():
            self.assertEqual(len(assignments), 2)
            
        # Check reception counts
        reception_counts = {p: 0 for p in players}
        for assignments in graph.assignments.values():
            for dst in assignments:
                reception_counts[dst] += 1
                
        for p, count in reception_counts.items():
            self.assertEqual(count, 2, f"Player {p.name} should receive 2 gifts")

    def test_complex_incompatibilities(self):
        """
        Scenario: 5 Players with multiple incompatibilities.
        Verification:
        - All incompatibilities are respected.
        - All counts are correct.
        """
        pa = Player("A", "a@example.com")
        pb = Player("B", "b@example.com")
        pc = Player("C", "c@example.com")
        pd = Player("D", "d@example.com")
        pe = Player("E", "e@example.com")
        players = {pa, pb, pc, pd, pe}
        
        # A cannot gift B
        # B cannot gift C
        # C cannot gift D
        incompatibilities = {
            Incompatibility(pa, pb),
            Incompatibility(pb, pc),
            Incompatibility(pc, pd)
        }

        graph = NGiftGraph(players, incompatibilities, number_of_gifts=1)
        
        graph.verify_assignments()
        
        # Verify incompatibilities
        if pa in graph.assignments:
            self.assertNotIn(pb, graph.assignments[pa])
        if pb in graph.assignments:
            self.assertNotIn(pc, graph.assignments[pb])
        if pc in graph.assignments:
            self.assertNotIn(pd, graph.assignments[pc])

    def test_max_retries_exceeded_raises_exception(self):
        """
        Test that an exception is raised when a valid flow cannot be found
        within the maximum number of retries.
        """
        pa = Player("A", "a@example.com")
        pb = Player("B", "b@example.com")
        pc = Player("C", "c@example.com")
        players = {pa, pb, pc}
        incompatibilities = set()
        
        with patch('secret_santa.secret_santa.gift_graph.NGiftGraph._build_flow_graph') as mock_build:
            mock_flow_graph = MagicMock()
            mock_build.return_value = mock_flow_graph
            
            p_a = list(players)[0]
            p_b = list(players)[1]
            
            mock_src_a = MagicMock()
            mock_src_a.player = p_a
            mock_dst_b = MagicMock()
            mock_dst_b.player = p_b
            mock_src_b = MagicMock()
            mock_src_b.player = p_b
            mock_dst_a = MagicMock()
            mock_dst_a.player = p_a

            mock_flow = MagicMock()
            mock_flow.graph = {
                mock_src_a: {mock_dst_b: 1},
                mock_src_b: {mock_dst_a: 1}
            }
            mock_flow_graph.compute_largest_flow.return_value = mock_flow
            
            with self.assertRaises(GiftAssignmentError) as cm:
                NGiftGraph(players, incompatibilities, allow_2cycles=False, max_attempts=3)
            
            self.assertIn("Could not find a valid solution after 3 attempts", str(cm.exception))
            self.assertEqual(mock_build.call_count, 3)

    def test_retry_succeeds_eventually(self):
        """
        Test that if the graph generation fails initially but succeeds later,
        it returns successfully.
        """
        players = {
            Player("A", "a@example.com"),
            Player("B", "b@example.com"),
            Player("C", "c@example.com")
        }
        incompatibilities = set()
        
        with patch('secret_santa.secret_santa.gift_graph.NGiftGraph._build_flow_graph') as mock_build:
            mock_flow_graph_bad = MagicMock()
            mock_flow_bad = MagicMock()
            
            players_list = list(players)
            p_a = players_list[0]
            p_b = players_list[1]
            
            mock_src_a = MagicMock()
            mock_src_a.player = p_a
            mock_dst_b = MagicMock()
            mock_dst_b.player = p_b
            mock_src_b = MagicMock()
            mock_src_b.player = p_b
            mock_dst_a = MagicMock()
            mock_dst_a.player = p_a
            
            mock_flow_bad.graph = {
                mock_src_a: {mock_dst_b: 1},
                mock_src_b: {mock_dst_a: 1}
            }
            mock_flow_graph_bad.compute_largest_flow.return_value = mock_flow_bad

            mock_flow_graph_good = MagicMock()
            mock_flow_good = MagicMock()
            p_c = players_list[2]
            mock_src_c = MagicMock()
            mock_src_c.player = p_c
            mock_dst_c = MagicMock()
            mock_dst_c.player = p_c
            
            mock_flow_good.graph = {
                mock_src_a: {mock_dst_b: 1},
                mock_src_b: {mock_dst_c: 1},
                mock_src_c: {mock_dst_a: 1}
            }
            mock_flow_graph_good.compute_largest_flow.return_value = mock_flow_good
            
            mock_build.side_effect = [mock_flow_graph_bad, mock_flow_graph_bad, mock_flow_graph_good]
            
            graph = NGiftGraph(players, incompatibilities, allow_2cycles=False, max_attempts=5)
            
            self.assertEqual(mock_build.call_count, 3)
            self.assertIn(p_b, graph.assignments[p_a])
            self.assertIn(p_c, graph.assignments[p_b])
            self.assertIn(p_a, graph.assignments[p_c])

if __name__ == '__main__':
    unittest.main()
