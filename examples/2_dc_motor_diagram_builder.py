# DC Motor Block Diagram Builder
# -------------------------------
# Builds an actual BlocSimPy block diagram of a DC motor from primitive
# blocks (Gain/Sum/Divide/Integrator), parametrized entirely by the
# global variables 1_dc_motor_identification.py identified -- run that
# one FIRST, in this same session.
#
# Fully scripted end to end -- new_diagram() creates a fresh, empty
# diagram tab itself (no need to already have one open via File -> New),
# and save_diagram() at the bottom writes the finished result to disk, so
# nothing here requires touching the GUI at all.
#
# The diagram implements the same two coupled equations that script used
# to synthesize its test data:
#
#   L * di/dt = V - R*i - K*w        (armature electrical circuit)
#   J * dw/dt = K*i - b*w - T_load   (rotor mechanical dynamics, T_load=0)
#
# as a direct block-diagram translation -- an electrical loop producing
# current i (fed back through R and the back-EMF term K*w), and a
# mechanical loop producing speed w (driven by torque K*i, opposed by
# friction b*w) -- rather than one opaque StateSpace/TransferFunction
# block, so every physical parameter shows up as its own named,
# variable-bound block in the diagram.
#
# Every Gain/Constant below that represents one of R/L/K/J/b is bound via
# var(name) -- typing the name directly into that block's own parameter
# field in the GUI does exactly the same thing (see the Scripting API
# help tab's "Workspace & Utilities" section).

print("=== Building DC Motor block diagram ===")

if not all(name in globals() for name in ("R", "L", "K", "J", "b")):
    print("Missing identified parameters -- run 1_dc_motor_identification.py first.")
else:
    new_diagram()  # a fresh, empty diagram -- no need to open one by hand first

    # --- Voltage source: a step to V_step at t=0 (Constant is DC, so it's
    # already a step from the simulation's very first instant) ---
    add_block('Constant', name='V_src', position=(0, 150))
    set_param('V_src', 'Value', 12.0)

    # --- Electrical loop: L*di/dt = V - R*i - K*w ---
    add_block('Gain', name='Gain_R', position=(200, 250))       # R * i
    set_param('Gain_R', 'Gain', var('R'))
    add_block('Gain', name='Invert_R', position=(350, 250))     # -> -R*i
    set_param('Invert_R', 'Gain', -1.0)

    add_block('Sum', name='Sum_elec1', position=(500, 150))     # V + (-R*i)
    add_block('Gain', name='Gain_K_bemf', position=(200, 350))  # K * w  (back-EMF)
    set_param('Gain_K_bemf', 'Gain', var('K'))
    add_block('Gain', name='Invert_K', position=(350, 350))     # -> -K*w
    set_param('Invert_K', 'Gain', -1.0)

    add_block('Sum', name='Sum_elec2', position=(650, 250))     # -> V - R*i - K*w

    add_block('Constant', name='L_const', position=(650, 400))
    set_param('L_const', 'Value', var('L'))
    add_block('Divide', name='Divide_L', position=(800, 300))   # -> (V-Ri-Kw)/L
    add_block('Integrator', name='Integrator_i', position=(950, 300))  # -> i

    # --- Mechanical loop: J*dw/dt = K*i - b*w  (T_load = 0, no load) ---
    add_block('Gain', name='Gain_K_torque', position=(1100, 150))  # K * i
    set_param('Gain_K_torque', 'Gain', var('K'))
    add_block('Gain', name='Gain_b', position=(1100, 450))         # b * w
    set_param('Gain_b', 'Gain', var('b'))
    add_block('Gain', name='Invert_b', position=(1250, 450))       # -> -b*w
    set_param('Invert_b', 'Gain', -1.0)

    add_block('Sum', name='Sum_mech', position=(1400, 300))     # -> K*i - b*w

    add_block('Constant', name='J_const', position=(1400, 450))
    set_param('J_const', 'Value', var('J'))
    add_block('Divide', name='Divide_J', position=(1550, 350))  # -> (Ki-bw)/J
    add_block('Integrator', name='Integrator_w', position=(1700, 350))  # -> w

    # --- Scopes ---
    add_block('Scope', name='Scope_i', position=(1100, 300))
    add_block('Scope', name='Scope_w', position=(1850, 350))

    # --- Wiring: electrical loop ---
    add_line('V_src', 'Sum_elec1', dst_port='in1')
    add_line('Integrator_i', 'Gain_R')
    add_line('Gain_R', 'Invert_R')
    add_line('Invert_R', 'Sum_elec1', dst_port='in2')
    add_line('Sum_elec1', 'Sum_elec2', dst_port='in1')
    add_line('Integrator_w', 'Gain_K_bemf')
    add_line('Gain_K_bemf', 'Invert_K')
    add_line('Invert_K', 'Sum_elec2', dst_port='in2')
    add_line('Sum_elec2', 'Divide_L', dst_port='num')
    add_line('L_const', 'Divide_L', dst_port='den')
    add_line('Divide_L', 'Integrator_i')
    add_line('Integrator_i', 'Scope_i')

    # --- Wiring: mechanical loop ---
    add_line('Integrator_i', 'Gain_K_torque')
    add_line('Integrator_w', 'Gain_b')
    add_line('Gain_b', 'Invert_b')
    add_line('Gain_K_torque', 'Sum_mech', dst_port='in1')
    add_line('Invert_b', 'Sum_mech', dst_port='in2')
    add_line('Sum_mech', 'Divide_J', dst_port='num')
    add_line('J_const', 'Divide_J', dst_port='den')
    add_line('Divide_J', 'Integrator_w')
    add_line('Integrator_w', 'Scope_w')

    print("Diagram built. Running a 1.5s step-response simulation...")
    result = sim(duration=1.5, dt=2e-4)
    if result is not None:
        i_final = result["scopes"]["Scope_i"]["data"][-1]
        w_final = result["scopes"]["Scope_w"]["data"][-1]
        print(f"Steady-state current i(inf) ~= {i_final:.3f} A")
        print(f"Steady-state speed   w(inf) ~= {w_final:.2f} rad/s")

    save_diagram("DC_Motor.json")  # written into the current Project Folder
