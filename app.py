import os
from flask import Flask, render_template, request, make_response, redirect, url_for, send_from_directory, Response
import secrets

# import sys
# sys.path.append('src/lib')

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = 'uploads'

from src.lib import PDF_TTS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index(message = "Upload a PDF file to get started."):
    # get data from request 'message'
    return render_template("./index.html", message=message)

@app.route('/<upload_id>')
def player(upload_id):
    upload_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_id)
    if not upload_id or not os.path.exists(upload_dir_path):
        r = render_template("./index.html", message="Error: Requested an invalid Document ID. Please upload a new document.")
        return r
    
    # get query param
    query = request.args.get('action')
    print(f"Query: {query}")
    
    # Find all PDF files in the upload directory
    pdf_files = [f for f in os.listdir(upload_dir_path) if f.endswith('.pdf')]
    
    # If there are no PDF files, remove the upload directory
    if not pdf_files:
        os.rmdir(upload_dir_path)
        r = render_template("./index.html", message="Error: No PDF files found in upload directory")
        return r
    
    # If there are more than one PDF files, return error
    if len(pdf_files) > 1:
        r =  render_template("./index.html", message="Error: More than one PDF file found in the upload directory")
        return r

    fname_pdf = pdf_files[0]
    fname_txt = fname_pdf.replace('.pdf', '.txt')
    p = PDF_TTS(os.path.join(upload_dir_path, fname_pdf))
    data = p.get_data()
    
    if not query:
        return render_template("./index.html", id=upload_id, data=data)   

    # check if query is valid    
    valid_queries = ['process', 'stream', 'download_pdf', 'download_txt', 'clean']
    if query not in valid_queries:
        return render_template("./index.html", message="Error: Invalid query")
    elif query == 'process':
        p.process()
        return redirect(upload_id)
    elif query == 'clean':
        p.clean()
        return redirect(upload_id)
    elif query == 'stream':
        stream_index = request.args.get('index')
        if not stream_index or not stream_index.isdigit():
            return "Required integer `index` query param not specified"
        stream_index = int(stream_index)
        return Response(p.stream_one(stream_index), mimetype="audio/x-wav")
    elif query == 'download_pdf':
        if not os.path.exists(os.path.join(upload_dir_path, fname_pdf)):
            r = render_template("./index.html", message="Error: PDF file not found")
            return r
        return send_from_directory(upload_dir_path, fname_pdf, as_attachment=True)
    elif query == 'download_txt':
        if not os.path.exists(os.path.join(upload_dir_path, fname_txt)):
            r = render_template("./index.html", message="Error: TXT file not found")
            return r
        return send_from_directory(upload_dir_path, fname_txt, as_attachment=True)

    # if not is_processed and not p.process():
        # resp = make_response(redirect('index'))
        # return resp 
    # return send_fom_directory(app.config['UPLOAD_FOLDER'],         filename)r
        
@app.route("/upload", methods = ['POST']) 
def upload():
    if request.method == "POST":
        if 'file' not in request.files:
            r = redirect(url_for('index', message='Upload file not found'))
            return r
        
        f = request.files["file"]
        
        if f.filename == '':
            r = redirect(url_for('index', message="Upload file not selected"))
            return r
        
        if f and allowed_file(f.filename):
            upload_id = secrets.token_urlsafe(36)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], upload_id))
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], upload_id, f.filename))
            
            resp = make_response(redirect(url_for('player', upload_id=upload_id, action='process')))
            return resp
        else:
            r = redirect(url_for('index', message="Upload file not allowed"))
            return r
    
    
if __name__ == "__main__":
    app.run(debug=True, threaded=True)