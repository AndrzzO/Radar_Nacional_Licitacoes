from datetime import datetime, date, timezone, timedelta
from typing import Optional
import zoneinfo

try:
    TZ_BRASILIA = zoneinfo.ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ_BRASILIA = timezone(timedelta(hours=-3), name="America/Sao_Paulo")


def get_current_time_sp() -> datetime:
    """Retorna o horário atual no fuso horário oficial de Brasília."""
    return datetime.now(TZ_BRASILIA)


def parse_datetime(val: Optional[str]) -> Optional[datetime]:
    """
    Converte com segurança uma string ISO ou formato comum em objeto datetime consciente de fuso.
    Não altera silenciosamente horários sem informação de fuso; atribui o fuso de Brasília.
    """
    if not val or not isinstance(val, str):
        return None

    clean_val = val.strip()
    if not clean_val:
        return None

    try:
        dt = datetime.fromisoformat(clean_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_BRASILIA)
        return dt
    except ValueError:
        pass

    # Tenta formatos alternativos comumente retornados
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(clean_val, fmt)
            return dt.replace(tzinfo=TZ_BRASILIA)
        except ValueError:
            continue

    return None


def format_datetime_br(val: Optional[str | datetime], include_time: bool = True) -> str:
    """Formata uma data para o padrão legível brasileiro (DD/MM/AAAA ou DD/MM/AAAA HH:MM)."""
    if not val:
        return ""

    if isinstance(val, str):
        dt = parse_datetime(val)
    else:
        dt = val

    if not dt:
        return str(val) if val else ""

    if include_time and (dt.hour != 0 or dt.minute != 0 or dt.second != 0):
        return dt.strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%d/%m/%Y")


def format_date_api(d: date | datetime) -> str:
    """Formata data no formato exigido pela API PNCP (yyyyMMdd)."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y%m%d")


def compute_situacao_prazo(data_encerramento: Optional[str]) -> str:
    """
    Calcula a situação do prazo de recebimento de propostas:
    - 'Aberto': prazo ainda futuro em relação ao momento atual em Brasília.
    - 'Encerrado': prazo já expirado.
    - 'Não informado': fonte não forneceu data de encerramento.
    """
    if not data_encerramento:
        return "Não informado"

    dt_fim = parse_datetime(data_encerramento)
    if not dt_fim:
        return "Não informado"

    agora = get_current_time_sp()
    return "Aberto" if dt_fim > agora else "Encerrado"


def timestamp_sp(value):
    dt=parse_datetime(value)
    return dt.timestamp() if dt else None


def proposal_status(end, start=None, state=None, current=None):
    current=current or get_current_time_sp()
    if state is not None and state != 1:
        return 'Indisponível'
    finish=parse_datetime(end)
    begin=parse_datetime(start)
    if not finish: return 'Não informado'
    if finish<=current: return 'Encerrado'
    if begin and begin>current: return 'Aguardando abertura'
    return 'Aberto'
