import os
import re
import sys
from datetime import datetime
from pathlib import Path


def get_exe_dir() -> Path:
    """Return the directory containing the exe (PyInstaller) or project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # __file__ is src/utils.py; parent.parent is the project root
    return Path(__file__).parent.parent


def setup_playwright_env() -> None:
    """Point Playwright to bundled browsers when running as a frozen exe."""
    if not getattr(sys, "frozen", False):
        return
    bundled = get_exe_dir() / "ms-playwright"
    if bundled.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))


def normalize_cpf(raw: str) -> str:
    """Strip all non-digit characters from a CPF/CNPJ string."""
    if not raw:
        return ""
    return re.sub(r"[^\d]", "", str(raw).strip())


def is_valid_cpf(cpf: str) -> bool:
    """Validate CPF check digits (11 digits)."""
    cpf = normalize_cpf(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    def _digit(digits: str, n: int) -> int:
        total = sum(int(d) * w for d, w in zip(digits[:n], range(n + 1, 1, -1)))
        rem = (total * 10) % 11
        return 0 if rem >= 10 else rem

    return int(cpf[9]) == _digit(cpf, 9) and int(cpf[10]) == _digit(cpf, 10)


def mask_cpf(cpf: str) -> str:
    """Partially mask CPF for safe logging: 123.***.***-09"""
    digits = normalize_cpf(cpf)
    if len(digits) == 11:
        return f"{digits[:3]}.***.*{digits[7:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.***.***/{digits[8:12]}-**"
    return "***"


def mask_phone(phone: str) -> str:
    """Partially mask phone number for safe logging."""
    if not phone:
        return ""
    digits = re.sub(r"[^\d]", "", phone)
    if len(digits) >= 8:
        return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]
    return "***"


def timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
