import re
import numpy as np
import ast
import pandas as pd

from hsn_sac_excel_loader import sac_mapping_dict
from single_field_extraction import get_field_from_key

# Regex patterns for PAN and GST number validation
PAN_REGEX = r'^[A-Za-z]{5}\d{4}[A-Za-z]$'
GST_REGEX = r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'


def pan_sanitizer(pan_number):
    pan_number = pan_number.upper() if pan_number else None

    if pan_number and re.match(PAN_REGEX, pan_number):
        return pan_number
    return None


def gst_sanitizer(gst_number):
    gst_number = gst_number.upper() if gst_number else None

    if gst_number and re.match(GST_REGEX, gst_number):
        return gst_number
    return None


def irn_sanitizer(irn_number):
    if irn_number and len(irn_number) == 64:
        return irn_number.lower()
    return None


def binary_validator(value):
    if value in ['True', 'true', '1', True, 'Yes', 'yes']:
        return True
    elif value in ['False', 'false', '0', False, 'No', 'no', 'n/a', 'N/A', 'Not mentioned in the invoice', 'Not mentioned']:
        return False
    return None


def convert_to_none(value):
    return None if value == "None" else value
def sanitize_key_dict_data(data, read_output, qr_data):
    # Convert "None" string to None
    for key, value in data.items():
        data[key] = convert_to_none(value)

    # Sanitize GST Numbers
    data['Vendor_Supplier_GSTN'] = gst_sanitizer(data.get('Vendor_Supplier_GSTN'))
    data['Buyer_GSTN'] = gst_sanitizer(data.get('Buyer_GSTN'))

    # If both GST numbers are the same, set both to None
    if data.get('Vendor_Supplier_GSTN') and data.get('Buyer_GSTN'):
        if data['Vendor_Supplier_GSTN'] == data['Buyer_GSTN']:
            data['Vendor_Supplier_GSTN'] = get_field_from_key('Vendor_Supplier_GSTN', read_output, qr_data)
            data['Buyer_GSTN'] = get_field_from_key('Buyer_GSTN', read_output, qr_data)

    # Sanitize IRN Number
    data['IRN_No'] = irn_sanitizer(data.get('IRN_No'))

    # Sanitize E_Invoice (True/False validation) and check consistency with IRN
    data['E_Invoice'] = binary_validator(data.get('E_Invoice'))

    # If there's an IRN number, E_Invoice must be True and vice versa
    if data['IRN_No']:
        data['E_Invoice'] = True
    else:
        data['E_Invoice'] = False

    if data['E_Invoice'] is False and not data['IRN_No']:
        data['IRN_No'] = "Not Mentioned"

    # Validate RCM_Applicability (True/False validation) and check consistency with TCS Amount
    data['RCM_Applicability'] = binary_validator(data.get('RCM_Applicability'))
    if not data['RCM_Applicability'] and not data['TCS Amount']:
        data['RCM_Applicability'] = False

    # If there's an TCS Amount, RCM_Applicability must be True and vice versa
    if data['TCS Amount']:
        data['RCM_Applicability'] = True
    else:
        data['RCM_Applicability'] = False

    if data['RCM_Applicability'] is False and not data['TCS Amount']:
        data['TCS Amount'] = "Not Mentioned"

    # Sanitize Supplier PAN number If there's or if there's Vendor_Supplier_GSTN get it from it
    data['Supplier_PAN'] = pan_sanitizer(data.get('Supplier_PAN'))
    if data['Supplier_PAN'] is None and data.get('Vendor_Supplier_GSTN') and data.get('Vendor_Supplier_GSTN') != "N/A":
        data['Supplier_PAN'] = data.get('Vendor_Supplier_GSTN')[2:12]
    elif data.get('Supplier_PAN') and data.get('Vendor_Supplier_GSTN') and data.get('Vendor_Supplier_GSTN') != "N/A":
        supplier_pan = data['Vendor_Supplier_GSTN'][2:12]
        if data['Supplier_PAN'] != supplier_pan:
            data['Supplier_PAN'] = supplier_pan


    # Logic to check if PAN is for a Company
    if data['Supplier_PAN'] is not None:
        entity_type = data['Supplier_PAN'][3]

        # Check if the entity is a company
        data['Is_Company'] = (entity_type == 'C')
    else:
        data['Is_Company'] = False

    # Sanitize CGST, SGST, IGST Logic should Exclusive OR
    if data.get('CGST_Amount') and data.get('SGST_Amount') and data.get('CGST_Tax_Rate') and data.get('SGST_Tax_Rate'):
        # If both CGST and SGST are present, IGST should be N/A
        data['IGST_Amount'] = "Not Mentioned"
        data['IGST_Tax_Rate'] = "Not Mentioned"

    elif data.get('IGST_Amount') and data.get('IGST_Tax_Rate'):
        # If IGST is present, CGST and SGST should be N/A
        data['CGST_Amount'] = "Not Mentioned"
        data['SGST_Amount'] = "Not Mentioned"
        data['CGST_Tax_Rate'] = "Not Mentioned"
        data['SGST_Tax_Rate'] = "Not Mentioned"

    elif not data.get('CGST_Amount') and not data.get('SGST_Amount'):
        # If neither CGST nor SGST, IGST can be used
        if data.get('IGST_Amount') and data.get('IGST_Tax_Rate'):
            data['CGST_Amount'] = "Not Mentioned"
            data['SGST_Amount'] = "Not Mentioned"
            data['CGST_Tax_Rate'] = "Not Mentioned"
            data['SGST_Tax_Rate'] = "Not Mentioned"
        else:
            # If neither is available, set all tax fields as N/A
            data['CGST_Amount'] = "Not Mentioned"
            data['SGST_Amount'] = "Not Mentioned"
            data['IGST_Amount'] = "Not Mentioned"
            data['CGST_Tax_Rate'] = "Not Mentioned"
            data['SGST_Tax_Rate'] = "Not Mentioned"
            data['IGST_Tax_Rate'] = "Not Mentioned"

    if data.get('Gross_Amount') == '' or not data.get('Gross_Amount'):
        data['Gross_Amount'] = get_field_from_key('Gross_Amount', read_output, qr_data)

    if data.get('Basic_Amount') == '' or not data.get('Basic_Amount'):
        data['Basic_Amount'] = get_field_from_key('Basic_Amount', read_output, qr_data)

    if data.get('Tax_Amount') == '' or not data.get('Tax_Amount'):
        data['Tax_Amount'] = get_field_from_key('Tax_Amount', read_output, qr_data)

    if data.get('Currency') == '' or not data.get('Currency'):
        data['Currency'] = get_field_from_key('Currency', read_output, qr_data)

    if data.get('PO_SO_Number') == '' or not data.get('PO_SO_Number'):
        data['PO_SO_Number'] = "Not Mentioned"

    if data['Is_Company'] is not None and data.get('HSN_SAC_No'):
        if "," not in data['HSN_SAC_No']:
            # Map the SAC values based on 'HSN_SAC_No' and conditionally select the value based on is_company
            sac_mapping_tuple = sac_mapping_dict.get(data['HSN_SAC_No'])
            if sac_mapping_tuple:
                if data['Is_Company']:
                    data['Suggestive TDS Rate Basis SAC'] = sac_mapping_tuple[0]
                else:
                    data['Suggestive TDS Rate Basis SAC'] = sac_mapping_tuple[1]

            else:
                data['Suggestive TDS Rate Basis SAC'] = 'No matching HSN/SAC found'
        else:
            data['Suggestive TDS Rate Basis SAC'] = 'Multiple HSN/SAC found'
    else:
        data['Suggestive TDS Rate Basis SAC'] = 'N/A since no HSN/SAC found'

    if data.get('Supplier_Name') and data.get('Buyer_Receiver_Name'):
        if data['Supplier_Name'] == data['Buyer_Receiver_Name']:
            data['Supplier_Name'] = get_field_from_key('Supplier_Name', read_output, qr_data)
            data['Buyer_Receiver_Name'] = get_field_from_key('Buyer_Receiver_Name', read_output, qr_data)

    return data
