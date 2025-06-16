import base64
import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from mistralai import Mistral
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import get_ocr_analysis_prompt, get_system_prompt

# Load environment variables from .env file
load_dotenv()

# Pydantic models for structured data
class ImageData(BaseModel):
    id: str
    top_left_x: int
    top_left_y: int
    bottom_right_x: int
    bottom_right_y: int
    image_base64: str

class PageDimensions(BaseModel):
    dpi: int
    height: int
    width: int

class OCRPage(BaseModel):
    index: int
    markdown: str
    images: List[ImageData]
    dimensions: PageDimensions

class OCRResponse(BaseModel):
    pages: List[OCRPage]

def encode_pdf(pdf_path):
    """Encode the pdf to base64."""
    try:
        with open(pdf_path, "rb") as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file {pdf_path} was not found.")
        return None
    except Exception as e:  # Added general exception handling
        print(f"Error: {e}")
        return None

# Path to your pdf
pdf_path = "./Input Data/Abdulla/PA.pdf"

# Getting the base64 string
base64_pdf = encode_pdf(pdf_path)

mistrtal_api_key = os.environ["MISTRAL_API_KEY"]
client = Mistral(api_key=mistrtal_api_key)

''' 
STEP 1:
Mistral OCR API Call
- model: mistral-ocr-latest
- document:
    - type: document_url
    - document_url: base64 encoded pdf
- include_image_base64: True
- response_format: markdown

Parses over the Base64 encoded PA PDF and returns a JSON object with markdown text
containing the contents of the PDF.
'''
ocr_response = client.ocr.process(
    model="mistral-ocr-latest",
    document={
        "type": "document_url",
        "document_url": f"data:application/pdf;base64,{base64_pdf}" 
    },
    include_image_base64=True,
)

# Convert Mistral response to our Pydantic model
try:
    structured_response = OCRResponse(
        pages=[
            OCRPage(
                index=page.index,
                markdown=page.markdown,
                images=[
                    ImageData(
                        id=image.id,
                        top_left_x=image.top_left_x,
                        top_left_y=image.top_left_y,
                        bottom_right_x=image.bottom_right_x,
                        bottom_right_y=image.bottom_right_y,
                        image_base64=image.base64
                    )
                    for image in page.images
                ],
                dimensions=PageDimensions(
                    dpi=page.dimensions.dpi,
                    height=page.dimensions.height,
                    width=page.dimensions.width
                )
            )
            for i, page in enumerate(ocr_response.pages or [])
        ]
    )

    # Save structured OCR response
    with open('structured_ocr_response.json', 'w') as f:
        json.dump(structured_response.model_dump(), f, indent=2)

except Exception as e:
    print(f"Error processing OCR response: {e}")
    # Save raw response for debugging
    with open('raw_ocr_response.txt', 'w') as f:
        f.write(str(ocr_response))

'''
STEP 2:
LLM Pre-Processing API Call
- model: gpt-4-turbo-preview
- text:
    - type: markdown
    - markdown: markdown text from the OCR response
- response_format: json_object

Parses over the markdown text from the OCR response and returns a JSON object with 
the fillable fields parsed out and their corresponding value types.
'''
def process_with_llm(ocr_text: str) -> str:
    """Process OCR text with LLMs to extract structured information."""
    
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    system_prompt = get_system_prompt()
    prompt = get_ocr_analysis_prompt(ocr_text)
    
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json"),
        contents=[prompt]
    )
    
    print(response.text)
    return response.text
    
try:
    llm_analysis = process_with_llm(structured_response.pages[1].markdown)
    
    # Save the complete analysis
    results = {
        "ocr_response": structured_response.model_dump(),
        "llm_analysis": json.loads(llm_analysis)
    }
    
    with open('document_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Analysis complete. Results saved to document_analysis.json")
    
except Exception as e:
    print(f"Error in LLM processing: {e}")


'''

'''