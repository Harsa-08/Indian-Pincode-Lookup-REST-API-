import os
import sys
import csv
from datetime import datetime
from dotenv import load_dotenv
from app import app, db
from models import Pincode

load_dotenv()

# Flexible mapping to handle variations in CSV column headers from data.gov.in
HEADER_MAPPINGS = {
    'pincode': ['pincode', 'pin code', 'pin', 'pincodes', 'pincode_queried'],
    'post_office': ['officename', 'office name', 'post office name', 'post office', 'post_office'],
    'delivery_status': ['deliverystatus', 'delivery status', 'delivery_status'],
    'division': ['divisionname', 'division name', 'division', 'division_name'],
    'region': ['regionname', 'region name', 'region', 'region_name'],
    'circle': ['circlename', 'circle name', 'circle', 'circle_name'],
    'taluk': ['taluk', 'tehsil', 'taluka', 'sub-dist', 'sub-district', 'subdistrict'],
    'district_name': ['districtname', 'district name', 'district', 'district_name'],
    'state_name': ['statename', 'state name', 'state', 'state_name']
}

def map_headers(headers):
    """Map CSV file headers to our database table columns."""
    mapping = {}
    normalized_headers = [h.strip().lower().replace('_', '').replace(' ', '') for h in headers]
    
    for db_col, variations in HEADER_MAPPINGS.items():
        for variation in variations:
            normalized_var = variation.replace('_', '').replace(' ', '').lower()
            if normalized_var in normalized_headers:
                idx = normalized_headers.index(normalized_var)
                mapping[db_col] = headers[idx]
                break
    return mapping

def import_csv(file_path, batch_size=5000):
    """Read and bulk insert CSV records into the database."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at path: {file_path}")
        return False

    print(f"Reading {file_path}...")
    
    # Try different encodings as CSV files from Government portals can have varying encodings
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    csv_file = None
    
    for encoding in encodings:
        try:
            csv_file = open(file_path, mode='r', encoding=encoding)
            # Read first line to test encoding
            csv_file.readline()
            csv_file.seek(0)
            print(f"Successfully opened file with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            if csv_file:
                csv_file.close()
            csv_file = None
            continue

    if not csv_file:
        print("Error: Could not decode the CSV file using standard encodings.")
        return False

    try:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames
        if not headers:
            print("Error: Empty CSV file or invalid header row.")
            csv_file.close()
            return False

        col_map = map_headers(headers)
        
        # Verify that essential fields are mapped
        essential_fields = ['pincode', 'post_office', 'district_name', 'state_name']
        missing_fields = [f for f in essential_fields if f not in col_map]
        
        if missing_fields:
            print(f"Warning: Could not automatically map some key columns: {missing_fields}")
            print(f"Available CSV headers: {headers}")
            print("Will attempt to import anyway using fallbacks...")
            
            # Simple fallback if auto-mapping misses essential fields
            for f in missing_fields:
                for h in headers:
                    if f[:4] in h.lower(): # e.g. 'state' in 'state_name'
                        col_map[f] = h
                        print(f"Mapped {f} -> {h} (fallback)")
                        break

        # Ensure database tables exist
        with app.app_context():
            print("Ensuring database tables are initialized...")
            db.create_all()

        records_to_insert = []
        total_inserted = 0
        
        with app.app_context():
            # Clear existing data optionally? 
            # Usually we don't, but let's provide warning
            print("Importing records...")
            
            start_time = datetime.now()
            
            for row in reader:
                # Basic validation: check pincode is valid (6 digits)
                raw_pincode = row.get(col_map.get('pincode', 'pincode'))
                if not raw_pincode:
                    continue
                pincode_clean = str(raw_pincode).strip()
                # Clean up float-like pincodes if any (e.g. '560001.0')
                if '.' in pincode_clean:
                    pincode_clean = pincode_clean.split('.')[0]
                
                # Zero pad if it got parsed as a shorter number in some sheets
                if pincode_clean.isdigit():
                    pincode_clean = pincode_clean.zfill(6)
                
                if len(pincode_clean) != 6 or not pincode_clean.isdigit():
                    continue

                record = {
                    'pincode': pincode_clean,
                    'post_office': row.get(col_map.get('post_office', '')),
                    'delivery_status': row.get(col_map.get('delivery_status', '')),
                    'division': row.get(col_map.get('division', '')),
                    'region': row.get(col_map.get('region', '')),
                    'circle': row.get(col_map.get('circle', '')),
                    'taluk': row.get(col_map.get('taluk', '')),
                    'district_name': row.get(col_map.get('district_name', '')),
                    'state_name': row.get(col_map.get('state_name', ''))
                }
                
                # Trim fields to match DB column limits or strip spaces
                for k, v in record.items():
                    if v:
                        record[k] = str(v).strip()
                
                records_to_insert.append(record)

                if len(records_to_insert) >= batch_size:
                    db.session.bulk_insert_mappings(Pincode, records_to_insert)
                    db.session.commit()
                    total_inserted += len(records_to_insert)
                    print(f"Inserted {total_inserted} records...")
                    records_to_insert = []

            # Insert remaining records
            if records_to_insert:
                db.session.bulk_insert_mappings(Pincode, records_to_insert)
                db.session.commit()
                total_inserted += len(records_to_insert)
                
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"Success! Imported {total_inserted} records in {duration:.2f} seconds.")
            return True

    except Exception as e:
        print(f"An error occurred during import: {e}")
        return False
    finally:
        csv_file.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python data_import.py <path_to_csv_file>")
        print("Example: python data_import.py pincodes.csv")
        sys.exit(1)
        
    csv_path = sys.argv[1]
    import_csv(csv_path)
