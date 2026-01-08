# services/whisper_service.py
import os
import tempfile
import aiohttp
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from pydub import AudioSegment
from services.config import Config


logger = logging.getLogger(__name__)


class WhisperService:
    """Service for audio transcription via OpenAI Whisper API"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._client: Optional[AsyncOpenAI] = None
            self._session: Optional[aiohttp.ClientSession] = None
            self.config = Config()
            self._initialized = True

            
            # Initialize OpenAI client
            self._init_openai_client()
    
    def _init_openai_client(self) -> None:
        """Initialize OpenAI client"""
        try:
            # Get API key from environment variables
            api_key = self.config.whisper_api_key
            
            if not api_key:
                logger.warning("OPENAI_API_KEY not found in environment variables")
                return
            
            self._client = AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized for Whisper API")
            
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
    
    async def close(self) -> None:
        """Закрывает сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._client:
            await self._client.close()
    
    async def transcribe_audio_file(
        self, 
        audio_path: str,
        language: Optional[str] = "ru"
    ) -> Dict[str, Any]:
        """
        Transcribes audio file via Whisper API
        
        Args:
            audio_path: Path to audio file
            language: Audio language ("ru" for Russian)
            
        Returns:
            Dictionary with transcription result
        """
        if not self._client:
            raise Exception("OpenAI клиент не инициализирован. Проверьте OPENAI_API_KEY")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Файл не найден: {audio_path}")
        
        try:
            # Проверяем размер файла (Whisper лимит: 25MB)
            file_size = os.path.getsize(audio_path)
            if file_size > 25 * 1024 * 1024:
                raise ValueError(f"File too large: {file_size / (1024*1024):.2f}MB (maximum 25MB)")
            
            # Open file for reading
            with open(audio_path, "rb") as audio_file:
                # Perform transcription
                response = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="text"
                )
            
            logger.info(f"Transcription successful: {len(response)} characters")
            
            return {
                "text": response,
                "success": True,
                "language": language,
                "file_size": file_size
            }
            
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            raise
    
    async def transcribe_telegram_voice(
        self,
        voice_bytes: bytes,
        language: Optional[str] = "ru"
    ) -> Dict[str, Any]:
        """
        Transcribes voice message from Telegram
        
        Args:
            voice_bytes: Bytes of voice message
            language: Audio language
            
        Returns:
            Transcription result
        """
        temp_file_path = None
        
        try:
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
                tmp_file.write(voice_bytes)
                temp_file_path = tmp_file.name
            
            # Конвертируем OGG в MP3 если нужно
            converted_path = await self._convert_ogg_to_mp3(temp_file_path)
            
            # Транскрибируем
            result = await self.transcribe_audio_file(converted_path, language)
            
            return result
            
        finally:
            # Удаляем временные файлы
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    async def _convert_ogg_to_mp3(self, ogg_path: str) -> str:
        """
        Converts OGG to MP3
        
        Args:
            ogg_path: Path to OGG file
            
        Returns:
            str: Path to MP3 file
        """
        try:
            mp3_path = ogg_path.replace('.ogg', '.mp3')
            
            # Конвертация с помощью pydub
            audio = AudioSegment.from_file(ogg_path, format="ogg")
            audio.export(mp3_path, format="mp3", bitrate="128k")
            
            return mp3_path
        except Exception as e:
            logger.error(f"Error converting audio: {e}")
            # If conversion fails, return original file
            return ogg_path
    
    async def is_available(self) -> bool:
        """Проверяет доступность сервиса"""
        return self._client is not None


# Фабричная функция для получения экземпляра
def get_whisper_service() -> WhisperService:
    """Возвращает экземпляр WhisperService"""
    return WhisperService()