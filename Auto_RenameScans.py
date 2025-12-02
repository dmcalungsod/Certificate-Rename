import os
import re
import warnings
import pdfplumber
import easyocr
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
from concurrent.futures import ProcessPoolExecutor, as_completed


warnings.filterwarnings("ignore")


# ------------------------------------------------------------
# INIT OCR INSIDE EACH PROCESS
# ------------------------------------------------------------
def init_ocr():
    # No verbose logs
    return easyocr.Reader(['en'], gpu=True, verbose=False)


# ------------------------------------------------------------
# IMAGE PREPROCESSING
# ------------------------------------------------------------
def preprocess_image(pil_image):
    gray = ImageOps.grayscale(pil_image)
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    np_img = np.array(gray)
    binary = np.where(np_img > 180, 255, 0).astype(np.uint8)
    return Image.fromarray(binary)


# ------------------------------------------------------------
# NAME REFORMATTING
# ------------------------------------------------------------
def reformat_name(name):
    # 1. Handle "Surname, Firstname..." format (already has comma)
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        if len(parts) >= 2:
            p1, p2 = parts[0], parts[1]
            
            # Check if p1 ends with a suffix like Jr. or Sr. (e.g. "David J. Jr., Alcarde")
            # Clean p1 to check suffix
            p1_clean = re.sub(r'[^\w\s]', '', p1).strip()
            last_token = p1_clean.split()[-1].lower() if p1_clean else ""
            
            suffixes = ['jr', 'sr', 'ii', 'iii', 'iv', 'v', 'vi']
            if last_token in suffixes:
                # Case: "David J. Jr., Alcarde" -> "Alcarde, David J. Jr."
                return f"{p2}, {p1}"
            else:
                # Case: "Paloma, Karl..." -> Keep as is
                return name

    # 2. Handle "First Middle Surname [Suffix]" (no comma)
    tokens = name.split()
    if not tokens: return name
    
    suffix = ""
    suffixes_regex = r'^(jr|sr|ii|iii|iv|v|vi)\.?$'
    
    # Check if last token is a suffix
    if re.match(suffixes_regex, tokens[-1], re.IGNORECASE):
        suffix = tokens[-1]
        tokens = tokens[:-1]
        
    if not tokens: return name
    
    # Assume last remaining token is Surname
    surname = tokens[-1]
    first_middle = " ".join(tokens[:-1])
    
    if suffix:
        return f"{surname}, {first_middle} {suffix}".strip()
    else:
        return f"{surname}, {first_middle}".strip()


