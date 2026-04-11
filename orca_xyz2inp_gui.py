# -*- coding: utf-8 -*-
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QHBoxLayout, QSpinBox, QMessageBox, QComboBox, QFileDialog)
from rdkit import Chem

import json
import logging

__version__="2026.04.11"
__author__="HiroYokoyama"
PLUGIN_NAME = "ORCA xyz2inp GUI"
SETTINGS_JSON = os.path.join(os.path.dirname(__file__), "orca_xyz2inp_gui.json")

class OrcaInputDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.setWindowTitle(PLUGIN_NAME)
        self.main_window = main_window
        self.resize(400, 350)
        self.setup_ui()
        self.load_defaults()

    def setup_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # 1. Template File Selection
        # Template Directory: same name as script file (without extension)
        self.template_dir = os.path.splitext(__file__)[0]
        if not os.path.exists(self.template_dir):
            try:
                os.makedirs(self.template_dir)
            except OSError:
                pass # Ignore if cannot create
        
        self.combo_template = QComboBox()
        self.combo_template.currentIndexChanged.connect(self.on_template_combo_changed)
        
        self.btn_open_dir = QPushButton("Open Dir")
        self.btn_open_dir.clicked.connect(self.open_template_dir)

        self.le_template = QLineEdit()
        self.btn_template = QPushButton("Browse...")
        self.btn_template.clicked.connect(self.browse_template)
        
        # Initial populate
        self.populate_templates()

        h_template_top = QHBoxLayout()
        h_template_top.addWidget(self.combo_template, 1)
        h_template_top.addWidget(self.btn_open_dir)
        
        h_template_btm = QHBoxLayout()
        h_template_btm.addWidget(self.le_template)
        h_template_btm.addWidget(self.btn_template)

        form_layout.addRow("Template Preset:", h_template_top)
        form_layout.addRow("Template Path:", h_template_btm)

        # 1.5. Filename Suffix
        self.le_suffix = QLineEdit()
        form_layout.addRow("Filename Suffix:", self.le_suffix)

        # 2. Parameters (Charge, Multiplicity)
        self.sb_charge = QSpinBox()
        self.sb_charge.setRange(-10, 10)
        self.sb_charge.setValue(0)
        
        self.sb_mult = QSpinBox()
        self.sb_mult.setRange(1, 10)
        self.sb_mult.setValue(1)

        form_layout.addRow("Charge:", self.sb_charge)
        form_layout.addRow("Multiplicity:", self.sb_mult)

        # 3. ORCA Resources (NProcs, MaxCore)
        self.sb_nprocs = QSpinBox()
        self.sb_nprocs.setRange(1, 128)
        self.sb_nprocs.setValue(1)

        self.sb_maxcore = QSpinBox()
        self.sb_maxcore.setRange(100, 100000)
        self.sb_maxcore.setSingleStep(100)
        self.sb_maxcore.setValue(1000)
        self.sb_maxcore.setSuffix(" MB")

        form_layout.addRow("NProcs:", self.sb_nprocs)
        form_layout.addRow("MaxCore:", self.sb_maxcore)

        layout.addLayout(form_layout)

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_generate = QPushButton("Generate Input")
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self.generate_file) # ここで保存ダイアログを開く
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_generate)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_defaults(self):
        # 1. Load from JSON
        defaults = {"nprocs": 1, "maxcore": 1000}
        if os.path.exists(SETTINGS_JSON):
            try:
                with open(SETTINGS_JSON, 'r') as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}")

        # 2. Override with Environment Variables
        if "orca_xyz2inp_nprocs" in os.environ:
            try:
                defaults["nprocs"] = int(os.environ["orca_xyz2inp_nprocs"])
            except ValueError as _e:
                logging.warning("[orca_xyz2inp_gui.py:124] silenced: %s", _e)
        
        if "orca_xyz2inp_maxcore" in os.environ:
            try:
                defaults["maxcore"] = int(os.environ["orca_xyz2inp_maxcore"])
            except ValueError as _e:
                logging.warning("[orca_xyz2inp_gui.py:129] silenced: %s", _e)

        # 3. Set UI
        self.sb_nprocs.setValue(int(defaults.get("nprocs", 1)))
        self.sb_maxcore.setValue(int(defaults.get("maxcore", 1000)))

        # 電荷と多重度の自動推測
        if hasattr(self.main_window, 'current_mol') and self.main_window.current_mol:
            mol = self.main_window.current_mol
            try:
                # Charge
                charge = Chem.GetFormalCharge(mol)
                self.sb_charge.setValue(charge)
                
                # Multiplicity
                # RDKit keeps track of radical electrons on atoms
                num_radical_electrons = sum(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms())
                multiplicity = num_radical_electrons + 1
                self.sb_mult.setValue(multiplicity)
            except Exception as e:
                print(f"Error estimating charge/multiplicity: {e}")

    def populate_templates(self):
        self.combo_template.blockSignals(True)
        self.combo_template.clear()
        
        found_templates = []
        if os.path.exists(self.template_dir):
            for f in os.listdir(self.template_dir):
                if f.lower().endswith(".tmplt"):
                    found_templates.append(f)
        
        found_templates.sort()
        self.combo_template.addItems(found_templates)
        self.combo_template.addItem("External File...")
        
        self.combo_template.blockSignals(False)
        # Trigger update of visibility/path based on initial selection
        self.on_template_combo_changed()

    def on_template_combo_changed(self):
        text = self.combo_template.currentText()
        if text == "External File...":
            self.le_template.setEnabled(True)
            self.btn_template.setEnabled(True)
            # Retain previous text if generic, or clear? Better keep it.
        else:
            self.le_template.setEnabled(False)
            self.btn_template.setEnabled(False)
            full_path = os.path.join(self.template_dir, text)
            self.le_template.setText(full_path)

    def open_template_dir(self):
        if not os.path.exists(self.template_dir):
            try:
                os.makedirs(self.template_dir)
            except:
                QMessageBox.warning(self, "Error", f"Could not create directory:\n{self.template_dir}")
                return
        try:
            os.startfile(self.template_dir)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open directory:\n{e}")

    def browse_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Template", "", "ORCA Template (*.tmplt);;Text Files (*.txt *.inp);;All Files (*)"
        )
        if path:
            self.le_template.setText(path)
            # Ensure External File is selected
            idx = self.combo_template.findText("External File...")
            if idx >= 0:
                self.combo_template.setCurrentIndex(idx)

    def generate_file(self):
        # 1. バリデーション
        template_path = self.le_template.text()
        if not template_path or not os.path.exists(template_path):
            QMessageBox.warning(self, "Error", "Template file not found.")
            return

        mol = self.main_window.current_mol
        if not mol:
            QMessageBox.warning(self, "Error", "No molecule loaded.")
            return

        # 2. 保存先ダイアログを表示 (Generateボタン押下時)
        suffix = self.le_suffix.text().strip()
        
        default_name = "orca_input.inp"
        # V3 compatibility: current_file_path is now on init_manager
        current_file_path = getattr(self.main_window.init_manager, 'current_file_path', None)
        if current_file_path:
             base_name = os.path.splitext(os.path.basename(current_file_path))[0]
             default_name = f"{base_name}{suffix}.inp"
        else:
             default_name = f"orca_input{suffix}.inp"

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save ORCA Input File", default_name, "ORCA Input (*.inp)"
        )
        
        if not output_path:
            return # キャンセル時は何もしない

        # 3. Saving Settings
        try:
             settings_to_save = {
                 "nprocs": self.sb_nprocs.value(),
                 "maxcore": self.sb_maxcore.value()
             }
             with open(SETTINGS_JSON, 'w') as f:
                 json.dump(settings_to_save, f)
        except Exception as e:
             print(f"Warning: Could not save settings: {e}")

        # 4. ファイル生成処理
        try:
            # パラメータ取得
            charge = self.sb_charge.value()
            mult = self.sb_mult.value()
            nprocs = self.sb_nprocs.value()
            maxcore = self.sb_maxcore.value()

            # テンプレート読み込み
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read().strip()

            # 座標データの作成
            xyz_block = Chem.MolToXYZBlock(mol)
            xyz_lines = xyz_block.strip().split('\n')
            # 1,2行目(原子数/コメント)をスキップ
            coords_data = "\n".join(xyz_lines[2:]) if len(xyz_lines) > 2 else ""

            # 書き込み
            with open(output_path, 'w', encoding='utf-8') as out:
                out.write(f"# Generated by MoleditPy ({PLUGIN_NAME})\n")
                out.write(f"%pal nprocs {nprocs} end\n")
                out.write(f"%MaxCore {maxcore}\n\n")
                out.write(f"{template_content}\n\n")
                out.write(f"* xyz {charge} {mult}\n")
                out.write(f"{coords_data}\n")
                out.write("*\n")

            QMessageBox.information(self, "Success", f"Input file generated:\n{output_path}")
            self.accept() # ダイアログを閉じる

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate file:\n{str(e)}")

def run_plugin(context):
    mw = context.get_main_window()
    if not context.current_mol:
        QMessageBox.warning(mw, PLUGIN_NAME, "No molecule loaded.")
        return

    dialog = OrcaInputDialog(mw)
    dialog.exec()

def initialize(context):
    """Initialize the ORCA Input Generator plugin."""
    context.add_export_action("ORCA xyz2inp...", lambda: run_plugin(context))

def run(mw):
    if not hasattr(mw, 'plugin_manager'):
        return

    from moleditpy.plugins.plugin_interface import PluginContext
    context = PluginContext(mw.plugin_manager, PLUGIN_NAME)
    if not context:
        context = PluginContext(mw.plugin_manager, PLUGIN_NAME)

    run_plugin(context)