def sanitize_line_items_data(line_items_df, is_company):
    df = line_items_df.copy()

    # Replace string representations of 'None', 'NaN', and 'null' with corresponding Python literals
    df.replace(to_replace=[r'(?i)none', r'(?i)nan', r'(?i)null'], value=[None, np.nan, np.nan], regex=True,
               inplace=True)

    # Remove columns and rows where all values are None (or NaN)
    # df = df.dropna(axis=1, how='all')
    # df = df.dropna(axis=0, how='all')

    # Check if CGST, SGST, and IGST columns exist
    cgst_columns_present = {'CGST Rate', 'CGST Amount'}.issubset(df.columns)
    sgst_columns_present = {'SGST Rate', 'SGST Amount'}.issubset(df.columns)
    igst_columns_present = {'IGST Rate', 'IGST Amount'}.issubset(df.columns)

    # Apply logic based on the presence of CGST/SGST and IGST columns
    if cgst_columns_present and sgst_columns_present:
        if igst_columns_present:
            df['IGST Rate'] = 'Not Mentioned'
            df['IGST Amount'] = 'Not Mentioned'

    elif igst_columns_present:
        if cgst_columns_present:
            df['CGST Rate'] = 'Not Mentioned'
            df['CGST Amount'] = 'Not Mentioned'
        if sgst_columns_present:
            df['SGST Rate'] = 'Not Mentioned'
            df['SGST Amount'] = 'Not Mentioned'

    HSN_SAC_Code_columns_present = {'HSN/SAC Code'}.issubset(df.columns)

    if is_company is not None and HSN_SAC_Code_columns_present:
        # Map the SAC values based on 'HSN/SAC_No' and conditionally select the value based on is_company
        df['Suggestive TDS Rate Basis SAC'] = df['HSN/SAC Code'].map(sac_mapping_dict).apply(
            lambda x: x[0] if x is not np.nan and is_company else x[1] if x is not np.nan else np.nan
        )

    # Setting the index from 1
    df.index = df.index + 1

    return df


