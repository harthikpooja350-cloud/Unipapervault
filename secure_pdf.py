
import sys
import os
from pypdf import PdfReader, PdfWriter

def secure_pdf(input_pdf_path, owner_password="unipaper_admin_secret"):
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Encrypt with an owner password
        # User permissions:
        # 0 = No permissions (strictly locked)
        # We might want to allow Printing (maybe?) -> Let's say NO editing.
        # Permissions reference: https://pypdf.readthedocs.io/en/stable/user/encryption.html
        
        # encrypt(user_pwd, owner_pwd, ... permissions_flag_bits ...)
        # We leave user_pwd empty so they can open it without password.
        # But they need owner_pwd to edit it.
        
        writer.encrypt(
            user_password="", 
            owner_password=owner_password,
            permissions_flag=0  # Disallow everything (Print, Modify, Copy, Annotate) by default or selective?
                                # Let's allow printing at least? usually universities allow printing.
        )
        
        # Pypdf's permission flags are a bit complex to set individually easily in one go without bitmasking.
        # Providing valid user_password="" allows opening. Owner password protects changes.
        
        output_path = input_pdf_path + ".secure.pdf"
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
            
        # Replace original
        os.replace(output_path, input_pdf_path)
        print(f"Success: Secured {os.path.basename(input_pdf_path)}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python secure_pdf.py <pdf_path>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    secure_pdf(pdf_path)
