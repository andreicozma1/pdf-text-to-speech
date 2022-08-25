import os
import traceback
from flask import Flask, render_template, request, make_response, \
    redirect, url_for, send_from_directory, Response, session
import secrets
from dotenv import load_dotenv
from src.lib import PDF_TTS
from pathlib import Path
import hashlib

load_dotenv()

# Check if the secret key exists in the environment
if 'FLASK_DEBUG' not in os.environ:
    raise Exception(
        'FLASK_DEBUG not found in environment. Please set this key in your environment, or use the .env file.')
if 'TEMPLATES_AUTO_RELOAD' not in os.environ:
    raise Exception(
        'TEMPLATES_AUTO_RELOAD not found in environment. Please set this key in your environment, or use the .env file.')
if 'SECRET_KEY' not in os.environ:
    raise Exception(
        'SECRET_KEY not found in environment. Please set this key in your environment, or use the .env file.')
if 'UPLOAD_FOLDER' not in os.environ:
    raise Exception(
        'UPLOAD_FOLDER not found in environment. Please set this key in your environment, or use the .env file.')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['TEMPLATES_AUTO_RELOAD'] = os.environ['TEMPLATES_AUTO_RELOAD']
app.config['UPLOAD_FOLDER'] = os.environ['UPLOAD_FOLDER']
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

print("=" * 80)
print("FLASK_DEBUG = " + os.environ['FLASK_DEBUG'])
print("TEMPLATES_AUTO_RELOAD = " + app.config['TEMPLATES_AUTO_RELOAD'])
print("UPLOAD_FOLDER = " + app.config['UPLOAD_FOLDER'])
print("ALLOWED_EXTENSIONS = " + str(app.config['ALLOWED_EXTENSIONS']))
print("=" * 80)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def rrmdir(path):
    for entry in os.scandir(path):
        if entry.is_dir():
            rrmdir(entry)
        else:
            os.remove(entry)
    os.rmdir(path)

@app.before_request
def make_session_permanent():
    session.permanent = True
    
@app.route("/")
def index():
    print("=" * 80)
    uploads = session.get('uploads', {})
    print(f"Uploads: {uploads}")
    return render_template("./index.html", uploads=uploads, message="Upload a PDF file to get started.")


@app.route('/<upload_id>')
def player(upload_id):
    upload_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_id)
    if not upload_id or not os.path.exists(upload_dir_path):
        r = render_template("./index.html",
                            message="Error: Requested an invalid Document ID. Please upload a new document.")
        return r

    print('-' * 80)
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
        r = render_template("./index.html", message="Error: More than one PDF file found in the upload directory")
        return r

    fname_pdf = pdf_files[0]
    fname_txt = fname_pdf.replace('.pdf', '.txt')
    fname_txt_processed = fname_txt.replace('.txt', '_processed.txt')
    p = PDF_TTS(os.path.join(upload_dir_path, fname_pdf))

    try:
        data = p.get_data()

    except Exception:
        traceback.print_exc()
        r = render_template("./index.html", dialog="Error: Failed to get data for this document")
        return r

    uploads = session.get('uploads', {})
    if upload_id not in uploads:
        uploads[upload_id] = data['info']['file_name']
        session['uploads'] = uploads
    print(f"Uploads: {uploads}")

    if not query:
        return render_template("./index.html", id=upload_id, data=data, uploads=uploads)

    # check if query is valid
    valid_queries = ['process', 'stream', 'download_pdf', 'download_txt', 'clean', 'remove_doc']
    if query not in valid_queries:
        return render_template("./index.html", dialog="Error: Invalid query")

    elif query == 'process':
        try:
            p.process()
        except Exception:
            traceback.print_exc()
            r = render_template("./index.html", uploads=uploads, dialog="Error: Failed to process PDF file")
            return r
        return redirect(upload_id)
    elif query == 'clean':
        try:
            p.clean()
        except Exception:
            traceback.print_exc()
            r = render_template("./index.html", id=upload_id, data=data, uploads=uploads,
                                message="Error: Failed to clean processed state for PDF file")
            return r
        return redirect(upload_id)
    elif query == 'stream':
        stream_index = request.args.get('index')
        if not stream_index or not stream_index.isdigit():
            r = render_template("./index.html", id=upload_id, data=data, uploads=uploads,
                                dialog="Required integer `index` query param not specified")
            return r
        stream_index = int(stream_index)
        return Response(p.stream_one(stream_index), mimetype="audio/x-wav")
    elif query == 'download_pdf':
        if not os.path.exists(os.path.join(upload_dir_path, fname_pdf)):
            r = render_template("./index.html", id=upload_id, data=data, uploads=uploads,
                                dialog="Error: PDF file not found")
            return r
        return send_from_directory(upload_dir_path, fname_pdf, as_attachment=True)
    elif query == 'download_txt':
        if not os.path.exists(os.path.join(upload_dir_path, fname_txt_processed)):
            r = render_template("./index.html", id=upload_id, data=data, uploads=uploads,
                                dialog="Error: TXT file not found")
            return r
        return send_from_directory(upload_dir_path, fname_txt_processed, as_attachment=True)
    elif query == 'remove_doc':
        try:
            rrmdir(upload_dir_path)
            # Remove cookie for removed document
            uploads.pop(upload_id)
            session['uploads'] = uploads
        except Exception:
            traceback.print_exc()
            r = render_template("./index.html", id=upload_id, data=data, uploads=uploads,
                                message="Error: Failed to remove upload directory for this document")
            return r
        return redirect(url_for('index'))


@app.route("/upload", methods=['POST'])
def upload():
    if request.method != "POST":
        return
    if 'file' not in request.files:
        r = render_template("./index.html", message='Upload file not found')
        return r

    f = request.files["file"]

    if f.filename == '':
        r = render_template("./index.html", message="Upload file not selected")
        return r

    if f and allowed_file(f.filename):
        # upload_id = secrets.token_urlsafe(36)
        filebytes = f.read()
        upload_id = hashlib.md5(filebytes).hexdigest()

        f_save_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_id)
        if not os.path.exists(f_save_path):
            os.makedirs(f_save_path)
            f.seek(0)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], upload_id, f.filename))

        current_uploads = session.get('uploads', {})
        current_uploads[upload_id] = f.filename
        session['uploads'] = current_uploads
        session.permanent = True
        return make_response(redirect(url_for('player', upload_id=upload_id, action='process')))
    else:
        r = render_template("./index.html", message="Upload file not allowed")
        return r


if __name__ == "__main__":
    # app.run(debug=True, use_reloader=True, threaded=True
    app.run()
