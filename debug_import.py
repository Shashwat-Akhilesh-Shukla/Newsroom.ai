import sys
import traceback

sys.path.insert(0, 'c:/Users/passi/OneDrive/Desktop/Projects/FlagShip projects/AI_NEWSROOM/src/storage')

try:
    from database import DatabaseManager
    print("Import successful!")
except Exception as e:
    print("Error occurred - writing to error.txt")
    with open('error.txt', 'w') as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
