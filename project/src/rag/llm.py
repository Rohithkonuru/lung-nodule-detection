import os
import google.generativeai as genai
from typing import Optional

def run_llm(prompt: str, max_tokens: int = 500, model: str = "models/gemini-2.5-pro") -> str:
    """Run LLM inference using Google Gemini API.

    Args:
        prompt: Input prompt for the LLM
        max_tokens: Maximum tokens to generate
        model: Model name (default: gemini-pro)

    Returns:
        Generated text response
    """
    try:
        api_key = os.getenv("gemini_apikey")
        if not api_key:
            raise ValueError("gemini_apikey not found in environment variables")

        # Configure each call so that dotenv-loaded values are taken into account
        genai.configure(api_key=api_key)

        model_instance = genai.GenerativeModel(
            model_name=model,
            system_instruction="You are a medical expert specializing in lung nodule analysis and pulmonology. Provide accurate, evidence-based clinical insights."
        )

        response = model_instance.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.4,
                top_p=0.9
            )
        )

        return response.text.strip()

    except Exception as e:
        print(f"LLM Error: {e}")
        return f"Error generating response: {str(e)}"
