# BlocSimPy - Developer Quick Reference

## 📍 Where to Add New Features

### Adding a New Block Type

**Location:** `engine/blocks/my_new_block.py`

```python
from ..models import BlockModel

class MyNewBlock(BlockModel):
    def __init__(self):
        super().__init__("MyNewBlock")
        self.add_input("in")
        self.add_output("out")
        self.add_param("MyParameter", 1.0)
    
    def compute(self, t, dt):
        u = self.inputs["in"].value
        self.outputs["out"].value = u * self.params["MyParameter"]
    
    # Optional: Custom editor dialog
    def get_editor_dialog(self, parent=None):
        # Return a QDialog here
        pass
```

**Register in:** `engine/blocks/__init__.py`
```python
from .my_new_block import MyNewBlock

BLOCK_REGISTRY = {
    # ... existing blocks ...
    "MyNewBlock": MyNewBlock,
}
```

### Adding a New Toolbar Action

**Location:** `gui/managers/toolbar_manager.py`

```python
def create_toolbar(self):
    # ... existing actions ...
    
    action_my_feature = QAction("✨ My Feature", self.main_window)
    action_my_feature.triggered.connect(self._my_feature_handler)
    self.toolbar.addAction(action_my_feature)

def _my_feature_handler(self):
    # Implement your feature here
    pass
```

### Adding a New Context Menu Item

**Location:** `gui/menus/block_menu.py` or `connection_menu.py`

```python
@staticmethod
def show(block_ui, scene, screen_pos):
    menu = QMenu()
    
    # ... existing actions ...
    action_my_action = menu.addAction("My Action")
    
    selected_action = menu.exec(screen_pos)
    
    if selected_action == action_my_action:
        # Handle your action
        pass
```

### Adding a New Dialog

**Location:** `gui/dialogs.py`

```python
class MyNewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Dialog")
        # Setup your dialog
```

### Modifying UI Appearance

**Location:** `config/ui_config.py`

```python
class UIConfig:
    # Add new constants
    MY_NEW_COLOR = QColor(100, 150, 200)
    MY_NEW_SIZE = 50
```

Then use in your code:
```python
from config.ui_config import UIConfig

color = UIConfig.MY_NEW_COLOR
```

### Modifying Simulation Parameters

**Location:** `config/sim_config.py`

```python
class SimConfig:
    # Add new constants
    MY_SIMULATION_LIMIT = 100.0
```

## 🎯 Common Tasks

### Task: Add a new scene operation

**Location:** `gui/managers/scene_manager.py`

```python
class SceneManager:
    def my_new_operation(self):
        # Access blocks via self.blocks_ui
        # Access scene via self.main_window.scene
        pass
```

**Call from toolbar:**
```python
# In toolbar_manager.py
action.triggered.connect(self.main_window.scene_manager.my_new_operation)
```

### Task: Add a new dock widget

**Location:** `gui/managers/dock_manager.py`

```python
def create_my_dock(self):
    dock = QDockWidget("My Dock", self.main_window)
    # Configure dock
    return dock
```

**Add in MainWindow init:**
```python
# In main_window.py __init__
my_dock = self.dock_manager.create_my_dock()
self.addDockWidget(Qt.RightDockWidgetArea, my_dock)
```

### Task: Modify connection behavior

**Location:** `gui/items/ui_connection.py`

All connection routing, dragging, and rendering logic is here.

### Task: Modify block rendering

**Location:** `gui/items/ui_block.py`

The `paint()` method controls how blocks are drawn.

### Task: Change simulation algorithm

**Location:** `engine/simulation/engine.py`

The `run()` method contains the main simulation loop.

## 🔍 Finding Code

### "Where is the code that...?"

