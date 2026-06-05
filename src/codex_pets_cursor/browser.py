from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .paths import DOWNLOADS_DIR

try:
    from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineScript
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ModuleNotFoundError:  # pragma: no cover - depends on optional distro package
    QWebEngineDownloadRequest = None
    QWebEngineScript = None
    QWebEngineView = None


class BrowserPage(QWidget):
    downloaded = pyqtSignal(Path)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        if QWebEngineView is None:
            label = QLabel("Install python-pyqt6-webengine to browse Codex-Pets.net inside the app.")
            label.setWordWrap(True)
            layout.addWidget(label)
            return

        self.view = QWebEngineView()
        profile = self.view.page().profile()
        self._install_site_compat_script(profile)
        profile.downloadRequested.connect(self._download_requested)
        self.view.setUrl(QUrl("https://codex-pets.net/"))
        layout.addWidget(self.view)

    def _install_site_compat_script(self, profile) -> None:
        if QWebEngineScript is None:
            return
        script = QWebEngineScript()
        script.setName("codex-pets-net-compat")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        script.setSourceCode(
            """
            if (typeof window.__name !== "function") {
              window.__name = function(fn, name) {
                try { Object.defineProperty(fn, "name", { value: name, configurable: true }); } catch (e) {}
                return fn;
              };
            }
            """
        )
        profile.scripts().insert(script)

    def _download_requested(self, download) -> None:
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        filename = download.downloadFileName() or f"codex-pet-{int(time.time())}.zip"
        if not filename.endswith(".zip"):
            filename = f"{filename}.zip"
        target = DOWNLOADS_DIR / filename
        download.setDownloadDirectory(str(DOWNLOADS_DIR))
        download.setDownloadFileName(filename)
        download.accept()
        download.stateChanged.connect(lambda state, path=target: self._state_changed(download, path))

    def _state_changed(self, download, path: Path) -> None:
        if QWebEngineDownloadRequest is None:
            return
        if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.downloaded.emit(path)
