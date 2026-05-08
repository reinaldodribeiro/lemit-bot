import logging
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config import Config

log = logging.getLogger("lemit_bot.session")

LEMITTI_LOGIN_URL = "https://lemitti.com/auth/login"

EMAIL_SELECTOR = (
    "input[type='email'], "
    "input[name='email'], "
    "input[placeholder*='email'], "
    "input[placeholder*='Email']"
)
PASSWORD_SELECTOR = (
    "input[type='password'], "
    "input[name='password'], "
    "input[name='senha']"
)
SUBMIT_SELECTOR = (
    "button[type='submit'], "
    "button:has-text('Entrar'), "
    "button:has-text('Login'), "
    "button:has-text('Acessar'), "
    "button:has-text('Continuar')"
)
CAPTCHA_SELECTOR = (
    "iframe[src*='recaptcha'], iframe[src*='captcha'], "
    "[class*='captcha'], [id*='captcha']"
)
OTP_SELECTOR = (
    "input#password_otp, "
    "input[name='password_otp'], "
    "input[name='otp'], "
    "input[name='codigo'], "
    "input[autocomplete='one-time-code']"
)
ERROR_SELECTOR = (
    ".error, .alert-danger, .alert-error, "
    "[role='alert'], .error-message, .mensagem-erro"
)


