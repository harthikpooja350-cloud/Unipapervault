from pymongo import MongoClient

# Connect to DB
client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
papers_collection = db['papers']

def list_papers():
    papers = list(papers_collection.find())
    print("\n========== PAPERS IN DB ==========")
    print(f"Total Count: {len(papers)}")
    for p in papers:
        print(f"ID: {p.get('_id')}")
        print(f"Subject: {p.get('subject')}")
        print(f"Filename: {p.get('filename')}")
        print("-" * 20)
    print("==================================\n")

if __name__ == '__main__':
    list_papers()
