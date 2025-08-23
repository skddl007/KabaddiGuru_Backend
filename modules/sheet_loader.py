import pandas as pd
import os

# Get the absolute path to the Excel file
EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SKDB.xlsx")

def load_sheets():
    xl = pd.ExcelFile(EXCEL_PATH)
    return {
        name: xl.parse(name).to_dict(orient="records")
        for name in ["S_RBR"]
    }
