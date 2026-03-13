import os
import logging
from flask import Flask, jsonify, request, make_response

app = Flask(__name__)

log_dir = "./logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "app.log")),
        logging.StreamHandler()
    ]
)

@app.route('/info', methods=['GET'])
def healthy_endpoint():
    logging.info("User accessed the healthy endpoint. Everything is fine.")

    numerator = 100
    denominator = 0

    calculated_value = None
    if denominator != 0:
        try:
            calculated_value = numerator / denominator
            logging.info(f"Dummy calculation: {numerator} / {denominator} = {calculated_value}")
        except Exception as e:
            logging.error(f"Error during dummy calculation: {str(e)}", exc_info=True)
            calculated_value = "ERROR"
    else:
        logging.warning(f"Attempted to divide {numerator} by zero. Operation skipped.")
        calculated_value = "Division by zero avoided."

    return jsonify({
        "status": "success",
        "message": "I am working perfectly!",
        "dummy_calculation_result": str(calculated_value)
    })

@app.route('/error', methods=['GET'])
def crash_endpoint():
    # This endpoint is designed to trigger a truly unhandled error for CI/CD testing
    # as indicated by the log message and task description.
    # The previous try-except block was handling it, defeating the purpose of an "unhandled" error.
    logging.info("Triggering an unhandled simulated error for the /error endpoint as expected by the CI/CD agent.")
    raise RuntimeError("Simulated unhandled error for CI/CD testing.")

if __name__ == '__main__':
    print("Server starting on http://127.0.0.1:5000")
    print("Hit /info for a success log (includes ZeroDivisionError fix demo)")
    print("Hit /error to trigger the simulated 500 error (this endpoint now causes an unhandled error)")
    app.run(port=5000)