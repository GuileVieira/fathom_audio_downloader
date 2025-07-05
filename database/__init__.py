"""
Módulo de banco de dados para o sistema Fathom Analytics
"""

from .supabase_client import SupabaseClient
from .models import FathomCall, CallParticipant, CallTopic

__all__ = ['SupabaseClient', 'FathomCall', 'CallParticipant', 'CallTopic'] 