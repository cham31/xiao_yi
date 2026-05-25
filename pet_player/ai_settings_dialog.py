"""
AI API 配置窗口。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pet_player.ai_config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AiApiConfig,
    config_path,
    load_ai_config,
    masked_key,
    save_ai_config,
    test_ai_config,
)


class _ApiTestWorker(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(self, config: AiApiConfig):
        super().__init__()
        self._config = config

    def run(self) -> None:
        ok, message = test_ai_config(self._config)
        self.finished.emit(ok, message)


class AiSettingsDialog(QDialog):
    """大模型 API 设置弹窗"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI API 设置")
        self.setMinimumWidth(460)

        self._thread: QThread | None = None
        self._worker: _ApiTestWorker | None = None

        self._provider = QComboBox()
        self._provider.addItems(["deepseek", "custom"])

        self._base_url = QLineEdit()
        self._model = QLineEdit()
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._timeout = QSpinBox()
        self._timeout.setRange(5, 300)
        self._timeout.setSuffix(" 秒")

        self._status = QTextEdit()
        self._status.setReadOnly(True)
        self._status.setFixedHeight(96)

        self._test_button = QPushButton("测试连接")
        self._reset_button = QPushButton("DeepSeek 默认")
        self._toggle_key_button = QPushButton("显示 Key")

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )

        self._build_layout()
        self._wire_signals()
        self._load()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("提供商", self._provider)
        form.addRow("Base URL", self._base_url)
        form.addRow("模型", self._model)

        key_row = QHBoxLayout()
        key_row.addWidget(self._api_key, 1)
        key_row.addWidget(self._toggle_key_button)
        form.addRow("API Key", key_row)
        form.addRow("超时", self._timeout)

        actions = QHBoxLayout()
        actions.addWidget(self._reset_button)
        actions.addStretch(1)
        actions.addWidget(self._test_button)

        hint = QLabel(f"配置文件: {config_path()}")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(hint)
        root.addLayout(actions)
        root.addWidget(self._status)
        root.addWidget(self._buttons)

    def _wire_signals(self) -> None:
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._reset_button.clicked.connect(self._reset_deepseek)
        self._test_button.clicked.connect(self._test_connection)
        self._toggle_key_button.clicked.connect(self._toggle_key_visibility)

    def _load(self) -> None:
        cfg = load_ai_config()
        self._provider.setCurrentText(cfg.provider if cfg.provider in {"deepseek", "custom"} else "custom")
        self._base_url.setText(cfg.base_url)
        self._model.setText(cfg.model)
        self._api_key.setText(cfg.api_key)
        self._timeout.setValue(cfg.timeout_seconds)
        key_status = masked_key(cfg.api_key) if cfg.api_key else "未设置"
        self._set_status(f"已加载配置。当前 Key: {key_status}")

    def _config_from_form(self) -> AiApiConfig:
        return AiApiConfig(
            provider=self._provider.currentText().strip(),
            base_url=self._base_url.text().strip(),
            api_key=self._api_key.text().strip(),
            model=self._model.text().strip(),
            timeout_seconds=int(self._timeout.value()),
        )

    def _reset_deepseek(self) -> None:
        self._provider.setCurrentText("deepseek")
        self._base_url.setText(DEFAULT_BASE_URL)
        self._model.setText(DEFAULT_MODEL)
        self._timeout.setValue(20)
        self._set_status("已填入 DeepSeek 默认配置。API Key 需要使用你自己的 DeepSeek Key。")

    def _toggle_key_visibility(self) -> None:
        if self._api_key.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_button.setText("隐藏 Key")
        else:
            self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_button.setText("显示 Key")

    def _test_connection(self) -> None:
        cfg = self._config_from_form()
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, "配置不完整", "\n".join(errors))
            return

        self._test_button.setEnabled(False)
        self._buttons.setEnabled(False)
        self._set_status("正在测试连接...")

        self._thread = QThread(self)
        self._worker = _ApiTestWorker(cfg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_test_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_test_finished(self, ok: bool, message: str) -> None:
        self._test_button.setEnabled(True)
        self._buttons.setEnabled(True)
        self._thread = None
        self._worker = None
        prefix = "成功" if ok else "失败"
        self._set_status(f"{prefix}: {message}")

    def _set_status(self, text: str) -> None:
        self._status.setPlainText(text)

    def accept(self) -> None:
        cfg = self._config_from_form()
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, "配置不完整", "\n".join(errors))
            return
        save_ai_config(cfg)
        self._set_status(f"已保存到 {config_path()}")
        super().accept()
