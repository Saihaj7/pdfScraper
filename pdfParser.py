import os
import re
import tempfile
from flask import Flask, request, send_file, after_this_request
from PyPDF2 import PdfReader
import tabula
import pandas as pd

app = Flask(__name__)

@app.route("/")
def serve_html():
    return send_file('index.html')

@app.route('/convert', methods=['POST'])
def convert_to_csv():
    try:
        # Check if a PDF file was provided
        if 'pdfFile' not in request.files:
            return 'No PDF file provided', 400

        pdf_file = request.files['pdfFile']

        # Check if the file has a PDF extension
        if pdf_file.filename == '' or not pdf_file.filename.endswith('.pdf'):
            return 'Invalid file format. Please provide a PDF file', 400

        # Save the PDF file to a temporary location
        temp_pdf = tempfile.NamedTemporaryFile(delete=False)
        pdf_file.save(temp_pdf.name)

        print("PDF file saved to:", temp_pdf.name)

        try:
            csv_data = tabulaParser(temp_pdf.name)
        except Exception as e:
            print("Error converting PDF to CSV:", e)
            return f'Error converting PDF to CSV: {str(e)}', 500

        temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        csv_data.to_csv(temp_csv.name, index=False)

        print("CSV file saved to:", temp_csv.name)

        # Register a function to delete the temporary CSV file after the response is sent
        @after_this_request
        def cleanup(response):
            temp_pdf.close()
            os.unlink(temp_pdf.name)
            temp_csv.close()
            os.unlink(temp_csv.name)
            return response

        return send_file(temp_csv.name, as_attachment=True, download_name='converted_data.csv')
    except Exception as e:
        print("Error processing request:", e)
        return f'Error processing request: {str(e)}', 500


def getPageNumber(path):
    reader = PdfReader(path)
    return len(reader.pages)


def tabulaParser(path):
    firstpage_df = tabula.read_pdf(path, pages=[1], stream=True, area=[395.95, 39.26, 534.27, 296.08],
                                   pandas_options={'header': None})
    otherpages_df = tabula.read_pdf(path, multiple_tables=True, pages=list(range(2, getPageNumber(path) + 1)),
                                    stream=True, area=[70.5, 38.21, 519.96, 299], pandas_options={'header': None})

    tab = pd.DataFrame(data=pd.concat(firstpage_df + otherpages_df, ignore_index=True)).ffill()  # fills NaN columns
    tab = tab.groupby(0)[1].apply(' '.join).reset_index()  # merges rows with identical column index

    tab['ID'] = tab[1].apply(lambda x: extract_numbers(x, r'(?<=XO\s|US\s|MX\s)\d{5}'))  # match ID by regex
    tab['KG'] = tab[1].apply(lambda x: extract_numbers(x, r'\d+\.\d+(?=\sKG)'))  # match KG by regex

    return_df = tab[['ID', 'KG']]

    return return_df


def extract_numbers(text, pattern):
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None


if __name__ == "__main__":
    app.run(debug=True)
