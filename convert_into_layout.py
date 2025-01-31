import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient


endpoint = os.getenv("endpoint")
key = os.getenv("key")


def find_intersection(range1, range2):
    # Check if the ranges overlap
    if range1[0] <= range2[1] and range1[1] >= range2[0]:
        return 1
    else:
        # No intersection
        return 0


def convert_into_text(result):
    pdf_read = ''
    page_number=0
    for page in result.pages:
        pagetext = "\n".join([line.content for line in result.pages[page_number].lines])
        if ("checklist" not in pagetext.lower() or page_number>0):
            pdf_read = pdf_read + "\n\n"
            pdf_read = pdf_read + "------------------------------- Page " + str(
                page.page_number) + " -------------------------------"
            pdf_read = pdf_read + "\n"
            tb = []
            lb = []
            for line in page.lines:
                # lines = lines + "\n" + line.content
                box_x_min = min(point[0] for point in line.polygon)
                box_x_max = max(point[0] for point in line.polygon)
                box_y_min = min(point[1] for point in line.polygon)
                box_y_max = max(point[1] for point in line.polygon)
                table_box = (box_x_min, box_y_min, box_x_max, box_y_max)
                lb.append(line.content)
                tb.append(table_box)
            # Create a DataFrame
            df = pd.DataFrame(tb)
            df['page_content'] = lb
            df.columns = ["xmin", "ymin", "xmax", "ymax", "page_content"]
            df["yavg"] = (df['ymin'] + df['ymax']) / 2
            df.sort_values(["yavg", "ymin"], inplace=True)
            df.reset_index(inplace=True)
            intersections = []
            I = [1]
            for i in range(1, len(df)):
                range1 = [df.at[i - 1, 'ymin'] * (1.005), df.at[i - 1, 'ymax'] * (0.995)]
                range2 = [df.at[i, 'ymin'] * (1.005), df.at[i, 'ymax'] * (0.995)]
                intersection = find_intersection(range1, range2)
                if i == 1:
                    m = 1
                    if intersection == 1:
                        I.append(m)
                    else:
                        m = m + 1
                        I.append(m)
                else:
                    if intersection == 1:
                        I.append(m)
                    else:
                        m = m + 1
                        I.append(m)
                intersections.append(intersection)
            intersections.append(0)
            df['YIntersection'] = intersections
            df['YI'] = I
            df_final = pd.DataFrame()
            for i in df['YI'].unique():
                samp = df[df['YI'] == i]
                samp["xavg"] = (samp['xmin'] + samp['xmax']) / 2
                samp.sort_values(["xavg", "xmin"], inplace=True)
                samp.reset_index(inplace=True)
                intersections = []
                I = [1]
                for i in range(1, len(samp)):
                    range1 = [samp.at[i - 1, 'xmin'], samp.at[i - 1, 'xmax']]
                    range2 = [samp.at[i, 'xmin'], samp.at[i, 'xmax']]
                    intersection = find_intersection(range1, range2)
                    if i == 1:
                        m = 1
                        if intersection == 1:
                            I.append(m)
                        else:
                            m = m + 1
                            I.append(m)
                    else:
                        if intersection == 1:
                            I.append(m)
                        else:
                            m = m + 1
                            I.append(m)
                    intersections.append(intersection)
                intersections.append(0)
                samp['XIntersection'] = intersections
                samp['XI'] = I
                df_final = pd.concat([df_final, samp])
            read = ""
            mi = min(df_final['xmin'])
            hold_x = 0
            hold_YI = 0
            df_final = df_final.drop(columns=['index'])
            df_final.reset_index(inplace=True)
            for i in range(df_final.shape[0]):
                if (i == 0): hold_y_min, hold_y_max = 0, 0
                i = i + 1
                temp = int((df_final.at[i - 1, 'xmin'] - hold_x) / (30 / 30) * page.height)
                if (temp <= 2):
                    temp = 2
                space = " " * temp
                if (df_final.at[i - 1, 'YI'] - hold_YI) == 0:
                    read = read + space + df_final.at[i - 1, 'page_content']
                else:
                    read = read + "\n" + " " * int((df_final.at[i - 1, 'xmin'] - mi) / (30 / 30) * page.height) + \
                           df_final.at[i - 1, 'page_content']
                hold_x = df_final.at[i - 1, 'xmax']
                # hold_y_min = df_final.at[i - 1, 'ymin']
                # hold_y_max = df_final.at[i - 1, 'ymax']
                hold_YI = df_final.at[i - 1, 'YI']
            pdf_read = pdf_read + read
        page_number = page_number + 1
    return pdf_read

def analyze_read(file_path):
    document_analysis_client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    with open(file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            model_id="prebuilt-invoice", document=f, locale="en-US"
        )
    result = poller.result()
    read = convert_into_text(result)
    # read = ''
    # for j in range(len(result.pages)):
    #     read = read + "\n\n\n" + "--------------- " + str(j + 1) + " ---------------"
    #     for i in range(len(result.pages[j].lines)):
    #         read = read + "\n" + result.pages[j].lines[i].content
    return read


def read_digital_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for i in range(len(pdf.pages)):
            text = text + "\n\n" + "--------------- Page " + str(i + 1) + " ---------------"
            text += pdf.pages[i].extract_text(layout=True)
    return text


def check_pdf_type(file_path):
    doc = fitz.open(file_path)
    for page in doc:
        text = page.get_text()  # Extract text from the page
        if text.strip():
            return "Digital PDF"  # Found text
        elif page.get_images():  # Check for images
            return "Scanned PDF"
    return "Unknown PDF type"


def get_final_text(file_path):
    pdf_type = check_pdf_type(file_path)
    if pdf_type == "Digital PDF":
        # read = read_digital_pdf(file_path)
        read = analyze_read(file_path)
    elif pdf_type == "Scanned PDF":
        read = analyze_read(file_path)
    return read


if __name__ == '__main__':
    file_path = r"C:\Users\yash.dharme.AD_ICC\Downloads\My Work New\Adani POC\POC\Invoice Samples\Invoice Samples from Adani\1P2107002#5000362481_1.pdf"

    text = get_final_text(file_path)
    print(text)
