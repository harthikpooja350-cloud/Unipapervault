from pymongo import MongoClient

# Connect to DB
client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
users_collection = db['users']

def list_users():
    users = list(users_collection.find())
    print("\n========== USERS IN DB ==========")
    print(f"Total Count: {len(users)}")
    for u in users:
        print(f"Name: {u.get('name')}")
        print(f"Email: {u.get('email')}")
        print(f"Password: {u.get('password')}")
        print(f"Role: {u.get('role')}")
        print("-" * 20)
    print("=================================\n")

if __name__ == '__main__':
    list_users()
