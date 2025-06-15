import base64
import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from mistralai import Mistral
from openai import OpenAI

# Pydantic models for structured data
class OCRTextBlock(BaseModel):
    text: str
    confidence: float
    bounding_box: Optional[List[float]] = None

class OCRPage(BaseModel):
    page_number: int
    text_blocks: List[OCRTextBlock]
    width: float
    height: float

class OCRResponse(BaseModel):
    text: str
    pages: List[OCRPage]
    metadata: dict = Field(default_factory=dict)

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

api_key = os.environ["MISTRAL_API_KEY"]
client = Mistral(api_key=api_key)

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
        text=ocr_response.text,
        pages=[
            OCRPage(
                page_number=page.get('page_number', i),
                text_blocks=[
                    OCRTextBlock(
                        text=block.get('text', ''),
                        confidence=block.get('confidence', 0.0),
                        bounding_box=block.get('bounding_box', None)
                    )
                    for block in page.get('text_blocks', [])
                ],
                width=page.get('width', 0.0),
                height=page.get('height', 0.0)
            )
            for i, page in enumerate(ocr_response.pages or [])
        ],
        metadata=ocr_response.metadata or {}
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
def process_with_openai(ocr_text: str) -> str:
    """Process OCR text with OpenAI to extract structured information."""
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    prompt = f"""
    Analyze the following OCR text from a medical document and extract key information in a structured format.
    Focus on identifying:
    - Patient information
    - Medical conditions
    - Medications
    - Dates
    - Important medical terms
    
    OCR Text:
    {ocr_text}
    
    Please provide a structured analysis of this information in JSON format.
    """
    
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a medical document analysis assistant. Extract and structure key information from medical documents in JSON format."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={ "type": "json_object" }
    )
    
    return response.choices[0].message.content

# Process the OCR text with OpenAI
try:
    openai_analysis = process_with_openai(structured_response.text)
    
    # Save the complete analysis
    results = {
        "ocr_response": structured_response.model_dump(),
        "openai_analysis": json.loads(openai_analysis)
    }
    
    with open('document_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Analysis complete. Results saved to document_analysis.json")
    
except Exception as e:
    print(f"Error in OpenAI processing: {e}")

