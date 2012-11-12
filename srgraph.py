import glob
import os

from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    resp = ['<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<title>Test</title>',
            '</head>',
            '<body>',
            '<ul>']
    files = glob.glob('data/*.json')
    for f in files:
        resp.append('<li>%s</li>' % (f,))
    resp.extend(['</ul>',
                 '</body>',
                 '</html>'])

    return '\n'.join(resp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
