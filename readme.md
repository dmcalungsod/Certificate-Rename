# Auto Rename Scans (Certificate Renamer)

This tool automates the process of renaming scanned PDF certificates by extracting the recipient's name using Optical Character Recognition (OCR). It is designed to handle scanned images without text layers and intelligently formats names for consistent file organization.

## Features

* **Modern GUI:** A user-friendly PySide6 graphical interface with drag-and-drop support, dark/light themes, and real-time progress tracking.
* **OCR-Powered Extraction:** Uses `easyocr` to read text from scanned PDF images.
* **Smart Name Detection:** Locates names based on context phrases like "presented to" or "awarded to".
* **Advanced Formatting:** Automatically reformats names to `Surname, Firstname Middle Suffix` (e.g., "Alcarde, David J. Jr.").
* **Suffix Handling:** Correctly identifies and places suffixes like Jr., Sr., III, etc.
* **Batch Processing:** Processes all PDF files in a specified folder.
* **GPU Acceleration:** Utilizes CUDA (if available) for faster OCR processing, optimized for low-VRAM GPUs.
* **Debug Logging:** Generates a `debug_ocr.txt` file containing the raw OCR output for verification.

## Prerequisites

* **Python 3.8+**
* Install dependencies via `pip install -r requirements.txt`

## Usage

### Option 1: Graphical User Interface (GUI) - Recommended

Open a terminal/command prompt in the script's directory and run:

```bash
python gui_app.py
```

1. **Drag and Drop:** Drag your folder containing certificates onto the drop zone, or click "Browse Folder".
2. **Scan:** Click "Scan Names" to perform a dry-run OCR extraction. You can review the extracted names in the table before any files are changed.
3. **Rename:** Once satisfied, select the files you want to rename and click "Rename Selected".
4. **Settings:** Use the ⚙ icon to adjust the number of worker threads or toggle CPU/GPU execution.

### Option 2: Command Line Interface (CLI)

Open a terminal/command prompt in the script's directory and run:

```bash
python Auto_RenameScans.py
```

1. When prompted, enter the full path to the folder containing your PDF certificates.
2. Press **Enter** to use the current directory.
3. The script will process each file, displaying the status:
    * `[RENAME]`: Successfully renamed.
    * `[SKIP]`: File is already named correctly.
    * `[FAIL]`: Could not extract a valid name.
    * `[WARNING]`: Target filename already exists.

## How It Works

1. **Image Conversion:** Converts the first page of the PDF into a high-contrast binary image to improve OCR accuracy.
2. **Text Recognition:** Scans the image for text using `easyocr`.
3. **Pattern Matching:** Looks for key phrases (e.g., "this certificate is presented to") to locate the name.
4. **Name Parsing:**
    * Extracts the text following the key phrase.
    * Checks subsequent lines for multi-line names or suffixes.
    * Reformats the name into `Surname, Firstname` format.
5. **Renaming:** Renames the file while sanitizing the filename (removing illegal characters).

## Troubleshooting

* **Wrong Name Extracted:** Check the `debug_ocr.txt` file created in the target folder. This shows exactly what the OCR "saw".
* **Slow Performance:** OCR is computationally intensive. Performance depends on your hardware (GPU vs. CPU).
* **"No PDF files found":** Ensure you entered the correct folder path.

## Author

Diffon M. Calungsod

## Attributions

The application icon (`favicon.ico`) was downloaded from [Magnific](https://magnific.com/) stock images.
