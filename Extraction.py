from dotenv import load_dotenv
import requests
from anthropic import Anthropic, APIError


from pdf_qr_reader import extract_qr_data_from_pdf
from validation_rules import sanitize_key_dict_data
from validation_rules import sanitize_line_items_data


load_dotenv('cloude_cred.txt')
import openai
import json
import re
import os
import pandas as pd
import time
import streamlit as st
from dateutil import parser
from datetime import datetime


import azure.ai.vision as sdk
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from convert_into_layout import get_final_text
from temp_directory import temp_directory
from df_transformation import apply_transformations
from df_transformation import check_amounts
from df_transformation import keypairs_df_conversion
from df_transformation import convert_amountdf
from df_transformation import linetable_validation, replace_amount_rows, rcm_applicability, find_irn, replace_irn


openai.api_type = os.getenv("OPENAI_API_Type")
openai.api_base = os.getenv("OPENAI_API_BASE")
openai.api_version = os.getenv("OPENAI_API_VERSION")
openai.api_key = os.getenv("OPENAI_API_KEY")

endpoint = os.getenv("OPENAI_API_KEY")
key = os.getenv("OPENAI_API_KEY")
service_options = sdk.VisionServiceOptions(endpoint, key)

# claude_client = Anthropic(api_key=os.getenv("Anthropic_API_KEY"))

from unstract.llmwhisperer import LLMWhispererClientV2

def get_layout_from_pdf_whisperer(file_path):
    whisperer_base_url = "https://llmwhisperer-api.us-central.unstract.com/api/v2"
    whisperer_api_key = "pU9WJLt-JLYcqpHXXY-uzlaudk1MyIiJuVus6W5plKE"
    client = LLMWhispererClientV2(base_url=whisperer_base_url, api_key=whisperer_api_key)
    mode = 'high_quality'
    output_mode = 'layout_preserving'
    result = client.whisper(
        file_path=file_path,
        mode=mode,
        output_mode=output_mode if output_mode != "None" else None,
        wait_for_completion=True,
        wait_timeout=200,
    )
    return result.get("extraction", {}).get("result_text", "")

def formresult(prompt):
    response = openai.Completion.create(engine='text-davinci-003', prompt=prompt, temperature=0, max_tokens=2000,
                                        top_p=1, frequency_penalty=0, presence_penalty=0, best_of=1, stop=None)
    # print(response)
    text = response['choices'][0]['text']
    return extract_substring_after_first(text, "\n\n")
def get_claude_response(prompt):
    try:
        message = claude_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    except APIError as e:
        print(f"An API error occurred: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
def get_prompt35_output(prompt):
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
                                            temperature=0,
                                            max_tokens=2000)

    text = response.choices[0].message.content
    return extract_substring_after_first(text, "\n\n")
def run_openai_key(read_output, keypairs, key_fields_Description):
    keypairsprompt = f"Below is a sample of fields description \n {key_fields_Description}.\n\n\n" \
                     f"Extract key-value pairs {keypairs} " \
                     f"from the below text and separate them by line \n\n" \
                     f"Document text: {read_output} \n\n" \
                     f"""Guidelines:\n\n \
                        1. Since, E_Invoice and RCM_Applicability are Yes/No type fields, both should contain only boolean values.
                        2. Return `None` if not able to find it in the Invoice.
                        3. Extract all `Amount` related values without including any thousands separators (e.g., commas or spaces) or currency symbols (e.g., Rs. or $ or ₹) in the output (e.g., "$1,234.56" should be extracted as "1234.56").
                        4. Return all Rate related fields with Percentage sign at the end.
                        5. Standardize the `Currency` field using the three-letter ISO 4217 currency code.\n\n"""\
                     f"Entities:"
    keypairstext = get_prompt35_output(keypairsprompt)
    print(keypairsprompt)
    return keypairstext
