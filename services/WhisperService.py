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
    """
    Service for audio transcription via OpenAI Whisper API.
    
    This service handles voice message transcription by interfacing with the OpenAI Whisper API.
    It manages temporary file handling, audio format conversion, and API communication.
    
    Attributes:
        _client (Optional[AsyncOpenAI]): OpenAI API client for Whisper transcription
        _session (Optional[aiohttp.ClientSession]): HTTP session for API requests
        config (Config): Configuration instance with API keys and settings
        
    Example:
        >>> service = WhisperService()
        >>> result = await service.transcribe_audio_file("recording.mp3", "en")
        >>> print(result["text"])  # Transcribed text
    """
    
    _instance = None
    
    def __new__(cls):
        """
        Create or return the singleton instance of the WhisperService class.
        
        This method ensures that only one instance of the WhisperService class exists
        throughout the application lifecycle.
        
        Returns:
            WhisperService: The singleton instance of the WhisperService class
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Initialize the WhisperService instance with configuration and API client.
        """
        if not self._initialized:
            self._client: Optional[AsyncOpenAI] = None
            self._session: Optional[aiohttp.ClientSession] = None
            self.config = Config()
            self._initialized = True

            
            # Initialize OpenAI client
            self._init_openai_client()
    
    def _init_openai_client(self) -> None:
        """
        Initialize the OpenAI client with the API key from configuration.
        
        This method creates an AsyncOpenAI client instance using the API key
        stored in the configuration. If the API key is not found, a warning
        is logged but no exception is raised to allow graceful degradation.
        """
        try:
            # Get API key from environment variables
            api_key = self.config.whisper_api_key
            
            if not api_key:
                logger.warning("WHISPER_API_KEY not found in environment variables")
                return
            
            self._client = AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized for Whisper API")
            
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
    
    async def close(self) -> None:
        """
        Close the WhisperService session and clean up resources.
        
        This method closes both the HTTP session and the OpenAI client to free up resources.
        """
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
        Transcribes audio file via Whisper API.
        
        This method sends an audio file to the OpenAI Whisper API for transcription.
        It performs validation checks including file size verification (max 25MB).
        
        Args:
            audio_path: Path to audio file to be transcribed
            language: Audio language code (default: "ru" for Russian)
            
        Returns:
            Dictionary containing the transcription result with text, success status,
            language, and file size information
            
        Raises:
            FileNotFoundError: If the audio file does not exist
            ValueError: If the file exceeds the size limit
            Exception: If the OpenAI client is not initialized or other API errors occur
            
        Example:
            >>> service = WhisperService()
            >>> result = await service.transcribe_audio_file("recording.mp3", "en")
            >>> print(result["text"])  # Transcribed text
        """
        if not self._client:
            raise Exception("OpenAI client not initialized. Please check WHISPER_API_KEY")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"File not found: {audio_path}")
        
        try:
            # Check file size (Whisper limit: 25MB)
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
            logger.error(f"Transcription error: {e}")
            raise
     
    async def transcribe_telegram_voice(
        self,
        voice_bytes: bytes,
        language: Optional[str] = "ru"
    ) -> Dict[str, Any]:
        """
        Transcribes voice message from Telegram.
        
        This method handles voice messages received from Telegram by first saving
        them as temporary files, converting the format if needed, and then
        performing transcription via the Whisper API.
        
        Args:
            voice_bytes: Raw bytes of the voice message from Telegram
            language: Audio language code (default: "ru" for Russian)
            
        Returns:
            Dictionary containing the transcription result
        """
        temp_file_path = None
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
                tmp_file.write(voice_bytes)
                temp_file_path = tmp_file.name
            
            # Convert OGG to MP3 if needed
            converted_path = await self._convert_ogg_to_mp3(temp_file_path)
            
            # Transcribe the audio file
            result = await self.transcribe_audio_file(converted_path, language)
            
            return result
            
        finally:
            # Clean up temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    async def _convert_ogg_to_mp3(self, ogg_path: str) -> str:
        """
        Converts OGG to MP3 format.
        
        This method converts an OGG audio file to MP3 format using pydub,
        which may be required for compatibility with the Whisper API.
        
        Args:
            ogg_path: Path to the input OGG file
            
        Returns:
            str: Path to the converted MP3 file
        """
        try:
            mp3_path = ogg_path.replace('.ogg', '.mp3')
            
            # Conversion using pydub
            audio = AudioSegment.from_file(ogg_path, format="ogg")
            audio.export(mp3_path, format="mp3", bitrate="128k")
            
            return mp3_path
        except Exception as e:
            logger.error(f"Error converting audio: {e}")
            # If conversion fails, return original file
            return ogg_path
    
    async def is_available(self) -> bool:
        """
        Check if the Whisper service is available.
        
        This method verifies if the OpenAI client has been properly initialized
        and is ready to process transcription requests.
        
        Returns:
            bool: True if the service is available, False otherwise
        """
        return self._client is not None


# Factory function to get an instance of WhisperService
def get_whisper_service() -> WhisperService:
    """
    Returns an instance of WhisperService.
    
    This factory function provides a convenient way to get the singleton
    instance of the WhisperService class.
    
    Returns:
        WhisperService: The singleton instance of WhisperService
    """
    return WhisperService()