from src.crewai_server.main import app  # Import your FastAPI app
from mangum import Mangum

# Wrap it with Mangum for AWS Lambda / Vercel compatibility
handler = Mangum(app)
