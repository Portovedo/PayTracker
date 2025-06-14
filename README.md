# Payslip Management Application

This is a Flask-based web application designed to help users upload their payslip PDFs, extract key information, store it, and visualize trends over time.

## Features

*   **PDF Upload:** Securely upload payslip PDF files.
*   **Data Extraction (Placeholder):** Extracts raw text from PDFs. Currently, it generates *dummy data* for Net Income, Meal Allowance, and Worked Days for demonstration purposes. **Actual data extraction logic needs to be customized based on specific PDF layouts.**
*   **Data Storage:** Stores extracted payslip information in an SQLite database.
*   **Tabular Data View:** View all stored payslip details in an organized table.
*   **Data Visualization:** Interactive charts display trends for:
    *   Monthly Net Income
    *   Monthly Meal Allowance
    *   Monthly Worked Days
*   **Styled UI:** A clean and user-friendly interface.
*   **Unit Tests:** Includes a suite of unit tests to ensure application reliability.

## Project Structure

```
.
├── app.py              # Main Flask application file
├── requirements.txt    # Python dependencies
├── schema.sql          # Database schema
├── static/             # Static files (CSS)
│   └── style.css
├── templates/          # HTML templates
│   ├── payslips_table.html
│   └── upload.html
├── tests/              # Unit tests
│   └── test_app.py
├── uploads/            # Directory for uploaded PDF files (created automatically)
└── payslips.db         # SQLite database file (created automatically)
```

## Setup and Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the database:**
    Run the following command from the project's root directory:
    ```bash
    flask initdb
    ```
    This will create the `payslips.db` file.

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Run the Flask development server:**
    ```bash
    python app.py
    ```
3.  Open your web browser and navigate to `http://127.0.0.1:5000/`.

## Running Tests

1.  **Ensure your virtual environment is activated and test dependencies are installed.**
2.  **Run pytest from the project's root directory:**
    ```bash
    pytest
    ```
    Or for more verbose output:
    ```bash
    pytest -v
    ```
    *Note: Depending on your project setup and how you run pytest, you might need to ensure the project root is in the PYTHONPATH, e.g., by running `PYTHONPATH=. pytest -v` or by configuring pytest (e.g. in a `pyproject.toml` or `pytest.ini`). The tests provided are structured assuming `app.py` is importable when tests are run from the root directory.*

## PDF Parsing Customization

The current PDF parsing logic in `app.py` (within the `parse_payslip_pdf` function) primarily extracts all text and then substitutes dummy values for structured data fields.

To make this application useful with your actual payslips, you will need to:

1.  **Analyze your payslip PDF structure:** Identify unique keywords, text patterns, or table structures that reliably locate the "Total Net Income," "Meal Allowance," and "Worked Days."
2.  **Modify `parse_payslip_pdf` function in `app.py`:**
    *   Use string searching, regular expressions (regex), or table extraction features from `pdfplumber` to find and extract the correct values from the `raw_text` or by directly querying PDF elements with `pdfplumber`.
    *   Update the function to return these actual extracted values instead of the current dummy data.

## Future Enhancements (Ideas)

*   More sophisticated PDF parsing (e.g., handling different layouts, OCR for scanned PDFs).
*   User authentication.
*   Ability to edit or delete entries.
*   More advanced data analysis and reporting features.
*   Support for different currencies.

This project provides a solid foundation for a personal payslip management tool.
