import fitz
from pyzbar.pyzbar import decode
from PIL import Image
import io
import base64
import json
from collections import defaultdict
import logging as log


def extract_qr_codes_from_pdf(pdf_path):
    try:
        document = fitz.open(pdf_path)
    except Exception as e:
        log.error(f"Error opening PDF file {pdf_path}: {e}")
        return {}

    qr_codes_by_page = {}

    for page_num in range(len(document)):
        try:
            page = document.load_page(page_num)
            image_list = page.get_images(full=True)
        except Exception as e:
            log.error(f"Error processing page {page_num + 1} in PDF: {e}")
            continue

        page_qr_codes = []

        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = document.extract_image(xref)
                image_bytes = base_image["image"]
                image = Image.open(io.BytesIO(image_bytes))
                decoded_objects = decode(image)

                for obj in decoded_objects:
                    page_qr_codes.append(obj.data.decode("utf-8"))
            except Exception as e:
                log.error(f"Error decoding image on page {page_num + 1}, image index {img_index}: {e}")

        if page_qr_codes:
            qr_codes_by_page[page_num + 1] = page_qr_codes

    return qr_codes_by_page


def is_jwt(token):
    if token.count('.') != 2:
        return False

    parts = token.split('.')

    try:
        header = base64.urlsafe_b64decode(parts[0] + "==")
        payload = base64.urlsafe_b64decode(parts[1] + "==")

        header_json = json.loads(header)
        payload_json = json.loads(payload)

        if "alg" not in header_json or "typ" not in header_json or header_json["typ"] != "JWT":
            return False

        return True
    except Exception as e:
        return False


def decode_jwt(token):
    parts = token.split('.')
    try:
        header = base64.urlsafe_b64decode(parts[0] + "==")
        header_json = json.loads(header)

        payload = base64.urlsafe_b64decode(parts[1] + "==")
        payload_json = json.loads(payload)
    except Exception as e:
        log.error(f"Error decoding JWT token: {e}")
        return None, None

    return header_json, payload_json


def sanitize_qr_code_decoded_data(extracted_qr_code_data):
    if extracted_qr_code_data is None:
        return {}

    else:
        seen_values = set()
        result = {}
        data_counter = 1

        for key, value in extracted_qr_code_data.items():
            # Check if the key starts with 'data' and if so, apply sanitization
            if key.startswith('data') and value not in seen_values:
                result[f'data_{data_counter}'] = value
                seen_values.add(value)
                data_counter += 1
            elif not key.startswith('data'):
                # For keys not starting with 'data', keep them as they are
                result[key] = value

        return result


def extract_qr_data_from_pdf(pdf_file_path, include_non_jwt_data=False):
    qr_codes = extract_qr_codes_from_pdf(pdf_file_path)
    if not qr_codes:
        log.info(f"No QR codes found in the PDF {pdf_file_path}.")
        return {}

    result = {}

    for page, qr_codes_list in qr_codes.items():
        for qr_index, qr_code in enumerate(qr_codes_list):
            key_name = f'_{qr_index + 1}_from_page_{page}'
            if is_jwt(qr_code):
                header, payload = decode_jwt(qr_code)
                if header is None or payload is None:
                    continue

                # result[f'jwt_data{key_name}'] = payload
                data_string = payload.pop('data', None)
                if data_string:
                    try:
                        data_json = json.loads(data_string)
                        result[f'QR_data{key_name}'] = data_json
                    except json.JSONDecodeError:
                        result[f'data{key_name}'] = data_string
            elif include_non_jwt_data:
                result[f'data{key_name}'] = qr_code

    # if not result:
    #     log.info(f"No valid JWTs found in the QR codes from the PDF {pdf_file_path}.")
    #     return result

    return sanitize_qr_code_decoded_data(result)


if __name__ == "__main__":
    # pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\My Work New\Adani POC\POC\Invoice Samples\PO\InvoivePrint - 2024-08-06T105049.904.pdf"
    # pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\Image 2024-12-24 at 9.02.38 PM.pdf"
    # pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\Image 2024-12-24 at 8.59.29 PM.pdf"
    # pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\Image 2024-12-24 at 9.04.30 PM.pdf"
    # pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\My Work New\Adani POC\POC\Invoice Samples\PO\InvoivePrint - 2024-08-06T105049.904.pdf"
    pdf_file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\My Work New\Adani POC\POC\Invoice Samples\Invoice Samples from Adani\1P2107002#5000362481_1.pdf"
    result = extract_qr_data_from_pdf(pdf_file_path, True)
    from pprint import pprint

    pprint(result)
