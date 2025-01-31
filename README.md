# Invoice Field Extraction System

A Streamlit-based web application for extracting and analyzing fields from invoice PDFs using various AI models and OCR techniques.

## Features

- PDF invoice processing and field extraction
- QR code/barcode data decoding
- Line item detection and analysis
- Document type classification
- Amount validation and standardization
- Support for both PO and Non-PO orders
- Field sanitization and validation
- Export results to CSV

## Prerequisites

### Required Python Libraries
```bash
pip install python-dotenv
pip install requests
pip install anthropic
pip install pandas
pip install streamlit
pip install python-dateutil
pip install azure-ai-vision
pip install azure-core
pip install azure-ai-formrecognizer
```

### API Keys Required
- OpenAI API credentials
- Anthropic API key
- Azure Vision API credentials
- LLM Whisperer API credentials

## Environment Setup

Create a `cloude_cred.txt` file with the following environment variables:
```
OPENAI_API_Type=
OPENAI_API_BASE=
OPENAI_API_VERSION=
OPENAI_API_KEY=
Anthropic_API_KEY=
```

## Project Structure

The system consists of several key components:

1. **Data Extraction**
   - PDF text extraction using LLM Whisperer
   - QR code/barcode data extraction
   - Form recognition using Azure AI

2. **Field Processing**
   - Key-value pair extraction
   - Line item table extraction
   - Amount validation and standardization

3. **Document Classification**
   - PO vs Non-PO classification
   - Expense category determination
   - Document type identification

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Upload a PDF invoice through the web interface

3. Click "Extract fields" to process the document

4. View results:
   - Extracted key fields
   - Line items (if present)
   - QR code data (if present)
   - Amount validation results
   - Document classification

5. Results are automatically saved as CSV files:
   - `{filename}_keyfields.csv`
   - `{filename}_line_Item_Fields.csv`

## Field Descriptions

The system extracts various fields including:
- Invoice details (number, date)
- Amount information (gross, basic, tax)
- GST-related fields (GSTIN, tax rates)
- Vendor/buyer information
- Line item details
- Document classification

## Error Handling

- The system attempts extraction up to 3 times in case of failures
- Fallback to key-only extraction if line item extraction fails
- Comprehensive error reporting in the UI

## Limitations

- Requires valid API credentials for all services
- PDF files only
- May require manual verification for complex documents
- Processing time varies based on document complexity

## Security Notes

- API keys should be stored securely
- Sensitive document information should be handled according to organizational policies
- Temporary files are created during processing

## Contributing

To contribute to this project:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description of changes

## License

[Specify your license here]

## Support

For support and questions, please contact [specify contact information]