| Task | Location |
|------|----------|
| Creates the toolbar | `gui/managers/toolbar_manager.py` |
| Runs simulations | `gui/managers/toolbar_manager.py` → `engine/simulation/engine.py` |
| Saves/loads graphs | `gui/managers/scene_manager.py` → `engine/serialization/` |
| Handles right-click menus | `gui/menus/` |
| Draws blocks | `gui/items/ui_block.py` |
| Routes connections | `gui/items/ui_connection.py` |
| Enters subsystems | `gui/managers/scene_manager.py` |
| Manages library | `gui/managers/dock_manager.py` + `gui/library.py` |
| Defines block types | `engine/blocks/*.py` |
| Handles keyboard shortcuts | `gui/scene.py` (keyPressEvent) |

## 🎨 Styling Guide

### Colors
All colors should use `UIConfig`:
```python
from config.ui_config import UIConfig

painter.setPen(UIConfig.TEXT_COLOR)
painter.setBrush(UIConfig.BLOCK_BG_COLOR)
```

### Sizes
All sizes should use `UIConfig`:
```python
self.width = UIConfig.DEFAULT_BLOCK_WIDTH
self.height = UIConfig.DEFAULT_BLOCK_HEIGHT
```

### DO NOT use magic numbers!
```python
# ❌ BAD
self.pen = QPen(QColor(200, 200, 200), 2)

# ✅ GOOD
self.pen = QPen(UIConfig.CONNECTION_COLOR, UIConfig.CONNECTION_WIDTH)
```

## 🧪 Testing Your Changes

### Manual Testing Checklist

After making changes, test:

1. **Block Operations**
   - [ ] Create blocks from library
   - [ ] Connect blocks
   - [ ] Edit block parameters
   - [ ] Delete blocks
   - [ ] Rotate blocks (R key)

2. **File Operations**
   - [ ] Save graph
   - [ ] Load graph
   - [ ] Save As

3. **Simulation**
   - [ ] Run simulation
   - [ ] View scope results

4. **Subsystems**
   - [ ] Enter subsystem (double-click SubGraph)
   - [ ] Go up (toolbar button)

5. **Library**
   - [ ] Save SubGraph to library
   - [ ] Load SubGraph from library

## 🐛 Debugging Tips

### Print Debugging

```python
# In any file
print(f"DEBUG: {variable_name}")
```

### Common Issues

**Issue:** Block doesn't appear in list
- **Check:** Is it registered in `engine/blocks/__init__.py`?

**Issue:** Parameter changes don't take effect
- **Check:** Did you call `_update_label()` in your block?

**Issue:** Connection doesn't work
- **Check:** Did you add the port in block's `__init__`?

**Issue:** Toolbar button does nothing
- **Check:** Is the signal connected in `toolbar_manager.py`?

## 📦 Import Guidelines

### Standard Import Structure

```python
# Standard library
import os
import json

# Third-party
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

# Local - config first
from config.ui_config import UIConfig
from config.sim_config import SimConfig

# Local - engine
from engine.blocks import BLOCK_REGISTRY
from engine.simulation import SimulationEngine

# Local - gui
from gui.items import UIBlock
```

## 🚀 Best Practices

1. **One class per file** (with exceptions for small helper classes)
2. **Use managers** for complex operations
3. **Use config** for all constants
4. **Document new features** in docstrings
5. **Keep blocks self-contained** - all block logic in its file
6. **Maintain separation** - don't mix GUI and engine code

## 📞 Quick Access Patterns

### Access the scene from anywhere in GUI
```python
self.main_window.scene
```

### Access blocks list
```python
self.main_window.scene_manager.blocks_ui
```

### Show a message box
```python
from PySide6.QtWidgets import QMessageBox

QMessageBox.information(self.main_window, "Title", "Message")
```

### Get user input
```python
from PySide6.QtWidgets import QInputDialog

text, ok = QInputDialog.getText(None, "Title", "Prompt:")
if ok:
    # Use text
```

## 🎓 Architecture Summary

```
MainWindow (orchestrator)
    ↓
├── ToolbarManager → SimulationEngine
├── SceneManager → GraphSerializer
└── DockManager → UserLibraryWidget

Scene → Items (UIBlock, UIPort, UIConnection)
Items → BlockModel (from engine/blocks/)
```

Remember: **MainWindow delegates everything to managers!**
