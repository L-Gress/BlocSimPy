from .sine_wave import SineWave
from .gain import Gain
from .sum_block import Sum
from .integrator import Integrator
from .lookup_table import LookupTable
from .scope import Scope
from .constant import Constant
from .transfer_function import TransferFunction
from .pid import PID
from .clock import Clock
from .if_else import IfElse
from .logical_operator import LogicalOperator
from .relational_operator import RelationalOperator
from .product import Product
from .divide import Divide
from .input_port import InputPort
from .output_port import OutputPort
from .subgraph import SubGraph
from .delay import Delay
from .abs import Abs
from .max import Max
from .min import Min
from .modulo import Modulo
from .saturation import Saturation
from .ramp import Ramp
from .switch import Switch
from .derivative import Derivative
from .math_func import MathFunction
from .mux import Mux
from .demux import Demux
from .bus_creator import BusCreator
from .bus_selector import BusSelector
from .dead_zone import DeadZone
from .rate_limiter import RateLimiter
from .quantizer import Quantizer
from .backlash import Backlash
from .state_space import StateSpace
from .discrete_transfer_function import DiscreteTransferFunction
from .python_function import PythonFunction

BLOCK_REGISTRY = {
    "SineWave": SineWave,
    "Constant": Constant,
    "Gain": Gain,
    "Integrator": Integrator,
    "TransferFunction": TransferFunction,
    "PID": PID,
    "Scope": Scope,
    "Clock": Clock,
    "LookupTable": LookupTable,
    "Sum": Sum,
    "Product": Product,
    "Divide": Divide,
    "Modulo": Modulo,
    "LogicalOperator": LogicalOperator,
    "RelationalOperator": RelationalOperator,
    "IfElse": IfElse,
    "SubGraph": SubGraph,
    "InputPort": InputPort,
    "OutputPort": OutputPort,
    "Delay": Delay,
    "Abs": Abs,
    "MathFunction": MathFunction,
    "Max": Max,
    "Min": Min,
    "Saturation": Saturation,
    "Ramp": Ramp,
    "Switch": Switch,
    "Derivative": Derivative,
    "Mux": Mux,
    "Demux": Demux,
    "BusCreator": BusCreator,
    "BusSelector": BusSelector,
    "DeadZone": DeadZone,
    "RateLimiter": RateLimiter,
    "Quantizer": Quantizer,
    "Backlash": Backlash,
    "StateSpace": StateSpace,
    "DiscreteTransferFunction": DiscreteTransferFunction,
    "PythonFunction": PythonFunction,
}
