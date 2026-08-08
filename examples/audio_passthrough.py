"""
Example: Threaded SubGraph for Audio Processing

This script demonstrates how to set up a BlocSimPy graph programmatically that:
1. Uses a threaded SubGraph for Audio processing.
2. Captures Microphone Input (AudioInput).
3. Applies a Gain.
4. Outputs to Speakers (AudioOutput).

Usage:
    python examples/audio_passthrough.py
"""

import sys
import os

# Ensure we can import from engine
sys.path.append(os.getcwd())

from engine.models import BlockModel
from engine.blocks.subgraph import SubGraph
from engine.blocks.gain import Gain
from engine.blocks.audio_input import AudioInput
from engine.blocks.audio_output import AudioOutput
from engine.simulation.engine import SimulationEngine

def create_example_graph():
    # 1. Main Graph (Empty container for now, usually we'd have things here)
    # But for this example, we just run the SubGraph as a top-level block in a simulation?
    # Actually, the SimulationEngine runs a list of blocks.
    
    # Let's create a SubGraph
    sg = SubGraph()
    sg.name = "Audio Processor SubGraph"
    sg.params["Execution Mode"] = "Audio"
    sg.params["Sample Rate"] = 44100.0
    
    # 2. Inside the SubGraph: Audio In -> Gain -> Audio Out
    # We need to manually build the internal data matching serialized format
    
    # Block 1: Audio Input
    # ID: 1, Type: AudioInput
    b1 = {
        "id": "audio_in", 
        "type": "AudioInput",
        "params": {"Channel": 0, "Device": "default"}
    }
    
    # Block 2: Gain
    # ID: 2, Type: Gain
    b2 = {
        "id": "gain",
        "type": "Gain",
        "params": {"Gain": 0.5} # Reduce volume by half
    }
    
    # Block 3: Audio Output
    # ID: 3, Type: AudioOutput
    b3 = {
        "id": "audio_out",
        "type": "AudioOutput",
        "params": {"Channel": 0, "Device": "default"}
    }
    
    sg.internal_blocks_data = [b1, b2, b3]
    
    # Connections
    # AudioIn.out -> Gain.in
    c1 = {
        "from_block_id": "audio_in", "from_port": "out",
        "to_block_id": "gain", "to_port": "in"
    }
    # Gain.out -> AudioOut.in
    c2 = {
        "from_block_id": "gain", "from_port": "out",
        "to_block_id": "audio_out", "to_port": "in"
    }
    
    sg.internal_connections_data = [c1, c2]
    
    return [sg]

def run_example():
    print("Initializing Audio Example...")
    blocks = create_example_graph()
    
    # Configure Simulation Engine
    sim = SimulationEngine()
    sim.configure(blocks, duration=5.0, dt=0.1) # 5 seconds run
    
    print("Running Simulation (5 seconds)... Speak into mic!")
    
    # The SubGraph will start its internal thread when 'reset' is called inside sim.run()
    # The main simulation loop just ticks the empty SubGraph container.
    result = sim.run()
    
    if result.success:
        print("Simulation Finished Successfully.")
    else:
        print(f"Simulation Failed: {result.error_message}")

if __name__ == "__main__":
    run_example()
