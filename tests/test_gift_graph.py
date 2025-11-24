import unittest
from secret_santa.secret_santa.gift_graph import NGiftGraph
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
        p1 = Player("A", "a@example.com")
        p2 = Player("B", "b@example.com")
        p3 = Player("C", "c@example.com")
        p4 = Player("D", "d@example.com")
        players = {p1, p2, p3, p4}
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
        p1 = Player("A", "a@example.com")
        p2 = Player("B", "b@example.com")
        p3 = Player("C", "c@example.com")
        p4 = Player("D", "d@example.com")
        p5 = Player("E", "e@example.com")
        players = {p1, p2, p3, p4, p5}
        
        # A cannot gift B
        # B cannot gift C
        # C cannot gift D
        incompatibilities = {
            Incompatibility(p1, p2),
            Incompatibility(p2, p3),
            Incompatibility(p3, p4)
        }

        graph = NGiftGraph(players, incompatibilities, number_of_gifts=1)
        
        graph.verify_assignments()
        
        # Verify incompatibilities
        if p1 in graph.assignments:
            self.assertNotIn(p2, graph.assignments[p1])
        if p2 in graph.assignments:
            self.assertNotIn(p3, graph.assignments[p2])
        if p3 in graph.assignments:
            self.assertNotIn(p4, graph.assignments[p3])

if __name__ == '__main__':
    unittest.main()