class LemitSession:
    def __init__(self, config: Config, state_path: Optional[Path] = None):
        self._config = config
        self._state_path = state_path
        self._playwright: Playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        self.page: Page = None

    def start(self) -> "LemitSession":
        log.info("Iniciando navegador (headless=%s)", self._config.bot.headless)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._config.bot.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        if self._state_path and self._state_path.exists():
            log.info("Tentando reutilizar sessao salva")
            self._context = self._new_context(storage_state=str(self._state_path))
            self.page = self._context.new_page()
            if self._verify_session():
                log.info("Sessao reutilizada sem novo login")
                return self
            log.info("Sessao salva expirada, fazendo novo login")
            self._context.close()

        self._context = self._new_context()
        self.page = self._context.new_page()
        self._do_login()
        self._save_state()
        return self

    def ensure_authenticated(self) -> None:
        if not self._is_on_login_page():
            return
        log.warning("Sessao expirada (URL de login) — fazendo re-login")
        self.force_relogin()

    def force_relogin(self) -> None:
        log.warning("Forçando novo login (limpando cookies)")
        try:
            self._context.clear_cookies()
        except Exception as e:
            log.debug("Falha ao limpar cookies: %s", e)
        try:
            self.page.goto(LEMITTI_LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
        except Exception as e:
            log.debug("Falha ao navegar para login: %s", e)
        self._do_login()
        self._save_state()

    def _is_unauthorized(self) -> bool:
        try:
            return self.page.locator(
                "text=Não autorizado, text=nao autorizado, .toast:has-text('autorizado')"
            ).count() > 0
        except Exception:
            return False

    def handle_captcha(self, context: str = "") -> None:
        where = f" {context}" if context else ""
        if self._config.bot.headless:
            log.warning("Captcha detectado%s mas headless=true.", where)
            print(
                f"\n[AVISO] Captcha detectado{where}.\n"
                "O navegador está oculto (headless: true). "
                "Configure 'headless: false' no config.json para resolver captchas manualmente.\n"
                "Aguardando 30 segundos..."
            )
            time.sleep(30)
            return

        print(
            f"\n[CAPTCHA] Captcha detectado{where}.\n"
            "Resolva o captcha na janela do navegador e pressione ENTER para continuar..."
        )
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        log.info("Usuário confirmou resolução do captcha")

    def close(self) -> None:
        log.info("Encerrando sessao do navegador")
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            log.debug("Erro ao fechar navegador: %s", e)

    # ------------------------------------------------------------------

    def _new_context(self, storage_state=None) -> BrowserContext:
        kwargs = dict(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        if storage_state:
            kwargs["storage_state"] = storage_state
        return self._browser.new_context(**kwargs)

    def _verify_session(self) -> bool:
        try:
            self.page.goto(
                "https://lemitti.com/queries/cpf",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            return not self._is_on_login_page()
        except Exception:
            return False

    def _save_state(self) -> None:
        if not self._state_path:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self._state_path))
            log.debug("Estado da sessao salvo em %s", self._state_path)
        except Exception as e:
            log.debug("Nao foi possivel salvar estado da sessao: %s", e)

    def _do_login(self) -> None:
        log.info("Fazendo login em %s", LEMITTI_LOGIN_URL)
        self.page.goto(LEMITTI_LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

        if not self._is_on_login_page():
            log.info("Sessao ainda ativa. URL: %s", self.page.url)
            return

        if self._has_captcha():
            self.handle_captcha("na página de login")

        email_input = self.page.locator(EMAIL_SELECTOR).first
        try:
            email_input.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._save_debug_screenshot("login_timeout")
            log.error(
                "Input de email nao encontrado. URL: %s | Inputs: %s",
                self.page.url,
                [el.get_attribute("type") or el.get_attribute("name") or "?"
                 for el in self.page.locator("input").all()[:10]],
            )
            raise

        email_input.fill(self._config.lemit.email)
        self.page.locator(PASSWORD_SELECTOR).first.fill(self._config.lemit.password)
        self.page.locator(SUBMIT_SELECTOR).first.click()

        try:
            self.page.wait_for_url(
                lambda url: not self._url_is_login(url) or self._has_otp(),
                timeout=15_000,
            )
        except Exception:
            pass

        if self._has_captcha():
            self.handle_captcha("após tentativa de login")
            try:
                self.page.wait_for_url(
                    lambda url: not self._url_is_login(url) or self._has_otp(),
                    timeout=60_000,
                )
            except Exception:
                pass

        self._handle_otp_if_needed()

        if self._is_on_login_page():
            error_msg = self._get_login_error()
            raise RuntimeError(
                f"Login falhou. {error_msg or 'Verifique o email/senha no config.json.'}"
            )

        log.info("Login realizado com sucesso. URL: %s", self.page.url)

    def _is_on_login_page(self) -> bool:
        return self._url_is_login(self.page.url)

    @staticmethod
    def _url_is_login(url: str) -> bool:
        return "/auth/login" in url or url.endswith("/login")

    def _has_captcha(self) -> bool:
        try:
            return self.page.locator(CAPTCHA_SELECTOR).count() > 0
        except Exception:
            return False

    def _has_otp(self) -> bool:
        try:
            return self.page.locator(OTP_SELECTOR).count() > 0
        except Exception:
            return False

    def _handle_otp_if_needed(self) -> None:
        try:
            otp_input = self.page.locator(OTP_SELECTOR).first
            if not otp_input.count():
                return
            try:
                otp_input.wait_for(state="visible", timeout=5_000)
            except Exception:
                return
        except Exception:
            return

        log.info("Verificação em duas etapas detectada")
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(
                "\n[2FA] Verificação em duas etapas necessária.\n"
                "Digite o código de 6 dígitos recebido e pressione ENTER: ",
                end="",
                flush=True,
            )
            try:
                code = input().strip()
            except (EOFError, KeyboardInterrupt):
                raise RuntimeError("Login cancelado: código 2FA não informado.")

            digits = "".join(ch for ch in code if ch.isdigit())
            if len(digits) != 6:
                print(f"[2FA] Código inválido (esperado 6 dígitos). Tentativa {attempt}/{max_attempts}.")
                continue

            try:
                otp_input.fill(digits)
                self._submit_otp_form(otp_input)
            except Exception as e:
                log.warning("Falha ao enviar código 2FA: %s", e)
                continue

            if self._wait_otp_resolved(timeout_ms=25_000):
                log.info("Código 2FA aceito")
                return

            error_msg = self._get_login_error()
            if error_msg:
                print(f"[2FA] {error_msg}")
            else:
                print("[2FA] Código rejeitado ou tempo esgotado. Tente novamente.")

        raise RuntimeError("Login falhou: código 2FA inválido após várias tentativas.")

    def _submit_otp_form(self, otp_input) -> None:
        try:
            otp_input.focus()
        except Exception:
            pass
        try:
            otp_input.press("Enter")
        except Exception as e:
            log.debug("Enter no input OTP falhou: %s", e)

        if not self._has_otp():
            return

        candidates = [
            "button:has-text('Verificar')",
            "button:has-text('Confirmar')",
            "button:has-text('Validar')",
            "button:has-text('Continuar')",
            "button:has-text('Entrar')",
            "form:has(input#password_otp) button[type='submit']",
            "form:has(input[name='password_otp']) button[type='submit']",
            "button[type='submit']",
        ]
        for sel in candidates:
            try:
                btn = self.page.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click()
                    return
            except Exception:
                continue

    def _wait_otp_resolved(self, timeout_ms: int = 20_000) -> bool:
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            try:
                self.page.wait_for_load_state("networkidle", timeout=1_500)
            except Exception:
                pass
            if not self._has_otp() and not self._is_on_login_page():
                return True
            if self._get_login_error():
                return False
            time.sleep(0.5)
        return not self._has_otp() and not self._is_on_login_page()

    def _save_debug_screenshot(self, label: str) -> None:
        try:
            if not self._state_path:
                return
            path = self._state_path.parent / f"debug_{label}.png"
            self.page.screenshot(path=str(path))
            log.info("Screenshot salvo em %s", path)
        except Exception as e:
            log.debug("Nao foi possivel salvar screenshot: %s", e)

    def _get_login_error(self) -> str:
        try:
            el = self.page.locator(ERROR_SELECTOR).first
            if el.count():
                return el.inner_text().strip()
        except Exception:
            pass
        return ""
