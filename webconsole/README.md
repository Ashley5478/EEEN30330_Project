# Webconsole

This web console is generated using Claude AI with context from [rainer_client.py](../rainer_client.py).

This Web UI uses Flask and communicates with the Rainer IoT device.

## How to run it

### Initial Setup
```bash
cd webconsole   # Skip if you are already here.  

# Creating virtual environment
python -m venv .venv

# Load virtual environment
source .venv/Scripts/activate   # Windows Python might be different
pip install -r requirements.txt

# Run (Note that this is a development environment)
python app.py
```
This runs a website in localhost at 5000, giving you a web UI that is only visible from your computer.

You should now be able to go to [Web Console](http://localhost:5000/).

You can shut down the server by Control+C.

## How to run again
After the initial setup, you can skip some of the virtual environment setup.
```bash
cd webconsole   # Skip if you are already here.  

# Load virtual environment
source .venv/bin/activate   # Windows Python might be different

# Run (Note that this is a development environment)
python app.py
```