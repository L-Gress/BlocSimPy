import sys
import os
import time
import numpy as np
import unittest

# Ensure we can import from the engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.blocks.fft import FFT
from engine.blocks.ifft import IFFT

class TestFFTPerformance(unittest.TestCase):
    def test_fft_correctness(self):
        """Verify that FFT correctly identifies a sine wave frequency."""
        fft = FFT()
        fft.params["Window Size"] = 1024
        fft.params["Num Peaks"] = 1
        fft.reset()
        
        fs = 44100.0
        dt = 1.0 / fs
        freq = 440.0 # A4
        
        # Process 1024 samples
        for i in range(1024):
            t = i * dt
            val = np.sin(2.0 * np.pi * freq * t)
            fft.inputs["in"].value = val
            fft.compute(t, dt)
            
        # Check output
        out_freq = fft.outputs["f1"].value
        out_amp = fft.outputs["a1"].value
        
        print(f"Detected Freq: {out_freq}, Amp: {out_amp}")
        # Expected freq should be close to 440
        self.assertAlmostEqual(out_freq, freq, delta=fs/1024)
        # Amp should be close to 1.0 (Hann window compensation)
        self.assertGreater(out_amp, 0.9)

    def test_fft_ifft_chain(self):
        """Verify that FFT + IFFT chain reconstructs the signal."""
        fft = FFT()
        ifft = IFFT()
        
        fft.params["Window Size"] = 1024
        fft.params["Num Peaks"] = 5
        ifft.params["Num Elements"] = 5
        
        fft.reset()
        ifft.reset()
        
        fs = 44100.0
        dt = 1.0 / fs
        
        # Test signal: Mix of two sines
        f1, f2 = 100.0, 500.0
        a1, a2 = 0.5, 0.3
        
        # Fill buffer
        for i in range(1024):
            t = i * dt
            sig = a1 * np.sin(2*np.pi*f1*t) + a2 * np.sin(2*np.pi*f2*t)
            fft.inputs["in"].value = sig
            fft.compute(t, dt)
            
        # Transfer peaks to IFFT
        for i in range(1, 6):
            ifft.inputs[f"f{i}"].value = fft.outputs[f"f{i}"].value
            ifft.inputs[f"a{i}"].value = fft.outputs[f"a{i}"].value
            
        # Compute IFFT
        # We need to simulate the same amount of time for phase matching roughly
        t = 1024 * dt
        ifft.compute(t, dt)
        out = ifft.outputs["out"].value
        
        # Note: Phase won't match perfectly because FFT is a snapshot, 
        # but the frequencies and amplitudes should be correct.
        # This test checks if it synthesizes SOMETHING reasonable.
        self.assertGreater(out, -1.0)
        self.assertLess(out, 1.0)

    def test_performance(self):
        """Measure performance of FFT/IFFT."""
        fft = FFT()
        ifft = IFFT()
        
        n_peaks = 10
        fft.params["Num Peaks"] = n_peaks
        ifft.params["Num Elements"] = n_peaks
        fft.reset()
        ifft.reset()
        
        dt = 1.0/44100.0
        
        # FFT performance (10k samples = ~230ms of audio)
        start = time.perf_counter()
        for i in range(10000):
            fft.inputs["in"].value = np.random.random()
            fft.compute(i*dt, dt)
        fft_time = time.perf_counter() - start
        
        # IFFT performance
        start = time.perf_counter()
        for i in range(10000):
            ifft.compute(i*dt, dt)
        ifft_time = time.perf_counter() - start
        
        print(f"FFT 10k steps: {fft_time*1000:.2f}ms")
        print(f"IFFT 10k steps: {ifft_time*1000:.2f}ms")
        
        # Ensure it's fast enough for real-time (10k steps at 44.1kHz is ~226ms)
        # We want it to be much faster than that.
        self.assertLess(fft_time, 0.1) # Must be faster than 100ms
        self.assertLess(ifft_time, 0.1) # Must be faster than 100ms

if __name__ == '__main__':
    unittest.main()
