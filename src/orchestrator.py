import logging
import time
from typing import List

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

from config import Config
from excel_io.checkpoint import CheckpointManager
from excel_io.output_writer import OutputWriter
from models import InputRow, PageState, QueryResult
from queries.cpf_query import query_by_cpf
from queries.extractor import extract_emails, extract_phones
from queries.name_query import query_by_name
from session import LemitSession
from utils import mask_cpf, mask_phone, normalize_cpf, now_str

log = logging.getLogger("lemit_bot.orchestrator")
console = Console()

_EMPTY_STATS = {
    "encontrado_por_cpf": 0,
    "encontrado_por_nome": 0,
    "nao_encontrado": 0,
    "erro": 0,
}


def run(
    config: Config,
    rows: List[InputRow],
    session: LemitSession,
    output_writer: OutputWriter,
    checkpoint: CheckpointManager,
) -> dict:
    skipped = checkpoint.processed_count()
    pending = [r for r in rows if not checkpoint.is_processed(r.row_index)]

    if config.bot.max_rows:
        pending = pending[: config.bot.max_rows]

    if skipped > 0:
        console.print(
            f"[yellow]Retomando: {skipped} linhas já processadas, "
            f"{len(pending)} restantes.[/yellow]\n"
        )

    stats = dict(_EMPTY_STATS)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Processando...", total=len(pending))

        for i, row in enumerate(pending, 1):
            progress.update(
                task,
                description=f"[{i}/{len(pending)}] {row.nome[:28]}",
            )

            result = _process_row(config, row, session)

            output_writer.append_row(result)
            checkpoint.mark_done(row.row_index, result.status_consulta)
            stats[result.status_consulta] = stats.get(result.status_consulta, 0) + 1

            progress.advance(task)

            if i < len(pending):
                time.sleep(config.bot.delay_between_queries_seconds)

    return stats


def _process_row(config: Config, row: InputRow, session: LemitSession) -> QueryResult:
    result = QueryResult(
        row_index=row.row_index,
        nome=row.nome,
        cpf=row.cpf,
        data_consulta=now_str(),
    )

    try:
        cpf_digits = normalize_cpf(row.cpf)
        log.info(
            "Processando linha %d | %s | CPF: %s",
            row.row_index,
            row.nome[:30],
            mask_cpf(cpf_digits) if cpf_digits else "(vazio)",
        )

        # --- CPF query ---
        if cpf_digits:
            state = _query_with_retry(config, session, "cpf", cpf_digits)
            if state == PageState.FOUND:
                phones = extract_phones(session.page)
                emails = extract_emails(session.page)
                _log_found(row.nome, phones, "CPF")
                return _build_result(result, phones, emails, "cpf", "encontrado_por_cpf")

        # --- Name query (fallback) — desativado ---
        # if row.nome:
        #     if cpf_digits:
        #         log.info("CPF sem resultado, tentando por nome: %s", row.nome[:30])
        #     state = _query_with_retry(config, session, "nome", row.nome)
        #     if state == PageState.FOUND:
        #         phones = extract_phones(session.page)
        #         emails = extract_emails(session.page)
        #         _log_found(row.nome, phones, "nome")
        #         return _build_result(result, phones, emails, "nome", "encontrado_por_nome")

        result.status_consulta = "nao_encontrado"
        result.consulta_usada = _consulta_usada(cpf_digits, row.nome)
        log.info("Nao encontrado: %s", row.nome[:30])

    except Exception as e:
        log.error(
            "Erro linha %d (%s): %s", row.row_index, row.nome[:30], e, exc_info=True
        )
        result.status_consulta = "erro"
        result.observacao = str(e)[:200]

    return result


def _query_with_retry(
    config: Config, session: LemitSession, query_type: str, value: str
) -> PageState:
    for attempt in range(config.bot.max_retries + 1):
        if attempt > 0:
            log.warning(
                "Tentativa %d/%d: %s='%s'", attempt, config.bot.max_retries, query_type, value[:20]
            )
            time.sleep(config.bot.delay_between_queries_seconds * 2)

        screenshot_dir = config.base_dir / "checkpoint" / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        state = query_by_cpf(session.page, value, screenshot_dir) if query_type == "cpf" else query_by_name(session.page, value)

        if state == PageState.SESSION_EXPIRED:
            session.ensure_authenticated()
            continue

        if state == PageState.CAPTCHA:
            session.handle_captcha(f"durante consulta por {query_type}")
            continue

        if state in (PageState.ERROR, PageState.NOT_FOUND) and attempt < config.bot.max_retries:
            continue

        return state

    return PageState.ERROR


def _build_result(
    result: QueryResult,
    phones: List[str],
    emails: List[str],
    consulta: str,
    status: str,
) -> QueryResult:
    result.telefone_1 = phones[0] if len(phones) > 0 else ""
    result.telefone_2 = phones[1] if len(phones) > 1 else ""
    result.telefone_3 = phones[2] if len(phones) > 2 else ""
    result.email_1 = emails[0] if len(emails) > 0 else ""
    result.email_2 = emails[1] if len(emails) > 1 else ""
    result.consulta_usada = consulta
    result.status_consulta = status
    return result


def _consulta_usada(cpf: str, nome: str) -> str:
    if cpf and nome:
        return "cpf+nome"
    return "cpf" if cpf else "nome"


def _log_found(nome: str, phones: List[str], method: str) -> None:
    masked = [mask_phone(p) for p in phones]
    log.info(
        "Encontrado por %s: %s | Telefones: %s",
        method,
        nome[:30],
        ", ".join(masked) if masked else "nenhum",
    )