# ------------------------------------------------------------
# OCR + NAME DETECTION
# ------------------------------------------------------------
def extract_name_with_ocr(pdf_path):
    reader = init_ocr()

    try:
        debug_path = os.path.join(os.path.dirname(pdf_path), "debug_ocr.txt")

        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return None

            page = pdf.pages[0]
            # OPTIMIZATION: Lower resolution to 150 (faster, usually sufficient for headers)
            pil_im = page.to_image(resolution=150).original

            # OPTIMIZATION: User requested to scan the ENTIRE page to ensure no name parts are missed.
            # We skip cropping and use the full image.
            processed = preprocess_image(pil_im)
            processed_np = np.array(processed)

            results = reader.readtext(processed_np, detail=1, paragraph=False)

            lines = sorted(
                [(bbox[0][1], text) for bbox, text, conf in results],
                key=lambda x: x[0]
            )

            # Save OCR text only
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n===== FILE: {os.path.basename(pdf_path)} =====\n")
                for _, text in lines:
                    f.write(text + "\n")

            targets = [
                "this certificate is presented to",
                "this certificate is awarded to",
                "is presented to",
                "is awarded to",
                "presented to",
                "awarded to",
                "to"
            ]
            # Sort by length descending to match longest phrase first
            targets.sort(key=len, reverse=True)
            
            name = None

            for i, (_, text) in enumerate(lines):
                text_lower = text.lower()
                matched_target = next((t for t in targets if t in text_lower), None)
                
                if matched_target:
                    # Check if name is on the same line
                    start_index = text_lower.find(matched_target) + len(matched_target)
                    remainder = text[start_index:].strip()
                    
                    next_line_idx = i + 1
                    
                    # If remainder has substantial content, use it
                    if len(re.sub(r'[^\w]', '', remainder)) > 1:
                        name = remainder
                    elif i + 1 < len(lines):
                        name = lines[i + 1][1].strip()
                        next_line_idx = i + 2
                    else:
                        break

                    # FIX 1: If the "name" is just "This certificate is" (OCR split issue), skip it and take next line
                    if name and "certificate" in name.lower() and "is" in name.lower():
                        if next_line_idx < len(lines):
                            name = lines[next_line_idx][1].strip()
                            next_line_idx += 1
                    
                    # 1. Handle "Jr.," "Sr.," etc. appearing as the START of the name
                    if name and re.match(r'^(jr|sr|ii|iii|iv|v|vi|mr|ms|mrs|dr|engr|atty|hon)\.?[\.,]?$', name, re.IGNORECASE):
                        if next_line_idx < len(lines):
                            name = f"{name} {lines[next_line_idx][1].strip()}"
                            next_line_idx += 1

                    # 2. Handle multi-line names (e.g. "David J." + "Jr." + "Alcarde")
                    # Loop to check subsequent lines for suffixes or name continuations
                    while next_line_idx < len(lines):
                        next_text = lines[next_line_idx][1].strip()
                        
                        # Check for suffix on the next line (Jr, Sr, etc.)
                        if re.match(r'^(jr|sr|ii|iii|iv|v|vi)\.?[\.,]?$', next_text, re.IGNORECASE):
                            name = f"{name} {next_text}"
                            next_line_idx += 1
                            continue # Check the line AFTER the suffix too (for "Alcarde")
                        
                        # Check for name continuation (starts with Capital, no keywords)
                        elif (next_text and next_text[0].isupper() and 
                              not any(k in next_text.lower() for k in ["webinar", "held", "participation", "given", "signed", "date", "theme"])):
                             
                             # Heuristic: if current name is short (<15 chars) or ends in ".", append next line
                             # OR if we just appended a suffix (like Jr.), we almost certainly want the next part
                             if len(name) < 15 or name.endswith(".") or re.search(r'(jr|sr|ii|iii|iv|v|vi)\.?[\.,]?$', name, re.IGNORECASE):
                                 name = f"{name} {next_text}"
                                 next_line_idx += 1
                                 continue
                        
                        # If no match, stop looking
                        break
                    
                    break

            if not name:
                # fallback to first valid OCR line
                for _, text in lines:
                    if any(c.isalpha() for c in text):
                        name = text.strip()
                        break

            if not name:
                return None

            # Remove illegal filename chars (KEEP commas/periods)
            name = re.sub(r'[\\/*?:"<>|]', "", name)

            # Semicolon fix (OCR sometimes misreads "," as ";")
            name = name.replace(";", ",")

            # Remove duplicate spaces
            name = re.sub(r"\s+", " ", name).strip()

            # Remove trailing period to avoid "..pdf"
            if name.endswith("."):
                name = name[:-1]

            # Reformat to "Surname, Firstname Middle Suffix"
            name = reformat_name(name)

            return name

    except Exception:
        return None


# ------------------------------------------------------------
# CLEAN FILENAME
# ------------------------------------------------------------
def clean_filename(text):
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = text.replace(";", ",")
    text = re.sub(r"\s+", " ", text)

    if text.endswith("."):
        text = text[:-1]

    return text.strip()


# ------------------------------------------------------------
# PROCESS ONE PDF
# ------------------------------------------------------------
def process_pdf(full_path):
    folder, filename = os.path.split(full_path)

    extracted = extract_name_with_ocr(full_path)
    if not extracted:
        return f"[FAIL] {filename} — Could not extract name"

    safe = clean_filename(extracted)
    if len(safe) > 100:
        safe = safe[:100]

    new_name = safe + ".pdf"
    new_path = os.path.join(folder, new_name)

    if filename == new_name:
        return f"[SKIP] {filename} — Already correct"

    if os.path.exists(new_path):
        return f"[WARNING] {new_name} already exists"

    try:
        os.rename(full_path, new_path)
        return f"[RENAME] {filename} → {new_name}"
    except Exception as e:
        return f"[ERROR] Rename failed for {filename}: {e}"


# ------------------------------------------------------------
# PROCESS FOLDER (MAX 3 WORKERS)
# ------------------------------------------------------------
def process_folder(folder):
    print()

    if not os.path.exists(folder):
        print("Folder not found.")
        return

    pdf_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".pdf")
    ]
    total = len(pdf_files)
    if total == 0:
        print("No PDF files found.")
        return

    print(f"Found {total} PDF files. Processing...")

    # OPTIMIZATION: Use 1 worker for GPU. 
    # Multiple workers would load the model multiple times, exhausting the 2GB VRAM of the MX330.
    with ProcessPoolExecutor(max_workers=1) as executor:
        futures = {executor.submit(process_pdf, f): f for f in pdf_files}

        for future in as_completed(futures):
            result = future.result()
            print(result)


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    print("--- Auto Rename Script by DMC ---")

    folder = input("Enter folder path (empty = current folder): ").strip()
    folder = folder.replace('"', '').replace("'", "")

    if not folder:
        folder = os.getcwd()

    process_folder(folder)
    input("\nPress Enter to exit...")
