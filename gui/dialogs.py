from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QTextEdit, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class SimulationSettingsDialog(QDialog):
    """Dialog to set Simulation Duration and Time Step."""
    def __init__(self, parent=None, current_duration=10.0, current_dt=0.01):
        super().__init__(parent)
        self.setWindowTitle("Simulation Settings")
        self.resize(300, 150)

        layout = QFormLayout(self)

        self.dur_edit = QLineEdit(str(current_duration))
        self.dt_edit = QLineEdit(str(current_dt))

        layout.addRow("Duration (s):", self.dur_edit)
        layout.addRow("Time Step (s):", self.dt_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self):
        try:
            dur = float(self.dur_edit.text())
            dt = float(self.dt_edit.text())
            if dt <= 0 or dur <= 0:
                raise ValueError("Values must be positive")
            return dur, dt
        except ValueError:
            return None, None


class HelpDialog(QDialog):
    """Enhanced help dialog with searchable block reference."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help - BlocSimPy Block Reference")
        self.resize(900, 700)
        
        # Load block descriptions dynamically from block classes
        self.block_descriptions = self._load_block_descriptions()
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📚 BlocSimPy - Block Reference & Help")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Search bar
        search_layout = QVBoxLayout()
        search_label = QLabel("🔍 Search Blocks:")
        search_label_font = search_label.font()
        search_label_font.setBold(True)
        search_label.setFont(search_label_font)
        search_layout.addWidget(search_label)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Type block name or keyword to filter...")
        self.search_bar.textChanged.connect(self._filter_blocks)
        search_layout.addWidget(self.search_bar)
        layout.addLayout(search_layout)
        
        # Block reference area
        self.reference_text = QTextEdit()
        self.reference_text.setReadOnly(True)
        layout.addWidget(self.reference_text)
        
        # Show all blocks initially
        self._update_reference("")
        
        # Quick start guide
        guide_label = QLabel("💡 Quick Start:")
        guide_label_font = guide_label.font()
        guide_label_font.setBold(True)
        guide_label.setFont(guide_label_font)
        layout.addWidget(guide_label)
        
        guide_text = QTextEdit()
        guide_text.setReadOnly(True)
        guide_text.setMaximumHeight(120)
        guide_text.setPlainText(
            "1. Drag blocks from Library to scene  |  2. Connect output ports to input ports\n"
            "3. Double-click blocks to edit parameters  |  4. Set simulation settings in toolbar\n"
            "5. Run simulation  |  6. Double-click Scope blocks to view results\n"
            "7. Use SubGraphs (double-click to enter) for hierarchical designs  |  8. Save/Load your designs"
        )
        layout.addWidget(guide_text)
        
        # Close button
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)
    
    def _load_block_descriptions(self):
        """Load block descriptions from each block's BLOCK_INFO attribute."""
        from engine.blocks import BLOCK_REGISTRY
        
        descriptions = {}
        for block_name, block_class in BLOCK_REGISTRY.items():
            if hasattr(block_class, 'BLOCK_INFO'):
                descriptions[block_name] = block_class.BLOCK_INFO
            else:
                # Default info if block doesn't have BLOCK_INFO yet
                descriptions[block_name] = {
                    "description": f"{block_name} block",
                    "parameters": "See block properties",
                    "formula": "Not documented yet",
                    "usage": "Documentation pending"
                }
        return descriptions
    
    def _filter_blocks(self, search_text):
        """Filter blocks based on search text."""
        self._update_reference(search_text.lower())
    
    def _update_reference(self, search_text):
        """Update the reference text with filtered blocks."""
        html_content = "<html><body style='font-family: Arial, sans-serif;'>"
        
        # Sort blocks alphabetically
        sorted_blocks = sorted(self.block_descriptions.items())
        
        matched_count = 0
        for block_name, info in sorted_blocks:
            # Filter based on search
            if search_text:
                searchable = f"{block_name} {info['description']} {info['usage']}".lower()
                if search_text not in searchable:
                    continue
            
            matched_count += 1
            
            # Format each block entry
            html_content += f"""
            <div style='margin-bottom: 20px; padding: 10px; background-color: #f5f5f5; border-left: 4px solid #2E86AB;'>
                <h3 style='margin: 0 0 8px 0; color: #2E86AB;'>🔷 {block_name}</h3>
                <p style='margin: 5px 0;'><b>Description:</b> {info['description']}</p>
                <p style='margin: 5px 0;'><b>Parameters:</b> {info['parameters']}</p>
                <p style='margin: 5px 0;'><b>Formula:</b> <code style='background-color: #e0e0e0; padding: 2px 6px; border-radius: 3px;'>{info['formula']}</code></p>
                <p style='margin: 5px 0;'><b>Usage:</b> <i>{info['usage']}</i></p>
            </div>
            """
        
        if matched_count == 0:
            html_content += "<p style='text-align: center; color: #666; margin-top: 50px;'>❌ No blocks found matching your search.</p>"
        
        html_content += "</body></html>"
        self.reference_text.setHtml(html_content)
