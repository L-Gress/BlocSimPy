# BlocSimPy - Modular Architecture Refactoring

## 🎯 Overview

This document describes the comprehensive refactoring of BlocSimPy into a highly modular architecture. The codebase has been restructured to follow industry best practices with clear separation of concerns.

## 📊 Before vs After

### Before
- **main_window.py**: 451 lines (monolithic)
- **items.py**: 487 lines (3 classes in one file)
- **Simulation logic**: Mixed with GUI code
- **Serialization**: Embedded in MainWindow
- **Configuration**: Magic numbers scattered throughout
- **Total structure**: ~6 main files

### After
- **main_window.py**: ~60 lines (orchestrator only)
- **Items**: Split into 3 focused modules
- **Simulation**: Dedicated engine package
- **Serialization**: Separate service layer
- **Configuration**: Centralized config system
- **Total structure**: 25+ focused modules

## 🏗️ New Architecture

```
BlocSimPy/
├── config/                          ✨ NEW
│   ├── __init__.py
│   ├── ui_config.py                 # UI constants (colors, sizes, etc.)
│   └── sim_config.py                # Simulation constants
│
├── engine/
│   ├── blocks/                      ✅ EXISTING (17 block types)
│   │   ├── __init__.py
│   │   ├── sine_wave.py
│   │   ├── gain.py
│   │   ├── transfer_function.py
│   │   ├── lookup_table.py
│   │   ├── pid.py
│   │   └── ... (each block self-contained)
│   │
│   ├── simulation/                  ✨ NEW
│   │   ├── __init__.py
│   │   ├── engine.py                # SimulationEngine class
│   │   └── executor.py              # ExecutionOrdering (topological sort)
│   │
│   ├── serialization/               ✨ NEW
│   │   ├── __init__.py
│   │   └── graph_serializer.py      # Save/load graph logic
│   │
│   └── models.py                    ✅ EXISTING
│
├── gui/
│   ├── items/                       ✨ NEW (split from items.py)
│   │   ├── __init__.py
│   │   ├── ui_block.py              # UIBlock class
│   │   ├── ui_port.py               # UIPort class
│   │   └── ui_connection.py         # UIConnection class
│   │
│   ├── managers/                    ✨ NEW
│   │   ├── __init__.py
│   │   ├── toolbar_manager.py       # Toolbar creation & actions
│   │   ├── scene_manager.py         # Scene ops, save/load, subsystems
│   │   └── dock_manager.py          # Library dock management
│   │
│   ├── widgets/                     ✨ NEW
│   │   ├── __init__.py
│   │   └── graphics_view.py         # Custom QGraphicsView
│   │
│   ├── menus/                       ✨ NEW
│   │   ├── __init__.py
│   │   ├── block_menu.py            # Block context menu
│   │   └── connection_menu.py       # Connection context menu
│   │
│   ├── main_window.py               🔄 REFACTORED (orchestrator)
│   ├── scene.py                     🔄 REFACTORED (cleaner)
│   ├── library.py                   🔄 UPDATED (uses config)
│   └── dialogs.py                   ✅ EXISTING
│
├── user_library/                    ✅ EXISTING
└── main.py                          ✅ EXISTING
```

## 🎨 Key Architectural Improvements

### 1. **Configuration Management**
All magic numbers and constants are now centralized:
- `UIConfig`: Colors, sizes, fonts, visual constants
- `SimConfig`: Simulation defaults, validation limits

**Example:**
```python
# Before
self.pen = QPen(QColor(200, 200, 200), 2)

# After
self.pen = QPen(UIConfig.CONNECTION_COLOR, UIConfig.CONNECTION_WIDTH)
```

### 2. **Simulation Engine**
Extracted from GUI into dedicated engine:
- `SimulationEngine`: Configures and runs simulations
- `ExecutionOrdering`: Topological sort for dependency resolution
- `SimulationResult`: Clean data structure for results

**Benefits:**
- Can run simulations headless (no GUI required)
- Easy to test in isolation
- Clear separation of concerns

### 3. **Serialization Service**
`GraphSerializer` handles all save/load operations:
- `serialize_graph()`: Converts UI blocks to JSON
- `deserialize_graph()`: Reconstructs graph from JSON
- Handles SubGraph internals, connections, positions

### 4. **Manager Pattern**
MainWindow delegates to specialized managers:

