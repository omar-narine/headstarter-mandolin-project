import base64
import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from mistralai import Mistral
from openai import OpenAI
from dotenv import load_dotenv

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
def process_with_openai(ocr_text: str) -> str:
    """Process OCR text with OpenAI to extract structured information."""

    openai_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    
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
        model="google/gemini-2.5-flash-preview-05-20",
        messages=[
            {"role": "developer", "content": "You are a medical document analysis assistant. Extract and structure key information from medical documents in JSON format."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={ "type": "json_object" }
    )
    
    
    print(response.choices[0].message.content)
    return response.choices[0].message.content



# Process the OCR text with OpenAI
try:
    openai_analysis = process_with_openai(structured_response.pages[0].markdown)
    
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

