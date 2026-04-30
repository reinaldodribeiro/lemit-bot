import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("lemit_bot.config")


@dataclass
class LemitConfig:
    email: str
    password: str


@dataclass
class BotConfig:
    headless: bool
    delay_between_queries_seconds: float
    max_retries: int
    max_rows: Optional[int]
    input_folder: str
    output_folder: str


@dataclass
class ExcelConfig:
    cpf_column: str
    name_column: str
    whatsapp_template: str


@dataclass
class Config:
    lemit: LemitConfig
    bot: BotConfig
    excel: ExcelConfig
    base_dir: Path


def load_config(config_path: Optional[Path] = None) -> Config:
    from utils import get_exe_dir

    if config_path is None:
        config_path = get_exe_dir() / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"config.json nao encontrado em: {config_path}\n"
            "Edite o arquivo config.json com suas credenciais antes de executar o bot."
        )

    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)

    _validate(raw, config_path)

    return Config(
        lemit=LemitConfig(
            email=raw["lemit"]["email"],
            password=raw["lemit"]["password"],
        ),
        bot=BotConfig(
            headless=bool(raw["bot"].get("headless", True)),
            delay_between_queries_seconds=float(raw["bot"].get("delay_between_queries_seconds", 2)),
            max_retries=int(raw["bot"].get("max_retries", 2)),
            max_rows=int(v) if (v := raw["bot"].get("max_rows")) is not None else None,
            input_folder=raw["bot"].get("input_folder", "entrada"),
            output_folder=raw["bot"].get("output_folder", "saida"),
        ),
        excel=ExcelConfig(
            cpf_column=raw["excel"].get("cpf_column", "cpf"),
            name_column=raw["excel"].get("name_column", "nome"),
            whatsapp_template=raw["excel"].get("whatsapp_template", "Olá {nome}, tudo bem?"),
        ),
        base_dir=config_path.parent,
    )


def _validate(raw: dict, path: Path) -> None:
    for section, key in [("lemit", "email"), ("lemit", "password")]:
        if section not in raw or key not in raw.get(section, {}):
            raise ValueError(f"config.json: campo '{section}.{key}' ausente em {path}")

    if raw["lemit"]["email"] in ("usuario@email.com", ""):
        raise ValueError(
            "Edite o config.json: substitua o email placeholder pelo seu email real."
        )
    if raw["lemit"]["password"] in ("senha", ""):
        raise ValueError(
            "Edite o config.json: substitua a senha placeholder pela sua senha real."
        )
