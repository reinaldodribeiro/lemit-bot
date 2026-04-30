import logging
from typing import List

from playwright.sync_api import Page

log = logging.getLogger("lemit_bot.extractor")


def has_results(page: Page) -> bool:
    try:
        return page.locator(".panel-lemit").filter(
            has=page.locator("h4.lemit-title")
        ).count() > 0
    except Exception:
        return False


def check_no_results(page: Page) -> bool:
    try:
        return page.locator(".panel-lemit").filter(
            has=page.locator("h4.lemit-title")
        ).count() == 0
    except Exception:
        return False


def extract_phones(page: Page) -> List[str]:
    """Extrai telefones dos painéis 'Telefones celulares' e 'Telefones fixos'."""
    phones: List[str] = []
    try:
        panels = page.locator(".panel-lemit").filter(
            has=page.locator("h4.lemit-title", has_text="Telefones")
        )
        for link in panels.locator("a[href^='tel:']").all():
            text = link.inner_text().strip()
            if text and text not in phones:
                phones.append(text)
    except Exception as e:
        log.debug("Extração de telefones falhou: %s", e)

    log.debug("%d telefone(s) extraido(s)", len(phones))
    return phones[:3]


def extract_emails(page: Page) -> List[str]:
    """Extrai emails do painel 'E-mails'."""
    emails: List[str] = []
    try:
        panel = page.locator(".panel-lemit").filter(
            has=page.locator("h4.lemit-title", has_text="E-mails")
        )
        for link in panel.locator("a[href^='mailto:']").all():
            text = link.inner_text().strip()
            if text and text not in emails:
                emails.append(text)
    except Exception as e:
        log.debug("Extração de emails falhou: %s", e)

    log.debug("%d email(s) extraido(s)", len(emails))
    return emails[:2]
