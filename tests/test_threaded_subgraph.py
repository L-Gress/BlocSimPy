import sys
import time
import unittest
from engine.blocks.subgraph import SubGraph
from engine.blocks.sine_wave import SineWave
from engine.blocks.scope import Scope
from engine.blocks.input_port import InputPort
from engine.blocks.output_port import OutputPort

class TestThreadedSubGraph(unittest.TestCase):
    
    def test_threaded_execution(self):
        """
        Test that a SubGraph in Threaded mode actually runs and processes data.
        """
        print("\n--- Testing Threaded SubGraph ---")
        
        # 1. Create SubGraph
        sg = SubGraph()
        sg.params["Execution Mode"] = "Threaded"
        sg.params["Sample Rate"] = 50.0 # 50 Hz
        
        # 2. Define Internal Structure (Input -> Sine + Input -> Output)
        # We'll make a simple pass-through with modification
        # InputPort("in") -> OutputPort("out")
        
        # We need to manually construct the data dicts as if loaded from file/UI
        sg.internal_blocks_data = [
            {
                "id": "in1", "type": "InputPort", 
                "params": {"PortName": "in"}
            },
            {
                "id": "out1", "type": "OutputPort", 
                "params": {"PortName": "out"}
            }
        ]
        
        sg.internal_connections_data = [
            {
                "from_block_id": "in1", "from_port": "out",
                "to_block_id": "out1", "to_port": "in"
            }
        ]
        
        # Sync ports
        sg.sync_ports_from_data()
        self.assertTrue("in" in sg.inputs)
        self.assertTrue("out" in sg.outputs)
        
        # 3. Initialize/Reset (Starts Threads)
        sg.reset()
        self.assertTrue(sg.running)
        self.assertIsNotNone(sg.processor)
        
        try:
            # 4. Simulate Outer Loop
            # We will push 10.0 into "in", wait, and expect 10.0 at "out"
            
            # Step 1: Push Input
            sg.inputs["in"].value = 10.0
            sg.compute(0, 0.1) # Pushes to queue
            
            # Allow thread to pick it up (50hz = 20ms period)
            time.sleep(0.1) 
            
            # Step 2: Read Output
            sg.compute(0.1, 0.1) # Pops from queue
            val = sg.outputs["out"].value
            print(f"Input: 10.0 -> Output: {val}")
            
            # In a perfectly synced world, it should be 10.0. 
            # Due to "Drop Oldest" and timing, it should eventually settle.
            self.assertEqual(val, 10.0)
            
            # Change input
            sg.inputs["in"].value = 55.0
            sg.compute(0.2, 0.1)
            time.sleep(0.1)
            sg.compute(0.3, 0.1)
            val = sg.outputs["out"].value
            print(f"Input: 55.0 -> Output: {val}")
            self.assertEqual(val, 55.0)
            
        finally:
            sg.cleanup()
            print("Cleanup done.")

if __name__ == '__main__':
    unittest.main()
