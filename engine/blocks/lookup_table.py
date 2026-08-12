from ..models import BlockModel
from ..variables import variable_ref_name, make_variable_ref
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                               QPushButton, QCheckBox, QLabel, QLineEdit,
                               QDialogButtonBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt
import csv


class LookupTableDialog(QDialog):
    """Dialog to edit LookupTable data with dynamic rows and CSV import, or
    -- via "Bind entire table to a variable" -- bind the whole X/Y table to
    a global variable instead (see engine/variables.py), e.g. one holding a
    list of (x, y) pairs built by a Script. Resolution doesn't care what
    shape a bound variable's value is, so this needs no engine changes,
    same as StateSpace's matrix/vector params. Just type the variable's
    name -- no picker -- same as ParamValueEditor."""
    def __init__(self, parent=None, table_data=None):
        super().__init__(parent)

        self.setWindowTitle("Edit Lookup Table")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        bound_name = variable_ref_name(table_data)

        bind_row = QHBoxLayout()
        self.bind_check = QCheckBox("Bind entire table to a global variable named:")
        self.bind_check.setChecked(bound_name is not None)
        bind_row.addWidget(self.bind_check)
        self.var_name_edit = QLineEdit(bound_name or "")
        bind_row.addWidget(self.var_name_edit, 1)
        layout.addLayout(bind_row)
        layout.addWidget(QLabel(
            "The variable's value should be a list of (x, y) pairs -- e.g. "
            "Curve = [(0, 0), (1, 1), (2, 4)]."
        ))

        # Table widget for editing rows
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["X", "Y"])
        layout.addWidget(self.table_widget)

        # Load data or create empty table
        if bound_name is None and table_data:
            self.load_table_data(table_data)
        else:
            self.add_row()

        # Buttons for row management
        btn_layout = QVBoxLayout()

        btn_add = QPushButton("Add Row")
        btn_add.clicked.connect(self.add_row)
        btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("Remove Row")
        btn_remove.clicked.connect(self.remove_row)
        btn_layout.addWidget(btn_remove)

        btn_load_csv = QPushButton("Load CSV")
        btn_load_csv.clicked.connect(self.load_csv)
        btn_layout.addWidget(btn_load_csv)

        layout.addLayout(btn_layout)
        self._row_editors = [self.table_widget, btn_add, btn_remove, btn_load_csv]

        self.bind_check.toggled.connect(self._on_bind_toggled)
        self._on_bind_toggled(self.bind_check.isChecked())

        # OK/Cancel buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_bind_toggled(self, checked):
        self.var_name_edit.setVisible(checked)
        for widget in self._row_editors:
            widget.setVisible(not checked)

    def load_table_data(self, table_data):
        """Load table data into the widget."""
        if isinstance(table_data, list) and table_data:
            if isinstance(table_data[0], (tuple, list)):
                self.table_widget.setRowCount(len(table_data))
                for i, (x, y) in enumerate(table_data):
                    x_item = QTableWidgetItem(str(x))
                    y_item = QTableWidgetItem(str(y))
                    self.table_widget.setItem(i, 0, x_item)
                    self.table_widget.setItem(i, 1, y_item)

    def add_row(self):
        """Add a new row to the table."""
        row = self.table_widget.rowCount()
        self.table_widget.insertRow(row)
        self.table_widget.setItem(row, 0, QTableWidgetItem("0.0"))
        self.table_widget.setItem(row, 1, QTableWidgetItem("0.0"))

    def remove_row(self):
        """Remove the selected row."""
        current_row = self.table_widget.currentRow()
        if current_row >= 0:
            self.table_widget.removeRow(current_row)

    def load_csv(self):
        """Load data from a CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            self.table_widget.setRowCount(0)
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header if present
                for row in reader:
                    if len(row) >= 2:
                        x, y = row[0].strip(), row[1].strip()
                        self.add_row()
                        current_row = self.table_widget.rowCount() - 1
                        self.table_widget.setItem(current_row, 0, QTableWidgetItem(x))
                        self.table_widget.setItem(current_row, 1, QTableWidgetItem(y))
            QMessageBox.information(self, "Success", f"Loaded {self.table_widget.rowCount()} rows from CSV.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load CSV: {str(e)}")

    def get_table_data(self):
        """Return table data as list of tuples."""
        data = []
        for i in range(self.table_widget.rowCount()):
            try:
                x = float(self.table_widget.item(i, 0).text())
                y = float(self.table_widget.item(i, 1).text())
                data.append((x, y))
            except (ValueError, AttributeError):
                pass
        return data if data else [(0.0, 0.0)]

    def get_value(self):
        """The "Table" param's new value -- a variable reference if bound
        (see engine/variables.py), else the edited row data."""
        if self.bind_check.isChecked():
            return make_variable_ref(self.var_name_edit.text().strip())
        return self.get_table_data()


class LookupTable(BlockModel):
    """Linear interpolation 1D with editable table and CSV support."""
    
    BLOCK_INFO = {
        "description": "Maps input values to output using linear interpolation",
        "parameters": "Table data (X-Y pairs), supports CSV import",
        "formula": "Output = interp(Input, X_data, Y_data)",
        "usage": "Implement nonlinear functions, calibration curves, or empirical data",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("LookupTable")
        self.add_input("in")
        self.add_output("out")
        # Store as list of tuples for better flexibility
        self.add_param("Table", [(0.0, 0.0), (1.0, 1.0), (2.0, 4.0), (3.0, 9.0)])

    def compute(self, t, dt, context=None):
        try:
            table = self.params["Table"]
            if isinstance(table, str):
                # Legacy support: parse string format
                xs = np.fromstring(table.split('|')[0], sep=',')
                ys = np.fromstring(table.split('|')[1], sep=',')
            else:
                # New format: list of tuples
                table = list(table) if not isinstance(table, list) else table
                if table:
                    xs, ys = zip(*table)
                    xs = np.array(xs)
                    ys = np.array(ys)
                else:
                    self.outputs["out"].value = 0.0
                    return

            inp = self.inputs["in"].value
            self.outputs["out"].value = np.interp(inp, xs, ys)
        except Exception as e:
            self.outputs["out"].value = 0.0

    def get_editor_dialog(self, parent=None):
        """Return a custom dialog for editing the lookup table."""
        dialog = LookupTableDialog(parent, self.params.get("Table", []))

        # Intercept accept to save data back to the block
        original_accept = dialog.accept

        def accept_with_save():
            self.params["Table"] = dialog.get_value()
            original_accept()

        dialog.accept = accept_with_save
        return dialog


