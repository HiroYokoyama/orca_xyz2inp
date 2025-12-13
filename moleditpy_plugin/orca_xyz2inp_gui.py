import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QSpinBox, QFileDialog, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt
from rdkit import Chem

PLUGIN_NAME = "ORCA xyz2inp GUI"

class OrcaInputDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.setWindowTitle(PLUGIN_NAME)
        self.main_window = main_window
        self.resize(400, 250) # 出力欄が減ったので少しコンパクトに
        self.setup_ui()
        self.load_defaults()

    def setup_ui(self):
        layout = QVBoxLayout()

        # --- Form Layout for Settings ---
        form_layout = QFormLayout()

        # 1. Template File Selection (*.tmplt)
        self.le_template = QLineEdit()
        self.btn_template = QPushButton("Browse...")
        self.btn_template.clicked.connect(self.browse_template)
        
        h_template = QHBoxLayout()
        h_template.addWidget(self.le_template)
        h_template.addWidget(self.btn_template)
        h_template.addWidget(self.btn_template)
        form_layout.addRow("Template File:", h_template)

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
        # 環境変数の読み込み
        if "orca_xyz2inp_nprocs" in os.environ:
            try:
                val = int(os.environ["orca_xyz2inp_nprocs"])
                self.sb_nprocs.setValue(val)
            except ValueError:
                pass
        
        if "orca_xyz2inp_maxcore" in os.environ:
            try:
                val = int(os.environ["orca_xyz2inp_maxcore"])
                self.sb_maxcore.setValue(val)
            except ValueError:
                pass

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

    def browse_template(self):
        # 拡張子フィルタを .tmplt 優先に変更
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Template", "", "ORCA Template (*.tmplt);;Text Files (*.txt *.inp);;All Files (*)"
        )
        if path:
            self.le_template.setText(path)

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
        if hasattr(self.main_window, 'current_file_path') and self.main_window.current_file_path:
             base_name = os.path.splitext(os.path.basename(self.main_window.current_file_path))[0]
             default_name = f"{base_name}{suffix}.inp"
        else:
             default_name = f"orca_input{suffix}.inp"

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save ORCA Input File", default_name, "ORCA Input (*.inp)"
        )
        
        if not output_path:
            return # キャンセル時は何もしない

        # 3. ファイル生成処理
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

def run(main_window):
    """Entry point for the plugin"""
    if not hasattr(main_window, 'current_mol') or not main_window.current_mol:
        QMessageBox.warning(main_window, PLUGIN_NAME, "No molecule loaded.")
        return

    dialog = OrcaInputDialog(main_window)
    dialog.exec()
