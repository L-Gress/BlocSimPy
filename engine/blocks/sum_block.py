from ..models import BlockModel


class Sum(BlockModel):
    def __init__(self):
        super().__init__("Sum")
        self.add_input("in1")
        self.add_input("in2")
        self.add_output("out")

    def compute(self, t, dt):
        self.outputs["out"].value = self.inputs["in1"].value + self.inputs["in2"].value

    def get_editor_dialog(self, parent=None):
        """Sum has no parameters, return None."""
        return None
