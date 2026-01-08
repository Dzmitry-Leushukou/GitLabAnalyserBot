import json
import re
import uuid
from typing import Dict, List, Optional
import aiohttp
import logging
from services.config import Config

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with Large Language Models (LLMs).
    
    This service handles communication with external LLM services to process
    task assignments and label suggestions based on user input and available
    worker information.
    
    Attributes:
        _session (Optional[aiohttp.ClientSession]): HTTP session for API requests
        config (Config): Configuration instance with API keys and settings
        
    Example:
        >>> async with LLMService() as service:
        ...     result = await service.process_task_assignment(
        ...         ["John Doe", "Jane Smith"],
        ...         "Create a login page"
        ...     )
        ...     print(result)
    """
    _instance = None
    
    def __new__(cls):
        """
        Create or return the singleton instance of the LLMService class.
        
        This method ensures that only one instance of the LLMService class exists
        throughout the application lifecycle.
        
        Returns:
            LLMService: The singleton instance of the LLMService class
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the LLMService instance with configuration and session.
        """
        if not self._initialized:
            self.config = Config()
            self._session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
    
    async def __aenter__(self):
        """
        Context manager entry method.
        
        Returns:
            LLMService: The current instance
        """
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit method that closes the session.
        """
        await self.close()
    
    async def _ensure_session(self) -> None:
        """
        Ensure the aiohttp session is initialized and ready for use.
        
        Creates a new session if none exists or if the current session is closed.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'Content-Type': 'application/json'}
            )
    
    async def close(self) -> None:
        """
        Close the aiohttp session and clean up resources.
        """
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from response text, removing markdown code block formatting.
        
        Args:
            response_text: The raw response text that may contain markdown formatting
            
        Returns:
            str: Clean JSON string extracted from the response
        """
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
        """
        Validate JSON structure and convert types as needed.
        
        Args:
            data: The parsed JSON data to validate
            
        Returns:
            Dict: The validated and potentially modified data
            
        Raises:
            ValueError: If required fields are missing or types are incorrect
        """
        required_fields = ["project_id", "title", "description", "assignee_name"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Required field is missing in response: {field}")
        
        # Convert project_id to string
        if data["project_id"] is None:
            data["project_id"] = self.config.default_project_id
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
    
    async def send_chat_request(self, api_key, message: str, chat_id: Optional[str] = None) -> Dict:
        """
        Send request to server endpoint /chat.
        
        This method sends a message to the configured LLM service endpoint
        and returns the response.
        
        Args:
            api_key: The API key for authentication with the LLM service
            message: The message content to process
            chat_id: Optional chat identifier (not currently used)
        
        Returns:
            Response from server in ChatResponse format
            
        Raises:
            aiohttp.ClientError: HTTP request error
            json.JSONDecodeError: Invalid JSON in server response
            
        Example:
            >>> async with LLMService() as service:
            ...     response = await service.send_chat_request("my-api-key", "Hello, world!")
            ...     print(response.get('answer'))
        """
        await self._ensure_session()
        
        # Form server endpoint URL
        url = f"{self.config.llm_url}/chat"
        
        # Form payload according to ChatRequest
        payload = {
            "api_key": api_key,
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
        """
        Process assignment and return structured data.
        
        This method takes a list of workers and a user message, formats them
        appropriately, and sends them to the LLM service to determine task
        assignment details.
        
        Args:
            workers: List of workers in format ["First Last", ...]
            user_message: User message text describing the task
            
        Returns:
            Dictionary with fields: project_id, title, description, assignee_name
            
        Raises:
            aiohttp.ClientError: HTTP request error
            json.JSONDecodeError: Invalid JSON in response
            ValueError: Invalid JSON structure or missing required fields
            
        Example:
            >>> async with LLMService() as service:
            ...     result = await service.process_task_assignment(
            ...         ["John Doe", "Jane Smith"],
            ...         "Create a new login page"
            ...     )
            ...     print(f"Assigned to: {result['assignee_name']}")
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
            server_response = await self.send_chat_request(self.config.create_task_llm_api_key,message_content)
            
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
     
    async def set_labels(self, labels: List[Dict[str, str]], user_message:str)-> Dict[str, str]:
        """
        Set appropriate labels for a task based on user message and available labels.
        
        This method analyzes the user's message and suggests appropriate labels
        from the provided list of available labels.
        
        Args:
            labels: List of label dictionaries with name and description
            user_message: The user's message describing the task
            
        Returns:
            Dictionary containing the selected labels
            
        Raises:
            aiohttp.ClientError: HTTP request error
            json.JSONDecodeError: Invalid JSON in response
            ValueError: Invalid JSON structure or missing required fields
        """
        # Formulate a string with labels for the LLM
        labels_info_str = ""
        for label in labels:
            name = label.get('name', '')
            description = label.get('description', '')
            if name:
                labels_info_str += f"- {name}"
                if description:
                    labels_info_str += f" ({description})"
                labels_info_str += "\n"
        
        message_content = f"Available labels with descriptions:\n{labels_info_str}\n\nUser message for analysis: {user_message}\n\nPlease select appropriate labels from the list above."

        logger.info("Sending request for labels analysis")
        try:
            # Send request to server endpoint
            server_response = await self.send_chat_request(self.config.get_labels_llm_api_key,message_content)
            
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
                
                # Validate structure for labels response - only require labels field
                if "labels" not in result:
                    raise ValueError(f"Required field is missing in response: labels")
                
                # Ensure labels is a list
                if not isinstance(result["labels"], list):
                    raise ValueError(f"Field labels must be a list, received: {type(result['labels'])}")
                
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