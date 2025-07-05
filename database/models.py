"""
Modelos de dados para o sistema Fathom Analytics
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
import json


class CallParticipant(BaseModel):
    """Modelo para participantes de chamadas"""
    speaker_id: str
    name: str
    is_host: bool = False
    
    class Config:
        extra = "allow"


class CallTopic(BaseModel):
    """Modelo para tópicos de chamadas"""
    title: str
    points: List[str] = []
    
    class Config:
        extra = "allow"


class CallSummary(BaseModel):
    """Modelo para resumo de chamadas"""
    purpose: Optional[str] = None
    key_takeaways: List[str] = []
    topics: List[CallTopic] = []
    next_steps: List[str] = []
    
    class Config:
        extra = "allow"


class CallQuestion(BaseModel):
    """Modelo para perguntas em chamadas"""
    speaker_id: Optional[str] = None
    question: str
    
    class Config:
        extra = "allow"


class FathomCall(BaseModel):
    """Modelo principal para chamadas do Fathom"""
    
    # Identificadores
    id: Union[int, str]
    url: str
    share_url: Optional[str] = None
    
    # Informações básicas
    title: str
    date: str
    date_formatted: str
    duration: str
    
    # Host e empresa
    host_name: Optional[str] = None
    company_domain: Optional[str] = None
    
    # Dados estruturados
    participants: List[CallParticipant] = []
    summary: Optional[CallSummary] = None
    questions: List[CallQuestion] = []
    
    # Transcrição
    transcript_text: Optional[str] = None
    
    # Metadados
    extracted_at: Optional[str] = None
    status: str = "extracted"
    
    # Dados brutos (para flexibilidade)
    raw_data: Optional[Dict[str, Any]] = None
    
    @validator('id')
    def validate_id(cls, v):
        """Converte ID para int se for string numérica"""
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v
    
    @validator('date_formatted')
    def validate_date_format(cls, v):
        """Valida formato de data"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data deve estar no formato YYYY-MM-DD')
    
    @validator('duration')
    def validate_duration(cls, v):
        """Valida formato de duração"""
        if not v:
            return v
        # Aceita formatos como "8 mins", "1h 30mins", etc.
        return v.strip()
    
    def get_duration_minutes(self) -> Optional[int]:
        """Converte duração para minutos"""
        if not self.duration:
            return None
        
        duration_str = self.duration.lower()
        total_minutes = 0
        
        # Extrai horas
        if 'h' in duration_str:
            hours_part = duration_str.split('h')[0].strip()
            if hours_part.isdigit():
                total_minutes += int(hours_part) * 60
        
        # Extrai minutos
        if 'min' in duration_str:
            # Pega a parte dos minutos
            mins_part = duration_str.split('min')[0]
            if 'h' in mins_part:
                mins_part = mins_part.split('h')[1].strip()
            else:
                mins_part = mins_part.strip()
            
            # Remove caracteres não numéricos
            mins_clean = ''.join(c for c in mins_part if c.isdigit())
            if mins_clean:
                total_minutes += int(mins_clean)
        
        return total_minutes if total_minutes > 0 else None
    
    def get_call_date(self) -> Optional[date]:
        """Retorna data da chamada como objeto date"""
        try:
            return datetime.strptime(self.date_formatted, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None
    
    def get_participant_count(self) -> int:
        """Retorna número de participantes"""
        return len(self.participants)
    
    def get_topics_count(self) -> int:
        """Retorna número de tópicos"""
        return len(self.summary.topics) if self.summary else 0
    
    def get_questions_count(self) -> int:
        """Retorna número de perguntas"""
        return len(self.questions)
    
    def get_key_takeaways_count(self) -> int:
        """Retorna número de key takeaways"""
        return len(self.summary.key_takeaways) if self.summary else 0
    
    def get_next_steps_count(self) -> int:
        """Retorna número de next steps"""
        return len(self.summary.next_steps) if self.summary else 0
    
    def to_database_dict(self) -> Dict[str, Any]:
        """Converte para dicionário otimizado para banco de dados"""
        return {
            'id': int(self.id) if isinstance(self.id, str) and self.id.isdigit() else self.id,
            'url': self.url,
            'share_url': self.share_url,
            'title': self.title,
            'call_date': self.get_call_date(),
            'date_formatted': self.date_formatted,
            'duration_raw': self.duration,
            'duration_minutes': self.get_duration_minutes(),
            'host_name': self.host_name,
            'company_domain': self.company_domain,
            'participant_count': self.get_participant_count(),
            'topics_count': self.get_topics_count(),
            'questions_count': self.get_questions_count(),
            'key_takeaways_count': self.get_key_takeaways_count(),
            'next_steps_count': self.get_next_steps_count(),
            'raw_data': self.raw_data or self.dict(),
            'summary_data': self.summary.dict() if self.summary else None,
            'participants_data': [p.dict() for p in self.participants],
            'transcript_data': {'transcript_text': self.transcript_text} if self.transcript_text else None,
            'extracted_at': self.extracted_at,
            'status': self.status
        }
    
    @classmethod
    def from_json_file(cls, file_path: str) -> 'FathomCall':
        """Cria instância a partir de arquivo JSON"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Guarda dados brutos
        raw_data = data.copy()
        
        # Processa participantes
        participants = []
        if 'participants' in data:
            for p in data['participants']:
                participants.append(CallParticipant(**p))
        
        # Processa summary
        summary = None
        if 'summary' in data:
            summary_data = data['summary']
            
            # Processa tópicos
            topics = []
            if 'topics' in summary_data:
                for t in summary_data['topics']:
                    topics.append(CallTopic(**t))
            
            summary = CallSummary(
                purpose=summary_data.get('purpose'),
                key_takeaways=summary_data.get('key_takeaways', []),
                topics=topics,
                next_steps=summary_data.get('next_steps', [])
            )
        
        # Processa perguntas
        questions = []
        if 'questions' in data:
            for q in data['questions']:
                questions.append(CallQuestion(**q))
        
        return cls(
            id=data['id'],
            url=data['url'],
            share_url=data.get('share_url'),
            title=data['title'],
            date=data['date'],
            date_formatted=data['date_formatted'],
            duration=data['duration'],
            host_name=data.get('host_name'),
            company_domain=data.get('company_domain'),
            participants=participants,
            summary=summary,
            questions=questions,
            transcript_text=data.get('transcript_text'),
            extracted_at=data.get('extracted_at'),
            status=data.get('status', 'extracted'),
            raw_data=raw_data
        )
    
    class Config:
        extra = "allow"
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class DatabaseCallRecord(BaseModel):
    """Modelo para registros do banco de dados"""
    id: int
    uuid: Optional[str] = None
    url: str
    title: str
    call_date: date
    duration_minutes: Optional[int] = None
    host_name: Optional[str] = None
    company_domain: Optional[str] = None
    participant_count: int = 0
    topics_count: int = 0
    questions_count: int = 0
    status: str = "extracted"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        extra = "allow"
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class CallStats(BaseModel):
    """Modelo para estatísticas de chamadas"""
    total_calls: int
    total_duration_minutes: int
    avg_duration_minutes: float
    unique_participants: int
    unique_hosts: int
    unique_companies: int
    most_active_host: Optional[str] = None
    most_discussed_topic: Optional[str] = None
    
    class Config:
        extra = "allow"


class ParticipantActivity(BaseModel):
    """Modelo para atividade de participantes"""
    name: str
    call_count: int
    hosted_calls: int
    first_call: date
    last_call: date
    avg_call_duration: Optional[float] = None
    
    class Config:
        extra = "allow"
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class TopicFrequency(BaseModel):
    """Modelo para frequência de tópicos"""
    title: str
    frequency: int
    unique_calls: int
    avg_points_per_topic: Optional[float] = None
    
    class Config:
        extra = "allow" 