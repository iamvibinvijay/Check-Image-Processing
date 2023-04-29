from flask import Flask, render_template, redirect, url_for, request
from wtforms import SubmitField, MultipleFileField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
import os
import boto3
import re
import tempfile
from datetime import datetime

aws_access_key_id = ''
aws_secret_access_key = ''

# Define the folder to save uploaded images
UPLOAD_FOLDER = os.path.join('static', 'images')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'mySecretKey'


class JSONUploadForm(FlaskForm):
    choose_file = MultipleFileField('Choose your file', validators=[DataRequired()])
    submit = SubmitField('Submit')


# Define the route for uploading files
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    # Create an instance of the JSONUploadForm
    form = JSONUploadForm()
    if form.validate_on_submit():
        # Process the uploaded file
        file = form.choose_file.data

        # Call the function to process the check image
        extracted_dict = process_check(file[0])

        # Redirect to the results page and pass the text variable as a parameter
        return redirect(url_for('results', extracted_dict=extracted_dict))

    # Render the upload form template
    return render_template('upload.html', upload_form=form)


# Define a route for displaying the results page
@app.route('/results/<extracted_dict>')
def results(extracted_dict):
    extracted_info = eval(extracted_dict.replace("'", '"'))
    # extracted_info = json.loads(extracted_dict)
    return render_template('results.html', extracted_info=extracted_info)


def process_check(file):
    """This function is to process the check image and return the extracted attributes of check image"""
    try:
        # Save the uploaded file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file.read())
            file_path = temp_file.name

        # AWS connection
        client = boto3.client('textract', aws_access_key_id=aws_access_key_id,
                              aws_secret_access_key=aws_secret_access_key, region_name='us-east-1')

        with open(file_path, 'rb') as image:
            response = client.detect_document_text(Document={'Bytes': image.read()})

        # Extract the detected text from the response and store in a list
        lines = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                lines.append(block['Text'])
        print("Extracted info from the check image:", lines)

        # Call the function to fetch the check attributes
        extracted_dict = extract_info(lines)
        print("extracted_dict:", extracted_dict)
        return extracted_dict

    except Exception as exp:
        print(f"Exception occurred, {exp}")

    finally:
        # Delete the temporary file
        os.remove(file_path)


def extract_info(lines):
    """
    Extracts relevant information from a list of text lines representing a payment receipt.
    Args:
    - lines (list of str): The lines of text from the payment receipt.

    Returns:
    - A dictionary containing the extracted information:
        - 'payee_name': str, the name of the payee.
        - 'amount': float, the amount of the payment.
        - 'account_number': str, the account number of the payee.
        - 'bank_name': str, the name of the payee's bank.
        - 'ifsc': str, the IFSC code of the payee's bank.
        - 'date': str, the date of the payment in 'DD MMM YYYY' format.
    """

    # Define regex patterns to match different types of information in the text
    # name_pattern = r"PAY\n([A-Za-z\s]+)"
    amount_pattern = r"₹\s?([\d,]+)"
    account_pattern = r"\d{11}"
    # bank_pattern = r"Name of the bank\n([A-Za-z\s]+)"
    ifsc_pattern = r"IFS CODE: (\w{11})"
    prefix_pattern = r'PREFIX:\s*(.+)'
    date_pattern = r'\b(\d{2})(\d{2})(\d{4})\b'

    # Initialize variables to store extracted information
    payee_name = ""
    amount = 0.0
    account_number = ""
    bank_name = ""
    ifsc = ""
    date_str = ""

    # Iterate over the lines and extract information using regex patterns
    for line in lines:

        if line == "PAY":
            payee_name = lines[lines.index(line) + 1]

        amount_match = re.search(amount_pattern, line)
        if amount_match:
            amount = float(amount_match.group(1).replace(',', ''))

        account_match = re.search(account_pattern, line)
        if account_match:
            account_number = account_match.group()

        if "bank" in line.lower():
            bank_name = line.strip()

        ifsc_match = re.search(ifsc_pattern, line)
        if ifsc_match:
            ifsc = ifsc_match.group(1)

        prefix_match = re.search(prefix_pattern, line)
        if prefix_match:
            prefix = prefix_match.group(1)

        date_match = re.search(date_pattern, line)
        if date_match:
            date_str = date_match.group(1) + ' ' + date_match.group(2) + ' ' + date_match.group(3)

    # Convert the date string to datetime format and format it as 'DD MMM YYYY'
    if date_str:
        date_obj = datetime.strptime(date_str, '%d %m %Y')
        formatted_date = date_obj.strftime('%d %b %Y')
    else:
        formatted_date = ""

    # Create a dictionary containing the extracted information
    info_dict = {
        'payee_name': payee_name,
        'amount': amount,
        'account_number': account_number,
        'bank_name': bank_name,
        'ifsc': ifsc,
        'date': formatted_date
    }
    return info_dict


@app.route('/validate', methods=['POST'])
def validate():
    payee_name = request.form['payee_name']
    amount = request.form['amount']
    account_number = request.form['account_number']
    bank_name = request.form['bank_name']
    ifsc = request.form['ifsc']
    date = request.form['date']
    data_final = {
        "payee_name": payee_name,
        "amount": amount,
        "account_number": account_number,
        "bank_name": bank_name,
        "ifsc": ifsc,
        "date": date
    }
    response = f"Data received: {data_final}" \
               f"This will be sent to the bank for further processing"
    return render_template('final.html', text=response)


if __name__ == "__main__":
    app.run()
