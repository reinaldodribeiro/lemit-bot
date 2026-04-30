import logging
import time

from playwright.sync_api import Page

from models import PageState
from queries.extractor import has_results

log = logging.getLogger("lemit_bot.name_query")

LEMIT_NAME_QUERY_URL = "https://lemitti.com/queries/avancado/nome"

# Form selectors — confirmed from real HTML:
#   <input type="text" name="term" id="term" ...>
#   <button type="submit" class="btn btn-primary">
NAME_INPUT_SELECTOR = "input[name='term']"
SUBMIT_SELECTOR = "button[type='submit']"

# After name submit, the "Dados gerais" panel appears with CPF links:
#   <a href="https://lemitti.com/queries/cpf/07343551140">073.435.511-40</a>
CPF_LINK_SELECTOR = ".panel-lemit a[href*='/queries/cpf/']"

SETTLED_SELECTOR = ".panel-lemit, form.action-form, .alert"


def query_by_name(page: Page, nome: str) -> PageState:
    """
    Submit the name query form, then follow the first CPF link to the detail page.
    After this function returns FOUND, `page` is positioned on the CPF detail page,
    ready for phone/email extraction.
    """
    log.debug("Consulta por nome: %s", nome[:30])

    try:
        page.goto(LEMIT_NAME_QUERY_URL, wait_until="domcontentloaded", timeout=30_000)

        if _session_expired(page):
            return PageState.SESSION_EXPIRED
        if _has_captcha(page):
            return PageState.CAPTCHA

        name_input = page.locator(NAME_INPUT_SELECTOR).first
        name_input.wait_for(state="visible", timeout=10_000)
        name_input.fill("")
        name_input.type(nome, delay=40)
        page.locator(SUBMIT_SELECTOR).first.click()

        # Wait for "Dados gerais" panel or empty/error state
        try:
            page.wait_for_selector(SETTLED_SELECTOR, timeout=20_000)
        except Exception:
            time.sleep(2)

        if _has_captcha(page):
            return PageState.CAPTCHA
        if _session_expired(page):
            return PageState.SESSION_EXPIRED

        # Find CPF link in the results table
        cpf_link = page.locator(CPF_LINK_SELECTOR).first
        if cpf_link.count() == 0:
            log.debug("Nome nao encontrado: %s", nome[:30])
            return PageState.NOT_FOUND

        href = cpf_link.get_attribute("href")
        if not href:
            return PageState.NOT_FOUND

        log.debug("Seguindo link do resultado: %s", href)
        page.goto(href, wait_until="domcontentloaded", timeout=30_000)

        try:
            page.wait_for_selector(".panel-lemit", timeout=15_000)
        except Exception:
            time.sleep(2)

        if _session_expired(page):
            return PageState.SESSION_EXPIRED

        if has_results(page):
            log.debug("Resultado encontrado por nome: %s", nome[:30])
            return PageState.FOUND

        return PageState.NOT_FOUND

    except Exception as e:
        log.error("Erro na consulta por nome '%s': %s", nome[:30], e)
        return PageState.ERROR


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
