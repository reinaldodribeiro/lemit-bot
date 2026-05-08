import logging
import time
from contextlib import contextmanager
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
    "rate_limit": 0,
    "erro": 0,
}


@contextmanager
def _suspend_progress(progress: Progress, reason: str = ""):
    """Pausa o display do Progress para liberar stdin/stdout (ex.: prompt OTP)."""
    progress.stop()
    if reason:
        console.print(f"\n[yellow]{reason}[/yellow]")
    try:
        yield
    finally:
        progress.start()



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

            result = _process_row(config, row, session, progress)

            output_writer.append_row(result)
            checkpoint.mark_done(row.row_index, result.status_consulta)
            stats[result.status_consulta] = stats.get(result.status_consulta, 0) + 1

            progress.advance(task)

    return stats


def _process_row(config: Config, row: InputRow, session: LemitSession, progress: Progress) -> QueryResult:
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
            state = _query_with_retry(config, session, "cpf", cpf_digits, progress)
            if state == PageState.FOUND:
                phones = extract_phones(session.page)
                emails = extract_emails(session.page)
                _log_found(row.nome, phones, "CPF")
                return _build_result(result, phones, emails, "cpf", "encontrado_por_cpf")
            if state == PageState.UNAUTHORIZED:
                result.status_consulta = "rate_limit"
                result.consulta_usada = "cpf"
                result.observacao = "Rate limit (Nao autorizado) — reprocessar depois"
                log.info("Rate limit para %s — marcando para reprocessar", row.nome[:30])
                return result

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
    config: Config, session: LemitSession, query_type: str, value: str, progress: Progress
) -> PageState:
    UNAUTHORIZED_MAX_ATTEMPTS = 3

    unauthorized_count = 0
    other_attempts = 0
    max_other_attempts = config.bot.max_retries + 1
    safety_cap = max_other_attempts + UNAUTHORIZED_MAX_ATTEMPTS + 2
    iterations = 0

    while iterations < safety_cap:
        iterations += 1
        screenshot_dir = config.base_dir / "checkpoint" / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        state = (
            query_by_cpf(session.page, value, screenshot_dir)
            if query_type == "cpf"
            else query_by_name(session.page, value)
        )

        # 'Não autorizado' = rate limit do site, não perda de sessão.
        # Faz backoff e tenta de novo; após N tentativas, desiste sem relogin.
        if state == PageState.UNAUTHORIZED:
            unauthorized_count += 1
            log.warning(
                "'Não autorizado' (%d/%d) em %s='%s' — rate limit, aguardando",
                unauthorized_count, UNAUTHORIZED_MAX_ATTEMPTS, query_type, value[:20],
            )
            if unauthorized_count >= UNAUTHORIZED_MAX_ATTEMPTS:
                log.warning("Limite de retries para 'Não autorizado' atingido — desistindo da linha")
                return PageState.UNAUTHORIZED
            time.sleep(config.bot.delay_between_queries_seconds * 2)
            continue

        if state == PageState.SESSION_EXPIRED:
            with _suspend_progress(progress, "Sessao expirada — refazendo login (responda ao 2FA se solicitado)"):
                session.ensure_authenticated()
            continue

        if state == PageState.CAPTCHA:
            with _suspend_progress(progress, "Captcha detectado — resolva no navegador"):
                session.handle_captcha(f"durante consulta por {query_type}")
            continue

        if state == PageState.ERROR:
            other_attempts += 1
            if other_attempts < max_other_attempts:
                log.warning(
                    "Retry %d/%d (error) em %s='%s'",
                    other_attempts, max_other_attempts - 1, query_type, value[:20],
                )
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
