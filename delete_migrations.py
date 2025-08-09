import os
import shutil

def delete_migration_files():
    for root, dirs, files in os.walk('.'):
        if 'migrations' in dirs:
            migration_dir = os.path.join(root, 'migrations')
            for file in os.listdir(migration_dir):
                file_path = os.path.join(migration_dir, file)
                if file != '__init__.py':  # Skip __init__.py
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"Deleted file: {file_path}")
                        elif os.path.isdir(file_path):  # Handle directories like __pycache__
                            shutil.rmtree(file_path)
                            print(f"Deleted directory: {file_path}")
                    except PermissionError as e:
                        print(f"Permission denied: {file_path} - {e}")

if __name__ == '__main__':
    delete_migration_files()