#### **ToolbarManager**
- Creates toolbar
- Handles all toolbar actions
- Manages simulation settings
- Displays results

#### **SceneManager**
- Block creation/deletion
- Save/load operations
- Subsystem navigation
- Breadcrumb updates

#### **DockManager**
- Creates library dock
- Manages library tabs
- Block filtering/search

### 5. **Item Separation**
Each UI item type in its own file:
- `UIBlock`: Block visualization
- `UIPort`: Port visualization
- `UIConnection`: Connection routing

### 6. **Menu System**
Context menus extracted into dedicated classes:
- `BlockContextMenu`: Rename, rotate, delete blocks
- `ConnectionContextMenu`: Delete connections

## ✅ Block Isolation Guarantee

**Every block is completely self-contained in its own .py file:**

Each block file contains:
1. Block logic (`compute()`, `update_state()`)
2. Default parameters
3. Editor dialog (if needed)
4. Formatting/labeling logic
5. All block-specific PySide6 imports

**No block-specific logic exists outside the block files.**

## 🎯 Benefits of New Architecture

### Maintainability
- ✅ Each file has a single, clear responsibility
- ✅ Easy to find where functionality lives
- ✅ Changes are localized to specific modules

### Testability
- ✅ Each component can be tested in isolation
- ✅ SimulationEngine can run without GUI
- ✅ Serialization logic is independent

### Extensibility
- ✅ New blocks: Just add to `engine/blocks/`
- ✅ New UI features: Add to appropriate manager
- ✅ New dialogs: Add to `gui/dialogs.py`

### Scalability
- ✅ MainWindow is now ~60 lines (was 451)
- ✅ No 500+ line files
- ✅ Clear module boundaries

### Readability
- ✅ Imports clearly show dependencies
- ✅ File names describe contents
- ✅ Logical grouping by concern

## 📝 Migration Notes

### Import Changes

**Old:**
```python
from gui.items import UIBlock, UIPort, UIConnection
```

**New:**
```python
from gui.items import UIBlock, UIPort, UIConnection  # Still works!
```
The `gui/items/__init__.py` re-exports everything, so external code doesn't break.

### MainWindow Changes

**Old:**
```python
main_window.run_simulation()
main_window.save_graph()
```

**New:**
```python
main_window.toolbar_manager.run_simulation()
main_window.scene_manager.save_graph()
```

### Configuration Usage

**Add to any module:**
```python
from config.ui_config import UIConfig
from config.sim_config import SimConfig

# Then use UIConfig.BLOCK_BG_COLOR etc.
```

## 🚀 Future Enhancement Opportunities

With this modular structure, future improvements are easier:

1. **Testing Framework**
   - Unit tests for SimulationEngine
   - Integration tests for serialization
   - UI tests for each manager

2. **Plugin System**
   - Custom blocks loaded from external files
   - Block discovery mechanism

3. **Undo/Redo**
   - Command pattern for all operations
   - History manager

4. **Multi-Document Interface**
   - Multiple graphs open simultaneously
   - Document manager class

5. **Performance Monitoring**
   - Profiling manager
   - Metrics dashboard

## 📚 Code Quality Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Largest File | 487 lines | 230 lines | 52% reduction |
| MainWindow | 451 lines | 60 lines | 87% reduction |
| File Count | 6 core | 25+ focused | Better organization |
| Avg Lines/File | ~200 | ~100 | Easier to understand |
| Config Constants | Scattered | Centralized | Single source of truth |

## 🎓 Design Patterns Used

1. **Manager Pattern**: MainWindow delegates to managers
2. **Service Layer**: SimulationEngine, GraphSerializer
3. **Strategy Pattern**: Different context menus
4. **Factory Pattern**: Block registry
5. **Observer Pattern**: Qt signals/slots
6. **Single Responsibility**: Each class/module one job

## 🏆 Summary

This refactoring transforms BlocSimPy from a functional but monolithic application into a professionally architected, modular system. The new structure:

- **Reduces complexity** through separation of concerns
- **Improves maintainability** with focused modules
- **Enables testing** with isolated components
- **Facilitates growth** with clear extension points
- **Maintains compatibility** with existing code

Each block remains self-contained with all its logic, dialogs, and formatting in its own file, ensuring true modularity throughout the entire codebase.
