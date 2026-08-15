# Nested SubGraph Bugfix Demo
# ----------------------------
# Regression demo for a bug where a SubGraph nested INSIDE another SubGraph
# computed as 0.0 (instead of its real value) if you ran the simulation
# WITHOUT first double-clicking your way down into every nested level in
# the GUI. Root cause: SubGraph._instantiate_internal_blocks()
# (engine/blocks/subgraph.py) built a fresh runtime instance for each
# internal block, but for a nested SubGraph it never copied that nested
# block's own internal_blocks_data/internal_connections_data onto the new
# instance before calling reset() -- so the nested level always
# instantiated ZERO execution blocks. See tests/test_subgraph_standard.py
# ::test_nested_subgraph_computes_without_ever_being_entered for the
# equivalent headless unit test.
#
# This script builds the diagram entirely by script:
#
#   Top Level:      Const(5.0) -> Outer[SubGraph] -> Scope_Out
#   Outer contents:     In -> Inner[SubGraph] -> Out
#   Inner contents:         In -> Gain(2.0) -> Out
#
# so Outer's expected steady-state output is 5.0 * 2.0 = 10.0.
#
# The critical part: after building everything, the script calls
# go_to_top() and runs sim() DIRECTLY from there -- it does NOT re-enter
# Outer or Inner beforehand. That's exactly the scenario that used to
# silently produce 0.0. Run this file top to bottom (via the app's
# Console) to confirm the fix: it should print 10.0.

print("=== Building nested SubGraph diagram (Const -> Outer[Inner[Gain]] -> Scope) ===")

new_diagram()  # fresh, empty top-level diagram

# --- Top level: source, the outer SubGraph, and a scope to read its output ---
add_block('Constant', name='Const', position=(0, 150))
set_param('Const', 'Value', 5.0)

add_block('SubGraph', name='Outer', position=(250, 150))

add_block('Scope', name='Scope_Out', position=(500, 150))

# --- Step into Outer and build: In -> Inner[SubGraph] -> Out ---
enter_subgraph('Outer')

add_block('InputPort', name='OuterIn', position=(0, 100))
set_param('OuterIn', 'PortName', 'In')

add_block('SubGraph', name='Inner', position=(200, 100))

add_block('OutputPort', name='OuterOut', position=(400, 100))
set_param('OuterOut', 'PortName', 'Out')

# --- Step into Inner (nested two levels deep) and build: In -> Gain(2.0) -> Out ---
enter_subgraph('Inner')

add_block('InputPort', name='InnerIn', position=(0, 50))
set_param('InnerIn', 'PortName', 'In')

add_block('Gain', name='Gain2x', position=(200, 50))
set_param('Gain2x', 'Gain', 2.0)

add_block('OutputPort', name='InnerOut', position=(400, 50))
set_param('InnerOut', 'PortName', 'Out')

add_line('InnerIn', 'Gain2x')
add_line('Gain2x', 'InnerOut')

exit_subgraph()  # back up to Outer's level; Inner's In/Out ports are now exposed

# --- Wire Outer's own ports through Inner ---
add_line('OuterIn', 'Inner', dst_port='In')
add_line('Inner', 'OuterOut', src_port='Out')

exit_subgraph()  # back up to Top Level; Outer's In/Out ports are now exposed

# --- Wire the top level ---
add_line('Const', 'Outer', dst_port='In')
add_line('Outer', 'Scope_Out', src_port='Out')

# At this point we are at Top Level, and NEITHER Outer NOR Inner has ever
# been re-entered since being built. This is the exact condition that used
# to trigger the bug.
go_to_top()

print("Diagram built (2 levels of nested SubGraph). Running sim() WITHOUT re-entering either level...")
result = sim(duration=0.1, dt=1e-3)

if result is not None:
    value = result["scopes"]["Scope_Out"]["data"][-1]
    print(f"Scope_Out = {value} (expected 10.0 = 5.0 * 2.0)")
    if abs(value - 10.0) < 1e-6:
        print("PASS -- nested SubGraph computed correctly without being entered first.")
    else:
        print("FAIL -- nested SubGraph did NOT compute correctly (bug is present).")

save_diagram("Nested_SubGraph_Demo.json")
