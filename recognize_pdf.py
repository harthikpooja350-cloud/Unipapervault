
import os
import re
import json
import sys
from pypdf import PdfReader
from pymongo import MongoClient
from datetime import datetime

# Database Connection
client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
papers_collection = db['papers']

def extract_info(file_path):
    try:
        reader = PdfReader(file_path)
        text = ""
        # Read first 2 pages max
        for i in range(min(len(reader.pages), 5)):
            # Try layout mode to preserve spatial data (columns/headers)
            try:
                text += reader.pages[i].extract_text(extraction_mode="layout")
            except:
                 text += reader.pages[i].extract_text()
        
        # Normalize text
        text_lower = text.lower()
        
        # --- Extraction Logic ---
        
        # 1. Course (Heuristicts)
        course = "Unknown"
        if "bca" in text_lower or "b.c.a" in text_lower:
            course = "BCA"
        elif "b.com" in text_lower or "bcom" in text_lower:
            course = "B.Com"
        elif "b.sc" in text_lower or "bsc" in text_lower or "b.s.c" in text_lower:
            course = "B.Sc"
        elif "b.a" in text_lower or "ba " in text_lower or "b.a." in text_lower:
            course = "B.A"
        elif "b.e" in text_lower or "engineering" in text_lower:
            course = "B.E"
            
        # 2. Semester
        sem = "Unknown"
        # Check for sem
        sem_map = {
            "first": "1st Sem", "1st": "1st Sem", "i semester": "1st Sem", "i sem": "1st Sem",
            "second": "2nd Sem", "2nd": "2nd Sem", "ii semester": "2nd Sem", "ii sem": "2nd Sem",
            "third": "3rd Sem", "3rd": "3rd Sem", "iii semester": "3rd Sem", "iii sem": "3rd Sem",
            "fourth": "4th Sem", "4th": "4th Sem", "iv semester": "4th Sem", "iv sem": "4th Sem",
            "fifth": "5th Sem", "5th": "5th Sem", "v semester": "5th Sem", "v sem": "5th Sem",
            "sixth": "6th Sem", "6th": "6th Sem", "vi semester": "6th Sem", "vi sem": "6th Sem",
            "seventh": "7th Sem", "7th": "7th Sem", "vii semester": "7th Sem", "vii sem": "7th Sem",
            "eighth": "8th Sem", "8th": "8th Sem", "viii semester": "8th Sem", "viii sem": "8th Sem"
        }
        found_sem = False
        for k, v in sem_map.items():
            # regex for whole word match to avoid substrings
            if re.search(r'\b' + re.escape(k) + r'\b', text_lower):
                sem = v
                found_sem = True
                break
        
        if not found_sem:
            # Try roman numerals I, II, III etc explicitly ?
            pass
        
        # 3. Year
        year = "Unknown"
        # Look for years like 20xx
        years = re.findall(r'20\d{2}', text)
        if years:
            # Take the largest one that is likely an exam year (<= current_year + 1)
            valid_years = [y for y in years if int(y) >= 2010 and int(y) <= 2030]
            if valid_years:
                year = max(valid_years)
            
        # 4. Subject
        subject = "Unknown"
        # Heuristics based on "PST" in filename or content
        filename_lower = os.path.basename(file_path).lower()
        
        if "problem solving" in text_lower or "pst" in filename_lower:
            subject = "Problem Solving Techniques"
        elif "python" in text_lower:
            subject = "Python Programming"
        elif "c programming" in text_lower:
            subject = "C Programming"
        elif "artificial intelligence" in text_lower:
            subject = "Artificial Intelligence"
        elif "web" in text_lower:
            subject = "Web Programming"
        
        # 5. Code
        code = "Unknown"
        
        # Priority 1: Look for explicit Code/Max Marks text block often contains the code
        # Search for pattern like DCCA112 (Letters + Digits)
        # We look for Capital Letters followed immediately by Digits, len >= 5
        strong_code_match = re.search(r'\b([A-Z]{2,6}\s?\d{3,4})\b', text)
        if strong_code_match:
             # Verify it's not a common word/noise
             candidate = strong_code_match.group(1)
             # Avoid "SEMESTER1" or "MARKS80"
             if not re.search(r'(SEMESTER|MARKS|TIME|YEAR|JAN|FEB)', candidate.upper()):
                 code = candidate.replace(" ", "")
        
        if code == "Unknown":
            # Priority 2: QP Code explicit label
            qp_code_match = re.search(r'(?:qp|code|paper code)[\s.:-]*([a-zA-Z0-9-]{3,})', text_lower)
            if qp_code_match:
                candidate = qp_code_match.group(1).upper()
                if len(candidate) < 15:
                     code = candidate
        
        if code == "Unknown":
            # Priority 3: Top Right Heuristic (Fallback)
             pass 

        # 6. Scheme (SEP/NEP/CBCS)
        scheme = "Unknown"
        if "sep" in text_lower or "state education policy" in text_lower:
            scheme = "SEP"
        elif "nep" in text_lower or "national education policy" in text_lower:
            scheme = "NEP"
        elif "cbcs" in text_lower:
            scheme = "CBCS"

        return {
            "subject": subject,
            "code": code,
            "course": course,
            "year": year,
            "sem": sem,
            "type": "Question Paper", 
            "university": "Bengaluru City University",
            "scheme": scheme
        }
        
    except Exception as e:
        return {"error": str(e)}

def save_to_db(file_path):
    info = extract_info(file_path)
    if "error" in info:
        print(json.dumps({"success": False, "error": info["error"]}))
        return

    # User provided university overrides whatever we might have guessed
    
    # Rename to timestamp format
    timestamp = str(int(datetime.now().timestamp() * 1000))
    clean_filename = os.path.basename(file_path) # Pst_Bcu.pdf
    # If the file already starts with timestamp (digits-), skip?
    if not re.match(r'^\d{13}-', clean_filename):
         new_filename = f"{timestamp}-{clean_filename}"
    else:
         new_filename = clean_filename
    
    # New Path
    upload_folder = os.path.dirname(file_path)
    new_path = os.path.join(upload_folder, new_filename)
    
    try:
        if file_path != new_path:
            os.rename(file_path, new_path)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Rename failed: {e}"}))
        return

    # Check for Unknowns and try to be smarter or leave them
    if info['subject'] == 'Unknown' and 'pst' in clean_filename.lower():
        info['subject'] = 'Problem Solving Techniques'
        
    doc = {
        'subject': info['subject'],
        'code': info['code'],
        'course': info['course'],
        'university': info['university'],
        'year': info['year'],
        'sem': info['sem'],
        'type': info['type'],
        'scheme': info['scheme'],
        'filename': new_filename,
        'downloads': 0,
        'createdAt': datetime.now()
    }
    
    result = papers_collection.insert_one(doc)
    
    # Return result
    doc['_id'] = str(result.inserted_id)
    doc['createdAt'] = doc['createdAt'].isoformat()
    
    print(json.dumps({"success": True, "data": doc}, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No file provided"}))
        sys.exit(1)
        
    file_path = sys.argv[1]
    save_to_db(file_path)