if __name__ == '__main__':
    demo_data = {'Invoice_No': 'AVSPL/24-25/020', 'Invoice_Date': '3-Apr-24', 'Gross_Amount': '30,950.00',
                 'Vendor_Supplier_GSTN': '27AAFCA6963N1Z2', 'Adani_GSTN': '27AAACT8971E1Z3', 'E_Invoice': 'No',
                 'HSN_SAC_No': '21012090, 21011190, 9020, 1701, 21011120', 'Document_Type': 'Tax Invoice',
                 'IRN_No': 'N/A', 'RCM_Applicability': 'N/A', 'Basic_Amount': '30,950.00', 'Tax_Amount': '2,584.00',
                 'NatureOfGoodService': 'Gold Tea Premix - GAE, Gold Coffee Premix - GAC, Classic Assam Tea (100 Sachet), Sugar S/30, Instant Coffee 200gm',
                 'PO_SO_Number': 'N/A', 'CGST_Amount': '1,485.00', 'SGST_Amount': '1,485.00', 'IGST_Amount': 'N/A',
                 'CGST_Tax_Rate': '9%', 'SGST_Tax_Rate': '9%', 'IGST_Tax_Rate': 'N/A', 'Currency': 'INR',
                 'Supplier_PAN': 'N/A', 'Supplier_Name': 'Aromas Vending Services (P) Ltd',
                 'Adani_Receiver_Name': 'EXELA TECHNOLOGIES INDIA PRIVATE LIMITED', 'TCS Amount': 'N/A',
                 'Suggestive TDS Rate Basis Expense Description': 'N/A', 'Suggestive TDS Rate Basis SAC': 'N/A'}

    sanitized_data = sanitize_key_dict_data(demo_data)
    print(sanitized_data)
