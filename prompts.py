def get_analysis_prompt(ocr_text: str) -> str:
    return f"""
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
    
