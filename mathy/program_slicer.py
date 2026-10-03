"""
Forward Program Slicer for COBOL Programs.
Computes static forward slices on Program Dependence Graphs (PDG: CFG + DFG).
Provides classical baseline rankings:
  1. Binary forward slice membership
  2. Hop-count distance (BFS in slice)
  3. Random permutation in slice
"""

import collections
import random
from typing import Dict, List, Set, Any, Tuple, Optional


class ProgramSlicer:
    """
    Computes static forward slices and baseline graph-distance rankings.
    """

    def __init__(self, graph_data: Dict[str, Any]):
        self.graph_data = graph_data
        self.nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
        self.forward_adj: Dict[str, Set[str]] = collections.defaultdict(set)
        self.all_nodes: Set[str] = set(self.nodes_by_id.keys())
        self._build_dependence_graph()

    def _build_dependence_graph(self):
        """Constructs forward dependency adjacency from CFG and DFG edges."""
        # Include CFG control transfers (seq, call, branches) and DFG def-use
        for edge in self.graph_data.get("edges", []):
            src = edge["source"]
            dst = edge["target"]
            etype = edge.get("edge_type", "")

            # Include statement-to-statement dependencies
            if src in self.nodes_by_id and dst in self.nodes_by_id:
                # Direct control or data dependency
                self.forward_adj[src].add(dst)

            # Handle variable hub traversals if variables are nodes
            elif edge.get("edge_type") == "dfg_def_use" and src in self.nodes_by_id and dst in self.nodes_by_id:
                self.forward_adj[src].add(dst)

    def compute_forward_slice(self, seed_node_id: str) -> Set[str]:
        """
        Computes the standard Weiser forward slice from a seed node.
        Returns all nodes reachable via forward control and data dependencies.
        """
        if seed_node_id not in self.nodes_by_id:
            return set()

        visited = {seed_node_id}
        queue = collections.deque([seed_node_id])

        while queue:
            curr = queue.popleft()
            for neighbor in self.forward_adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return visited

    def compute_bfs_distances(self, seed_node_id: str) -> Dict[str, int]:
        """
        Computes shortest hop distance from seed_node_id in the forward dependence graph.
        Unreachable nodes have distance infinity.
        """
        distances: Dict[str, int] = {seed_node_id: 0}
        queue = collections.deque([seed_node_id])

        while queue:
            curr = queue.popleft()
            curr_dist = distances[curr]
            for neighbor in self.forward_adj.get(curr, set()):
                if neighbor not in distances:
                    distances[neighbor] = curr_dist + 1
                    queue.append(neighbor)

        return distances

    def rank_by_bfs(self, seed_node_id: str, slice_nodes: Optional[Set[str]] = None) -> List[str]:
        """
        Baseline B: Ranks nodes in the slice by ascending BFS hop distance from the seed.
        Closer nodes in dependency chain are ranked higher.
        """
        distances = self.compute_bfs_distances(seed_node_id)
        target_nodes = slice_nodes if slice_nodes is not None else self.compute_forward_slice(seed_node_id)
        
        # Exclude seed node itself from ranking of downstream targets
        candidates = [nid for nid in target_nodes if nid != seed_node_id]

        # Sort by (hop distance, alphabetical id for determinism)
        candidates.sort(key=lambda nid: (distances.get(nid, 999999), nid))
        return candidates

    def rank_by_random(self, seed_node_id: str, slice_nodes: Optional[Set[str]] = None, seed: int = 42) -> List[str]:
        """
        Baseline A: Uniform random ordering of nodes within the forward slice.
        """
        target_nodes = slice_nodes if slice_nodes is not None else self.compute_forward_slice(seed_node_id)
        candidates = [nid for nid in target_nodes if nid != seed_node_id]
        rng = random.Random(seed)
        rng.shuffle(candidates)
        return candidates