def run_claude_document(read_output, document):
    keypairsprompt = f"{read_output} " \
                     f"{document}" \
                     "Guideline: In your response do not include additional comment or any explanation, return the response in json format so that I can parse it into json."

    try:
        message = claude_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            messages=[
                {"role": "user", "content": keypairsprompt}
            ]
        )

        claude_response = message.content[0].text

        print(claude_response)

        return claude_response

    except APIError as e:
        print(f"An API error occurred: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
def run_openai_document(read_output, document):
    keypairsprompt = f"{read_output} " \
                     f"{document}"
    input_messages = [
        {"role": "system",
         "content": "You are a helpful assistant."},
        {"role": "user",
         "content": keypairsprompt}
    ]

    # print("HELLOW\n")
    # print(input_messages)
    # print("YELLOW\n")

    response = openai.ChatCompletion.create(engine="gpt-35-turbo-16k",
                                            messages=input_messages,
                                            temperature=0,
                                            max_tokens=2000)

    text = response.choices[0].message.content
    return text
def convertlineitems_to_dict(input_string):
    result = {}
    lines = input_string.split('\n')
    keypairs = []
    for line in lines:
        if len(line) < 2:
            continue
        try:
            split_values = line.split(':')  # Split each line by colon (:)
            keypairs.append(split_values[0].strip())
            if len(split_values) == 1:
                if keypairs.count(split_values[0].strip()) == 1:
                    key = split_values[0].strip() + "_1"
                else:
                    key = split_values[0].strip() + "_" + str(keypairs.count(split_values[0].strip()))
                result[key] = ''
            elif len(split_values) == 2:
                if keypairs.count(split_values[0].strip()) == 1:
                    key = split_values[0].strip() + "_1"
                else:
                    key = split_values[0].strip() + "_" + str(keypairs.count(split_values[0].strip()))
                value = split_values[1].strip()
                result[key] = value
            elif len(split_values) > 2:
                if keypairs.count(split_values[0].strip()) == 1:
                    key = split_values[0].strip() + "_1"
                else:
                    key = split_values[0].strip() + "_" + str(keypairs.count(split_values[0].strip()))
                value = ':'.join(split_values[1:]).strip()
                result[key] = value
        except ValueError:
            print(line)
            continue  # Ignore lines that don't contain a colon (:)
    return result
def convert_to_lineitem_dict(input_string):
    result = {}
    line_items = input_string.split("||")
    sequence_number = 1
    for line_item in line_items:
        lines = line_item.split('\n')
        print(len(lines))
        for line in lines:
            if len(line) < 2:
                continue
            try:
                split_values = line.split(':')  # Split each line by colon (:)
                if len(split_values) == 1:
                    key = split_values[0].strip()
                    result[key] = ''
                elif len(split_values) == 2:
                    key = split_values[0].strip()
                    value = split_values[1].strip()
                    result[key] = value
                elif len(split_values) > 2:
                    key = split_values[0].strip()
                    value = ':'.join(split_values[1:]).strip()
                    result[key] = value
            except ValueError:
                print(line)
                continue  # Ignore lines that don't contain a colon (:)
    sequence_number += 1
    return result
def extract_substring_after_first(string, search_substring):
    index = string.find(search_substring)
    if index != -1:
        substring = string[index + len(search_substring):]
        return substring.strip()
    else:
        return string
def analyze_po_order_new(file_path, include_qr_data=True):
    # read_output = get_final_text(file_path)
    read_output = get_layout_from_pdf_whisperer(file_path)
    qr_data = None
    if include_qr_data:
        qr_data = extract_qr_data_from_pdf(file_path, True)
        if qr_data:
            # Convert dictionary to JSON string with indentation
            json_str = json.dumps(qr_data, indent=2)

            # Convert JSON string to markdown format
            markdown_output = f"```json\n{json_str}\n```"

            read_output += f"\n\nHere the QR code decoded data extracted from the invoice to validate your extractions:\n\n{markdown_output}"
    return read_output, qr_data
def linetable_dict_convert(linetabletext):
    linetable_dict = convertlineitems_to_dict(linetabletext)
    linetable_dict = {**linetable_dict}
    for key, value in linetable_dict.items():
        if key.startswith('Quantity_'):
            try:
                linetable_dict[key] = re.search(r'\d+(\.\d+)?', str(value)).group()
            except:
                pass
        if key.startswith('Price_'):
            try:
                linetable_dict[key] = re.search(r'\d+(?:,\d+)*(?:\.\d+)?', str(value)).group()
            except:
                pass
        if key.startswith('Tax_'):
            try:
                linetable_dict[key] = re.search(r'\d+(?:,\d+)*(?:\.\d+)?', str(value)).group()
            except:
                pass
        if key.startswith('ExtendedPrice/LineValue/NetValue_'):
            try:
                linetable_dict[key] = re.search(r'\d+(?:,\d+)*(?:\.\d+)?', str(value)).group()
            except:
                pass
    linetable_df = pd.DataFrame(data=linetable_dict, index=[0])
    linetable_df = linetable_df.T
    linetable_df.reset_index(inplace=True)
    linetable_df.columns = ["key", "value"]
    linetable_df['source'] = 'OpenAI Linetable'
    return linetable_dict, linetable_df
def key_dict_convert(keypairstext, read_output, qr_data):
    key_dict = convert_to_lineitem_dict(keypairstext)

    # Sanitize the key_dict here
    key_dict = sanitize_key_dict_data(key_dict, read_output, qr_data)
    is_company = key_dict.get('Is_Company')

    key_dict = {**key_dict}
    try:
        key_dict['Invoice/PO/Order Total'] = re.search(r'\d+(?:,\d+)*(?:\.\d+)?',
                                                       str(key_dict['Invoice/PO/Order Total'])).group()

    except:
        pass
    keypairs_df = pd.DataFrame(data=key_dict, index=[0])
    keypairs_df = keypairs_df.T
    keypairs_df.reset_index(inplace=True)
    keypairs_df.columns = ["key", "value"]
    keypairs_df['source'] = 'OpenAI KeyValue'
    return key_dict, keypairs_df, is_company
def run(filepath, keypairs, linepairs, key_fields_Description, document):
    read_output, qr_data = analyze_po_order_new(filepath)
    keypairstext = run_openai_key(read_output, keypairs, key_fields_Description)
    linetabletext = run_openai_line(read_output)
    print(read_output)
    # linetable_dict, linetable_df = linetable_dict_convert(linetabletext)
    k = []
    for y in [x.split(",,") for x in linetabletext.split("\n")]:
        # m.append([i.split(":")[1].strip() for i in m[0] if ":" in i])
        k.append([i.split(":")[1].strip() for i in y if ":" in i])
    linetable_df = pd.DataFrame(k)
    linetable_df.columns = ["HSN/SAC Code", "Item_Description", "Item_Code", "Quantity", "Price", "CGST Rate",
                            "CGST Amount", "SGST Rate", "SGST Amount", "IGST Rate", "IGST Amount", "Total Amount"]
    linetable_df=linetable_df[linetable_df['Item_Description']!=None]
    linetable_df = linetable_df[linetable_df['Item_Description'] != 'None']

    print("linetable_df")
    print(linetable_df)
    print("\n\n\n")

    try:
        document_type = run_claude_document(read_output, document)
        dictionary = json.loads(document_type)
        po_nonpo = dictionary["document_type"].split("---")
        po_nonpo = ["Claude: " + x for x in po_nonpo]
    except:
        document_type = run_openai_document(read_output, document)
        dictionary = json.loads(document_type)
        po_nonpo = dictionary["document_type"].split("---")
        po_nonpo = ["openai: " + x for x in po_nonpo]

    key_dict, keypairs_df, is_company = key_dict_convert(keypairstext, read_output, qr_data)
    print("\n\n\n")
    print("keypairs_df")
    print(keypairs_df)
    linetable_df = sanitize_line_items_data(linetable_df, is_company)
    linetable_df = linetable_validation(linetable_df)
    if linepairs != "":
        linetabletext = run_openai_line(read_output, linepairs)
        linetable_dict, linetable_df = linetable_dict_convert(linetabletext)
        keypairs_df = keypairs_df_conversion(keypairs_df)
        finaldf = pd.concat([keypairs_df, linetable_df])
    else:
        keypairs_df = keypairs_df_conversion(keypairs_df)
        finaldf = keypairs_df
    # finaldf['key'] = finaldf['key'].str.lower()
    finaldf = finaldf[["key", "value"]]
    # Add new column 'item_id' with values from 0 to the number of rows - 1
    linetable_df['item_id'] = range(1, len(linetable_df) + 1)
    # Reordering columns to add 'item_id' at the start
    linetable_df = linetable_df[['item_id'] + [col for col in linetable_df.columns if col != 'item_id']]
    # Converting 'item_id' to string
    linetable_df['item_id'] = linetable_df['item_id'].astype(str)
    return read_output, finaldf, linetable_df, po_nonpo, qr_data
def run_openai_line(read_output):
    linetableprompt = f"Extract  HSN/SAC Code, Item_Description, Item_Code, Quantity, UnitPrice, CGST Rate, CGST Amount, SGST Rate, SGST Amount, IGST Rate, IGST Amount, Total Amount \n\n \
            from the below text for all line items and separate them by | for each line item and separate by ,, for each field  \
            example: HSN/SAC Code: 1234,,Item_Description: Item1,,Item_Code: 1234,,Quantity: 10,,UnitPrice: 100,,CGST Rate: 10,,CGST Amount: 10,,SGST Rate: 10,,SGST Amount: 10,,IGST Rate: 10,,IGST Amount: 10,,Total Amount: 200,,\n\n \
            Text:{read_output} \n\n \
            Guidelines for extraction: \n \
                1. Carefully identify how many line items are there in the whole invoice and provide your response in accurate format as explained in the example.\n \
                2. Sometimes Item_Code might not present in the Invoice, so return `None` value in that case.\n \
                3. Return all Amount related fields in numerical format such as Integer or Float, without using thousands separator like comma.\n \
                4. If both CGST Rate, SGST Rate, CGST Amount, and SGST Amount are all provided for a particular line item, return both IGST Rate and IGST Amount as `None`.\n \
                5. Conversely, if IGST Rate and IGST Amount are provided, return both CGST Rate, CGST Amount, SGST Rate, and SGST Amount as `None`.\n \
                6. Note that for any given line item, either CGST and SGST (with their respective Rate and Amount) will be provided, or IGST (with its Rate and Amount) will be provided, but **not** both. This means the rates and amounts of CGST & SGST and IGST are mutually exclusive (i.e., one set of rates and amounts will exist, not both).\n \
                7. Identify the invoicing currency and put the `UnitPrice` field with accurate prefix.\n \
                8. Identify the quantity unit accurately and put the `Quantity` field with accurate suffix.\n \
                9. Return all `Rate` related fields with Percentage sign at the end.\n\n \
            Entities:"

    linetabletext = get_prompt35_output(linetableprompt)
    return linetabletext
def run_only_keys(filepath, keypairs, linepairs, key_fields_Description, document):
    read_output, qr_data = analyze_po_order_new(filepath)
    keypairstext = run_openai_key(read_output, keypairs, key_fields_Description)
    print(read_output)
    try:
        document_type = run_claude_document(read_output, document)
        dictionary = json.loads(document_type)
        po_nonpo = dictionary["document_type"].split("---")
        po_nonpo = ["Claude: " + x for x in po_nonpo]
    except:
        document_type = run_openai_document(read_output, document)
        dictionary = json.loads(document_type)
        po_nonpo = dictionary["document_type"].split("---")
        po_nonpo = ["openai: " + x for x in po_nonpo]

    key_dict, keypairs_df, is_company = key_dict_convert(keypairstext, read_output, qr_data)
    print("\n\n\n")
    print("keypairs_df")
    print(keypairs_df)
    keypairs_df = keypairs_df_conversion(keypairs_df)
    finaldf = keypairs_df
    # finaldf['key'] = finaldf['key'].str.lower()
    finaldf = finaldf[["key", "value"]]
    return read_output, finaldf, po_nonpo, qr_data


title_text = "<h1 style='color: gray; font-family: Arial; font-size: 24px;'>Prakash Invoice Fields Extraction</h1>"
st.write(title_text, unsafe_allow_html=True)

# User input for filename
# filepath = st.text_input("Enter the file path:")
# title_text = "<h1 style='color: gray; font-family: Arial; font-size: 24px;'>PDF File Uploader</h1>"
# st.write(title_text, unsafe_allow_html=True)
filename = st.file_uploader("Upload a PDF file", type="pdf")
temp_path = r"D:\Prakash\Results"
temp_file_path = temp_directory(temp_path, filename)

##################### Documnet Fields ###############
KeyFields = "Invoice_No, Invoice_Date, Total Gross Amount/Total Amount After Tax, Vendor_Supplier_GSTN, Buyer_GSTN, E_Invoice, HSN_SAC_No, Document_Type, IRN_No, RCM_Applicability, Basic_Amount/Total Amount Before Tax, Total_Tax_Amount, Nature Of Good Service, PO_SO_Number, CGST_Amount, SGST_Amount, IGST_Amount, CGST_Tax_Rate, SGST_Tax_Rate, IGST_Tax_Rate, Currency, Supplier_PAN, Supplier_Name, Buyer_Receiver_Name, TCS Amount"
LineFields = ""
key_fields_Description = """
\nField Descriptions are Below

Field: Invoice_No
Description: A unique alphanumeric identifier for each purchase order, assigned by the vendor or supplier.

Field: Invoice_Date
Description: The exact date when the purchase order was generated or issued.

Field: Gross_Amount
Description: The total payable amount for the purchase order, inclusive of all taxes (e.g., GST), charges, discounts, and additional fees. It represents the final amount to be paid by the buyer.

Field: Vendor_Supplier_GSTN
Description: The GST Identification Number (GSTIN) of the vendor or supplier, a unique 15-character number issued by the GST authorities. This field is crucial for validating tax compliance and filing GST returns.

Field: Buyer_GSTN
Description: The GSTIN of the buyer or receiver. This identifier ensures that both the buyer and seller comply with GST regulations and facilitates accurate input tax credit claims.

Field: E_Invoice
Description: A boolean or categorical indicator specifying whether the invoice is an electronically generated e-invoice, mandated under GST regulations. E-invoices typically include an Invoice Reference Number (IRN) and a QR code.

Field: HSN_SAC_No
Description: The Harmonized System of Nomenclature (HSN) code for goods or Services Accounting Code (SAC) for services. These codes standardize classification, essential for GST compliance, and accurate tax calculation.

Field: Document_Type
Description: Indicates the type of purchase order issued, such as a Tax Invoice, Debit Note, or Credit Note.

Field: IRN_No
Description: The Invoice Reference Number, a unique identifier generated for e-invoices under the GST framework. It acts as a digital signature for the invoice, ensuring authenticity and traceability.

Field: RCM_Applicability
Description: A flag or indicator denoting if the Reverse Charge Mechanism (RCM) applies. Under RCM, the buyer is responsible for paying GST directly to the government instead of the supplier.

Field: Basic_Amount
Description: The net value of goods or services before any taxes are applied. This amount serves as the base for calculating applicable taxes like CGST, SGST, or IGST.

Field: Tax_Amount
Description: The total amount of tax levied on the document. This can be derived by subtracting the Basic_Amount from the Gross_Amount or by summing individual tax components (e.g., CGST, SGST, IGST).

Field: Nature of Goods & Services
Description: Describes the type or category of goods or services detailed in the purchase order. You can use Items sold in the purchase order as a reference.

Field: PO_SO_Number
Description: The associated Purchase Order (PO) or Sales Order (SO) number. It links the purchase order to specific orders, ensuring traceability in procurement and sales processes.

Field: CGST_Amount
Description: The amount of Central Goods and Services Tax applied to the basic value. This is applicable for intra-state transactions under GST laws.

Field: SGST_Amount
Description: The amount of State Goods and Services Tax applied to the basic value. This is applicable for intra-state transactions under GST laws.

Field: IGST_Amount
Description: The amount of Integrated Goods and Services Tax applied to the basic value. IGST is levied on inter-state transactions and shared between the central and state governments.

Field: CGST_Tax_Rate
Description: The percentage rate of CGST levied on the basic amount of the Purchase Order.

Field: SGST_Tax_Rate
Description: The percentage rate of SGST levied on the basic amount of the Purchase Order.

Field: IGST_Tax_Rate
Description: The percentage rate of IGST levied on the basic amount of the Purchase Order.

Field: Currency
Description: Specifies the currency in which the Purchase Order is denominated (e.g., INR, USD). This field ensures accurate financial reporting and currency conversion where necessary.

Field: Supplier_PAN
Description: The Permanent Account Number (PAN) of the supplier. This tax identification number is used for income tax purposes and ensures compliance with Indian tax regulations.

Field: Supplier_Name
Description: The name of the vendor or supplier issuing the Purchase Order. This field is essential for identification and record-keeping.

Field: Buyer_Receiver_Name
Description: The name of the buyer or receiver of goods/services. This helps in documenting the transaction and ensuring correct delivery.

Field: TCS Amount
Description: The amount of Tax Collected at Source (TCS), if applicable. TCS is collected by the seller at the time of sale and remitted to the government.
\n"""
document = """
Can you tell me document type of above document from below category list, by looking at the items description or nature of goods and services provided in the above document?

> Statutory / Government --- Custom Establishment Charges
> Statutory / Government --- License Fee-Railways Land
> Statutory / Government --- Port dues
> Statutory / Government --- Rail charges
> Statutory / Government --- Rates & Taxes
> Statutory / Government --- Taxes on Property
> Statutory / Government --- Terminal Royalty Expenditure
> Statutory / Government --- SEZ Establishment Charges
> Statutory / Government --- All dues payable to Government Authorities or any Statutory Bodies
> Statutory / Government --- Penalties/fines/interest of penal nature (Statutory and Government related transactions)
> Utility Payments --- Electricity Payments to Vendor / Dealer / Rental Owners (other than electricity board)
> Utility Payments --- Telephone expenses
> Utility Payments --- Leased line fees
> Intra Group Expenses --- Intra Group expenses in the nature of cost allocation
> CMN / MD / CXO / BD / Corp Comm / Corporate Affairs related expense --- Donation – Political
> CMN / MD / CXO / BD / Corp Comm / Corporate Affairs related expense --- Donation – Non-Political
> CMN / MD / CXO / BD / Corp Comm / Corporate Affairs related expense --- Bid and Tender Expenses directly paid to the company/authority who has issued the tender (other than third-party reimbursements) 
> CMN / MD / CXO / BD / Corp Comm / Corporate Affairs related expense --- Sponsorship
> Land purchases/ ROW Statutory and compensation related Expenses --- Land Procurement
> Land purchases/ ROW Statutory and compensation related Expenses --- Land - Brokerage & Commission charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Compensation
> Land purchases/ ROW Statutory and compensation related Expenses --- Right of Use / Way
> Land purchases/ ROW Statutory and compensation related Expenses --- Crop and farmer compensation
> Land purchases/ ROW Statutory and compensation related Expenses --- Land Development Expenses
> Land purchases/ ROW Statutory and compensation related Expenses --- Lease of Land
> Land purchases/ ROW Statutory and compensation related Expenses --- Legal and licence charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Stamp duty & registration charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Compensation for relocation
> Land purchases/ ROW Statutory and compensation related Expenses --- Rehabilitation & Resettlement (R8R) expenses
> Land purchases/ ROW Statutory and compensation related Expenses --- Inspection
> Land purchases/ ROW Statutory and compensation related Expenses --- Survey & Lawyer charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Shut down charges of transmission line
> Land purchases/ ROW Statutory and compensation related Expenses --- Charges for crossing the railway line, highway, bridge
> Land purchases/ ROW Statutory and compensation related Expenses --- Forest Charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Penalties/fines/interest of penal nature (Statutory related)
> Land purchases/ ROW Statutory and compensation related Expenses --- Measurement fees / Registration / Stamp duty / Lawyer
> Land purchases/ ROW Statutory and compensation related Expenses --- Non-agriculture land conversion charges
> Land purchases/ ROW Statutory and compensation related Expenses --- Land payments – real estate business
> Land purchases/ ROW Statutory and compensation related Expenses --- Rates & taxes
> Land purchases/ ROW Statutory and compensation related Expenses --- Consultancy / professional / certification fee related to Land
> Finance & Secretarial and other functions / activities related expenses --- License Charges paid to Government Authorities or Statutory Bodies 
> Finance & Secretarial and other functions / activities related expenses --- Fees / custody fees payable to Stock Exchange, ROC, SEBI, NSDL/CDSL and other depositories
> Finance & Secretarial and other functions / activities related expenses --- One time certification fee (where no milestone payment is involved)
> Finance & Secretarial and other functions / activities related expenses --- Qualified Coordinating Agent (QCA) Payments on account of Deviation Settlement Mechanism (DSM) Reimbursements
> Human Resource --- Sodexo Payment-Meal Voucher/Coupon (to the extent it is deducted from the employee’s salary)
> Human Resource --- Pluxee fuel reimbursement and lease plan invoices
> Human Resource --- Superannuation and National Pension Scheme Payments
> Secretarial --- Filing & Listing Fees
> Secretarial --- Statutory Expenses (reimbursement made to third party)
> Secretarial --- Artwork/ Publication of Results
> Secretarial --- Demat Account Charges
> Admin Expenses --- Office expenses for new project (Grocery, Vegetables, Milk, Gas, Cylinders, News Papers, Linen, Crockery)
> Expense Categories- Upto INR 20,000 --- Loading and unloading expenses
> Expense Categories- Upto INR 20,000 --- Weight and measurement charges (equipment calibration) paid to third party
> Expense Categories- Upto INR 20,000 --- Water Tanker/Drinking Water
> Expense Categories- Upto INR 10,000 --- Fuel Payments (all location)
> Expense Categories- Upto INR 10,000 --- Transportation Expenses
> Expense Categories- Upto INR 5,000 --- Admin Expense (including courier charges, stationary)
> Expense Categories- Upto INR 5,000 --- Doctor on call and Medicines
> Expense Categories- Upto INR 5,000 --- Factory & Office Expenses
> Expense Categories- Upto INR 5,000 --- Fire & Safety Expenses
> Expense Categories- Upto INR 5,000 --- Housekeeping Expenses
> Expense Categories- Upto INR 5,000 --- Pest Control Services
> Expense Categories- Upto INR 5,000 --- Horticulture Expenses
> Other expenses --- Domestic Seminar & Conference
> Expenses incurred in exigency --- Expenses incurred in exigency (Maximum up to INR 1 lac per transaction)
> Chairman / Promoter / CEO Office related expenses --- Biz. Promotion/Stall
> Chairman / Promoter / CEO Office related expenses --- Advertisement
> Chairman / Promoter / CEO Office related expenses --- Guest - Gifts/Event/Party/Business Entertainment Exp.
> Chairman / Promoter / CEO Office related expenses --- Credit Card Fuel Expenses for Executive Protection Vehicles
> Chairman / Promoter / CEO Office related expenses --- Repair & Maintenance of Executive Protection Vehicles
> Chairman / Promoter / CEO Office related expenses --- Vehicle Hiring Charges
> Chairman / Promoter / CEO Office related expenses --- Travel Expenses – Guests
> Chairman / Promoter / CEO Office related expenses --- Domestic Travel Expenses – Staff
> Chairman / Promoter / CEO Office related expenses --- Foreign Travel Expenses – Staff
> Chairman / Promoter / CEO Office related expenses --- Mobile Bill / Data Card Charges
> Chairman / Promoter / CEO Office related expenses --- Staff Welfare / Food Expenses
> Chairman / Promoter / CEO Office related expenses --- Security Automation Expenses
> Karnavati Aviation Private Limited --- Domestic travel staff / others
> Karnavati Aviation Private Limited --- Landing and parking, ambulance and fire tender
> Karnavati Aviation Private Limited --- Airport fees/charges
> Karnavati Aviation Private Limited --- Airport operational expenses
> Karnavati Aviation Private Limited --- Vehicle hiring charges
> Karnavati Aviation Private Limited --- Foreign travel expenses staff / others
> Karnavati Aviation Private Limited --- Factory / office expenses
> Karnavati Aviation Private Limited --- Airport PSF charges
> Karnavati Aviation Private Limited --- Airport RNFC and TNLC charges
> Karnavati Aviation Private Limited --- Airport ground handling charges
> Invoice --- Invoice
> Legal services --- Legal fees


Provide the output in json format
Example 1: {"document_type": "Statutory / Government --- Port dues"}
Example 2: {"document_type": "Legal services --- Legal fees"}
Example 3: {"document_type": "Invoice --- Invoice"}
"""
##################### Documnet Fields ###############

trys=0

if st.button("Extract fields"):
    start = time.time()
    st.info("Extraction of above document...")
    while trys<3:
        trys = trys + 1
        try:
            ############################# PDF Extrcation & LLM Extraction ##################################
            try:
                read_output, finaldf, linetable_df, po_nonpo, qr_data = run(temp_file_path,
                                                                                 KeyFields,
                                                                                 LineFields,
                                                                                 key_fields_Description,
                                                                                 document)
            except:
                read_output, finaldf, po_nonpo, qr_data = run_only_keys(temp_file_path,
                                                                        KeyFields,
                                                                        LineFields,
                                                                        key_fields_Description,
                                                                        document)
            # st.info("OCR Extraction")
            # st.text(read_output)
            # st.markdown(f"```\n{read_output}\n```")
            ###############################################################################
            print(finaldf)
            try:
                NIS_Expense_Category = po_nonpo[0].strip()
                NIS_Expense_Sub_Category = po_nonpo[1].strip()
                if 'Invoice' in NIS_Expense_Category:
                    # title_text = "<h1 style='color: gray; font-family: Arial; font-size: 24px;'>Order Type</h1>"
                    # st.write(title_text, unsafe_allow_html=True)
                    # title_text = "<h1 style='color: blue; font-family: Arial; font-size: 18px;'>PO Order</h1>"
                    # st.write(title_text, unsafe_allow_html=True)
                    new_rows = pd.DataFrame({
                        'key': ['Order Type', 'NIS_Expense_Category', 'NIS_Expense_Sub_Category'],
                        'value': ['Purchase Order', NIS_Expense_Category, NIS_Expense_Sub_Category]
                        # 'value': ['Purchase Order', 'Purchase Order', 'Purchase Order']
                        # 'value': ['Purchase Order', 'N/A since Purchase Order', 'N/A since Purchase Order']
                    })
                    # Concatenate the new rows to the existing dataframe
                    finaldf = pd.concat([finaldf, new_rows], ignore_index=True)
                else:
                    # title_text = "<h1 style='color: gray; font-family: Arial; font-size: 24px;'>Order Type</h1>"
                    # st.write(title_text, unsafe_allow_html=True)
                    # title_text = "<h1 style='color: blue; font-family: Arial; font-size: 18px;'>Non-PO Order</h1>"
                    # st.write(title_text, unsafe_allow_html=True)
                    new_rows = pd.DataFrame({
                        'key': ['Order Type', 'NIS_Expense_Category', 'NIS_Expense_Sub_Category'],
                        'value': ['Non Purchase Order', NIS_Expense_Category, NIS_Expense_Sub_Category]
                    })
                    # Concatenate the new rows to the existing dataframe
                    finaldf = pd.concat([finaldf, new_rows], ignore_index=True)
            except:
                pass
            ###############################################################################
            try:
                transformed_df = apply_transformations(finaldf)
                # st.info("Fields Extraction")
                # st.dataframe(transformed_df, width=1000, height=37 * transformed_df.shape[0], hide_index=True)
            except:
                pass
            ###############################################################################
            try:
                # st.info("Amounts Check")
                amountdf, txt = check_amounts(finaldf)
                amountdf = amountdf[["key", "value"]]
                transformed_amountdf = apply_transformations(amountdf)
                # st.dataframe(transformed_amountdf,  width=1000, hide_index=True)
            except:
                pass
            ###############################################################################
            try:
                # st.info("Amounts Check")
                transformed_convert_amountdf = apply_transformations(convert_amountdf(amountdf))
                # st.dataframe(transformed_convert_amountdf,  width=1000, hide_index=True)
            except:
                pass
            ###############################################################################
            # st.info("Final")
            transformed_convert_amountdf = replace_amount_rows(transformed_df, transformed_convert_amountdf)
            transformed_irn_df = find_irn(read_output, ["irn", "invoice ref no.", "invoice reference number",
                                                        "invoice reference no.", "invoice reference no"])
            transformed_convert_amountdf = replace_irn(transformed_convert_amountdf, transformed_irn_df)
            transformed_convert_amountdf = rcm_applicability(transformed_convert_amountdf)
            st.dataframe(transformed_convert_amountdf,  width=1000, hide_index=True)
            transformed_convert_amountdf.to_csv(".".join(temp_file_path.split(".")[:-1]) + "_keyfields.csv")
            # st.text(txt)
            ###############################################################################
            try:
                # title_text = "<h1 style='color: gray; font-family: Arial; font-size: 24px;'>Line Items Extraction</h1>"
                # st.write(title_text, unsafe_allow_html=True)
                st.info("Line Items Extraction")
                st.dataframe(linetable_df, width=1000, hide_index=True)
                linetable_df.to_csv(".".join(temp_file_path.split(".")[:-1]) + "_line_Item_Fields.csv")
            except:
                pass
            ###############################################################################
            if qr_data:
                title_text = f"<h1 style='color: blue; font-family: Arial; font-size: 18px;'>QR code/Bar code decoded data from Invoice</h1>"
                st.write(title_text, unsafe_allow_html=True)
                st.json(qr_data)
            ###############################################################################
            stop = time.time()
            execution_time = stop - start
            print(f"Execution time: {execution_time} seconds")
            trys = 4
        except:
            if trys == 3:
                st.error("Extraction failed")
