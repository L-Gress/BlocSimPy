"""Tests for SceneManager.enter_subsystem()/go_up_level() -- specifically,
that renaming an InputPort/OutputPort's PortName while inside a subsystem
does not silently drop the parent-level wire attached to that port.

This lives in the GUI layer (gui/managers/scene_manager.py), unlike the rest
of this test suite (which is deliberately Qt-free, see test_serialization.py's
module docstring) -- the bug being guarded against only exists in how
SceneManager reconciles renamed ports across enter/exit, so it can't be
exercised without real UIBlock/UIConnection/NodeScene objects. A QApplication
is required for that; offscreen platform keeps this runnable headlessly/in CI.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject

from gui.scene import NodeScene
from gui.managers.scene_manager import SceneManager
from gui.items import UIBlock, UIConnection
from engine.blocks.subgraph import SubGraph
from engine.blocks.constant import Constant
from engine.blocks.scope import Scope

_app = QApplication.instance() or QApplication([])


class _FakeMainWindow(QObject):
    """Minimal stand-in for MainWindow -- SceneManager/NodeScene only need
    a QObject parent and a `.scene_manager` back-reference."""
    pass


def _build_scene_with_passthrough_subgraph():
    """Constant -> SubGraph(In1 -> Out1 passthrough) -> Scope, fully wired."""
    mw = _FakeMainWindow()
    mw.scene = NodeScene(mw)
    mw.scene_manager = SceneManager(mw, mw.scene)
    sm = mw.scene_manager

    sg = SubGraph()
    sg.internal_blocks_data = [
        {"class": "InputPort", "type": "InputPort", "id": "ip1",
         "position": {"x": 0, "y": 0}, "rotation": 0, "params": {"PortName": "In1"}},
        {"class": "OutputPort", "type": "OutputPort", "id": "op1",
         "position": {"x": 200, "y": 0}, "rotation": 0, "params": {"PortName": "Out1"}},
    ]
    sg.internal_connections_data = [
        {"from_block_id": "ip1", "from_port": "out", "to_block_id": "op1", "to_port": "in", "points": []}
    ]
    sg.refresh_io_ports()

    c = Constant()
    scope = Scope()

    sg_ui = UIBlock(sg)
    c_ui = UIBlock(c)
    scope_ui = UIBlock(scope)
    mw.scene.addItem(sg_ui)
    mw.scene.addItem(c_ui)
    mw.scene.addItem(scope_ui)
    sm.blocks_ui = [c_ui, sg_ui, scope_ui]

    conn_in = UIConnection(c_ui.ports_ui["out"])
    conn_in.end_port = sg_ui.ports_ui["In1"]
    mw.scene.addItem(conn_in)
    c_ui.ports_ui["out"].connections.append(conn_in)
    sg_ui.ports_ui["In1"].connections.append(conn_in)
    sg_ui.ports_ui["In1"].model.connected_port = c_ui.ports_ui["out"].model

    conn_out = UIConnection(sg_ui.ports_ui["Out1"])
    conn_out.end_port = scope_ui.ports_ui["in1"]
    mw.scene.addItem(conn_out)
    sg_ui.ports_ui["Out1"].connections.append(conn_out)
    scope_ui.ports_ui["in1"].connections.append(conn_out)
    scope_ui.ports_ui["in1"].model.connected_port = sg_ui.ports_ui["Out1"].model

    return sm, sg_ui, c_ui, scope_ui


class TestSubgraphPortRename(unittest.TestCase):
    def test_renaming_input_port_preserves_parent_wire(self):
        sm, sg_ui, c_ui, scope_ui = _build_scene_with_passthrough_subgraph()

        sm.enter_subsystem(sg_ui)
        input_port_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "InputPort")
        input_port_ui.model.params["PortName"] = "RenamedIn"
        input_port_ui.model._update_label()
        sm.go_up_level()

        new_sg_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "SubGraph")
        self.assertIn("RenamedIn", new_sg_ui.model.inputs)
        renamed_port_ui = new_sg_ui.ports_ui["RenamedIn"]
        self.assertIsNotNone(renamed_port_ui.model.connected_port)
        new_constant_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "Constant")
        self.assertIs(renamed_port_ui.model.connected_port, new_constant_ui.ports_ui["out"].model)

    def test_renaming_output_port_preserves_parent_wire(self):
        sm, sg_ui, c_ui, scope_ui = _build_scene_with_passthrough_subgraph()

        sm.enter_subsystem(sg_ui)
        output_port_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "OutputPort")
        output_port_ui.model.params["PortName"] = "RenamedOut"
        output_port_ui.model._update_label()
        sm.go_up_level()

        new_sg_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "SubGraph")
        self.assertIn("RenamedOut", new_sg_ui.model.outputs)
        new_scope_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "Scope")
        self.assertIsNotNone(new_scope_ui.ports_ui["in1"].model.connected_port)
        self.assertIs(
            new_scope_ui.ports_ui["in1"].model.connected_port,
            new_sg_ui.ports_ui["RenamedOut"].model
        )

    def test_no_rename_still_reconnects_normally(self):
        # Regression guard: the rename-detection machinery must not break
        # the far more common case of entering/exiting without renaming anything.
        sm, sg_ui, c_ui, scope_ui = _build_scene_with_passthrough_subgraph()

        sm.enter_subsystem(sg_ui)
        sm.go_up_level()

        new_sg_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "SubGraph")
        self.assertIn("In1", new_sg_ui.model.inputs)
        self.assertIn("Out1", new_sg_ui.model.outputs)
        self.assertIsNotNone(new_sg_ui.ports_ui["In1"].model.connected_port)

        new_scope_ui = next(b for b in sm.blocks_ui if b.model.__class__.__name__ == "Scope")
        self.assertIsNotNone(new_scope_ui.ports_ui["in1"].model.connected_port)


if __name__ == "__main__":
    unittest.main()
