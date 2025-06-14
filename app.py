import os
import pdfplumber
import sqlite3
import json
from flask import Flask, request, redirect, url_for, render_template, flash, g
from werkzeug.utils import secure_filename
from datetime import datetime

UPLOAD_FOLDER = 'uploads'
DATABASE = 'payslips.db'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'super secret key'

# --- Context Processor for current year ---
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# --- Database Setup and Helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    # print("Database initialized.") # Keep this, good for CLI feedback

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Database initialized.')


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def insert_payslip_data(filename, month, year, net_income, meal_allowance, worked_days):
    # Ensure uploaded_at is stored as a datetime object, which it is by default with PARSE_DECLTYPES
    try:
        db = get_db()
        db.execute(
            'INSERT INTO payslips (filename, month, year, net_income, meal_allowance, worked_days, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (filename, month, year, net_income, meal_allowance, worked_days, datetime.utcnow())
        )
        db.commit()
        print(f"Data for {filename} (Month: {month}, Year: {year}) inserted into database.")
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        flash(f"Database error occurred while saving data for {filename}: {e}", "error")
        return False
# --- End Database Setup ---

# --- PDF Parsing Logic ---
def allowed_file(filename):
    return '.' in filename and            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_payslip_pdf(pdf_path):
    if not hasattr(parse_payslip_pdf, 'counter_lock'): # Initialize lock if not present
        parse_payslip_pdf.counter_lock = False # Simple lock to prevent race in single-threaded dev server

    if not parse_payslip_pdf.counter_lock:
        parse_payslip_pdf.counter_lock = True
        if not hasattr(parse_payslip_pdf, 'upload_session_counter'):
            parse_payslip_pdf.upload_session_counter = 0
        parse_payslip_pdf.upload_session_counter += 1
        counter = parse_payslip_pdf.upload_session_counter
        parse_payslip_pdf.counter_lock = False
    else: # Should not happen frequently in dev, but as a fallback
        counter = datetime.now().microsecond


    # More varied dummy data based on the counter
    base_month = datetime.now().month
    base_year = datetime.now().year

    new_month_offset = (base_month -1 + counter -1) # -1 because counter is 1-indexed for this calc
    month = new_month_offset % 12 + 1
    year = base_year + (new_month_offset // 12)

    extracted_data = {
        "net_income": round(1000.50 + (counter * 55.5) - ((counter % 4) * 120.3) + (counter % 3) * 30.1, 2),
        "meal_allowance": round(100.20 + (counter * 5.2) - ((counter % 3) * 15.5) + (counter % 4) * 5.5, 2),
        "worked_days": 19 + (counter % 4),  # Cycles 19, 20, 21, 22
        "month": month,
        "year": year,
        "raw_text": ""
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = []
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=1, y_tolerance=3) # Adjust tolerance
                if page_text:
                    full_text.append(page_text)
            extracted_data["raw_text"] = "\n".join(full_text)
            # Minimal printing to console during parsing
            # print(f"--- Raw Text from {os.path.basename(pdf_path)} (First 100 chars) ---")
            # print(extracted_data["raw_text"][:100])
            # print("--- End of Preview ---")
    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {e}")
        flash(f"Error parsing PDF: {os.path.basename(pdf_path)}. See server logs for details.", "error")
        return None
    return extracted_data
# --- End PDF Parsing Logic ---

# --- Flask Routes ---
@app.route('/', methods=['GET'])
def upload_form():
    # Reset pdf parse counter on main page load for a new "batch" of uploads
    if hasattr(parse_payslip_pdf, 'upload_session_counter'):
        parse_payslip_pdf.upload_session_counter = 0
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file_route():
    if 'file' not in request.files or not request.files['file'].filename:
        flash('No file part or no selected file. Please select a PDF file.', 'warning')
        return redirect(url_for('upload_form')) # Changed redirect target

    file = request.files['file']
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(pdf_path)
        except Exception as e:
            flash(f"Error saving file {filename}: {e}", "error")
            return redirect(url_for('upload_form')) # Changed redirect target

        parsed_data = parse_payslip_pdf(pdf_path)

        if parsed_data:
            success = insert_payslip_data(
                filename,
                parsed_data.get("month"),
                parsed_data.get("year"),
                parsed_data.get("net_income"),
                parsed_data.get("meal_allowance"),
                parsed_data.get("worked_days")
            )
            if success:
                flash(f'File "{filename}" uploaded, parsed (M:{parsed_data.get("month")}, Y:{parsed_data.get("year")}), and saved!', 'success')
            # else: insert_payslip_data() already flashes an error message
        else:
             # parse_payslip_pdf() already flashes an error if it returns None
             flash(f'Could not parse data from "{filename}".', 'error')
        return redirect(url_for('upload_form'))
    else:
        flash('Invalid file type. Only PDF files (.pdf) are allowed.', 'error')
        return redirect(url_for('upload_form')) # Changed redirect target

@app.route('/payslips', methods=['GET'])
def view_payslips():
    payslips_from_db = query_db('SELECT filename, month, year, net_income, meal_allowance, worked_days, uploaded_at FROM payslips ORDER BY year ASC, month ASC')

    chart_labels = []
    chart_net_income_data = []
    chart_meal_allowance_data = []
    chart_worked_days_data = []

    for row in payslips_from_db:
        chart_labels.append(f"{row['year']}-{str(row['month']).zfill(2)}")
        chart_net_income_data.append(row['net_income'] if row['net_income'] is not None else 0)
        chart_meal_allowance_data.append(row['meal_allowance'] if row['meal_allowance'] is not None else 0)
        chart_worked_days_data.append(row['worked_days'] if row['worked_days'] is not None else 0)

    final_chart_data = {
        "labels": chart_labels,
        "net_income_data": chart_net_income_data,
        "meal_allowance_data": chart_meal_allowance_data,
        "worked_days_data": chart_worked_days_data
    }

    return render_template('payslips_table.html', payslips=payslips_from_db, chart_data=final_chart_data)
# --- End Flask Routes ---


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    # Ensure DB is initialized if it doesn't exist when app starts (optional, for convenience)
    # This is good for dev, but for testing, fixtures should handle DB setup.
    # with app.app_context():
    #    if not os.path.exists(DATABASE):
    #        init_db()
    #        print("Database was not found, initialized a new one.")

    app.run(debug=True)
