"""Undo/Redo Manager for BlocSimPy."""
import json
from engine.serialization import GraphSerializer

class UndoManager:
    """ Manages the undo/redo stacks by storing snapshots of the graph state. """
    
    def __init__(self, scene_manager):
        self.scene_manager = scene_manager
        self.undo_stack = []
        self.redo_stack = []
        self.max_depth = 50
        self._is_undoing_redoing = False

    def take_snapshot(self):
        """ Captures the current state of the scene and pushes it to the undo stack. """
        if self._is_undoing_redoing:
            return
            
        # Serialize current state
        state = GraphSerializer.serialize_graph(self.scene_manager.blocks_ui, self.scene_manager.annotations_ui)
        state_str = json.dumps(state)
        
        # Only push if it's different from the last snapshot
        if self.undo_stack and self.undo_stack[-1] == state_str:
            return
            
        self.undo_stack.append(state_str)
        self.redo_stack.clear() # New action breaks redo chain
        
        # Limit stack size
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)

    def undo(self):
        """ Restores the previous state. """
        if len(self.undo_stack) < 2:
            return # Need at least one previous state to revert to
            
        self._is_undoing_redoing = True
        
        # Current state is at the top of undo_stack, move it to redo
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        
        # Get previous state
        prev_state_str = self.undo_stack[-1]
        prev_state = json.loads(prev_state_str)
        
        # Restore
        self.scene_manager._load_scene_data(prev_state)
        
        self._is_undoing_redoing = False

    def redo(self):
        """ Restores a state that was undone. """
        if not self.redo_stack:
            return
            
        self._is_undoing_redoing = True
        
        # Get redo state
        next_state_str = self.redo_stack.pop()
        self.undo_stack.append(next_state_str)
        
        next_state = json.loads(next_state_str)
        
        # Restore
        self.scene_manager._load_scene_data(next_state)
        
        self._is_undoing_redoing = False
