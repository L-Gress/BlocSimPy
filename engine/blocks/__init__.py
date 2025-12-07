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
from .product import Product
from .divide import Divide
from .input_port import InputPort
from .output_port import OutputPort
from .subgraph import SubGraph

BLOCK_REGISTRY = {
    "SineWave": SineWave,
    "Gain": Gain,
    "Sum": Sum,
    "Integrator": Integrator,
    "LookupTable": LookupTable,
    "Scope": Scope,
    "Constant": Constant,
    "TransferFunction": TransferFunction,
    "PID": PID,
    "Clock": Clock,
    "IfElse": IfElse,
    "LogicalOperator": LogicalOperator,
    "Product": Product,
    "Divide": Divide,
    "InputPort": InputPort,
    "OutputPort": OutputPort,
    "SubGraph": SubGraph,

}


