import os
import json

from openai import AzureOpenAI
from gpt_gateway.prompts.prompt import prompts_template, prompts_template_performance
from gpt_gateway.prompts.prompt_i18n_system import prompts_i18n_template
from gpt_gateway.apps import OpenAIClientManager 
from gpt_gateway.utils.image_handler import image_obj_base64_encode


openai_client_manager = OpenAIClientManager()

class OpenAIModel:
    def __init__(self) -> None:
        # self.api_version = "2024-02-01"
        # self.endpoint = "https://llm-proxy.us-east-2.int.infra.intelligence.capx.com/azure/v1"
        # Don't store client, get it dynamically to ensure fresh token
        print(f"✅ OpenAIModel initialized")
        self.started = True
        
    def get_client(self):
        """Get fresh client with current token"""
        client = openai_client_manager.get_client()
        if client is None:
            self.started = False
            return None
        self.started = True
        return client
    
    def _build_dialogs(self, test_scenario:str):

        # content = prompts_template(test_scenario)
        # content = test_scenario
        # case 1: "content": "You will be provided with a message, and your task is to respond using emojis only."
        content = "You are a helpful assistant."
        dialogs = [
            {
                "role": "user", 
                "content": test_scenario
            }
        ]

        return dialogs
    
    def ask_openai(self, test_scenario) -> str:
                
        chats = self._build_dialogs(test_scenario)
        
        llm_output_message = ''
        client = self.get_client()
        if client is None:
            print("OpenAI client is not initialized.")
            return ''
        try:
            completion = client.chat.completions.create(
                                                            model="gpt-4.1",
                                                            messages=chats # type: ignore
                                                            )
            llm_output_message = str(completion.choices[0].message.content).strip()

        except Exception as e:
            # logging.warn(f'Failed to call OpenAI,error={e}')
            print(f'Failed to call OpenAI,error={e}')
            return ''
        
        return llm_output_message
    
    def _build_dialogs_for_sr(self, test_scenario:str):

        content = prompts_template(test_scenario)
        dialogs = [
            {
                "role": "user", 
                "content": content
            }
        ]

        return dialogs
    
    def _build_dialogs_for_pf(self, performance_data:str):
        """
        Build dialogs for performance analysis
        
        Args:
            performance_data (str): Performance report data in markdown table format
            
        Returns:
            list: Dialog structure for OpenAI API
        """
        content = prompts_template_performance(performance_data)
        dialogs = [
            {
                "role": "user", 
                "content": content
            }
        ]

        return dialogs
    
    def ask_openai_for_sr(self, test_scenario) -> str:

        chats = self._build_dialogs_for_sr(test_scenario)

        llm_output_message = ''
        client = self.get_client()
        if client is None:
            print("OpenAI client is not initialized.")
            return ''
        try:
            completion = client.chat.completions.create(
                                                            model="gpt-4o",
                                                            messages=chats # type: ignore
                                                            )
            llm_output_message = str(completion.choices[0].message.content).strip()

        except Exception as e:
            # logging.warn(f'Failed to call OpenAI,error={e}')
            print(f'Failed to call OpenAI,error={e}')
            return ''
        
        return llm_output_message

    def get_response(self, user_message):
        if self.started:
            openai_response = self.ask_openai(user_message)
            return openai_response
        else:
            return 'OpenAI not started'

    def get_response_for_sr(self, user_message):
        if self.started:
            openai_response = self.ask_openai_for_sr(user_message)
            return openai_response
        else:
            return 'OpenAI not started'
    
    def ask_openai_for_pf(self, performance_data) -> str:
        """
        Ask OpenAI to analyze performance data
        
        Args:
            performance_data (str): Performance report data in markdown table format
            
        Returns:
            str: Performance analysis in markdown format
        """
        chats = self._build_dialogs_for_pf(performance_data)

        llm_output_message = ''
        client = self.get_client()
        if client is None:
            print("OpenAI client is not initialized.")
            return ''
        try:
            completion = client.chat.completions.create(
                                                            model="gpt-4.1",
                                                            messages=chats # type: ignore
                                                            )
            llm_output_message = str(completion.choices[0].message.content).strip()

        except Exception as e:
            # logging.warn(f'Failed to call OpenAI,error={e}')
            print(f'Failed to call OpenAI for performance analysis, error={e}')
            return ''
        
        return llm_output_message

    def get_response_for_pf(self, performance_data):
        """
        Get performance analysis response
        
        Args:
            performance_data (str): Performance report data in markdown table format
            
        Returns:
            str: Performance analysis response or error message
        """
        if self.started:
            openai_response = self.ask_openai_for_pf(performance_data)
            return openai_response
        else:
            return 'OpenAI not started'
    
    def get_response_for_i18n_analysis(self, image_file, message=None):
        """
        Analyze i18n/localization issues in an image
        
        Args:
            image_file: Image file object
            message (str, optional): Custom analysis instructions
            
        Returns:
            str: I18n analysis response
        """
        image_base64 = image_obj_base64_encode(image_file)
        
        client = self.get_client()
        if self.started and client is not None:
            try:
                content = prompts_i18n_template()
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "system",
                            "content": content
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": message if message else "Please analyze the localization issues in the image."},
                                {"type": "image_url", "image_url": {"url": image_base64}},
                            ],
                        },
                    ],
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Failed to analyze i18n from image, error={e}")
                return f"Failed to analyze i18n from image, error={e}"
        else:
            return 'OpenAI not started'
        
    def get_message_response(self, message):
        client = self.get_client()
        if self.started and client is not None:
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "user", "content": message}
                    ],
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Failed to analyze uploaded image, error={e}")
                return "Analysis failed"
        else:
            return 'OpenAI not started'

    def get_response_from_image_comparison(self, reference_image, image_url, message):
        reference_image = image_obj_base64_encode(reference_image)
        image_url = image_obj_base64_encode(image_url)

        client = self.get_client()
        if self.started and client is not None:
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an AI assistant for virtual background verification in video conferencing applications. "
                                "You will be given two images: the first is the reference virtual background image, and the second is a screenshot from a video meeting. "
                                "Your task is to verify if the correct virtual background was successfully applied, considering that video processing may cause mirroring, rotation, or flipping effects. "
                                "The reference background may contain a dynamic gradient (e.g., color shifting from purple to black). "
                                "Focus on overall visual characteristics (such as color tone family, gradient direction, blending style, and theme), rather than exact pixel-by-pixel matching or element positioning. "
                                "It is acceptable if the background is not identical, as long as it shares consistent stylistic elements with the reference. "
                                "Respond using one single line only, with no line breaks, no bullet points, and no extra formatting. "
                                "Your response must follow this exact format: "
                                "Output format: ✅Success or ❌Failed"
                                "Do not add quotation marks, new lines, or markdown symbols. Only return plain text. "
                                "The entire output must be contained in one continuous line, even if long. Newline characters are strictly prohibited."
                            )
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "{message}" if message else "Verify the virtual background in the test image against the reference image."},
                                {"type": "image_url", "image_url": {"url": reference_image}},  # Reference
                                {"type": "image_url", "image_url": {"url": image_url}},         # Test image
                            ],
                        },
                    ],
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Failed to analyze uploaded image, error={e}")
                return f"Failed to analyze uploaded image, error={e}"
        else:
            return 'OpenAI not started'
        
    def get_response_from_analyze_image(self, image_url, message):
        image_url = image_obj_base64_encode(image_url)

        client = self.get_client()
        if self.started and client is not None:
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a professional assistant who specializes in analyzing software test case results. "
                                "Your goal is to help the user understand and evaluate the outcome of test cases based on their provided message and a test result image. "
                                "Carefully examine the image and consider the user's description or questions. "
                                "Provide a clear, detailed, and structured analysis, including possible reasons for any failures, potential improvements, and next action steps if needed. "
                                "Use concise technical language, highlight important visual evidence from the image, and avoid making assumptions beyond what can be clearly seen or described. "
                                "If necessary, suggest what additional data or logs the user might collect to further confirm the analysis."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": message if message else "Please analyze this test case result image."},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        },
                    ],
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Failed to analyze uploaded image, error={e}")
                return f"Failed to analyze uploaded image, error={e}"
        else:
            return 'OpenAI not started'
    
    def get_text_from_image(self, image):
        image_base64 = image_obj_base64_encode(image)

        client = self.get_client()
        if self.started and client is not None:
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an OCR (Optical Character Recognition) assistant. "
                                "Your task is to extract and transcribe all visible text from the provided image. "
                                "Please follow these guidelines: "
                                "1. Extract all text accurately, including text in different fonts, sizes, and orientations. "
                                "2. Preserve the original formatting and line breaks when possible. "
                                "3. If text is in multiple languages, transcribe them as they appear. "
                                "4. If no text is found, respond with 'No text detected'. "
                                "5. Only return the extracted text content, no additional commentary or descriptions."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Please extract all text from this image."},
                                {"type": "image_url", "image_url": {"url": image_base64}},
                            ],
                        },
                    ],
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Failed to extract text from image, error={e}")
                return f"Failed to extract text from image, error={e}"
        else:
            return 'OpenAI not started'