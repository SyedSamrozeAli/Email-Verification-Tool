# verify-app.py — thin Flask layer over the verifier engine (see verifier/)

import csv
import io
import threading
import time
import uuid

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from verifier.engine import run_batch
from verifier.smtp_probe import is_smtp_available
from verifier.result import RESULT_COLUMNS

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload cap

EMAIL_FIELD_CANDIDATES = {"email", "emailaddress", "mail", "workemail", "businessemail", "e-mail"}
JOB_TTL_SECONDS = 2 * 60 * 60  # purge finished jobs after 2 hours

data = {}
data_lock = threading.Lock()

smtp_ready = is_smtp_available()
if smtp_ready:
    print("[SMTP OK] Port 25 is reachable - live mailbox verification is active.")
else:
    print("[SMTP BLOCKED] Port 25 is blocked on this network - running in offline mode.")
    print("  Results will use 'unknown' + a confidence score instead of a false 'valid'.")


def _cleanup_old_jobs():
    cutoff = time.time() - JOB_TTL_SECONDS
    with data_lock:
        stale = [jid for jid, job in data.items() if job.get("created_at", 0) < cutoff]
        for jid in stale:
            del data[jid]


def _detect_email_field(fieldnames):
    for f in fieldnames:
        key = f.lower().strip().replace("-", "").replace("_", "").replace(" ", "")
        if key in EMAIL_FIELD_CANDIDATES:
            return f
    return None


def _matches_filter(result, filter_type):
    if result is None:
        return False
    if filter_type == "all":
        return True
    if filter_type == "non_role":
        return not result.is_role
    return result.status == filter_type


def _build_csv(rows, results, filter_type):
    base_fields = list(rows[0].keys()) if rows else []
    fieldnames = base_fields + RESULT_COLUMNS
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row, result in zip(rows, results):
        if not _matches_filter(result, filter_type):
            continue
        merged = dict(row)
        merged.update(result.as_row())
        writer.writerow(merged)
    return output.getvalue()


@app.route("/verify", methods=["POST"])
def verify():
    _cleanup_old_jobs()

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]

    raw_bytes = file.read()
    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw_bytes.decode("latin-1")

    reader = list(csv.DictReader(io.StringIO(content)))
    if not reader:
        return jsonify({"error": "CSV is empty or has no data rows"}), 400

    email_field = _detect_email_field(reader[0].keys())
    if not email_field:
        return jsonify({"error": "No email column found. Expected a column named 'email' (or similar)."}), 400

    total = len(reader)
    job_id = str(uuid.uuid4())

    job = {
        "total": total,
        "progress_total": total,
        "completed": 0,
        "cancel": False,
        "rows": reader,
        "results": [None] * total,
        "email_field": email_field,
        "filename": file.filename,
        "log": "",
        "phase": "pass1",
        "retry_count": 0,
        "done": False,
        "created_at": time.time(),
    }
    with data_lock:
        data[job_id] = job

    def on_progress(completed, progress_total, result):
        job["completed"] = completed
        job["progress_total"] = progress_total
        job["log"] = f"{result.email} → {result.status} ({result.reason})"

    def on_phase(phase, extra):
        job["phase"] = phase
        if phase == "waiting" or phase == "pass2":
            job["retry_count"] = extra.get("retry_count", 0)

    def should_cancel():
        return job["cancel"]

    def run():
        results = run_batch(reader, email_field, on_progress, should_cancel, on_phase)
        job["results"] = results
        job["done"] = True

    threading.Thread(target=run, daemon=True).start()

    return jsonify({"job_id": job_id, "total": total, "smtp_available": smtp_ready})


@app.route("/progress")
def progress():
    job_id = request.args.get("job_id")
    job = data.get(job_id)
    if not job:
        return jsonify({"error": "Invalid job ID"}), 404

    counts = {"valid": 0, "invalid": 0, "risky": 0, "unknown": 0}
    for r in job["results"]:
        if r is not None:
            counts[r.status] = counts.get(r.status, 0) + 1

    progress_total = job.get("progress_total") or job["total"] or 1
    percent = int((job["completed"] / progress_total) * 100)
    return jsonify({
        "percent": percent,
        "row": job["completed"],
        "total": job["total"],
        "progress_total": progress_total,
        "phase": job.get("phase", "pass1"),
        "retry_count": job.get("retry_count", 0),
        "done": job["done"],
        "canceled": job["cancel"],
        "smtp_available": smtp_ready,
        "counts": counts,
    })


@app.route("/log")
def log():
    job_id = request.args.get("job_id")
    job = data.get(job_id, {})
    return Response(job.get("log", ""), mimetype="text/plain")


@app.route("/cancel", methods=["POST"])
def cancel():
    job_id = request.args.get("job_id")
    job = data.get(job_id)
    if job:
        job["cancel"] = True
    return "", 204


@app.route("/download")
def download():
    job_id = request.args.get("job_id")
    filter_type = request.args.get("type", "all")
    job = data.get(job_id)
    if not job:
        return "Invalid job ID", 404
    if not job["done"]:
        return "Job still running", 409

    csv_text = _build_csv(job["rows"], job["results"], filter_type)
    download_name = f"{filter_type}-{job['filename']}"
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


if __name__ == "__main__":
    app.run(port=5050)
