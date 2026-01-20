import os

def list_csv_files(folder):
    return sorted(
        [f for f in os.listdir(folder) if f.endswith(".csv")],
        key=lambda x: os.path.getmtime(os.path.join(folder, x)),
        reverse=True
    )

def get_latest_file(folder):
    files = list_csv_files(folder)
    return files[0] if files else None
