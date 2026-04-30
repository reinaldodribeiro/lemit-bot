import logging
import time
from pathlib import Path

from playwright.sync_api import Page

from models import PageState
from queries.extractor import has_results, check_no_results

log = logging.getLogger("lemit_bot.cpf_query")

# Direct GET URL — avoids form submission; confirmed from name-results page links.
# e.g. https://lemitti.com/queries/cpf/07343551140
LEMIT_CPF_URL = "https://lemitti.com/queries/cpf/{document}"

SEARCH_BUTTON_SELECTOR = "button[type='submit'], button .fa-search, .btn-search"
SETTLED_SELECTOR = ".panel-lemit, .alert"
UNAUTHORIZED_SELECTOR = "text=Não autorizado, text=nao autorizado, .toast:has-text('autorizado')"

_screenshot_count = 0


def query_by_cpf(page: Page, cpf: str, screenshot_dir: Path = None) -> PageState:
    """Navega para a página de CPF, clica na lupa e aguarda os resultados."""
    global _screenshot_count
    from utils import mask_cpf
    log.debug("Consulta CPF: %s", mask_cpf(cpf))

    try:
        url = LEMIT_CPF_URL.format(document=cpf)
        current_url = page.url
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        if _session_expired(page):
            return PageState.SESSION_EXPIRED
        if _has_captcha(page):
            return PageState.CAPTCHA

        # Clica no botão de pesquisa (lupa) para submeter o formulário
        try:
            submit_btn = page.locator(SEARCH_BUTTON_SELECTOR).first
            submit_btn.wait_for(state="visible", timeout=5_000)
            submit_btn.click()
            log.debug("Botao de pesquisa clicado")
        except Exception as e:
            log.debug("Botao de pesquisa nao encontrado, continuando: %s", e)

        # Aguarda os painéis de resultado renderizarem
        try:
            page.wait_for_selector(SETTLED_SELECTOR, timeout=15_000)
        except Exception:
            time.sleep(2)

        _screenshot_count += 1
        _save_screenshot(page, screenshot_dir, f"cpf_{_screenshot_count:03d}_apos_click")

        if _session_expired(page):
            return PageState.SESSION_EXPIRED
        if _has_captcha(page):
            return PageState.CAPTCHA
        if _is_unauthorized(page):
            log.warning("Consulta bloqueada (Nao autorizado) para CPF: %s", mask_cpf(cpf))
            return PageState.ERROR

        _save_screenshot(page, screenshot_dir, f"cpf_{_screenshot_count:03d}_apos_resultado")

        if has_results(page):
            log.debug("Resultado encontrado para CPF: %s", mask_cpf(cpf))
            return PageState.FOUND

        log.debug("CPF nao encontrado: %s", mask_cpf(cpf))
        return PageState.NOT_FOUND

    except Exception as e:
        log.error("Erro na consulta CPF %s: %s", mask_cpf(cpf), e)
        return PageState.ERROR


def _save_screenshot(page: Page, screenshot_dir: Path, label: str) -> None:
    if not screenshot_dir:
        return
    try:
        path = screenshot_dir / f"{label}.png"
        page.screenshot(path=str(path))
        log.debug("Screenshot: %s | URL: %s", path.name, page.url)
    except Exception as e:
        log.debug("Erro ao salvar screenshot: %s", e)


def _is_unauthorized(page: Page) -> bool:
    try:
        return page.locator("text=Não autorizado").count() > 0
    except Exception:
        return False


def _session_expired(page: Page) -> bool:
    url = page.url.lower()
    return "/login" in url or "/auth" in url


def _has_captcha(page: Page) -> bool:
    try:
        return page.locator(
            "iframe[src*='recaptcha'], iframe[src*='captcha'], "
            "[class*='captcha'], [id*='captcha']"
        ).count() > 0
    except Exception:
        return False
