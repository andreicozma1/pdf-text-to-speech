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
def index():
    return render_template("./index.html")

@app.route('/<upload_id>')
def player(upload_id):
    upload_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_id)
    if not upload_id or not os.path.exists(upload_dir_path):
        return redirect(url_for('index'))
    
    # get query param
    query = request.args.get('action')
    print(f"Query: {query}")

    p = PDF_TTS(os.path.join(upload_dir_path, 'document.pdf'))
    data = p.get_data()
    
    if not query:
        return render_template("./player.html", id=upload_id, data=data)   

    # check if query is valid    
    valid_queries = ['process', 'stream', 'download_pdf', 'download_txt', 'clean']
    if query not in valid_queries:
        return redirect(url_for('index'))
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
        return send_from_directory(upload_dir_path, "document.pdf", as_attachment=True)
    elif query == 'download_txt':
        return send_from_directory(upload_dir_path, "document.txt", as_attachment=True)

    # if not is_processed and not p.process():
        # resp = make_response(redirect('index'))
        # return resp 
    # return send_fom_directory(app.config['UPLOAD_FOLDER'],         filename)r
        
@app.route("/upload", methods = ['GET', 'POST']) 
def upload():
    if request.method == "POST":
        if 'file' not in request.files:
            return 'File not found'
        
        f = request.files["file"]
        
        if f.filename == '':
            return "File not selected"
        
        if f and allowed_file(f.filename):
            upload_id = secrets.token_urlsafe(36)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], upload_id))
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], upload_id, "document.pdf"))
            resp = make_response(redirect(upload_id))
            return resp
        else:
            return "File not allowed"
    
    
if __name__ == "__main__":
    app.run(debug=True, threaded=True)