# utils/context_processors.py
import logging
from utils.utils import get_long_obrat, URL_TO_RAW_MAPPING

# Configure the logger
logger = logging.getLogger(__name__)

def obrat_oddelek_context(request):
    obrat_short = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_short)

    # Prioritize GET params; fallback to session data
    safe_obrat = request.GET.get('safe_obrat', obrat_short)
    safe_oddelek = request.GET.get('safe_oddelek', request.session.get('safe_oddelek', ''))

    raw_oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek, safe_oddelek)
    context = {
        'safe_obrat': safe_obrat,
        'safe_oddelek': safe_oddelek,
        'long_obrat': obrat_long,
        'raw_oddelek': raw_oddelek,
    }
    logger.debug(f"Context Processor Output: {context}")
    return context