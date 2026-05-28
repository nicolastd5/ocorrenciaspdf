from PySide6.QtCore import QObject, Signal

from auto_update import check_and_update


class UpdateWorker(QObject):
    progress = Signal(int, int)   # (baixado, total) — total=0 => indeterminado
    status = Signal(str)          # "verificando" | "baixando" | "reiniciando" | "erro"
    finished = Signal()

    def run(self) -> None:
        try:
            self.status.emit("verificando")
            check_and_update(
                on_progress=lambda baixado, total: self.progress.emit(baixado, total),
                on_status=lambda estado: self.status.emit(estado),
            )
        finally:
            self.finished.emit()
