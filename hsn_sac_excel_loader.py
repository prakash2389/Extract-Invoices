import pandas as pd

hsn_sac_excel_path = r"C:\Users\prakash.tutika\PycharmProjects\Adani POC\POC\HSN_SAC_Mapping_data\HSN_SAC - SAC_MSTR.csv"

df = pd.read_csv(hsn_sac_excel_path)

sac_mapping_dict = dict(zip(df['Unnamed: 0'], zip(df['Company'], df['Non Company'])))
sac_mapping_dict.pop('SAC_CD', None)
sac_mapping_dict.pop('99', None)
