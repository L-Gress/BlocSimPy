# DC Motor Parameter Identification
# ----------------------------------
# A concrete, runnable example of BlocSimPy's scripting workflow:
#
#   1. THIS script identifies a DC motor's five physical parameters
#      (R, L, K, J, b) from synthetic bench-test data -- just as plain
#      top-level variables, which already makes them global variables
#      (a Script's/the Console's top-level names ARE the shared global
#      environment -- there's no separate store to explicitly declare
#      one into).
#   2. 2_dc_motor_diagram_builder.py then builds an actual block diagram
#      of the motor, binding each block's parameter to the SAME names
#      via var('R'), var('L'), ... -- so the diagram is always driven by
#      whatever this script most recently identified.
#
# Run this one first (toolbar Run/F5, or paste into the Console), then run
# 2_dc_motor_diagram_builder.py in the SAME session -- they share one
# persistent environment (see the Console's own banner), so the values
# declared here are still there for the second script to bind to.
#
# There's no real bench/motor here, so this generates synthetic
# "measured" data itself, from a hidden set of true parameters, by
# numerically integrating the same electrical/mechanical equations the
# real motor obeys:
#
#   L * di/dt = V - R*i - K*w        (armature electrical circuit)
#   J * dw/dt = K*i - b*w - T_load   (rotor mechanical dynamics)
#
# In a real identification you'd load i(t)/w(t) recorded from an actual
# bench test instead of simulate(); everything from "Test 1" onward is
# unchanged either way -- it only ever looks at V/i/w arrays.

print("=== DC Motor Parameter Identification ===")

# --- Ground truth, used only to synthesize fake bench data ------------
# (A real identification obviously doesn't get to see these -- they're
# here purely so this example has something to synthesize measurements
# from, and so the printed estimate-vs-truth comparison below means
# something.)
_R_true, _L_true, _K_true, _J_true, _b_true = 2.0, 0.05, 0.08, 0.0008, 0.0004

_rng = np.random.default_rng(0)


def _simulate(V_of_t, R, L, K, J, b, dt, n, lock_rotor=False, T_load=0.0):
    """Euler-integrate the motor's two coupled ODEs and return (t, i, w)
    arrays -- stands in for "read this off the oscilloscope" in a real
    identification. lock_rotor=True clamps w=0 throughout, modeling a
    bench test with the shaft physically held still (electrical dynamics
    only, no back-EMF)."""
    i = 0.0
    w = 0.0
    t = 0.0
    ts = np.empty(n)
    is_ = np.empty(n)
    ws_ = np.empty(n)
    for k in range(n):
        V = V_of_t(t)
        i += ((V - R * i - K * w) / L) * dt
        if not lock_rotor:
            w += ((K * i - b * w - T_load) / J) * dt
        ts[k] = t
        is_[k] = i
        ws_[k] = w
        t += dt
    return ts, is_, ws_


dt = 2e-4
noise_i = 0.01   # amps, measurement noise on the current sensor
noise_w = 0.5    # rad/s, measurement noise on the speed sensor

# --- Test 1: locked-rotor step (reduced voltage) -----------------------
# Shaft clamped, small step voltage applied -- current rises with the
# electrical time constant tau_e = L/R alone (no mechanical coupling).
print("\nTest 1: locked-rotor step...")
V_lr = 2.0
n_lr = 2000  # 0.4s -- several tau_e at the (unknown-to-us) true L/R
t_lr, i_lr, _ = _simulate(lambda t: V_lr, _R_true, _L_true, _K_true, _J_true, _b_true, dt, n_lr, lock_rotor=True)
i_lr = i_lr + _rng.normal(0, noise_i, size=i_lr.shape)

# R from the steady-state current (locked rotor: V = R*i at steady state).
I_lr_ss = np.mean(i_lr[int(0.9 * n_lr):])
R = V_lr / I_lr_ss

# tau_e from the early transient: V/R - i(t) = (V/R)*exp(-t/tau_e), so
# ln(V/R - i(t)) is linear in t with slope -1/tau_e. Fit only the early/
# mid part of the rise (skip near-asymptote samples, where noise swamps
# the signal) via a plain least-squares line fit.
mask = (i_lr < 0.8 * I_lr_ss) & (i_lr > 0.02 * I_lr_ss)
residual = np.clip(V_lr / R - i_lr[mask], 1e-9, None)
A = np.vstack([t_lr[mask], np.ones(mask.sum())]).T
slope, _ = np.linalg.lstsq(A, np.log(residual), rcond=None)[0]
tau_e = -1.0 / slope
L = tau_e * R

# --- Test 2: no-load step -----------------------------------------------
# Shaft free, rated voltage applied, no external load -- both electrical
# and mechanical dynamics run together.
print("Test 2: no-load step...")
V_nl = 12.0
n_nl = 5000  # 1.0s -- several mechanical time constants
t_nl, i_nl, w_nl = _simulate(lambda t: V_nl, _R_true, _L_true, _K_true, _J_true, _b_true, dt, n_nl)
i_nl = i_nl + _rng.normal(0, noise_i, size=i_nl.shape)
w_nl = w_nl + _rng.normal(0, noise_w, size=w_nl.shape)

I_nl_ss = np.mean(i_nl[int(0.9 * n_nl):])
W_nl_ss = np.mean(w_nl[int(0.9 * n_nl):])

# No-load steady state: V = R*I + K*w  and  K*I = b*w (no load torque).
K = (V_nl - R * I_nl_ss) / W_nl_ss
b = K * I_nl_ss / W_nl_ss

# tau_m from the speed transient, same log-linear trick as tau_e --
# skipping the fast initial electrical transient (a few tau_e) first,
# since the visible speed rise is dominated by the slower mechanical
# pole once that's settled.
mask2 = (t_nl > 5 * tau_e) & (w_nl < 0.85 * W_nl_ss)
residual2 = np.clip(W_nl_ss - w_nl[mask2], 1e-9, None)
A2 = np.vstack([t_nl[mask2], np.ones(mask2.sum())]).T
slope2, _ = np.linalg.lstsq(A2, np.log(residual2), rcond=None)[0]
tau_m = -1.0 / slope2
J = tau_m * (b + K**2 / R)

# R, L, K, J, b above are already global variables -- plain top-level
# names in this Script's environment ARE the shared global environment
# (see the module docstring) -- so there's nothing further to do to
# "store" them. 2_dc_motor_diagram_builder.py binds its blocks to these
# SAME names via var('R'), var('L'), etc.

print("\nIdentified parameters (now global variables):")
print(f"  R (armature resistance)      = {R:.4f}  ohm   (true {_R_true})")
print(f"  L (armature inductance)      = {L:.4f}  H     (true {_L_true})")
print(f"  K (torque/back-EMF constant) = {K:.4f}  N.m/A (true {_K_true})")
print(f"  J (rotor inertia)            = {J:.6f}  kg.m2 (true {_J_true})")
print(f"  b (viscous friction)         = {b:.6f}  N.m.s (true {_b_true})")
print("\nDone -- now run 2_dc_motor_diagram_builder.py to build the motor")
print("diagram parametrized by these exact values.")
