"""Reserved worker entry point for the optional full-stack profile.

No background processors are enabled in the synthetic MVP, so this process
exits cleanly instead of pretending that OCR or external ingestion is active.
"""
import logging
logging.basicConfig(level=logging.INFO)
logging.info("TriNetra optional worker has no configured demo jobs; exiting.")
