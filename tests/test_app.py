import os
import pytest
import tempfile
import shutil
from app import app as flask_app, init_db, get_db, parse_payslip_pdf # Import your Flask app and other necessary functions
from datetime import datetime

# --- Test Fixtures ---
@pytest.fixture
def app():
    # Create a temporary database for testing
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    # Create a temporary upload folder for testing
    upload_folder = tempfile.mkdtemp()

    flask_app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
        "UPLOAD_FOLDER": upload_folder,
        "SECRET_KEY": "test_secret_key", # Consistent secret key for tests
        "WTF_CSRF_ENABLED": False # Disable CSRF for simpler form tests
    })

    # Reset the PDF parsing counter before each test app instance
    if hasattr(parse_payslip_pdf, 'upload_session_counter'):
        parse_payslip_pdf.upload_session_counter = 0

    with flask_app.app_context():
        init_db() # Initialize the temporary database

    yield flask_app

    # Clean up: close and remove the temporary database and upload folder
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(upload_folder)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app): # For CLI commands
    return app.test_cli_runner()

# --- Basic Route Tests ---
def test_home_page(client):
    """Test the home page (upload form)."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Upload New Payslip PDF" in response.data
    # After styling updates, check for header/footer elements
    assert b"<header>" in response.data
    assert b"<footer>" in response.data

def test_payslips_page_empty(client):
    """Test the payslips page when no data is present."""
    response = client.get('/payslips')
    assert response.status_code == 200
    assert b"Payslip Dashboard" in response.data
    assert b"No payslip data found" in response.data
    assert b"<canvas id=\"netIncomeChart\">" in response.data # Check for chart canvas

# --- Database Tests ---
def test_init_db_command(runner, app):
    """Test the initdb command."""
    # The fixture already calls init_db
    result = runner.invoke(args=['initdb']) # Call it again to test command itself
    assert 'Database initialized.' in result.output

    with app.app_context():
        db = get_db()
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payslips';")
        table = cursor.fetchone()
        assert table is not None
        assert table['name'] == 'payslips'

def test_insert_and_query_payslip_data(app):
    """Test inserting and querying data from the payslips table."""
    with app.app_context():
        db = get_db()
        # Insert test data
        filename = "test_payslip.pdf"
        month = 1
        year = 2023
        net_income = 2500.75
        meal_allowance = 150.50
        worked_days = 22

        db.execute(
            'INSERT INTO payslips (filename, month, year, net_income, meal_allowance, worked_days, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (filename, month, year, net_income, meal_allowance, worked_days, datetime.utcnow())
        )
        db.commit()

        # Query the data using the query_db helper if preferred, or direct execute
        payslip = db.execute('SELECT * FROM payslips WHERE filename = ?', (filename,)).fetchone()

        assert payslip is not None
        assert payslip['filename'] == filename
        assert payslip['month'] == month
        assert payslip['year'] == year
        assert payslip['net_income'] == net_income
        assert payslip['meal_allowance'] == meal_allowance
        assert payslip['worked_days'] == worked_days

# --- File Upload Tests ---
# A minimal valid PDF structure that pdfplumber can open
MINIMAL_PDF_CONTENT = b"""%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Resources<<>>>>endobj
trailer<</Root 1 0 R>>
"""

def test_upload_pdf_success(client, app):
    """Test successful PDF file upload."""
    temp_dir = app.config['UPLOAD_FOLDER']
    dummy_pdf_filename = "test_upload.pdf"
    dummy_pdf_path = os.path.join(temp_dir, dummy_pdf_filename)

    with open(dummy_pdf_path, "wb") as f:
        f.write(MINIMAL_PDF_CONTENT)

    data = {
        'file': (open(dummy_pdf_path, 'rb'), dummy_pdf_filename)
    }

    # Ensure counter for dummy data generation is reset for predictable results
    if hasattr(parse_payslip_pdf, 'upload_session_counter'):
         parse_payslip_pdf.upload_session_counter = 0


    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

    assert response.status_code == 200 # After redirect to '/'
    # Updated flash message check to be more precise
    assert b'File &#34;test_upload.pdf&#34; uploaded, parsed (M:' in response.data
    assert b'), and saved!' in response.data

    # Check if data was inserted into the database
    with app.app_context():
        db = get_db()
        cursor = db.execute("SELECT * FROM payslips WHERE filename=?", (dummy_pdf_filename,))
        payslip_entry = cursor.fetchone()
        assert payslip_entry is not None
        assert payslip_entry['filename'] == dummy_pdf_filename

        # Check dummy data values based on counter being 1 after one parse
        counter = 1
        expected_net_income = round(1000.50 + (counter * 55.5) - ((counter % 4) * 120.3) + (counter % 3) * 30.1, 2)
        expected_meal_allowance = round(100.20 + (counter * 5.2) - ((counter % 3) * 15.5) + (counter % 4) * 5.5, 2)

        assert payslip_entry['net_income'] == expected_net_income
        assert payslip_entry['meal_allowance'] == expected_meal_allowance


def test_upload_non_pdf_file(client):
    """Test uploading a non-PDF file."""
    # Create a dummy non-PDF file
    temp_txt_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    temp_txt_file.write("This is not a PDF.")
    temp_txt_file.close()

    data = {
        'file': (open(temp_txt_file.name, 'rb'), 'test.txt')
    }
    try:
        response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200 # After redirect to /
        assert b"Invalid file type. Only PDF files (.pdf) are allowed." in response.data # Check flash
    finally:
        os.unlink(temp_txt_file.name) # Corrected variable name


def test_upload_no_file_selected(client):
    """Test submitting the upload form with no file selected."""
    response = client.post('/upload', data={}, content_type='multipart/form-data', follow_redirects=True) # data={} is fine
    assert response.status_code == 200 # After redirect to /
    assert b"No file part or no selected file." in response.data


# --- PDF Parsing Logic Tests (Basic) ---
def test_parse_payslip_pdf_dummy_data(app):
    """Test the parse_payslip_pdf function returns the expected structure with dummy data."""
    temp_pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=app.config['UPLOAD_FOLDER'])
    temp_pdf_file.write(MINIMAL_PDF_CONTENT)
    temp_pdf_file.close()

    # Ensure counter for dummy data generation is reset for predictable results
    if hasattr(parse_payslip_pdf, 'upload_session_counter'):
        parse_payslip_pdf.upload_session_counter = 0

    with app.app_context():
        parsed_data = parse_payslip_pdf(temp_pdf_file.name)

    os.unlink(temp_pdf_file.name)

    assert parsed_data is not None
    assert "net_income" in parsed_data
    assert "meal_allowance" in parsed_data
    assert "worked_days" in parsed_data
    assert "month" in parsed_data
    assert "year" in parsed_data
    assert "raw_text" in parsed_data

    counter = 1 # First parse in this "session"
    expected_net_income = round(1000.50 + (counter * 55.5) - ((counter % 4) * 120.3) + (counter % 3) * 30.1, 2)
    assert parsed_data["net_income"] == expected_net_income
    # For MINIMAL_PDF_CONTENT, raw_text might be empty or just whitespace.
    # This assertion is not critical if dummy data generation is the focus.
    # assert len(parsed_data["raw_text"].strip()) > 0
    # For now, let's check it's not None
    assert parsed_data["raw_text"] is not None


def test_parse_payslip_pdf_file_not_found(app):
    """Test parse_payslip_pdf with a non-existent file."""
    with app.app_context():
        parsed_data = parse_payslip_pdf("/tmp/non_existent_file_for_sure.pdf")
    # Check flash message (this requires the test to be within an app context that can catch flashes)
    # For this test, we will rely on the function returning None and logging an error.
    assert parsed_data is None

def test_payslips_page_with_data(client, app):
    """Test the payslips page when data is present and charts should get data."""
    # Insert some data first
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO payslips (filename, month, year, net_income, meal_allowance, worked_days, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ("dummy1.pdf", 1, 2023, 1200, 100, 20, datetime.utcnow())
        )
        db.execute(
            'INSERT INTO payslips (filename, month, year, net_income, meal_allowance, worked_days, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ("dummy2.pdf", 2, 2023, 1250, 110, 21, datetime.utcnow())
        )
        db.commit()

    response = client.get('/payslips')
    assert response.status_code == 200
    assert b"Payslip Dashboard" in response.data
    assert b"dummy1.pdf" in response.data # Check if table data is rendered
    assert b"dummy2.pdf" in response.data

    # Check if chart_data is passed and has expected structure (simplified check)
    assert b'const chartData = JSON.parse({"labels": ["2023-01", "2023-02"]' in response.data
    assert b'"net_income_data": [1200.0, 1250.0]' in response.data # Bokeh renders float with .0
    assert b'"meal_allowance_data": [100.0, 110.0]' in response.data
    assert b'"worked_days_data": [20, 21]' in response.data

    # Ensure no "No payslip data found" message
    assert b"No payslip data found" not in response.data

# Test for allowed_file utility function (though it's simple)
def test_allowed_file_logic(app):
    from app import allowed_file # import locally if not already at top
    assert allowed_file("test.pdf") == True
    assert allowed_file("test.PDF") == True
    assert allowed_file("test.txt") == False
    assert allowed_file("testpdf") == False # No extension
    assert allowed_file("test.doc.pdf") == True
    assert allowed_file("test.pdf.doc") == False
    assert allowed_file(".pdf") == True # Current logic allows this
    assert allowed_file("nodotextension") == False
    assert allowed_file("") == False

    # Test allowed_file with None, requires a modification in allowed_file or skip this
    # For now, we assume filename is always a string from the form.
    # assert allowed_file(None) == False


# It's good practice to reset the counter for parse_payslip_pdf in relevant test setups
# to ensure predictability, especially since it's a global-like attribute on the function.
# The app fixture now handles this reset.
# The test_upload_pdf_success and test_parse_payslip_pdf_dummy_data also explicitly reset it
# just before their specific calls to parse_payslip_pdf, ensuring they control the counter state.

# In test_upload_pdf_success, the counter will be 1 because parse_payslip_pdf is called once.
# In test_parse_payslip_pdf_dummy_data, it will also be 1.

# If you had a test that called parse_payslip_pdf multiple times, you'd expect the counter to increment.
# Example:
def test_parse_payslip_pdf_counter_increment(app):
    temp_pdf_file1 = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=app.config['UPLOAD_FOLDER'])
    temp_pdf_file1.write(MINIMAL_PDF_CONTENT)
    temp_pdf_file1.close()

    temp_pdf_file2 = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=app.config['UPLOAD_FOLDER'])
    temp_pdf_file2.write(MINIMAL_PDF_CONTENT)
    temp_pdf_file2.close()

    with app.app_context():
        if hasattr(parse_payslip_pdf, 'upload_session_counter'):
            parse_payslip_pdf.upload_session_counter = 0 # Reset for this test

        data1 = parse_payslip_pdf(temp_pdf_file1.name)
        counter1_val = parse_payslip_pdf.upload_session_counter

        data2 = parse_payslip_pdf(temp_pdf_file2.name)
        counter2_val = parse_payslip_pdf.upload_session_counter

    os.unlink(temp_pdf_file1.name)
    os.unlink(temp_pdf_file2.name)

    assert data1 is not None
    assert data2 is not None
    assert counter1_val == 1
    assert counter2_val == 2 # Counter should increment

    counter_val_for_data1 = 1
    expected_net1 = round(1000.50 + (counter_val_for_data1 * 55.5) - ((counter_val_for_data1 % 4) * 120.3) + (counter_val_for_data1 % 3) * 30.1, 2)
    assert data1['net_income'] == expected_net1

    counter_val_for_data2 = 2
    expected_net2 = round(1000.50 + (counter_val_for_data2 * 55.5) - ((counter_val_for_data2 % 4) * 120.3) + (counter_val_for_data2 % 3) * 30.1, 2)
    assert data2['net_income'] == expected_net2

# Add a test for the `now` context processor
def test_now_context_processor(client):
    """Test that 'now' is in the context and is a datetime object."""
    # This test is a bit indirect. We check if the year from 'now' is rendered.
    # A more direct test would involve accessing app.template_context_processors
    response = client.get('/')
    assert response.status_code == 200
    # Check if the current year is in the footer (assuming 'now.year' is used)
    # The year in the test might differ if the test runs near year change and app uses utcnow() differently
    # For robustness, might be better to check for "&copy; " and " Payslip Manager" separately
    # or inject a fixed datetime for 'now' in tests.
    # For now, this should generally pass.
    current_year_str = str(datetime.utcnow().year)
    assert bytes(f"&copy; {current_year_str} Payslip Manager", 'utf-8') in response.data
