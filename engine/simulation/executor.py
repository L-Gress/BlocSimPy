"""Execution ordering for block simulation."""
from typing import List, Set, Dict
from ..models import BlockModel


class ExecutionOrdering:
    """Determines the correct order to execute blocks in a graph."""
    
    @staticmethod
    def topological_sort(blocks: List[BlockModel]) -> List[BlockModel]:
        """
        Returns blocks in topologically sorted order (dependencies first).
        Uses Kahn's algorithm for cycle detection.
        """
        # Build adjacency list and in-degree count
        in_degree = {block: 0 for block in blocks}
        adjacency: Dict[BlockModel, List[BlockModel]] = {block: [] for block in blocks}
        
        for block in blocks:
            for inp in block.inputs.values():
                if inp.connected_port and inp.connected_port.owner in blocks:
                    source_block = inp.connected_port.owner
                    adjacency[source_block].append(block)
                    in_degree[block] += 1
        
        # Start with blocks that have no dependencies
        queue = [block for block in blocks if in_degree[block] == 0]
        sorted_blocks = []
        
        while queue:
            current = queue.pop(0)
            sorted_blocks.append(current)
            
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(sorted_blocks) != len(blocks):
            # Cycle detected, fall back to original order
            return blocks
        
        return sorted_blocks
