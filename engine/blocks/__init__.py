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
from .audio_input import AudioInput
from .audio_output import AudioOutput
from .delay import Delay
from .abs import Abs
from .max import Max
from .min import Min
from .rest_input import RestInput
from .rest_output import RestOutput
from .modulo import Modulo
from .audio_record import AudioRecord

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
    "AudioRecord": AudioRecord,
    "LogicalOperator": LogicalOperator,
    "RelationalOperator": RelationalOperator,
    "IfElse": IfElse,
    "SubGraph": SubGraph,
    "InputPort": InputPort,
    "OutputPort": OutputPort,
    "AudioInput": AudioInput,
    "AudioOutput": AudioOutput,
    "Delay": Delay,
    "Abs": Abs,
    "Max": Max,
    "Min": Min,
    "RestInput": RestInput,
    "RestOutput": RestOutput,
}
