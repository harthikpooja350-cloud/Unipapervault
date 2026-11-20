
from pymongo import MongoClient
from bson.objectid import ObjectId

client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
collection = db['papers']

# Find all papers with subject "Problem Solving Techniques"
cursor = collection.find({"subject": "Problem Solving Techniques"}).sort("createdAt", -1)
papers = list(cursor)

print(f"Found {len(papers)} PST papers.")

if len(papers) > 1:
    # Keep the first one (most recent, which should be the correct one with SEP/DCCA112)
    to_keep = papers[0]
    print(f"Keeping latest: ID={to_keep['_id']}, Code={to_keep.get('code')}, Scheme={to_keep.get('scheme')}")
    
    # Delete the rest
    for p in papers[1:]:
        print(f"Deleting duplicate: ID={p['_id']}, Code={p.get('code')}")
        collection.delete_one({"_id": p['_id']})
else:
    print("No duplicates found.")
