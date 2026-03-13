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
    try:
        calculated_value = numerator / denominator
        logging.info(f"Dummy calculation: {numerator} / {denominator} = {calculated_value}")
    except ZeroDivisionError:
        logging.error(f"Error during dummy calculation: Attempted to divide {numerator} by zero.", exc_info=True)
        calculated_value = "Division by zero error caught."
    except Exception as e:
        logging.error(f"An unexpected error occurred during dummy calculation: {str(e)}", exc_info=True)
        calculated_value = "ERROR"

    return jsonify({
        "status": "success",
        "message": "I am working perfectly!",
        "dummy_calculation_result": str(calculated_value)
    })

@app.route('/error', methods=['GET'])
def crash_endpoint():
    logging.info("Triggering a simulated unhandled error for the /error endpoint.")
    # This error will now propagate and be caught by the global error handler
    raise RuntimeError("Simulated unhandled error for CI/CD testing.")

@app.errorhandler(Exception)
def handle_exception(e):
    logging.exception(f"An unhandled application error occurred: {str(e)}")
    return jsonify({
        "status": "error",
        "message": "An unexpected server error occurred.",
        "details": str(e)
    }), 500

if __name__ == '__main__':
    print("Server starting on http://127.0.0.1:5000")
    print("Hit /info for a success log (includes ZeroDivisionError fix demo)")
    print("Hit /error to trigger the simulated 500 error (this endpoint now causes an unhandled error, caught by global handler)")
    app.run(port=5000)