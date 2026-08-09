"""Tests for engine.simulation.processors: the real-time drivers used for
top-level audio-driven Runs and SubGraph's Threaded/Audio execution modes.
"""
import time
import unittest
import numpy as np

from engine.simulation.processors import AudioProcessor, TimerProcessor
from engine.blocks.constant import Constant
from engine.blocks.gain import Gain
from engine.blocks.integrator import Integrator
from engine.blocks.audio_input import AudioInput
from engine.blocks.audio_output import AudioOutput
from conftest import set_params


class TestAudioProcessor(unittest.TestCase):
    def test_callback_pipes_indata_through_gain_to_outdata(self):
        audio_in = AudioInput()
        set_params(audio_in, Channel=0)
        gain = Gain()
        set_params(gain, Gain=2.0)
        gain.inputs["in"].connected_port = audio_in.outputs["out"]
        audio_out = AudioOutput()
        set_params(audio_out, Channel=0)
        audio_out.inputs["in"].connected_port = gain.outputs["out"]

        processor = AudioProcessor([audio_in, gain, audio_out], sample_rate=100)

        frames = 4
        indata = np.zeros((frames, 2))
        indata[:, 0] = [0.1, 0.2, 0.3, 0.4]
        outdata = np.zeros((frames, 2))

        processor.callback(indata, outdata, frames, None, None)

        np.testing.assert_allclose(outdata[:, 0], [0.2, 0.4, 0.6, 0.8])

    def test_callback_advances_internal_clock(self):
        audio_in = AudioInput()
        processor = AudioProcessor([audio_in], sample_rate=100)  # dt = 0.01
        frames = 10
        indata = np.zeros((frames, 2))
        outdata = np.zeros((frames, 2))

        processor.callback(indata, outdata, frames, None, None)
        self.assertAlmostEqual(processor.time, 0.1)

        processor.callback(indata, outdata, frames, None, None)
        self.assertAlmostEqual(processor.time, 0.2)

    def test_stateful_blocks_get_update_state_chunk_called(self):
        # Integrator has update_state/update_state_chunk; verify AudioProcessor
        # actually invokes it (i.e. state accumulates across callbacks).
        const = Constant()
        const.params["Value"] = 1.0
        integ = Integrator()
        integ.inputs["in"].connected_port = const.outputs["out"]

        processor = AudioProcessor([const, integ], sample_rate=100)  # dt = 0.01
        frames = 100  # 1 second worth
        indata = np.zeros((frames, 2))
        outdata = np.zeros((frames, 2))
        processor.callback(indata, outdata, frames, None, None)

        self.assertAlmostEqual(integ.state, 1.0, places=6)

    def test_survives_missing_status_gracefully(self):
        audio_in = AudioInput()
        processor = AudioProcessor([audio_in], sample_rate=100)
        frames = 2
        indata = np.zeros((frames, 2))
        outdata = np.zeros((frames, 2))
        # Should not raise even though status is falsy/None.
        processor.callback(indata, outdata, frames, None, None)


class TestTimerProcessor(unittest.TestCase):
    def test_start_runs_blocks_and_stop_halts_thread(self):
        const = Constant()
        const.params["Value"] = 1.0
        integ = Integrator()
        integ.inputs["in"].connected_port = const.outputs["out"]

        processor = TimerProcessor([const, integ], rate=200, steps_per_batch=1)
        processor.start()
        try:
            self.assertTrue(processor.is_active())
            time.sleep(0.2)
        finally:
            processor.stop()

        self.assertFalse(processor.is_active())
        self.assertFalse(processor.thread.is_alive())
        # After ~0.2s at 200Hz the integrator (of a constant 1.0) should have
        # accumulated noticeably above zero.
        self.assertGreater(integ.state, 0.0)

    def test_stop_is_safe_to_call_when_never_started(self):
        processor = TimerProcessor([Constant()], rate=100)
        processor.stop()  # should not raise
        self.assertFalse(processor.is_active())


if __name__ == "__main__":
    unittest.main()
