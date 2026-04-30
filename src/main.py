import logging
import sys
from pathlib import Path

# Ensure src/ is on sys.path when running as `python src/main.py`
sys.path.insert(0, str(Path(__file__).parent))

from utils import get_exe_dir, setup_playwright_env

# Must be called before Playwright is imported/started
setup_playwright_env()

from rich.console import Console

from config import load_config
from excel_io.checkpoint import CheckpointManager
from excel_io.input_reader import get_input_file, read_rows
from excel_io.output_writer import OutputWriter
from logger import setup_logging
from session import LemitSession
import orchestrator

console = Console()


def main() -> None:
    base_dir = get_exe_dir()

    # Minimal logging until config is loaded
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    console.print("[bold blue]╔══════════════════════════╗[/bold blue]")
    console.print("[bold blue]║    Lemit Dados Bot       ║[/bold blue]")
    console.print("[bold blue]╚══════════════════════════╝[/bold blue]\n")

    # --- Load config ---
    try:
        config = load_config(base_dir / "config.json")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]Erro de configuração:[/bold red] {e}")
        _pause_exit(1)

    # --- Setup logging ---
    log_dir = base_dir / "logs"
    setup_logging(log_dir)
    log = logging.getLogger("lemit_bot.main")
    log.info("Bot iniciado. Base: %s", base_dir)

    # --- Find and read input file ---
    input_folder = base_dir / config.bot.input_folder
    try:
        input_file = get_input_file(input_folder)
        console.print(f"Planilha: [cyan]{input_file.name}[/cyan]")

        rows = read_rows(input_file, config.excel.cpf_column, config.excel.name_column)
        if not rows:
            console.print("[yellow]Nenhuma linha encontrada na planilha.[/yellow]")
            _pause_exit(0)

        console.print(f"Total de registros: [cyan]{len(rows)}[/cyan]\n")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]Erro na planilha:[/bold red] {e}")
        _pause_exit(1)

    # --- Checkpoint and output ---
    checkpoint_dir = base_dir / "checkpoint"
    checkpoint = CheckpointManager(checkpoint_dir, input_file)

    output_dir = base_dir / config.bot.output_folder
    output_writer = OutputWriter(output_dir, config.excel.whatsapp_template)

    # --- Browser session ---
    session = LemitSession(config, state_path=checkpoint_dir / "auth_state.json")
    try:
        try:
            session.start()
        except RuntimeError as e:
            console.print(f"[bold red]Erro de login:[/bold red] {e}")
            log.error("Falha no login: %s", e)
            _pause_exit(1)

        console.print("[green]Sessao iniciada com sucesso![/green]\n")

        # --- Main processing loop ---
        stats = orchestrator.run(config, rows, session, output_writer, checkpoint)

        # --- Summary ---
        total_processed = sum(stats.values())
        console.print("\n[bold green]Processamento concluído![/bold green]")
        console.print(f"  Encontrado por CPF:  [green]{stats['encontrado_por_cpf']}[/green]")
        console.print(f"  Encontrado por nome: [yellow]{stats['encontrado_por_nome']}[/yellow]")
        console.print(f"  Não encontrado:      {stats['nao_encontrado']}")
        console.print(f"  Erros:               [red]{stats['erro']}[/red]")
        console.print(f"  Total:               {total_processed}")
        console.print(f"\nResultado salvo em: [cyan]{output_writer.file_path}[/cyan]")
        console.print(f"Logs em:            [cyan]{log_dir}[/cyan]")

        log.info(
            "Concluido. CPF=%d Nome=%d NaoEncontrado=%d Erros=%d",
            stats["encontrado_por_cpf"], stats["encontrado_por_nome"],
            stats["nao_encontrado"], stats["erro"],
        )

    finally:
        session.close()
        output_writer.close()

    _pause_exit(0)


def _pause_exit(code: int) -> None:
    """On Windows .exe, pause before closing so the user can read the output."""
    try:
        input("\nPressione ENTER para sair...")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(code)


if __name__ == "__main__":
    main()
