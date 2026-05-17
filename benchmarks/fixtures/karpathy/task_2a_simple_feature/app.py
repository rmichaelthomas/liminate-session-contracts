from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/version")
def version():
    return jsonify({"version": "1.0.0"})


if __name__ == "__main__":
    app.run(port=5000)
