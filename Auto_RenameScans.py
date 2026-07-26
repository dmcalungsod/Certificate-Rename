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
                r"certificate is presented to",
                r"certificate is awarded to",
                r"is hereby awarded to",
                r"is hereby granted to",
                r"this is to certify that",
                r"this certifies that",
                r"certifies that",
                r"certify that",
                r"is presented to",
                r"is awarded to",
                r"presented to",
                r"awarded to",
                r"granted to",
                r"awards this",
                r"certi[fp]icate of participation",
                r"certi[fp]icate of completion",
                r"certi[fp]icate of attendance",
                r"certi[fp]icate of appreciation"
            ]
            
            reverse_targets = [
                r"has successfully completed",
                r"has completed",
                r"for participating",
                r"for attending",
                r"for completing",
                r"for active",
                r"for his/her"
            ]

            name = None

            # 1. Try Forward Targets
            for i, (_, text) in enumerate(lines):
                text_lower = text.lower()
                matched_target = None
                for t in targets:
                    match = re.search(t, text_lower)
                    if match:
                        matched_target = match.group(0)
                        break
                
                if matched_target:
                    start_index = text_lower.find(matched_target) + len(matched_target)
                    remainder = text[start_index:].strip()
                    
                    next_line_idx = i + 1
                    
                    if len(re.sub(r'[^\w]', '', remainder)) > 3:
                        name = remainder
                    else:
                        # Look ahead up to 4 lines for a valid name
                        for j in range(1, 7):
                            if i + j < len(lines):
                                candidate = lines[i + j][1].strip()
                                # Skip noise
                                if len(re.sub(r'[^a-zA-Z]', '', candidate)) < 4:
                                    continue
                                if "@" in candidate or (candidate.isupper() and len(candidate.split()) == 1):
                                    continue
                                if re.search(r'(date|signature|director|president)', candidate, re.IGNORECASE):
                                    continue
                                # Skip if candidate is itself a target/keyword phrase
                                cand_lower = candidate.lower()
                                if any(re.search(t, cand_lower) for t in targets) or any(re.search(rt, cand_lower) for rt in reverse_targets):
                                    continue
                                
                                name = candidate
                                next_line_idx = i + j + 1
                                break
                        if not name:
                            break

                    # FIX: If "name" is just a leftover fragment, skip it
                    if name and "certificate" in name.lower() and "is" in name.lower():
                        if next_line_idx < len(lines):
                            name = lines[next_line_idx][1].strip()
                            next_line_idx += 1
                    
                    # Handle "Jr.," "Sr.," etc.
                    if name and re.match(r'^(jr|sr|ii|iii|iv|v|vi|mr|ms|mrs|dr|engr|atty|hon)\.?[\.,]?$', name, re.IGNORECASE):
                        if next_line_idx < len(lines):
                            name = f"{name} {lines[next_line_idx][1].strip()}"
                            next_line_idx += 1

                    # Handle multi-line names
                    while next_line_idx < len(lines):
                        next_text = lines[next_line_idx][1].strip()
                        if re.match(r'^(jr|sr|ii|iii|iv|v|vi)\.?[\.,]?$', next_text, re.IGNORECASE):
                            name = f"{name} {next_text}"
                            next_line_idx += 1
                            continue
                        elif (next_text and next_text[0].isupper() and
                              len(re.sub(r'[^a-zA-Z]', '', next_text)) >= 2 and
                              not any(k in next_text.lower() for k in ["webinar", "held", "participation", "given", "signed", "date", "theme", "attending", "completing"]) and
                              not re.search(r'\bfor\b', next_text, re.IGNORECASE)):
                             if len(name) < 15 or name.endswith(".") or re.search(r'(jr|sr|ii|iii|iv|v|vi)\.?[\.,]?$', name, re.IGNORECASE):
                                 name = f"{name} {next_text}"
                                 next_line_idx += 1
                                 continue
                        break
                    break

            # 2. Try Reverse Targets (if forward failed)
            if not name:
                for i, (_, text) in enumerate(lines):
                    text_lower = text.lower()
                    if any(re.search(rt, text_lower) for rt in reverse_targets):
                        # Look back up to 6 lines
                        for j in range(1, 7):
                            if i - j >= 0:
                                candidate = lines[i - j][1].strip()
                                if len(re.sub(r'[^a-zA-Z]', '', candidate)) < 4:
                                    continue
                                if candidate.isupper() and len(candidate.split()) == 1:
                                    continue
                                # Skip dates, titles, and boilerplate
                                if re.search(r'(date|signature|director|president|certificate|global|amanda|brophy|\d{4})', candidate, re.IGNORECASE):
                                    continue
                                cand_lower = candidate.lower()
                                if any(re.search(t, cand_lower) for t in targets) or any(re.search(rt, cand_lower) for rt in reverse_targets):
                                    continue
                                name = candidate
                                break
                        if name:
                            break

            # 3. Fallback to first valid OCR line (skip generic words)
            if not name:
                for _, text in lines:
                    candidate = text.strip()
                    cand_lower = candidate.lower()
                    if any(c.isalpha() for c in candidate):
                        if cand_lower in ["certificate", "of", "participation", "completion", "attendance", "appreciation", "course", "professional", "to", "t0"]:
                            continue
                        if len(re.sub(r'[^\w\s]', '', candidate)) < 4:
                            continue
                        if any(re.search(t, cand_lower) for t in targets) or any(re.search(rt, cand_lower) for rt in reverse_targets):
                            continue
                        name = candidate
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
