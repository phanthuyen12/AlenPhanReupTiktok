# utils.py
class LoadsFile:
    def load(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read().splitlines()
            return data
        except FileNotFoundError:
            print(f"File {file_path} không tồn tại!")
            return []
