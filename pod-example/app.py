import platform
import socket

from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return {"host": platform.node(), "ip": socket.gethostbyname(socket.gethostname())}
