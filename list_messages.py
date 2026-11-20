from pymongo import MongoClient
from datetime import datetime

# Connect to DB
client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
messages_collection = db['messages']

def list_messages():
    messages = list(messages_collection.find().sort('createdAt', -1))
    
    print("\n\n========== USER MESSAGES ==========")
    if not messages:
        print("No messages found.")
    else:
        for msg in messages:
            print(f"Date: {msg.get('createdAt')}")
            print(f"From: {msg.get('name')} ({msg.get('email')})")
            print(f"Message: {msg.get('message')}")
            print("-" * 30)
    print("===================================\n\n")

if __name__ == '__main__':
    list_messages()
