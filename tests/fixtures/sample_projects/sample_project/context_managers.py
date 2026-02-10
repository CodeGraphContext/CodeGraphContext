class FileOpener:
    def __enter__(self):
        return 'opened'
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

def use_file():
    with FileOpener() as f:
        return f
