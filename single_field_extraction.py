import json
import os

import openai

from convert_into_layout import get_final_text

field_descriptions = {
    "Invoice_No": "What is Invoice Number? Unique identifier for the invoice assigned by the vendor or supplier.",
    "Invoice_Date": "What is Invoice Date? The invoice date is when the invoice was issued.",
    "Gross_Amount": "What is Gross Amount? Gross Amount is the total amount of the invoice, including all taxes and charges.",
    "Vendor_Supplier_GSTN": "What is Vendor or Supplier's GST Number? It is Goods and Services Tax Identification Number (GSTIN) of the vendor or supplier.",
    "Buyer_GSTN": "What is Buyer's GST Number? GSTIN of the Buyer Group entity (buyer/receiver).",
    "E_Invoice": "Tell me whether the provided invoice is E Invoice or Not. Indicates whether the invoice is an e-invoice, as mandated by the GST system.",
    "HSN_SAC_No": "What is HSN or SAC Number(s)? Harmonized System of Nomenclature (HSN) code for goods or Services Accounting Code (SAC) for services.",
    "Document_Type": "What is the document type of the provided invoice? Type of the document issued (e.g., Tax Invoice, Debit Note, Credit Note).",
    "IRN_No": "What is the IRN number in the provided invoice? Invoice Reference Number generated for e-invoices under the GST system.",
    "RCM_Applicability": "Tell me whether this invoice RCM applicable or not? Indicates whether the Reverse Charge Mechanism (RCM) is applicable.",
    "Basic_Amount": "What is the basic amount mentioned in the invoice? The total value of goods or services before applying taxes.",
    "Tax_Amount": "What is the total tax amount mentioned in the invoice? Total tax amount calculated on the basic value. We can also by subtracting Basic_Amount from Gross_Amount.",
    "NatureOfGoodService": "What is nature or goods or service? Type of goods or services described in the invoice.",
    "PO_SO_Number": "What is Purchase Order (PO) or Sales Order (SO) number associated with the invoice?",
    "CGST_Amount": "What is CGST Amount? Amount of Central Goods and Services Tax applied.",
    "SGST_Amount": "What is SGST Amount? Amount of State Goods and Services Tax applied.",
    "IGST_Amount": "What is IGST Amount? Amount of Integrated Goods and Services Tax applied.",
    "CGST_Tax_Rate": "What is CGST Tax Rate? Tax rate for CGST applied on the basic amount.",
    "SGST_Tax_Rate": "What is SGST Tax Rate? Tax rate for SGST applied on the basic amount.",
    "IGST_Tax_Rate": "What is IGST Tax Rate? Tax rate for IGST applied on the basic amount.",
    "Currency": "What is the Currency in which the invoice amount is specified. Standardize the `Currency` field using the three-letter ISO 4217 currency code.",
    "Supplier_PAN": "What is Permanent Account Number (PAN) of the supplier.",
    "Supplier_Name": "What is the Name of the vendor or supplier issuing the invoice. Look at the Invoice Issued by, Vendor or Supplier term(s)",
    "Buyer_Receiver_Name": "What is the Name of the Buyer entity receiving the goods or services. Look at the Goods Receiver or Buyer term(s)",
    "TCS Amount": "How much Tax Collected at Source (TCS) amount applicable, if any."
}


def extract_substring_after_first(string, search_substring):
    index = string.find(search_substring)
    if index != -1:
        substring = string[index + len(search_substring):]
        return substring.strip()
    else:
        return string


def get_gpt_35_output(prompt, key):
    input_messages = [
        {"role": "system",
         "content": "You are an Invoice Information Extraction Expert. You have an impeccable performance in Extracting Relevant Information from provided Invoice. "
                    "Extract relevant fields from the provided invoice. Be precise, clear, complete and to the point in your extraction. "
                    "Respond only with information that is explicitly mentioned in the Invoice. Do not include extra details or interpretations outside the Invoice. "
                    "Prioritize accuracy and relevance while generating the response."
         },
        {"role": "user",
         "content": prompt}
    ]
    response = openai.ChatCompletion.create(engine="gpt-35-turbo-16k",
                                            messages=input_messages,
                                            temperature=0.2,
                                            max_tokens=2000)

    text = response.choices[0].message.content
    json_string = extract_substring_after_first(text, "\n\n")
    try:
        json_dict = json.loads(json_string)
        value_of_key = json_dict.get(f'{key}')
    except Exception as e:
        print(f"Exception {e} occurred at extracting single key field: {key}")
        return None

    return value_of_key


def get_field_from_key(key, read_output, qr_data):
    prompt = f"{field_descriptions[key]} Please respond in JSON format with the `{key}` as the key and the extracted value as the corresponding value. Document text: {read_output} \n\n"
    if qr_data:
        prompt += f"Decode QR code data from the above invoice:\n{qr_data}"

    field_value = get_gpt_35_output(prompt, key)
    print(field_value)
    return field_value if field_value is not None else "Not Mentioned"
