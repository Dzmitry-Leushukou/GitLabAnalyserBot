import json
import re
import uuid
from typing import Dict, List, Optional
import aiohttp
import logging
from services.config import Config

logger = logging.getLogger(__name__)

class LLMService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = Config()
            self._session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'Content-Type': 'application/json'}
            )
    
    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from response text, removing markdown code block."""
        response_text = response_text.strip()
        
        # Remove backticks and json label if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        elif response_text.startswith('```'):
            response_text = response_text[3:]
        
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        return response_text.strip()
    
    async def _validate_json_structure(self, data: Dict) -> Dict:
        """Validate JSON structure and convert types."""
        required_fields = ["project_id", "title", "description", "assignee_name"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Required field is missing in response: {field}")
        
        # Convert project_id to string
        if data["project_id"] is None:
            data["project_id"] = "18"
        else:
            data["project_id"] = str(data["project_id"])
        
        # Check types
        if not isinstance(data["title"], str):
            raise ValueError(f"Field title must be a string, received: {type(data['title'])}")
        
        if not isinstance(data["description"], str):
            raise ValueError(f"Field description must be a string, received: {type(data['description'])}")
        
        if data["assignee_name"] is not None and not isinstance(data["assignee_name"], str):
            raise ValueError(f"Field assignee_name must be a string or null, received: {type(data['assignee_name'])}")
        
        return data
    
    async def send_chat_request(self, message: str, chat_id: Optional[str] = None) -> Dict:
        """Send request to server endpoint /chat.
        
        Args:
            message: Message to process
            chat_id: Chat identifier (optional)
        
        Returns:
            Response from server in ChatResponse format
        """
        await self._ensure_session()
        
        # Form server endpoint URL
        url = f"{self.config.llm_url}/chat"
        
        # Form payload according to ChatRequest
        payload = {
            "api_key": self.config.llm_api_key,
            "message": message
        }
        
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        logger.info(f"Sending request to server endpoint: {url}")
        logger.debug(f"Payload: {payload}")
        
        try:
            async with self._session.post(url, json=payload) as response:
                response.raise_for_status()
                response_data = await response.json()
                
            logger.info(f"Received response from server, status: {response_data.get('status')}")
            return response_data
            
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error when sending message: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in server response: {e}")
            raise
    
    async def process_task_assignment(self, workers: List[str], user_message: str) -> Dict[str, str]:
        """Process assignment and return structured data.
        
        Args:
            workers: List of workers in format ["First Last", ...]
            user_message: User message text
        
        Returns:
            Dictionary with fields: project_id, title, description, assignee_name
        
        Raises:
            aiohttp.ClientError: HTTP request error
            json.JSONDecodeError: Invalid JSON in response
            ValueError: Invalid JSON structure or missing required fields
        """
        # Form message for LLM according to prompt
        workers_str = json.dumps(workers, ensure_ascii=False)
        
        message_content = f"""
 Worker list for current request:
 {workers_str}
 
 User message for analysis:
 {user_message}
 """
        
        logger.info("Sending request for task analysis")
        
        try:
            # Send request to server endpoint
            server_response = await self.send_chat_request(message_content)
            
            # Extract AI response from server response
            ai_answer = server_response.get('answer', '')
            
            # Check if 'answer' field exists in response
            if 'answer' not in server_response:
                logger.error(f"Field 'answer' is missing in server response: {server_response}")
                # Check if there are other possible response fields
                if 'status' in server_response and server_response['status'] == 'Gateway Service is running':
                    raise ValueError("Server returned status but does not contain AI response. Possible LLM service configuration issue.")
                else:
                    raise ValueError(f"Unexpected server response format: {server_response}")
            
            if not ai_answer:
                logger.error(f"Empty AI response in field 'answer', full response: {server_response}")
                raise ValueError("Empty AI response")
            
            logger.info(f"Received AI response: {ai_answer[:500]}...")
            
            try:
                # Extract and parse JSON from AI response
                json_text = await self._extract_json_from_response(ai_answer)
                result = json.loads(json_text)
                
                # Validate structure
                result = await self._validate_json_structure(result)
                
                logger.info("Successfully processed LLM response")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in AI response: {e}")
                logger.error(f"Raw AI response: {ai_answer}")
                raise json.JSONDecodeError(
                    f"Invalid JSON in AI response: {e}",
                    e.doc,
                    e.pos
                )
            
            except ValueError as e:
                logger.error(f"Invalid JSON structure: {e}")
                logger.error(f"Parsed JSON: {result if 'result' in locals() else 'No data'}")
                raise
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error when sending message: {e}")
            raise
    
    async def send_message(self, message: str, chat_id: Optional[str] = None) -> Dict:
        """Send message to LLM via server endpoint.
        
        Args:
            message: Message to send
            chat_id: Chat identifier (optional)
        
        Returns:
            Server response
        """
        return await self.send_chat_request(message, chat_id)