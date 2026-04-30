from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any


class PageState(Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    CAPTCHA = "captcha"
    ERROR = "error"
    SESSION_EXPIRED = "session_expired"


@dataclass
class InputRow:
    row_index: int
    nome: str
    cpf: str
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    row_index: int
    nome: str
    cpf: str
    telefone_1: str = ""
    telefone_2: str = ""
    telefone_3: str = ""
    email_1: str = ""
    email_2: str = ""
    consulta_usada: str = ""
    status_consulta: str = ""
    observacao: str = ""
    data_consulta: str = ""
