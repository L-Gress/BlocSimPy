"""Simulation Configuration Constants."""


class SimConfig:
    """Centralized simulation configuration."""
    
    # Default Parameters
    DEFAULT_DURATION = 10.0  # seconds
    DEFAULT_TIMESTEP = 0.01  # seconds
    
    # Validation
    MIN_TIMESTEP = 1e-6
    MAX_TIMESTEP = 1.0
    MIN_DURATION = 0.001
    MAX_DURATION = 1e6
