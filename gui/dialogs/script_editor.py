from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextEdit, 
                               QHBoxLayout, QPushButton, QFileDialog)

class ScriptEditorDialog(QDialog):
    """Dialog to edit and run Python scripts."""
    
    def __init__(self, parent, script_manager):
        super().__init__(parent)
        self.script_manager = script_manager
        self.setWindowTitle("User Scripts")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Editor Area
        layout.addWidget(QLabel("Python Script:"))
        
        # Use Monospace font
        font = self.font()
        font.setFamily("Consolas") 
        font.setPointSize(10)
        
        self.editor = QTextEdit()
        self.editor.setFont(font)
        self.editor.setPlainText(self.script_manager.current_script)
        layout.addWidget(self.editor)
        
        # Output Area
        layout.addWidget(QLabel("Output:"))
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMaximumHeight(150)
        self.output_console.setStyleSheet(
            "background-color: #f6f6f7; color: #1d7a3c; font-family: Consolas;"
        )
        layout.addWidget(self.output_console)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self.load_script)

        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_script)

        btn_run = QPushButton("Run Script")
        btn_run.setDefault(True)  # picks up the accent-blue QPushButton:default styling
        btn_run.clicked.connect(self.run_script)
        
        btn_clear = QPushButton("Clear Output")
        btn_clear.clicked.connect(self.output_console.clear)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_run)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def load_script(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Script", "", "Python Files (*.py);;Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.editor.setPlainText(f.read())
                self.output_console.append(f"Loaded: {file_path}")
            except Exception as e:
                self.output_console.append(f"Error loading file: {e}")

    def save_script(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Script", "", "Python Files (*.py);;Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                self.output_console.append(f"Saved: {file_path}")
            except Exception as e:
                self.output_console.append(f"Error saving file: {e}")
        
    def run_script(self):
        """Execute the current script."""
        script_content = self.editor.toPlainText()
        self.script_manager.current_script = script_content # Save state
        
        result = self.script_manager.execute_script(script_content)
        self.output_console.append(">>> Execution:")
        self.output_console.append(result)
        self.output_console.append("-" * 30)
        # Scroll to bottom
        sb = self.output_console.verticalScrollBar()
        sb.setValue(sb.maximum())
