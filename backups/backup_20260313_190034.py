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
    denominator = 0 # This will now be handled by the try-except block

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
    try:
        logging.info("Triggering a simulated error for the /error endpoint.")
        raise RuntimeError("Simulated unhandled error for CI/CD testing.")
    except RuntimeError as e:
        logging.error(f"Caught simulated error on /error endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"An expected simulated error occurred: {str(e)}"
        }), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred on /error endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}"
        }), 500

if __name__ == '__main__':
    print("Server starting on http://127.0.0.1:5000")
    print("Hit /info for a success log (includes ZeroDivisionError fix demo)")
    print("Hit /error to trigger the simulated 500 error (this endpoint now causes an unhandled error)")
    app.run(port=5000)