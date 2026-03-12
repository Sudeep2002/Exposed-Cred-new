import pandas as pd

def load_current_batch(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["email"] = df["Email"].str.lower().str.strip()
    df["exposure_date"] = pd.to_datetime(df["Date of Exposure"])
    df["source"] = df["Source"]
    return df[["email", "exposure_date", "source"]]


def load_master_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["email"] = df["Email"].str.lower().str.strip()
    df["last_exposed_date"] = pd.to_datetime(df["Date of Exposure"])
    return df[["email", "last_exposed_date", "source"]]
