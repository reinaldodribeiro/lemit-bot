import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("lemit_bot.checkpoint")


class CheckpointManager:
    def __init__(self, checkpoint_dir: Path, input_file: Path):
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._path = checkpoint_dir / "checkpoint.json"
        self._input_file = input_file
        self._input_hash = self._hash_file(input_file)
        self._data = self._load()

    def _hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _load(self) -> dict:
        empty = {
            "input_file": self._input_file.name,
            "input_hash": self._input_hash,
            "processed_rows": {},
        }

        if not self._path.exists():
            return empty

        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            log.warning("Checkpoint corrompido, iniciando do zero")
            return empty

        if data.get("input_hash") != self._input_hash:
            log.warning("Planilha modificada desde o ultimo checkpoint")
            return self._ask_hash_mismatch(data, empty)

        count = len(data.get("processed_rows", {}))
        if count > 0:
            log.info("Checkpoint: %d linhas ja processadas", count)

        return data

    def _ask_hash_mismatch(self, old: dict, empty: dict) -> dict:
        from rich.console import Console

        console = Console()
        old_count = len(old.get("processed_rows", {}))
        console.print(
            f"\n[yellow]Aviso:[/yellow] a planilha foi modificada desde a última execução.\n"
            f"  Checkpoint anterior: {old.get('input_file')} ({old_count} linhas processadas)\n"
        )
        console.print("  [cyan]1[/cyan] - Iniciar do zero (reprocessar tudo)")
        console.print("  [cyan]2[/cyan] - Manter checkpoint mesmo assim\n")

        while True:
            try:
                choice = console.input("Escolha [1/2]: ").strip()
                if choice == "1":
                    return empty
                if choice == "2":
                    old["input_hash"] = self._input_hash
                    return old
            except (EOFError, KeyboardInterrupt):
                return empty

    def is_processed(self, row_index: int) -> bool:
        return str(row_index) in self._data.get("processed_rows", {})

    def mark_done(self, row_index: int, status: str) -> None:
        self._data["processed_rows"][str(row_index)] = {
            "status": status,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._save()

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def processed_count(self) -> int:
        return len(self._data.get("processed_rows", {}))

    def clear(self) -> None:
        self._data = {
            "input_file": self._input_file.name,
            "input_hash": self._input_hash,
            "processed_rows": {},
        }
        self._save()
        log.info("Checkpoint limpo")
